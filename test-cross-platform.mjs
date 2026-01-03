/**
 * 跨平台加密互操作性测试
 *
 * 前端加密 -> 输出密文 -> 后端解密验证
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

async function test() {
    console.log('=== Cross-Platform Test: Frontend Encrypt ===\n');

    const userId = 'test-user-123';
    const sessionToken = 'test-session-token-abc';

    const key = await deriveKeyFromPassword(sessionToken, userId);

    // 加密一条消息
    const plaintext = 'Cross-platform encryption test!';
    const encrypted = await encryptText(plaintext, key);

    console.log(`Plaintext: ${plaintext}`);
    console.log(`Encrypted: ${encrypted}`);
    console.log('\nCopy the encrypted text above and test in Python backend.');
}

test().catch(console.error);
