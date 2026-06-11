"""字段加密器 — AES-256-GCM 加密/解密/脱敏

用于环境变量等敏感字段的加密存储。加密后格式:
  "enc:v1:<base64_nonce>:<base64_ciphertext>:<base64_tag>"

密钥从环境变量 AUTOTEST_ENCRYPTION_KEY 读取。
"""

from __future__ import annotations

import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(Exception):
    """解密失败异常."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message or "解密失败")


class FieldEncryptor:
    """字段加密器（AES-256-GCM）.

    加密后格式: "enc:v1:<base64_nonce>:<base64_ciphertext>:<base64_tag>"

    Attributes:
        ENCRYPTION_PREFIX: 加密值前缀标识。
    """

    ENCRYPTION_PREFIX: str = "enc:v1:"
    NONCE_LENGTH: int = 12  # 96-bit nonce for GCM
    KEY_LENGTH: int = 32  # 256-bit key

    def __init__(self, key: bytes) -> None:
        """初始化加密器.

        Args:
            key: 32 字节 AES-256 密钥.

        Raises:
            ValueError: 密钥长度不足 32 字节时抛出.
        """
        if len(key) < self.KEY_LENGTH:
            raise ValueError(
                f"密钥长度不足: 需要至少 {self.KEY_LENGTH} 字节, 实际 {len(key)} 字节"
            )
        self._key: bytes = key[: self.KEY_LENGTH]
        self._aesgcm: AESGCM = AESGCM(self._key)

    @classmethod
    def from_env(cls, env_var: str = "AUTOTEST_ENCRYPTION_KEY") -> FieldEncryptor:
        """从环境变量读取密钥创建实例.

        若环境变量未设置，自动生成一个随机密钥并写入环境变量。

        Args:
            env_var: 环境变量名.

        Returns:
            FieldEncryptor 实例.
        """
        key_str = os.environ.get(env_var, "")
        if not key_str:
            key = AESGCM.generate_key(bit_length=256)
            os.environ[env_var] = base64.b64encode(key).decode("ascii")
            return cls(key)
        try:
            key = base64.b64decode(key_str)
        except Exception:
            key = hashlib.sha256(key_str.encode("utf-8")).digest()
        return cls(key)

    def encrypt(self, plaintext: str) -> str:
        """加密明文.

        Args:
            plaintext: 明文.

        Returns:
            加密后字符串（带 enc:v1: 前缀）.
        """
        nonce = os.urandom(self.NONCE_LENGTH)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # ciphertext 包含 ciphertext + tag（AESGCM.encrypt 自动追加 16 字节 tag）
        # 分离 ciphertext 和 tag
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        return (
            f"{self.ENCRYPTION_PREFIX}"
            f"{base64.b64encode(nonce).decode('ascii')}:"
            f"{base64.b64encode(ct).decode('ascii')}:"
            f"{base64.b64encode(tag).decode('ascii')}"
        )

    def decrypt(self, ciphertext: str) -> str:
        """解密密文.

        Args:
            ciphertext: 加密字符串（带 enc:v1: 前缀）.

        Returns:
            明文.

        Raises:
            DecryptionError: 解密失败时（格式错误、密钥不匹配等）.
        """
        if not self.is_encrypted(ciphertext):
            raise DecryptionError("不是有效的加密格式")

        try:
            payload = ciphertext[len(self.ENCRYPTION_PREFIX):]
            parts = payload.split(":")
            if len(parts) != 3:
                raise DecryptionError("加密数据格式错误: 期望 3 部分")
            nonce_b64, ct_b64, tag_b64 = parts
            nonce = self._b64decode_safe(nonce_b64, "nonce")
            ct = self._b64decode_safe(ct_b64, "ciphertext")
            tag = self._b64decode_safe(tag_b64, "tag")
            if len(nonce) != self.NONCE_LENGTH:
                raise DecryptionError(f"nonce 长度异常: {len(nonce)}")
            if len(tag) != 16:
                raise DecryptionError(f"tag 长度异常: {len(tag)}")
            combined = ct + tag
            plaintext = self._aesgcm.decrypt(nonce, combined, None)
            return plaintext.decode("utf-8")
        except DecryptionError:
            raise
        except Exception as e:
            raise DecryptionError(f"解密失败: {e}")

    @staticmethod
    def _b64decode_safe(data: str, label: str) -> bytes:
        """安全 Base64 解码.

        Args:
            data: Base64 编码字符串.
            label: 字段标签（用于错误消息）.

        Returns:
            解码后的字节.

        Raises:
            DecryptionError: 解码失败时.
        """
        try:
            result = base64.b64decode(data, validate=True)
        except (ValueError, base64.binascii.Error) as e:
            raise DecryptionError(f"Base64 解码失败 [{label}]: {e}")
        except TypeError:
            # Python < 3.11 没有 validate 参数，手动校验
            result = base64.b64decode(data)
            # 验证重新编码后是否一致
            re_encoded = base64.b64encode(result).decode("ascii")
            if re_encoded.rstrip("=") != data.rstrip("="):
                raise DecryptionError(f"Base64 解码失败 [{label}]: 无效字符")
        return result

    def mask(self, value: str) -> str:
        """脱敏显示.

        对加密值返回简短掩码，对明文返回首尾字符加掩码。

        Args:
            value: 原始值（明文或加密字符串）.

        Returns:
            脱敏后值（如 "a***z" 或 "enc:***"）.
        """
        if not value:
            return "***"
        if self.is_encrypted(value):
            return "enc:***"
        if len(value) <= 2:
            return value[0] + "*" if len(value) == 2 else "*"
        return value[0] + "***" + value[-1]

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """判断是否已加密.

        Args:
            value: 待检测值.

        Returns:
            是否以 enc:v1: 开头.
        """
        return isinstance(value, str) and value.startswith(FieldEncryptor.ENCRYPTION_PREFIX)

    def is_encrypted_instance(self, value: str) -> bool:
        """判断是否已加密（实例方法别名）.

        Args:
            value: 待检测值.

        Returns:
            是否以 enc:v1: 开头.
        """
        return self.is_encrypted(value)
