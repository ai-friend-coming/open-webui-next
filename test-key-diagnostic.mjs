/**
 * 密钥派生诊断测试
 */

const KEY_LENGTH = 32;
const IV_LENGTH = 12;
const PBKDF2_ITERATIONS = 100000;

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

async function runDiagnostic() {
    console.log('=== Detailed Key Derivation Test ===\n');

    const userId = 'test-user-123';
    const sessionToken = 'test-session-token-abc';

    // 派生密钥
    const key = await deriveKeyFromPassword(sessionToken, userId);
    const keyExported = await crypto.subtle.exportKey('raw', key);
    const keyHex = Array.from(new Uint8Array(keyExported))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');

    console.log(`Frontend Key (hex): ${keyHex}`);
    console.log(`Frontend Key length: ${keyExported.byteLength} bytes\n`);

    // 测试加密解密
    const plaintext = 'Test message';
    const encrypted = await encryptText(plaintext, key);
    console.log(`Frontend encrypted: ${encrypted}`);

    // 解析 Base64 查看结构
    const combined = Uint8Array.from(atob(encrypted), c => c.charCodeAt(0));
    const iv = combined.slice(0, IV_LENGTH);
    const ciphertext = combined.slice(IV_LENGTH);

    const ivHex = Array.from(iv)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');

    console.log(`IV (hex): ${ivHex}`);
    console.log(`IV length: ${iv.length} bytes`);
    console.log(`Ciphertext length: ${ciphertext.length} bytes\n`);

    // 解密验证
    const decrypted = await decryptText(encrypted, key);
    console.log(`Frontend decrypted: ${decrypted}`);
    console.log(`Match: ${plaintext === decrypted}`);
}

runDiagnostic().catch(console.error);
