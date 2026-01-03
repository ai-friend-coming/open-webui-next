/**
 * 加密解密工具模块
 *
 * 使用 AES-GCM 对称加密算法，提供高性能的流式解密能力
 */

// 全局加密密钥（存储在内存中）
let encryptionKey: CryptoKey | null = null;

// 算法配置
const ALGORITHM = 'AES-GCM';
const KEY_LENGTH = 256; // 256位密钥
const IV_LENGTH = 12; // GCM 推荐 12 字节 IV

/**
 * 从密码生成加密密钥
 * @param password 用户密码或会话令牌
 * @param salt 盐值（建议使用用户ID）
 */
export async function deriveKeyFromPassword(password: string, salt: string): Promise<CryptoKey> {
	const encoder = new TextEncoder();

	// 使用 PBKDF2 从密码派生密钥
	const keyMaterial = await crypto.subtle.importKey(
		'raw',
		encoder.encode(password),
		'PBKDF2',
		false,
		['deriveKey']
	);

	const key = await crypto.subtle.deriveKey(
		{
			name: 'PBKDF2',
			salt: encoder.encode(salt),
			iterations: 100000, // OWASP 推荐至少 10万次
			hash: 'SHA-256'
		},
		keyMaterial,
		{ name: ALGORITHM, length: KEY_LENGTH },
		true, // 可导出（用于存储）
		['encrypt', 'decrypt']
	);

	return key;
}

/**
 * 初始化加密密钥（在用户登录后调用）
 * @param userId 用户ID
 * @param sessionToken 会话令牌
 */
export async function initEncryptionKey(userId: string, sessionToken: string): Promise<void> {
	try {
		// 使用 sessionToken 作为密码，userId 作为盐值
		encryptionKey = await deriveKeyFromPassword(sessionToken, userId);
		console.log('[Crypto] Encryption key initialized');
	} catch (error) {
		console.error('[Crypto] Failed to initialize key:', error);
		throw error;
	}
}

/**
 * 清除加密密钥（在用户登出时调用）
 */
export function clearEncryptionKey(): void {
	encryptionKey = null;
	console.log('[Crypto] Encryption key cleared');
}

/**
 * 获取当前加密密钥
 */
export function getEncryptionKey(): CryptoKey | null {
	return encryptionKey;
}

/**
 * 加密文本
 * @param plaintext 明文
 * @returns Base64 编码的密文（格式: IV + 密文）
 */
export async function encryptText(plaintext: string): Promise<string> {
	if (!encryptionKey) {
		throw new Error('Encryption key not initialized');
	}

	const encoder = new TextEncoder();
	const data = encoder.encode(plaintext);

	// 生成随机 IV
	const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));

	// 加密
	const ciphertext = await crypto.subtle.encrypt(
		{ name: ALGORITHM, iv },
		encryptionKey,
		data
	);

	// 合并 IV 和密文
	const combined = new Uint8Array(iv.length + ciphertext.byteLength);
	combined.set(iv, 0);
	combined.set(new Uint8Array(ciphertext), iv.length);

	// 返回 Base64 编码
	return btoa(String.fromCharCode(...combined));
}

/**
 * 解密文本
 * @param encryptedText Base64 编码的密文
 * @returns 明文
 */
export async function decryptText(encryptedText: string): Promise<string> {
	if (!encryptionKey) {
		throw new Error('Encryption key not initialized');
	}

	try {
		// Base64 解码
		const combined = Uint8Array.from(atob(encryptedText), (c) => c.charCodeAt(0));

		// 分离 IV 和密文
		const iv = combined.slice(0, IV_LENGTH);
		const ciphertext = combined.slice(IV_LENGTH);

		// 解密
		const decrypted = await crypto.subtle.decrypt(
			{ name: ALGORITHM, iv },
			encryptionKey,
			ciphertext
		);

		// 解码为字符串
		const decoder = new TextDecoder();
		return decoder.decode(decrypted);
	} catch (error) {
		console.error('[Crypto] Decryption failed:', error);
		throw error;
	}
}

/**
 * 流式解密文本
 * 保持最后 N 个字符为密文，前面的字符显示为明文
 *
 * @param encryptedChunks 加密的文本块数组
 * @param keepEncryptedCount 保持密文的字符数（默认10）
 * @returns 部分解密的文本
 */
export async function streamDecrypt(
	encryptedChunks: string[],
	keepEncryptedCount: number = 10
): Promise<{ decrypted: string; encrypted: string }> {
	if (encryptedChunks.length === 0) {
		return { decrypted: '', encrypted: '' };
	}

	// 合并所有加密块
	const fullEncrypted = encryptedChunks.join('');

	// 如果总长度小于等于保持密文的长度，全部显示为密文
	if (fullEncrypted.length <= keepEncryptedCount) {
		return {
			decrypted: '',
			encrypted: fullEncrypted
		};
	}

	try {
		// 解密整个文本
		const fullDecrypted = await decryptText(fullEncrypted);

		// 分离明文和密文部分
		const decryptedPart = fullDecrypted.slice(0, -keepEncryptedCount);
		const encryptedPart = fullEncrypted.slice(-keepEncryptedCount);

		return {
			decrypted: decryptedPart,
			encrypted: encryptedPart
		};
	} catch (error) {
		// 解密失败，返回原始密文
		console.warn('[Crypto] Stream decrypt failed, showing encrypted text:', error);
		return {
			decrypted: '',
			encrypted: fullEncrypted
		};
	}
}

/**
 * 高性能批量解密（用于历史消息）
 * @param encryptedTexts 加密文本数组
 * @returns 解密后的文本数组
 */
export async function batchDecrypt(encryptedTexts: string[]): Promise<string[]> {
	const promises = encryptedTexts.map((text) =>
		decryptText(text).catch((error) => {
			console.warn('[Crypto] Batch decrypt item failed:', error);
			return text; // 失败时返回原文
		})
	);

	return Promise.all(promises);
}

/**
 * 检查是否已初始化加密密钥
 */
export function isEncryptionEnabled(): boolean {
	return encryptionKey !== null;
}
