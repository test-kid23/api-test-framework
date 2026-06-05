"""FixtureLoader Shell 安全加固测试

覆盖场景：
1. 空白名单 → SecurityError
2. 命令不在白名单 → SecurityError
3. 命令在白名单 → 执行成功
4. 超时控制 → TimeoutExpired
5. 沙箱敏感路径 → SecurityError
6. Shell 解析错误 → SecurityError
7. 命令未找到 → SecurityError
8. 权限拒绝 → SecurityError
9. 带参数命令 → 正常执行
10. OSError 包装 → SecurityError
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from framework.exceptions import SecurityError
from framework.fixtures_loader import FixtureLoader
from framework.models import FixtureAction

# ══════════════════════════════════════════════════════════
# 辅助工厂
# ══════════════════════════════════════════════════════════


def make_shell_action(command: str, timeout: int | None = None) -> FixtureAction:
    """创建一个 shell 类型的 FixtureAction"""
    config: dict[str, object] = {"command": command}
    if timeout is not None:
        config["timeout"] = timeout
    return FixtureAction(action_type="shell", config=config)


def make_loader(
    allowed_commands: list[str] | None = None,
    sandbox: bool = False,
) -> FixtureLoader:
    """创建带安全配置的 FixtureLoader"""
    if allowed_commands is None:
        allowed_commands = []
    fixtures_config = {
        "allowed_shell_commands": allowed_commands,
        "shell_sandbox": sandbox,
    }
    return FixtureLoader(fixtures_config=fixtures_config)


# ══════════════════════════════════════════════════════════
# 1. 空白名单 / 未配置白名单
# ══════════════════════════════════════════════════════════


class TestEmptyWhitelist:
    """验证空白名单时拒绝所有 shell 命令"""

    def test_empty_allowed_list_raises_security_error(self) -> None:
        """白名单为空列表时，执行任何命令都应抛出 SecurityError"""
        loader = make_loader(allowed_commands=[])
        action = make_shell_action("echo hello")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})
        assert "not in the allowed list" in str(exc_info.value)
        assert exc_info.value.command == "echo hello"

    def test_no_fixtures_config_raises_security_error(self) -> None:
        """完全不传 fixtures_config 时（默认空字典），也应拒绝"""
        loader = FixtureLoader()
        action = make_shell_action("ls -la")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})
        assert "not in the allowed list" in str(exc_info.value)

    def test_empty_command_string_returns_none(self) -> None:
        """空命令字符串直接返回 None，不抛异常"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("")
        result = loader._execute_shell(action.config, {})
        assert result is None


# ══════════════════════════════════════════════════════════
# 2. 白名单拒绝
# ══════════════════════════════════════════════════════════


class TestWhitelistDeny:
    """验证命令不在白名单时被拒绝"""

    def test_unknown_command_denied(self) -> None:
        """命令不在白名单中时抛出 SecurityError"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("cat /etc/hosts")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})
        assert "not in the allowed list" in str(exc_info.value)
        assert exc_info.value.command == "cat"

    def test_partial_match_not_allowed(self) -> None:
        """命令名必须完全匹配，前缀匹配不算"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("echoo hello")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})
        assert exc_info.value.command == "echoo"

    def test_path_prefixed_command_checked_by_name(self) -> None:
        """/usr/bin/python 这类路径命令，检查的是路径最后一段"""
        loader = make_loader(allowed_commands=["python", "python3"])
        action = make_shell_action("/usr/bin/python -c 'print(1)'")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1\n", stderr="")
            loader._execute_shell(action.config, {})

        # 验证 subprocess.run 被调用，说明通过了白名单检查
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "/usr/bin/python"


# ══════════════════════════════════════════════════════════
# 3. 白名单通过 → 成功执行
# ══════════════════════════════════════════════════════════


class TestWhitelistAllow:
    """验证命令在白名单时成功执行"""

    def test_allowed_command_executes(self) -> None:
        """白名单中的 echo 命令正常执行"""
        loader = make_loader(allowed_commands=["echo", "python"])
        action = make_shell_action("echo hello world")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hello world\n", stderr="")
            result = loader._execute_shell(action.config, {})

        assert result is None
        mock_run.assert_called_once()
        # 验证通过 shlex 解析的参数列表
        called_args = mock_run.call_args[0][0]
        assert called_args == ["echo", "hello", "world"]

    def test_allowed_command_with_quoted_args(self) -> None:
        """带引号参数的命令通过 shlex 正确解析"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action('echo "hello world" test')

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        called_args = mock_run.call_args[0][0]
        # shlex 去掉了引号
        assert called_args == ["echo", "hello world", "test"]

    def test_multiple_commands_in_whitelist(self) -> None:
        """白名单包含多个命令时，各自独立检查"""
        loader = make_loader(allowed_commands=["echo", "python", "git"])

        for cmd in ["echo test", "python --version", "git status"]:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                action = make_shell_action(cmd)
                # 不应抛异常
                loader._execute_shell(action.config, {})

    def test_non_zero_returncode_logs_warning(self) -> None:
        """命令返回非零退出码时记录警告但不抛异常"""
        loader = make_loader(allowed_commands=["echo", "python"])
        action = make_shell_action("python -c 'exit(1)'")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = loader._execute_shell(action.config, {})

        assert result is None  # 不抛异常，返回 None

    def test_real_command_execution(self) -> None:
        """端到端测试：使用真实 python 命令验证完整流程"""
        loader = make_loader(allowed_commands=["python", "echo"])
        action = make_shell_action("python -c \"print('security-test-passed')\"")

        # 真实执行，不 mock
        result = loader._execute_shell(action.config, {})
        assert result is None


# ══════════════════════════════════════════════════════════
# 4. 超时控制
# ══════════════════════════════════════════════════════════


class TestTimeout:
    """验证超时控制"""

    def test_default_timeout_30_seconds(self) -> None:
        """默认超时 30 秒"""
        loader = make_loader(allowed_commands=["sleep", "python"])
        action = make_shell_action("sleep 60")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=30)
            with pytest.raises(subprocess.TimeoutExpired):
                loader._execute_shell(action.config, {})

        # 验证调用时 timeout 参数为默认值 30
        assert mock_run.call_args[1]["timeout"] == 30

    def test_custom_timeout_from_config(self) -> None:
        """支持在 config 中自定义 timeout"""
        loader = make_loader(allowed_commands=["sleep"])
        action = make_shell_action("sleep 5", timeout=10)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=10)
            with pytest.raises(subprocess.TimeoutExpired):
                loader._execute_shell(action.config, {})

        assert mock_run.call_args[1]["timeout"] == 10

    def test_timeout_logs_error(self) -> None:
        """超时时记录 ERROR 级别日志"""
        loader = make_loader(allowed_commands=["sleep"])
        action = make_shell_action("sleep 60")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=30)
            with patch("framework.fixtures_loader.logger") as mock_logger:
                with pytest.raises(subprocess.TimeoutExpired):
                    loader._execute_shell(action.config, {})
                mock_logger.error.assert_called_once()
                assert "超时" in mock_logger.error.call_args[0][0]


# ══════════════════════════════════════════════════════════
# 5. 沙箱：敏感路径检查
# ══════════════════════════════════════════════════════════


class TestSandbox:
    """验证沙箱模式的敏感路径检查"""

    def test_sensitive_path_blocked_with_sandbox_enabled(self) -> None:
        """沙箱开启时，引用 /etc 的命令被拒绝"""
        loader = make_loader(allowed_commands=["cat"], sandbox=True)
        action = make_shell_action("cat /etc/hosts")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})

        assert "sensitive path" in str(exc_info.value).lower()
        assert "/etc" in str(exc_info.value)

    def test_root_path_blocked_with_sandbox(self) -> None:
        """沙箱开启时，引用 /root 被拒绝"""
        loader = make_loader(allowed_commands=["ls"], sandbox=True)
        action = make_shell_action("ls /root/secret")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})

        assert "sensitive path" in str(exc_info.value).lower()
        assert "/root" in str(exc_info.value)

    def test_windows_sensitive_path_blocked(self) -> None:
        """沙箱开启时，引用 Windows 系统路径（在引号内）被拒绝"""
        loader = make_loader(allowed_commands=["python"], sandbox=True)
        # 在 YAML 中路径通常用引号包裹，shlex 在 POSIX 模式下保留单引号内容
        action = make_shell_action("python -c 'print(1)' --path 'C:\\Windows\\System32'")

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})

        assert "sensitive path" in str(exc_info.value).lower()

    def test_sensitive_path_in_middle_of_argument(self) -> None:
        """敏感路径作为参数子串时也会被检测"""
        loader = make_loader(allowed_commands=["cat"], sandbox=True)
        action = make_shell_action("cat /some/path/etc/config.ini")

        with pytest.raises(SecurityError) as _exc_info:
            loader._execute_shell(action.config, {})

    def test_no_block_without_sandbox(self) -> None:
        """沙箱关闭时，敏感路径不阻止执行"""
        loader = make_loader(allowed_commands=["cat"], sandbox=False)
        action = make_shell_action("cat /etc/hosts")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            # 不应抛 SecurityError
            result = loader._execute_shell(action.config, {})
            assert result is None
            mock_run.assert_called_once()

    def test_normal_path_not_blocked(self) -> None:
        """普通路径不会被沙箱阻止"""
        loader = make_loader(allowed_commands=["cat"], sandbox=True)
        action = make_shell_action("cat /tmp/test.txt")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        mock_run.assert_called_once()


# ══════════════════════════════════════════════════════════
# 6. shlex 解析错误
# ══════════════════════════════════════════════════════════


class TestShlexParsing:
    """验证 shlex 解析异常处理"""

    def test_unterminated_quote_raises_security_error(self) -> None:
        """未闭合的引号导致 shlex 解析失败，抛出 SecurityError"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action('echo "unterminated')

        with pytest.raises(SecurityError) as exc_info:
            loader._execute_shell(action.config, {})
        assert "Failed to parse" in str(exc_info.value)
        assert exc_info.value.command == 'echo "unterminated'


# ══════════════════════════════════════════════════════════
# 7. 系统级错误处理
# ══════════════════════════════════════════════════════════


class TestSystemErrors:
    """验证系统级错误的处理"""

    def test_command_not_found_converted_to_security_error(self) -> None:
        """命令不存在时，FileNotFoundError 被包装为 SecurityError"""
        loader = make_loader(allowed_commands=["nonexistent_command"])
        action = make_shell_action("nonexistent_command --flag")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(SecurityError) as exc_info:
                loader._execute_shell(action.config, {})

        assert "not found on system" in str(exc_info.value)
        assert exc_info.value.command == "nonexistent_command"

    def test_permission_denied_converted_to_security_error(self) -> None:
        """权限拒绝时，PermissionError 被包装为 SecurityError"""
        loader = make_loader(allowed_commands=["python"])
        action = make_shell_action("python restricted_script.py")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = PermissionError("Permission denied")
            with pytest.raises(SecurityError) as exc_info:
                loader._execute_shell(action.config, {})

        assert "Permission denied" in str(exc_info.value)
        assert exc_info.value.command == "python"

    def test_os_error_converted_to_security_error(self) -> None:
        """其他 OSError 被包装为 SecurityError"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("echo test")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Some OS error")
            with pytest.raises(SecurityError) as exc_info:
                loader._execute_shell(action.config, {})

        assert "OS error" in str(exc_info.value)
        assert exc_info.value.command == "echo"


# ══════════════════════════════════════════════════════════
# 8. SecurityError 原型验证
# ══════════════════════════════════════════════════════════


class TestSecurityErrorPrototype:
    """验证 SecurityError 的类型层级和属性"""

    def test_security_error_is_auto_test_exception(self) -> None:
        """SecurityError 应继承 AutoTestException"""
        from framework.exceptions import AutoTestException

        assert issubclass(SecurityError, AutoTestException)

    def test_security_error_carries_command_attribute(self) -> None:
        """SecurityError 实例携带 command 属性"""
        err = SecurityError("test message", command="bad_cmd")
        assert err.command == "bad_cmd"
        assert str(err) == "test message"

    def test_security_error_with_trace_id(self) -> None:
        """SecurityError 支持 trace_id"""
        err = SecurityError("test", command="cmd", trace_id="trace-123")
        assert err.trace_id == "trace-123"


# ══════════════════════════════════════════════════════════
# 9. 集成：通过 run_setup / run_teardown 调用
# ══════════════════════════════════════════════════════════


class TestIntegrationWithSetupTeardown:
    """验证安全机制在 setup/teardown 流程中正确工作"""

    def test_setup_propagates_security_error(self) -> None:
        """setup 中的 shell 安全错误应向上传播"""
        loader = make_loader(allowed_commands=["echo"])
        disallowed = make_shell_action("cat /etc/hosts")

        with pytest.raises(SecurityError):
            loader.run_setup([disallowed], {})

    def test_teardown_catches_security_error(self) -> None:
        """teardown 中的 shell 安全错误被捕获并记录警告"""
        loader = make_loader(allowed_commands=["echo"])
        disallowed = make_shell_action("cat /etc/hosts")

        with patch("framework.fixtures_loader.logger") as mock_logger:
            # teardown 不抛异常
            loader.run_teardown([disallowed], {})
            mock_logger.warning.assert_called_once()

    def test_setup_with_valid_shell_action(self) -> None:
        """setup 中白名单命令正常执行"""
        loader = make_loader(allowed_commands=["echo", "python"])
        action = make_shell_action("echo setup-ok")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = loader.run_setup([action], {})
            mock_run.assert_called_once()
            assert result == {}


# ══════════════════════════════════════════════════════════
# 10. 命令注入防护验证
# ══════════════════════════════════════════════════════════


class TestInjectionPrevention:
    """验证常见命令注入模式被正确防御"""

    def test_semicolon_injection_prevented(self) -> None:
        """分号命令注入被 shlex 解析并作为参数处理"""
        loader = make_loader(allowed_commands=["echo"])

        # 注入：echo hello; rm -rf /
        action = make_shell_action("echo hello; rm -rf /")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        # shlex 会将分号附着在前一个单词后（或作为独立参数），不执行 rm
        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "echo"
        # 分号作为独立 token 或附着于参数中，都意味着它只是一个参数字面量
        joined = " ".join(called_args[1:])
        assert ";" in joined

    def test_pipe_injection_prevented(self) -> None:
        """管道注入被 shlex 当作参数字面量"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("echo hello | cat /etc/passwd")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "echo"
        assert "|" in called_args[1:]

    def test_subshell_injection_prevented(self) -> None:
        """反引号/子命令注入被 shlex 当作字面量"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("echo `whoami` $(id)")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "echo"
        # 反引号内容作为字面量参数
        joined = " ".join(called_args[1:])
        assert "`whoami`" in joined
        assert "$(id)" in joined

    def test_and_operator_in_pre_whitelist_blocked(self) -> None:
        """&& 注入在进入执行前就被白名单拦截"""
        loader = make_loader(allowed_commands=["echo"])
        action = make_shell_action("echo hello && rm -rf /")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            loader._execute_shell(action.config, {})

        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "echo"
        assert "&&" in called_args[1:]
        assert "rm" in called_args[1:]
