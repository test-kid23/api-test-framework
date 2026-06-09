"""Fixture 加载器 — 执行 setup/teardown 动作

Shell 动作安全策略：
- 必须配置命令白名单（config.yaml → fixtures.allowed_shell_commands），
  空列表表示拒绝所有 shell 命令。
- 使用 shlex.split() 解析命令参数，避免命令注入。
- 默认超时 30 秒，可配置。
- 可选沙箱模式：检查敏感路径引用。
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from typing import Any

from framework.exceptions import SecurityError
from framework.models import FixtureAction
from framework.utils.logger import Logger

logger = Logger.get("fixture")

# 敏感路径列表（Unix & Windows）
_SENSITIVE_PATHS: list[str] = [
    # Unix/Linux
    "/etc",
    "/root",
    "/boot",
    "/proc",
    "/sys",
    "/dev",
    "/var/log",
    "/var/spool/cron",
    "/var/spool/at",
    # Windows
    "C:\\Windows",
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
]


class FixtureLoader:
    """Fixture 加载器 — 执行 setup/teardown 中的动作

    Attributes:
        _http_client: HTTP 客户端（api_call 动作使用）。
        _db_executor: 数据库执行器（db_execute 动作使用）。
        _template: 模板引擎。
        _extractor: 变量提取器。
        _fixtures_config: fixtures 安全配置（白名单、沙箱开关等）。
    """

    def __init__(
        self,
        http_client: Any = None,  # HttpClient
        db_executor: Any = None,  # DBExecutor
        template_engine: Any = None,  # TemplateEngine
        extractor: Any = None,  # Extractor
        fixtures_config: dict[str, Any] | None = None,
        mock_store: Any = None,  # MockRuleStore
    ) -> None:
        self._http_client = http_client
        self._db_executor = db_executor
        self._template = template_engine
        self._extractor = extractor
        self._fixtures_config: dict[str, Any] = fixtures_config or {}
        self._mock_store = mock_store

    def run_setup(
        self,
        actions: list[FixtureAction],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 setup 动作，返回提取的变量"""
        extracted: dict[str, Any] = {}
        for i, action in enumerate(actions):
            logger.info("setup_action_starting", index=i + 1, total=len(actions),
                        action_type=action.action_type)
            try:
                result = self._execute_action(action, variables)
                if result:
                    extracted.update(result)
                    variables.update(result)
            except Exception as e:
                logger.error("setup_action_failed", action_type=action.action_type, error=str(e))
                raise
        return extracted

    def run_teardown(
        self,
        actions: list[FixtureAction],
        variables: dict[str, Any],
    ) -> None:
        """执行 teardown 动作"""
        for i, action in enumerate(actions):
            logger.info("teardown_action_starting", index=i + 1, total=len(actions),
                        action_type=action.action_type)
            try:
                self._execute_action(action, variables)
            except Exception as e:
                logger.warning("teardown_action_failed", action_type=action.action_type, error=str(e))

    def _execute_action(
        self,
        action: FixtureAction,
        variables: dict[str, Any],
    ) -> dict[str, Any] | None:
        """执行单个动作"""
        config = action.config

        if action.action_type == "api_call":
            return self._execute_api_call(config, variables)
        elif action.action_type == "db_execute":
            return self._execute_db(config, variables)
        elif action.action_type == "wait":
            return self._execute_wait(config)
        elif action.action_type == "shell":
            self._execute_shell(config, variables)
            return None
        elif action.action_type == "mock_setup":
            return self._execute_mock_setup(config, variables)
        elif action.action_type == "mock_teardown":
            self._execute_mock_teardown(config)
            return None
        else:
            logger.warning("unknown_fixture_action", action_type=action.action_type)
            return None

    def _execute_api_call(
        self,
        config: dict[str, Any],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 API 调用"""
        if self._http_client is None:
            raise RuntimeError("HttpClient 未初始化，无法执行 API 调用")

        from framework.models import HttpMethod, HttpRequest

        method_str = config.get("method", "GET").upper()
        method = HttpMethod(method_str)
        path = config.get("path", "")

        # 模板替换
        if self._template:
            path = self._template.render(path, variables)

        req = HttpRequest(
            method=method,
            path=path,
            headers=config.get("headers", {}),
            body=config.get("body"),
            timeout=config.get("timeout"),
        )

        response = self._http_client.request(req, variables)

        # 提取变量
        extracted: dict[str, Any] = {}
        extract_config = config.get("extract", {})
        if extract_config and self._extractor:
            from framework.models import ExtractItem

            extracts = [
                ExtractItem(var_name=k, source=v, source_type="jsonpath")
                for k, v in extract_config.items()
                if isinstance(v, str)
            ]
            extracted = self._extractor.extract(response, extracts, variables)

        return extracted

    def _execute_db(
        self,
        config: dict[str, Any],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """执行数据库操作"""
        if self._db_executor is None:
            logger.warning("db_skipped", reason="DBExecutor not initialized")
            return {}

        from framework.models import DBAction, ExtractItem

        # 模板替换
        sql = config.get("sql", "")
        if self._template:
            sql = self._template.render(sql, variables)

        extracts = []
        extract_config = config.get("extract", {})
        for var_name, col_name in extract_config.items():
            extracts.append(
                ExtractItem(var_name=var_name, source=col_name, source_type="sql_column")
            )

        action = DBAction(
            connection=config.get("connection", "main_db"),
            sql=sql,
            params=config.get("params", {}),
            extract=extracts,
            fetch_one=config.get("fetch_one", True),
        )

        return self._db_executor.execute_and_extract(action, variables)  # type: ignore[no-any-return]

    @staticmethod
    def _execute_wait(config: dict[str, Any]) -> None:
        """等待指定秒数"""
        seconds = config.get("seconds", 1)
        logger.debug("waiting", seconds=seconds)
        time.sleep(seconds)
        return None

    def _execute_shell(
        self,
        config: dict[str, Any],
        variables: dict[str, Any],
    ) -> None:
        """执行 shell 命令（安全加固版）

        安全检查流程：
        1. 从配置中读取命令白名单。
        2. 使用 shlex.split() 安全解析命令与参数。
        3. 检查命令名是否在白名单中。
        4. （可选）沙箱模式：检查参数中是否引用敏感路径。
        5. 以 subprocess.run 执行，默认超时 30 秒。

        Args:
            config: 动作配置，需包含 "command" 字段，可选 "timeout" 字段。
            variables: 当前变量上下文。

        Raises:
            SecurityError: 命令不在白名单中、引用了敏感路径或命令解析失败。
            subprocess.TimeoutExpired: 执行超时。
        """
        command: str = config.get("command", "")
        if not command:
            return

        logger.debug(f"执行 shell: {command}")

        # ── 1. 获取白名单配置 ──
        allowed_commands: list[str] = self._fixtures_config.get("allowed_shell_commands", [])
        if not allowed_commands:
            raise SecurityError(
                f"Shell command '{command}' is not in the allowed list (whitelist is empty)",
                command=command,
            )

        # ── 2. 安全解析命令与参数 ──
        try:
            args: list[str] = shlex.split(command)
        except ValueError as e:
            raise SecurityError(
                f"Failed to parse shell command '{command}': {e}",
                command=command,
            ) from e

        if not args:
            return

        cmd_name: str = args[0]
        cmd_basename: str = os.path.basename(cmd_name)

        # ── 3. 白名单检查（支持全路径与 basename 匹配）──
        cmd_matched: bool = cmd_name in allowed_commands or cmd_basename in allowed_commands
        if not cmd_matched:
            raise SecurityError(
                f"Shell command '{cmd_name}' is not in the allowed list",
                command=cmd_name,
            )

        # ── 4. 沙箱模式：敏感路径检查 ──
        sandbox_enabled: bool = self._fixtures_config.get("shell_sandbox", False)
        if sandbox_enabled:
            self._check_sensitive_paths(args)

        # ── 5. 执行命令（带超时） ──
        timeout: int = config.get("timeout", 30)
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                logger.warning("shell_nonzero_exit", returncode=result.returncode, stderr=result.stderr.strip())
            else:
                logger.debug("shell_output", stdout=result.stdout[:500])
        except subprocess.TimeoutExpired:
            logger.error(f"Shell 命令超时 ({timeout}s): {command}")
            raise
        except FileNotFoundError:
            logger.error(f"Shell 命令未找到: {cmd_name}")
            raise SecurityError(
                f"Shell command '{cmd_name}' not found on system",
                command=cmd_name,
            ) from None
        except PermissionError as e:
            logger.error(f"Shell 命令权限被拒绝: {cmd_name}")
            raise SecurityError(
                f"Permission denied for shell command '{cmd_name}'",
                command=cmd_name,
            ) from e
        except OSError as e:
            logger.error(f"Shell 命令执行失败 (OSError): {e}")
            raise SecurityError(
                f"Shell command '{cmd_name}' failed with OS error: {e}",
                command=cmd_name,
            ) from e

    def _execute_mock_setup(
        self,
        config: dict[str, Any],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """执行 mock_setup — 注册 Mock 规则

        config 格式:
            rules:
              - url_pattern: "/api/users/*"
                method: POST
                status_code: 201
                response_body:
                  id: 1
                  name: "created_user"
              - url_pattern: "/api/users/999"
                method: GET
                status_code: 404
                response_body:
                  error: "Not Found"

        Args:
            config: 动作配置，需包含 "rules" 列表。
            variables: 当前变量上下文。

        Returns:
            包含 _mock_rule_ids 的字典（供 teardown 使用）。
        """
        if self._mock_store is None:
            logger.warning("mock_store_not_available", hint="请确保 Mock 模块已初始化")
            return {}

        rules: list[dict[str, Any]] = config.get("rules", [])
        if not rules:
            logger.debug("mock_setup_no_rules")
            return {}

        registered_ids: list[str] = []
        for rule_config in rules:
            # 模板替换
            url_pattern = rule_config.get("url_pattern", "/*")
            if self._template:
                url_pattern = self._template.render(url_pattern, variables)

            resp_body = rule_config.get("response_body")
            if self._template and isinstance(resp_body, (str, dict)):
                resp_body = self._template.render_value(resp_body, variables)

            rule = self._mock_store.register(
                url_pattern=url_pattern,
                method=rule_config.get("method", "ANY"),
                status_code=rule_config.get("status_code", 200),
                response_body=resp_body,
                response_headers=rule_config.get("response_headers"),
                description=rule_config.get("description", ""),
                priority=rule_config.get("priority", 0),
                delay_ms=rule_config.get("delay_ms", 0),
            )
            registered_ids.append(rule.id)
            logger.info("mock_setup_rule_registered", rule_id=rule.id, url_pattern=url_pattern)

        # 将注册的 rule IDs 存入变量，供 teardown 使用
        return {"_mock_rule_ids": registered_ids}

    def _execute_mock_teardown(self, config: dict[str, Any]) -> None:
        """执行 mock_teardown — 清理 Mock 规则

        根据之前 mock_setup 注册的 rule IDs 删除规则。
        若未指定 IDs 则清空全部规则。

        Args:
            config: 动作配置，可选 "rule_ids" 列表。
        """
        if self._mock_store is None:
            return

        rule_ids: list[str] | None = config.get("rule_ids")
        if rule_ids:
            count = self._mock_store.delete_by_ids(rule_ids)
            logger.info("mock_teardown_cleaned", deleted=count)
        else:
            count = self._mock_store.clear()
            logger.info("mock_teardown_all_cleared", deleted=count)

    # ── 辅助方法 ──

    @staticmethod
    def _check_sensitive_paths(args: list[str]) -> None:
        """检查命令参数中是否引用了敏感路径。

        如果任一参数包含敏感路径前缀，抛出 SecurityError。

        Args:
            args: shlex 解析后的参数列表。

        Raises:
            SecurityError: 参数引用了敏感路径。
        """
        for arg in args:
            for sensitive in _SENSITIVE_PATHS:
                if sensitive.lower() in arg.lower():
                    raise SecurityError(
                        f"Shell command references sensitive path '{sensitive}' in argument: {arg}",
                        command=args[0] if args else "",
                    )
