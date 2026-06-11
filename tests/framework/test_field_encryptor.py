"""FieldEncryptor 单元测试 — AES-256-GCM 加密/解密/脱敏"""

from __future__ import annotations

import base64
import os

import pytest

from framework.utils.field_encryptor import (
    FieldEncryptor,
    DecryptionError,
)


# ==================== Fixtures ====================


@pytest.fixture
def key() -> bytes:
    """生成 32 字节 AES-256 密钥."""
    import os as _os
    return _os.urandom(32)


@pytest.fixture
def encryptor(key: bytes) -> FieldEncryptor:
    """创建加密器实例."""
    return FieldEncryptor(key)


# ==================== 初始化测试 ====================


class TestFieldEncryptorInit:
    """初始化相关测试."""

    def test_init_with_valid_key(self, key: bytes) -> None:
        """使用有效密钥初始化."""
        enc = FieldEncryptor(key)
        assert enc._key == key
        assert enc._aesgcm is not None

    def test_init_with_longer_key(self) -> None:
        """密钥超过 32 字节时截取前 32 字节."""
        long_key = os.urandom(48)
        enc = FieldEncryptor(long_key)
        assert len(enc._key) == 32
        assert enc._key == long_key[:32]

    def test_init_with_short_key_raises(self) -> None:
        """密钥不足 32 字节时抛出 ValueError."""
        short_key = os.urandom(16)
        with pytest.raises(ValueError, match="密钥长度不足"):
            FieldEncryptor(short_key)

    def test_init_with_exact_32_bytes(self) -> None:
        """恰好 32 字节密钥."""
        exact_key = os.urandom(32)
        enc = FieldEncryptor(exact_key)
        assert len(enc._key) == 32

    def test_encryption_prefix_constant(self) -> None:
        """验证加密前缀常量."""
        assert FieldEncryptor.ENCRYPTION_PREFIX == "enc:v1:"

    def test_from_env_with_key(self, encryptor: FieldEncryptor) -> None:
        """从环境变量读取密钥."""
        b64_key = base64.b64encode(os.urandom(32)).decode("ascii")
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AUTOTEST_ENCRYPTION_KEY", b64_key)
            enc = FieldEncryptor.from_env()
            assert enc._key == base64.b64decode(b64_key)

    def test_from_env_auto_generate(self) -> None:
        """环境变量未设置时自动生成密钥."""
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("AUTOTEST_ENCRYPTION_KEY", raising=False)
            enc = FieldEncryptor.from_env()
            assert len(enc._key) == 32
            # 验证环境变量已被设置
            assert "AUTOTEST_ENCRYPTION_KEY" in os.environ

    def test_from_env_with_custom_var_name(self) -> None:
        """自定义环境变量名."""
        b64_key = base64.b64encode(os.urandom(32)).decode("ascii")
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CUSTOM_KEY", b64_key)
            enc = FieldEncryptor.from_env("CUSTOM_KEY")
            assert enc._key == base64.b64decode(b64_key)

    def test_from_env_with_non_base64_key(self) -> None:
        """环境变量不是 Base64 时，使用 SHA256 派生密钥."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AUTOTEST_ENCRYPTION_KEY", "my-plain-password")
            enc = FieldEncryptor.from_env()
            assert len(enc._key) == 32


# ==================== 加密/解密测试 ====================


class TestEncryptDecrypt:
    """加密/解密核心功能测试."""

    def test_encrypt_returns_prefixed_string(self, encryptor: FieldEncryptor) -> None:
        """加密后返回带前缀的字符串."""
        result = encryptor.encrypt("hello")
        assert result.startswith("enc:v1:")
        assert ":" in result[len("enc:v1:"):]

    def test_encrypt_produces_different_ciphertexts(self, encryptor: FieldEncryptor) -> None:
        """相同明文每次加密产生不同密文（随机 nonce）."""
        r1 = encryptor.encrypt("same_text")
        r2 = encryptor.encrypt("same_text")
        assert r1 != r2

    def test_decrypt_roundtrip(self, encryptor: FieldEncryptor) -> None:
        """加密后解密还原."""
        plain = "my_secret_value_123"
        encrypted = encryptor.encrypt(plain)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plain

    def test_decrypt_empty_string(self, encryptor: FieldEncryptor) -> None:
        """空字符串加解密."""
        encrypted = encryptor.encrypt("")
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == ""

    def test_decrypt_long_text(self, encryptor: FieldEncryptor) -> None:
        """长文本加解密."""
        plain = "A" * 10000
        encrypted = encryptor.encrypt(plain)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plain

    def test_decrypt_unicode_text(self, encryptor: FieldEncryptor) -> None:
        """Unicode 文本加解密."""
        plain = "中文测试 🔐 パスワード"
        encrypted = encryptor.encrypt(plain)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plain

    def test_decrypt_special_characters(self, encryptor: FieldEncryptor) -> None:
        """特殊字符加解密."""
        plain = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = encryptor.encrypt(plain)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plain

    def test_decrypt_not_encrypted_raises(self, encryptor: FieldEncryptor) -> None:
        """解密非加密字符串抛出 DecryptionError."""
        with pytest.raises(DecryptionError, match="不是有效的加密格式"):
            encryptor.decrypt("plain_text")

    def test_decrypt_empty_string_raises(self, encryptor: FieldEncryptor) -> None:
        """解密空字符串抛出 DecryptionError."""
        with pytest.raises(DecryptionError, match="不是有效的加密格式"):
            encryptor.decrypt("")

    def test_decrypt_wrong_prefix_raises(self, encryptor: FieldEncryptor) -> None:
        """解密错误前缀的字符串抛出异常."""
        with pytest.raises(DecryptionError, match="不是有效的加密格式"):
            encryptor.decrypt("bad:v1:abc:def:ghi")

    def test_decrypt_malformed_format_raises(self, encryptor: FieldEncryptor) -> None:
        """解密格式错误的字符串抛出异常."""
        with pytest.raises(DecryptionError):
            encryptor.decrypt("enc:v1:only_two_parts")

    def test_decrypt_wrong_key(self) -> None:
        """使用不同密钥解密失败."""
        enc1 = FieldEncryptor(os.urandom(32))
        enc2 = FieldEncryptor(os.urandom(32))
        encrypted = enc1.encrypt("secret")
        with pytest.raises(DecryptionError):
            enc2.decrypt(encrypted)

    def test_decrypt_tampered_ciphertext(self, encryptor: FieldEncryptor) -> None:
        """篡改后的密文解密失败."""
        encrypted = encryptor.encrypt("secret")
        # 篡改最后一个字符
        tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered)

    def test_decrypt_invalid_base64(self, encryptor: FieldEncryptor) -> None:
        """无效 Base64 解密失败."""
        with pytest.raises(DecryptionError):
            encryptor.decrypt("enc:v1:!!!:!!!:!!!")


# ==================== 脱敏测试 ====================


class TestMask:
    """脱敏功能测试."""

    def test_mask_encrypted_value(self, encryptor: FieldEncryptor) -> None:
        """加密值脱敏返回 enc:***."""
        encrypted = encryptor.encrypt("secret")
        masked = encryptor.mask(encrypted)
        assert masked == "enc:***"

    def test_mask_short_plaintext(self, encryptor: FieldEncryptor) -> None:
        """短明文脱敏."""
        assert encryptor.mask("ab") == "a*"
        assert encryptor.mask("a") == "*"

    def test_mask_normal_plaintext(self, encryptor: FieldEncryptor) -> None:
        """正常长度明文脱敏（首尾字符保留）."""
        assert encryptor.mask("password123") == "p***3"
        assert encryptor.mask("token_abc") == "t***c"

    def test_mask_empty_string(self, encryptor: FieldEncryptor) -> None:
        """空字符串脱敏."""
        assert encryptor.mask("") == "***"


# ==================== is_encrypted 测试 ====================


class TestIsEncrypted:
    """is_encrypted 静态方法测试."""

    def test_encrypted_string(self) -> None:
        """加密字符串返回 True."""
        assert FieldEncryptor.is_encrypted("enc:v1:abc:def:ghi") is True

    def test_plain_string(self) -> None:
        """明文字符串返回 False."""
        assert FieldEncryptor.is_encrypted("hello") is False

    def test_empty_string(self) -> None:
        """空字符串返回 False."""
        assert FieldEncryptor.is_encrypted("") is False

    def test_similar_but_not_prefix(self) -> None:
        """类似但不完全匹配前缀."""
        assert FieldEncryptor.is_encrypted("enc:v2:abc:def") is False
        assert FieldEncryptor.is_encrypted("enc_v1:abc:def") is False

    def test_instance_method_alias(self, encryptor: FieldEncryptor) -> None:
        """实例方法 is_encrypted_instance 与静态方法一致."""
        assert encryptor.is_encrypted_instance("enc:v1:abc:def") is True
        assert encryptor.is_encrypted_instance("hello") is False


# ==================== 集成测试 ====================


class TestIntegration:
    """端到端集成测试."""

    def test_full_workflow(self) -> None:
        """完整工作流：加密 → 解密 → 脱敏."""
        enc = FieldEncryptor(os.urandom(32))
        original = "s3cr3t_p@ssw0rd!"

        # 加密
        encrypted = enc.encrypt(original)
        assert enc.is_encrypted(encrypted)

        # 解密
        decrypted = enc.decrypt(encrypted)
        assert decrypted == original

        # 脱敏
        masked = enc.mask(encrypted)
        assert masked == "enc:***"

        # 明文化后脱敏
        plain_masked = enc.mask(original)
        assert plain_masked == "s***!"

    def test_multiple_keys_independent(self) -> None:
        """不同密钥实例互不影响."""
        enc_a = FieldEncryptor(os.urandom(32))
        enc_b = FieldEncryptor(os.urandom(32))

        plain = "shared_secret"
        encrypted_a = enc_a.encrypt(plain)
        encrypted_b = enc_b.encrypt(plain)

        # 各自解密正确
        assert enc_a.decrypt(encrypted_a) == plain
        assert enc_b.decrypt(encrypted_b) == plain

        # 交叉解密失败
        with pytest.raises(DecryptionError):
            enc_a.decrypt(encrypted_b)
        with pytest.raises(DecryptionError):
            enc_b.decrypt(encrypted_a)

    def test_non_encrypted_value_in_workflow(self, encryptor: FieldEncryptor) -> None:
        """处理未加密值的场景."""
        plain = "plain_value"
        assert encryptor.is_encrypted(plain) is False
        assert encryptor.mask(plain) == "p***e"
