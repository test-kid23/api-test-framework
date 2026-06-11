"""Phase 5 P2 第三批单元测试 — T5-21, T5-22"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ==================== T5-21: 回放变量替换 ====================


class TestVarDetector:
    """VarDetector 动态变量检测器测试."""

    def test_import(self) -> None:
        """VarDetector 可正常导入."""
        from framework.recorder.var_detector import VarDetector
        assert VarDetector is not None

    def test_detect_uuid(self) -> None:
        """检测 UUID v4."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        uid = "550e8400-e29b-41d4-a716-446655440000"
        results = detector._detect_value(uid, location="body", key="request_id")
        assert len(results) >= 1
        assert results[0].template == "{{ $uuid }}"

    def test_detect_iso_timestamp(self) -> None:
        """检测 ISO 8601 时间戳."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        ts = "2024-01-15T10:30:00Z"
        results = detector._detect_value(ts, location="query_param", key="time")
        assert len(results) >= 1
        assert results[0].template == "{{ $timestamp }}"

    def test_detect_jwt_token(self) -> None:
        """检测 JWT token."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        jwt_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "dQw4w9WgXcQ"
        )
        results = detector._detect_value(jwt_token, location="header", key="Authorization")
        assert len(results) >= 1
        assert results[0].template == "{{ $token }}"

    def test_detect_unix_timestamp_seconds(self) -> None:
        """检测 Unix 秒级时间戳."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        ts = "1715328000"  # 2024-05-10
        results = detector._detect_value(ts, location="query_param", key="ts")
        assert len(results) >= 1
        assert results[0].template == "{{ $unix_timestamp }}"

    def test_detect_unix_timestamp_milliseconds(self) -> None:
        """检测 Unix 毫秒级时间戳."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        ts = "1715328000123"  # 2024-05-10
        results = detector._detect_value(ts, location="query_param", key="ts")
        assert len(results) >= 1
        assert results[0].template == "{{ $unix_timestamp }}"

    def test_detect_md5_hash(self) -> None:
        """检测 MD5 哈希."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        md5 = "5d41402abc4b2a76b9719d911017c592"
        results = detector._detect_value(md5, location="body", key="sign")
        assert len(results) >= 1
        assert results[0].template == "{{ $hash_md5 }}"

    def test_detect_sha256_hash(self) -> None:
        """检测 SHA256 哈希."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        results = detector._detect_value(sha256, location="body", key="hash")
        assert len(results) >= 1
        assert results[0].template == "{{ $hash_sha256 }}"

    def test_detect_signature_param_name(self) -> None:
        """签名类参数名自动标记."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        results = detector.detect_url("https://api.example.com/users?sign=abc123&ts=1715328000")
        # sign 参数名被标记
        sign_results = [r for r in results if r.key == "sign"]
        assert len(sign_results) >= 1
        assert sign_results[0].pattern_name == "signature_param_name"

    def test_detect_url_multiple_params(self) -> None:
        """URL 中多个动态参数同时检测."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        uid = str(uuid.uuid4())
        url = f"https://api.example.com/users?ts=1715328000&trace_id={uid}"
        results = detector.detect_url(url)
        assert len(results) >= 2

    def test_detect_headers_bearer_token(self) -> None:
        """检测 Authorization: Bearer <token>."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        jwt_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dQw4w9WgXcQ"
        )
        results = detector.detect_headers({"Authorization": f"Bearer {jwt_token}"})
        assert len(results) >= 1
        assert any(r.template == "{{ $auth_token }}" for r in results)

    def test_detect_body_dict(self) -> None:
        """检测 JSON body 中的动态值."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        body = {
            "user_id": str(uuid.uuid4()),
            "created_at": "2024-01-15T10:30:00Z",
            "name": "static_value",
        }
        results = detector.detect_body(body)
        # 至少检测到 uuid 和 timestamp
        assert len(results) >= 2
        templates = {r.template for r in results}
        assert "{{ $uuid }}" in templates
        assert "{{ $timestamp }}" in templates

    def test_detect_body_nested(self) -> None:
        """检测嵌套 JSON body 中的动态值."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        body = {
            "user": {
                "id": str(uuid.uuid4()),
                "profile": {
                    "avatar_hash": "5d41402abc4b2a76b9719d911017c592",
                },
            },
            "metadata": [
                {"key": "trace", "value": str(uuid.uuid4())},
            ],
        }
        results = detector.detect_body(body)
        assert len(results) >= 3  # 2 uuids + 1 md5

    def test_detect_body_list(self) -> None:
        """检测 list body 中的动态值."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        body = [
            {"id": str(uuid.uuid4()), "ts": "2024-01-15T10:30:00Z"},
            {"id": str(uuid.uuid4()), "ts": "2024-01-16T10:30:00Z"},
        ]
        results = detector.detect_body(body)
        assert len(results) >= 4

    def test_detect_entry_comprehensive(self) -> None:
        """综合条目检测."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        uid = str(uuid.uuid4())
        url = f"https://api.example.com/users?ts=1715328000&trace={uid}"
        headers = {
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
                "dQw4w9WgXcQ"
            ),
            "Content-Type": "application/json",
        }
        body = {"request_id": str(uuid.uuid4()), "sign": "abc123def456"}

        results = detector.detect_entry(url=url, headers=headers, body=body)
        # 应该有多种检测结果
        assert len(results) >= 3

    def test_detect_entry_no_dynamic(self) -> None:
        """无动态值的条目返回空列表."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        results = detector.detect_entry(
            url="https://api.example.com/static",
            headers={"Content-Type": "application/json"},
            body={"name": "John", "age": 30},
        )
        assert len(results) == 0

    def test_generate_replacements(self) -> None:
        """生成替换映射."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        uid = "550e8400-e29b-41d4-a716-446655440000"
        results = detector.detect_entry(
            url=f"https://api.example.com/users?id={uid}",
            body={"user_id": uid},
        )
        replacements = detector.generate_replacements(results)
        assert uid in replacements
        assert replacements[uid] == "{{ $uuid }}"

    def test_custom_pattern(self) -> None:
        """自定义检测模式."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        detector.add_pattern(
            name="custom_id",
            regex=r"ID-\d{8}",
            template="{{ $custom_id }}",
        )
        results = detector._detect_value("ID-20240115", location="body", key="ref")
        assert len(results) >= 1
        assert results[0].template == "{{ $custom_id }}"

    def test_custom_pattern_invalid_regex(self) -> None:
        """无效正则抛出异常."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        with pytest.raises(re.error):
            detector.add_pattern("bad", r"[invalid", "{{ $bad }}")

    def test_detected_var_dataclass(self) -> None:
        """DetectedVar 数据类字段正确."""
        from framework.recorder.var_detector import DetectedVar

        v = DetectedVar(
            original_value="test123",
            location="header",
            key="Authorization",
            template="{{ $token }}",
            pattern_name="bearer_token",
        )
        assert v.original_value == "test123"
        assert v.location == "header"
        assert v.key == "Authorization"

    def test_ignore_non_string_values(self) -> None:
        """非字符串值被忽略."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        results = detector._detect_value("", location="body", key="empty")
        assert results == []

    def test_unix_timestamp_out_of_range_ignored(self) -> None:
        """超出合理范围的 Unix 时间戳被忽略."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        # 9999999999 超出合理范围（年份 > 2100）
        results = detector._detect_value("9999999999", location="query_param", key="ts")
        unix_results = [r for r in results if r.pattern_name == "unix_timestamp"]
        assert len(unix_results) == 0

    def test_dedup_in_detect_entry(self) -> None:
        """detect_entry 对重复变量去重."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()
        uid = "550e8400-e29b-41d4-a716-446655440000"
        # 同一个 UUID 出现在 url 和 body 中
        results = detector.detect_entry(
            url=f"https://api.example.com/users?id={uid}",
            body={"user_id": uid},
        )
        # 按 (location, key, original_value) 去重后应只有 2 条
        uid_results = [r for r in results if r.original_value == uid]
        assert len(uid_results) == 2  # url 和 body 各一条

    def test_sanitize_key(self) -> None:
        """_sanitize_key 正确转换键名."""
        from framework.recorder.var_detector import _sanitize_key

        assert _sanitize_key("X-Api-Key") == "x_api_key"
        assert _sanitize_key("Content Type") == "content_type"


class TestHARPlayerVarDetection:
    """HARPlayer 动态变量检测集成测试."""

    def test_player_has_var_detector_attr(self) -> None:
        """HARPlayer 有 _var_detector 属性."""
        from framework.recorder.player import HARPlayer
        player = HARPlayer(client=MagicMock(), enable_var_detection=True)
        assert player._var_detector is not None

    def test_player_var_detection_disabled_by_default(self) -> None:
        """默认不启用变量检测."""
        from framework.recorder.player import HARPlayer
        player = HARPlayer(client=MagicMock())
        assert player._var_detector is None

    def test_playback_report_has_detected_vars_field(self) -> None:
        """PlaybackReport 有 detected_vars 字段."""
        from framework.recorder.player import PlaybackReport
        report = PlaybackReport()
        assert hasattr(report, "detected_vars")
        assert report.detected_vars == []

    def test_playback_report_to_dict_includes_detected_vars(self) -> None:
        """to_dict 在有检测结果时包含 detected_vars."""
        from framework.recorder.player import PlaybackReport
        report = PlaybackReport(
            detected_vars=[{"location": "body", "template": "{{ $uuid }}"}],
        )
        d = report.to_dict()
        assert "detected_vars" in d

    def test_playback_report_to_dict_omits_empty_detected_vars(self) -> None:
        """to_dict 在无检测结果时不包含 detected_vars."""
        from framework.recorder.player import PlaybackReport
        report = PlaybackReport(detected_vars=[])
        d = report.to_dict()
        assert "detected_vars" not in d

    def test_apply_var_replacements_no_detector(self) -> None:
        """未启用检测器时不替换."""
        from framework.recorder.player import HARPlayer
        player = HARPlayer(client=MagicMock(), enable_var_detection=False)
        url, headers, params, body, detected = player._apply_var_replacements(
            url="https://api.example.com/test",
            headers={"X-Token": "abc123"},
            params={"ts": "1715328000"},
            body={"id": str(uuid.uuid4())},
        )
        assert detected == []
        assert "1715328000" in params["ts"]

    def test_apply_var_replacements_with_detector(self) -> None:
        """启用检测器后自动替换."""
        from framework.recorder.player import HARPlayer

        player = HARPlayer(client=MagicMock(), enable_var_detection=True)
        uid = "550e8400-e29b-41d4-a716-446655440000"
        url, headers, params, body, detected = player._apply_var_replacements(
            url=f"https://api.example.com/users?id={uid}",
            headers={"Content-Type": "application/json"},
            params={},
            body={"user_id": uid},
        )
        assert len(detected) >= 1
        # body 中的 uuid 被替换
        assert body["user_id"] == "{{ $uuid }}"

    def test_replace_in_body_dict(self) -> None:
        """递归替换 body dict."""
        from framework.recorder.player import HARPlayer

        player = HARPlayer(client=MagicMock(), enable_var_detection=False)
        body = {"id": "550e8400-e29b-41d4-a716-446655440000", "nested": {"ref": "550e8400-e29b-41d4-a716-446655440000"}}
        result = player._replace_in_body(
            body,
            {"550e8400-e29b-41d4-a716-446655440000": "{{ $uuid }}"},
        )
        assert result["id"] == "{{ $uuid }}"
        assert result["nested"]["ref"] == "{{ $uuid }}"

    def test_replace_in_body_list(self) -> None:
        """递归替换 body list."""
        from framework.recorder.player import HARPlayer

        player = HARPlayer(client=MagicMock(), enable_var_detection=False)
        body = ["550e8400-e29b-41d4-a716-446655440000", "other"]
        result = player._replace_in_body(
            body,
            {"550e8400-e29b-41d4-a716-446655440000": "{{ $uuid }}"},
        )
        assert result[0] == "{{ $uuid }}"
        assert result[1] == "other"


# ==================== T5-22: 密码强度策略 ====================


class TestPasswordStrengthValidation:
    """validate_password_strength 测试."""

    def test_valid_password_passes(self) -> None:
        """合法密码通过校验."""
        from api.auth import validate_password_strength
        result = validate_password_strength("MyP@ssw0rd!")
        assert result is None

    def test_too_short_fails(self) -> None:
        """太短的密码不通过."""
        from api.auth import validate_password_strength
        result = validate_password_strength("Ab1!")
        assert result is not None
        assert "8" in result

    def test_no_uppercase_fails(self) -> None:
        """无大写字母不通过."""
        from api.auth import validate_password_strength
        result = validate_password_strength("myp@ssw0rd!")
        assert result is not None
        assert "大写" in result

    def test_no_lowercase_fails(self) -> None:
        """无小写字母不通过."""
        from api.auth import validate_password_strength
        result = validate_password_strength("MYP@SSW0RD!")
        assert result is not None
        assert "小写" in result

    def test_no_digit_fails(self) -> None:
        """无数字不通过."""
        from api.auth import validate_password_strength
        result = validate_password_strength("MyP@ssword!")
        assert result is not None
        assert "数字" in result

    def test_no_special_char_fails(self) -> None:
        """无特殊字符不通过."""
        from api.auth import validate_password_strength
        result = validate_password_strength("MyPassw0rd")
        assert result is not None
        assert "特殊" in result


class TestLoginLockout:
    """登录锁定机制测试."""

    def test_check_login_lockout_initial(self) -> None:
        """初始状态未锁定."""
        from api.auth import check_login_lockout
        result = check_login_lockout("test_lockout_user_1")
        assert result is None

    def test_record_and_check_lockout(self) -> None:
        """5 次失败后锁定."""
        from api.auth import check_login_lockout, record_login_failure, reset_login_failures

        username = "test_lockout_user_2"
        reset_login_failures(username)

        # 前 4 次不锁定
        for _ in range(4):
            locked = record_login_failure(username)
            assert locked is False

        # 第 5 次锁定
        locked = record_login_failure(username)
        assert locked is True

        # 检查锁定状态
        msg = check_login_lockout(username)
        assert msg is not None
        assert "锁定" in msg

        reset_login_failures(username)

    def test_reset_after_success(self) -> None:
        """登录成功后重置计数器."""
        from api.auth import check_login_lockout, record_login_failure, reset_login_failures

        username = "test_lockout_user_3"
        reset_login_failures(username)

        # 记录 3 次失败
        for _ in range(3):
            record_login_failure(username)

        # 重置
        reset_login_failures(username)
        msg = check_login_lockout(username)
        assert msg is None

    def test_lockout_not_triggered_below_threshold(self) -> None:
        """少于 5 次不锁定."""
        from api.auth import check_login_lockout, record_login_failure, reset_login_failures

        username = "test_lockout_user_4"
        reset_login_failures(username)

        for _ in range(4):
            record_login_failure(username)

        msg = check_login_lockout(username)
        # 可能不锁定（如果锁定时间为 0），也可能是 "已锁定"（如果锁定已触发）
        # 因为 record_login_failure 第 5 次才设置 lockout_until
        # 所以 4 次时 lockout_until=0，failures=4
        # 而 check_login_lockout 检查 failures >= 5 且 lockout_until > 0
        # 所以 4 次不应该锁定
        assert msg is None

        reset_login_failures(username)


class TestPasswordStrengthInRoutes:
    """路由中密码强度校验的集成测试."""

    def test_auth_imports_strength_functions(self) -> None:
        """auth router 导入了密码强度函数."""
        import inspect
        from api.routers import auth as auth_router

        source = inspect.getsource(auth_router)
        assert "validate_password_strength" in source
        assert "check_login_lockout" in source
        assert "record_login_failure" in source
        assert "reset_login_failures" in source

    def test_login_endpoint_has_lockout_check(self) -> None:
        """login 端点包含锁定检查逻辑."""
        import inspect
        from api.routers.auth import login

        source = inspect.getsource(login)
        assert "check_login_lockout" in source
        assert "record_login_failure" in source
        assert "reset_login_failures" in source
        assert "account_locked" in source

    def test_register_endpoint_has_strength_check(self) -> None:
        """register 端点包含密码强度检查."""
        import inspect
        from api.routers.auth import register

        source = inspect.getsource(register)
        assert "validate_password_strength" in source
        assert "weak_password" in source

    def test_change_password_endpoint_has_strength_check(self) -> None:
        """change-password 端点包含密码强度检查."""
        import inspect
        from api.routers.auth import change_password

        source = inspect.getsource(change_password)
        assert "validate_password_strength" in source
        assert "weak_password" in source

    def test_admin_create_user_has_strength_check(self) -> None:
        """admin 创建用户端点包含密码强度检查."""
        import inspect
        from api.routers.users import create_user

        source = inspect.getsource(create_user)
        assert "validate_password_strength" in source
        assert "weak_password" in source

    def test_admin_update_user_password_has_strength_check(self) -> None:
        """admin 重置密码端点包含密码强度检查."""
        import inspect
        from api.routers.users import update_user

        source = inspect.getsource(update_user)
        assert "validate_password_strength" in source
        assert "weak_password" in source


# ==================== 集成测试 ====================


class TestT21T22Integration:
    """T5-21 + T5-22 端到端集成测试."""

    def test_var_detector_full_flow(self) -> None:
        """完整变量检测流程：创建→检测→替换."""
        from framework.recorder.var_detector import VarDetector

        detector = VarDetector()

        # 模拟一个典型 API 请求
        url = "https://api.example.com/v1/orders?ts=1715328000&sign=abc123"
        headers = {
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
                "dQw4w9WgXcQ"
            ),
            "X-Request-Id": "550e8400-e29b-41d4-a716-446655440000",
        }
        body = {
            "order_id": "550e8400-e29b-41d4-a716-446655440000",
            "created_at": "2024-01-15T10:30:00Z",
            "checksum": "5d41402abc4b2a76b9719d911017c592",
        }

        results = detector.detect_entry(url=url, headers=headers, body=body)
        replacements = detector.generate_replacements(results)

        # 验证各种类型的检测
        templates = {v.template for v in results}
        assert "{{ $timestamp }}" in templates
        assert "{{ $uuid }}" in templates
        assert "{{ $token }}" in templates or "{{ $auth_token }}" in templates
        assert "{{ $hash_md5 }}" in templates

        # 验证替换映射
        assert len(replacements) >= 3

    def test_password_strength_all_cases(self) -> None:
        """密码强度全覆盖测试."""
        from api.auth import validate_password_strength

        valid_passwords = [
            "MyP@ssw0rd!",
            "C0mplex!Pass",
            "A1b2C3d4!@",
            "Str0ng#P@ss",
        ]
        for pw in valid_passwords:
            assert validate_password_strength(pw) is None, f"应通过: {pw}"

        invalid_cases = [
            ("short1!", "太短"),
            ("nouppercase1!", "无大写"),
            ("NOLOWERCASE1!", "无小写"),
            ("NoDigits!!", "无数字"),
            ("NoSpecial1", "无特殊"),
        ]
        for pw, reason in invalid_cases:
            result = validate_password_strength(pw)
            assert result is not None, f"{reason}: {pw} 应不通过"
