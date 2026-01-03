"""
端到端加密工具模块

使用 AES-GCM 对称加密算法，与前端保持一致
"""

import os
import base64
import hashlib
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# 算法配置（与前端保持一致）
KEY_LENGTH = 32  # 256位 = 32字节
IV_LENGTH = 12   # GCM 推荐 12 字节
PBKDF2_ITERATIONS = 100000  # 10万次迭代


def derive_key_from_password(password: str, salt: str) -> bytes:
    """
    从密码派生加密密钥（与前端 PBKDF2 逻辑一致）

    Args:
        password: 用户会话令牌
        salt: 用户ID

    Returns:
        bytes: 32字节的加密密钥
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt.encode('utf-8'),
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )

    key = kdf.derive(password.encode('utf-8'))
    return key


def encrypt_text(plaintext: str, key: bytes) -> str:
    """
    加密文本

    Args:
        plaintext: 明文
        key: 加密密钥（32字节）

    Returns:
        str: Base64 编码的密文（格式: IV + 密文）
    """
    try:
        # 创建 AES-GCM 加密器
        aesgcm = AESGCM(key)

        # 生成随机 IV
        iv = os.urandom(IV_LENGTH)

        # 加密（AAD=None，不使用额外认证数据）
        ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)

        # 合并 IV 和密文
        combined = iv + ciphertext

        # Base64 编码
        encoded = base64.b64encode(combined).decode('utf-8')

        return encoded
    except Exception as e:
        print(f"[Crypto] Encryption failed: {e}")
        raise


def decrypt_text(encrypted_text: str, key: bytes) -> str:
    """
    解密文本

    Args:
        encrypted_text: Base64 编码的密文
        key: 加密密钥（32字节）

    Returns:
        str: 明文
    """
    try:
        # Base64 解码
        combined = base64.b64decode(encrypted_text)

        # 分离 IV 和密文
        iv = combined[:IV_LENGTH]
        ciphertext = combined[IV_LENGTH:]

        # 创建 AES-GCM 解密器
        aesgcm = AESGCM(key)

        # 解密
        plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)

        # 解码为字符串
        plaintext = plaintext_bytes.decode('utf-8')

        return plaintext
    except Exception as e:
        print(f"[Crypto] Decryption failed: {e}")
        raise


class EncryptionSession:
    """
    加密会话管理器

    为每个用户会话维护加密密钥
    """

    def __init__(self, user_id: str, session_token: str):
        """
        初始化加密会话

        Args:
            user_id: 用户ID
            session_token: 会话令牌
        """
        self.user_id = user_id
        self.session_token = session_token
        self._key: Optional[bytes] = None
        self._initialize_key()

    def _initialize_key(self):
        """初始化加密密钥"""
        try:
            self._key = derive_key_from_password(self.session_token, self.user_id)
            print(f"[Crypto] Encryption key initialized for user: {self.user_id}")
        except Exception as e:
            print(f"[Crypto] Failed to initialize key: {e}")
            raise

    @property
    def key(self) -> bytes:
        """获取加密密钥"""
        if self._key is None:
            raise ValueError("Encryption key not initialized")
        return self._key

    def encrypt(self, plaintext: str) -> str:
        """
        加密文本

        Args:
            plaintext: 明文

        Returns:
            str: Base64 编码的密文
        """
        return encrypt_text(plaintext, self.key)

    def decrypt(self, encrypted_text: str) -> str:
        """
        解密文本

        Args:
            encrypted_text: Base64 编码的密文

        Returns:
            str: 明文
        """
        return decrypt_text(encrypted_text, self.key)

    def encrypt_stream_chunk(self, chunk: str) -> str:
        """
        加密流式输出的单个块

        Args:
            chunk: 文本块

        Returns:
            str: 加密后的块
        """
        if not chunk:
            return chunk

        try:
            return self.encrypt(chunk)
        except Exception as e:
            print(f"[Crypto] Stream chunk encryption failed: {e}")
            # 失败时返回原文（优雅降级）
            return chunk


def create_encryption_session(user_id: str, session_token: str) -> EncryptionSession:
    """
    创建加密会话

    Args:
        user_id: 用户ID
        session_token: 会话令牌

    Returns:
        EncryptionSession: 加密会话对象
    """
    return EncryptionSession(user_id, session_token)


# 测试函数
def test_encryption():
    """测试加密解密功能"""
    print("=== Testing Encryption ===")

    # 1. 密钥派生测试
    user_id = "test-user-123"
    session_token = "test-session-token-abc"

    key1 = derive_key_from_password(session_token, user_id)
    key2 = derive_key_from_password(session_token, user_id)

    print(f"Key 1: {key1.hex()[:32]}...")
    print(f"Key 2: {key2.hex()[:32]}...")
    print(f"Keys match: {key1 == key2}")

    # 2. 加密解密测试
    plaintext = "这是一段测试文本，用来测试端到端加密功能！Hello World! 🔒"
    print(f"\nOriginal: {plaintext}")

    encrypted = encrypt_text(plaintext, key1)
    print(f"Encrypted: {encrypted[:50]}...")

    decrypted = decrypt_text(encrypted, key1)
    print(f"Decrypted: {decrypted}")
    print(f"Match: {plaintext == decrypted}")

    # 3. 会话测试
    session = create_encryption_session(user_id, session_token)

    encrypted2 = session.encrypt(plaintext)
    print(f"\nSession Encrypted: {encrypted2[:50]}...")

    decrypted2 = session.decrypt(encrypted2)
    print(f"Session Decrypted: {decrypted2}")
    print(f"Match: {plaintext == decrypted2}")

    print("\n=== Test Complete ===")


async def encrypt_streaming_response(response_iterator, encryption_session: EncryptionSession):
    """
    加密流式响应的包装器

    Args:
        response_iterator: 原始响应迭代器
        encryption_session: 加密会话对象

    Yields:
        bytes: 加密后的数据块
    """
    import json

    async for chunk in response_iterator:
        try:
            # 解码数据块
            if isinstance(chunk, bytes):
                chunk_str = chunk.decode('utf-8')
            else:
                chunk_str = str(chunk)

            # SSE 格式: "data: {...}\n\n"
            if chunk_str.startswith('data: '):
                data_part = chunk_str[6:].strip()  # 移除 "data: " 前缀

                if data_part == '[DONE]':
                    # 保持结束标记不变
                    yield chunk
                    continue

                try:
                    # 解析 JSON
                    data = json.loads(data_part)

                    # 检查是否有内容需要加密
                    if 'choices' in data:
                        for choice in data['choices']:
                            if 'delta' in choice and 'content' in choice['delta']:
                                content = choice['delta']['content']
                                if content:
                                    # 加密内容
                                    encrypted_content = encryption_session.encrypt(content)
                                    choice['delta']['content'] = encrypted_content

                    # 重新编码为 SSE 格式
                    encrypted_chunk = f"data: {json.dumps(data)}\n\n"
                    yield encrypted_chunk.encode('utf-8')

                except json.JSONDecodeError:
                    # 不是 JSON，直接传递
                    yield chunk
            else:
                # 不是 SSE 格式，直接传递
                yield chunk

        except Exception as e:
            print(f"[Crypto] Stream encryption failed: {e}")
            # 失败时返回原始块
            yield chunk


if __name__ == "__main__":
    test_encryption()
