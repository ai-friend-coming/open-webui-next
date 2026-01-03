/**
 * 跨平台测试：后端加密 -> 前端解密
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

async function test() {
    console.log('=== Cross-Platform Test: Frontend Decrypt ===\n');

    const userId = 'test-user-123';
    const sessionToken = 'test-session-token-abc';

    const key = await deriveKeyFromPassword(sessionToken, userId);

    // 后端生成的密文
    const backendEncrypted = 'Sj/kBG6/ofqXe4aH2wyHvphpVNs34P0GEcZF/7opK+PP0/VK3kyLyOReYbEZd+BiwT081Vc=';

    console.log(`Backend encrypted: ${backendEncrypted}`);

    try {
        const decrypted = await decryptText(backendEncrypted, key);
        console.log(`Frontend decrypted: ${decrypted}`);
        console.log('\n✅ Cross-platform decryption SUCCESS!');
        console.log('   Backend -> Frontend interoperability verified!');
    } catch (e) {
        console.log(`\n❌ Decryption failed: ${e.message}`);
    }
}

test().catch(console.error);
