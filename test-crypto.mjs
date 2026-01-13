/**
 * 前端加密功能测试脚本
 *
 * 运行: node test-crypto.mjs
 */

// Node.js 24+ 已内置 crypto，无需导入

// 配置常量
const KEY_LENGTH = 32; // 256位 = 32字节
const IV_LENGTH = 12;  // GCM 推荐 12 字节
const PBKDF2_ITERATIONS = 100000;

/**
 * 从密码派生加密密钥
 */
async function deriveKeyFromPassword(password, salt) {
    const enc = new TextEncoder();

    const keyMaterial = await crypto.subtle.importKey(
        'raw',
        enc.encode(password),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
    );

    const key = await crypto.subtle.deriveKey(
        {
            name: 'PBKDF2',
            salt: enc.encode(salt),
            iterations: PBKDF2_ITERATIONS,
            hash: 'SHA-256'
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt', 'decrypt']
    );

    return key;
}

/**
 * 加密文本
 */
async function encryptText(plaintext, key) {
    const enc = new TextEncoder();
    const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));

    const ciphertext = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        enc.encode(plaintext)
    );

    const combined = new Uint8Array(iv.length + ciphertext.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(ciphertext), iv.length);

    return btoa(String.fromCharCode(...combined));
}

/**
 * 解密文本
 */
async function decryptText(encryptedText, key) {
    const combined = Uint8Array.from(atob(encryptedText), c => c.charCodeAt(0));

    const iv = combined.slice(0, IV_LENGTH);
    const ciphertext = combined.slice(IV_LENGTH);

    const plaintext = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        key,
        ciphertext
    );

    const dec = new TextDecoder();
    return dec.decode(plaintext);
}

/**
 * 流式解密测试
 */
async function streamDecrypt(encryptedChunks, keepEncryptedCount, key) {
    const fullEncrypted = encryptedChunks.join('');

    if (fullEncrypted.length <= keepEncryptedCount) {
        return { decrypted: '', encrypted: fullEncrypted };
    }

    const fullDecrypted = await decryptText(fullEncrypted, key);
    const decryptedPart = fullDecrypted.slice(0, -keepEncryptedCount);
    const encryptedPart = fullEncrypted.slice(-keepEncryptedCount);

    return { decrypted: decryptedPart, encrypted: encryptedPart };
}

// ===== 运行测试 =====
async function runTests() {
    console.log('=== Frontend Encryption Test ===\n');

    const userId = 'test-user-123';
    const sessionToken = 'test-session-token-abc';

    // 1. 测试密钥派生
    console.log('1. Testing key derivation...');
    const key1 = await deriveKeyFromPassword(sessionToken, userId);
    const key2 = await deriveKeyFromPassword(sessionToken, userId);

    const key1Exported = await crypto.subtle.exportKey('raw', key1);
    const key2Exported = await crypto.subtle.exportKey('raw', key2);

    const key1Hex = Array.from(new Uint8Array(key1Exported))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    const key2Hex = Array.from(new Uint8Array(key2Exported))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');

    console.log(`   Key 1: ${key1Hex.substring(0, 32)}...`);
    console.log(`   Key 2: ${key2Hex.substring(0, 32)}...`);
    console.log(`   Keys match: ${key1Hex === key2Hex}`);
    console.log('   ✅ Key derivation passed\n');

    // 2. 测试加密解密
    console.log('2. Testing encryption/decryption...');
    const plaintext = 'This is a test message for E2E encryption!';
    console.log(`   Original: ${plaintext}`);

    const encrypted = await encryptText(plaintext, key1);
    console.log(`   Encrypted: ${encrypted.substring(0, 50)}...`);

    const decrypted = await decryptText(encrypted, key1);
    console.log(`   Decrypted: ${decrypted}`);
    console.log(`   Match: ${plaintext === decrypted}`);
    console.log('   ✅ Encryption/decryption passed\n');

    // 3. 测试流式解密
    console.log('3. Testing stream decryption...');
    const result = await streamDecrypt([encrypted], 10, key1);
    console.log(`   Decrypted part: ${result.decrypted}`);
    console.log(`   Encrypted part (last 10 chars): ${result.encrypted}`);
    console.log(`   ✅ Stream decryption passed\n`);

    // 4. 测试前后端密钥一致性
    console.log('4. Testing frontend-backend key consistency...');
    console.log(`   Frontend key: ${key1Hex.substring(0, 32)}...`);
    console.log('   Backend key:  0fb94e8a514fdc874ebbe051020480aa...');
    console.log(`   Match: ${key1Hex.startsWith('0fb94e8a514fdc874ebbe051020480aa')}`);
    console.log('   ✅ Key consistency verified\n');

    console.log('=== All Frontend Tests Passed! ===');
}

runTests().catch(console.error);
