"""统一执行编排器

消除 worker/tasks.py 和 api/routers/executions.py 中的重复执行逻辑。
所有执行入口（Celery Worker、本地模式、API 触发）统一调用本编排器。

Suite Setup 自动预解析（T2-8）：
- 单用例/批量执行时，自动查找用例所属套件的 setup 并执行
- 可缓存 setup 结果（如 token），避免重复登录
- 确保 {{access_token}} 等变量在单独执行时可用

Attributes:
    ExecutionContext: 执行上下文，封装 runner + repos + 环境配置
    ExecutionResult: 统一执行结果
    ExecutionOrchestrator: 执行编排器
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from framework.models import CaseResult, CaseStatus, FixtureAction
from framework.persistence.models.execution import ExecutionModel
from framework.persistence.models.report import ReportModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.execution_repo import (
    ExecutionRepository,
    ExecutionResultRepository,
)
from framework.utils.logger import Logger

if TYPE_CHECKING:
    from framework.runner import TestRunner

_log = Logger.get("execution_orchestrator")

# ── Suite Setup 缓存 ─────────────────────────────────────

# 默认 token/变量缓存 TTL（秒）
_DEFAULT_SETUP_CACHE_TTL = 300


@dataclass
class _CachedSetup:
    """缓存的套件 setup 结果.

    Attributes:
        variables: setup 提取的变量字典
        expires_at: 过期时间戳（epoch 秒）
    """

    variables: dict[str, Any]
    expires_at: float


# 进程级缓存：{(suite_name, env_name): _CachedSetup}
_suite_setup_cache: dict[tuple[str, str], _CachedSetup] = {}
_suite_setup_cache_lock = asyncio.Lock()


@dataclass
class ExecutionContext:
    """执行上下文，封装一次执行所需的全部依赖.

    Attributes:
        runner: 测试执行引擎
        execution_repo: 执行记录 Repository
        result_repo: 执行结果 Repository
        env_name: 环境名称
        timeout: 用例超时时间（秒）
        trace_id: 追踪 ID（可选）
    """

    runner: TestRunner
    execution_repo: ExecutionRepository
    result_repo: ExecutionResultRepository
    env_name: str = "default"
    timeout: int = 1800
    trace_id: str | None = None


@dataclass
class ExecutionResult:
    """统一执行结果.

    Attributes:
        execution_id: 执行记录 ID
        status: 执行状态 ("PASSED" | "FAILED" | "ERROR" | "TIMEOUT")
        duration_ms: 总耗时（毫秒）
        case_count: 用例总数
        passed_count: 通过数
        failed_count: 失败数
        error_count: 错误数
        skipped_count: 跳过数
        error_message: 错误信息（可选）
    """

    execution_id: str
    status: str
    duration_ms: int = 0
    case_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    error_message: str | None = None


def _compute_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """根据结果列表计算汇总统计."""
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    error_count = sum(1 for r in results if r.get("status") == "ERROR")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "error": error_count,
        "skipped": skipped,
    }


def _execution_status_from_summary(summary: dict[str, int]) -> str:
    """根据汇总数据推断执行状态."""
    if summary["total"] == 0:
        return "ERROR"
    if summary["error"] == summary["total"]:
        return "ERROR"
    if summary["passed"] == summary["total"]:
        return "PASSED"
    return "FAILED"


def _make_error_case_result(case_name: str, error_msg: str) -> CaseResult:
    """创建表示错误的伪 CaseResult 对象."""
    return CaseResult(
        case_name=case_name,
        status=CaseStatus.ERROR,
        passed=False,
        error=error_msg,
        elapsed_ms=0.0,
    )


class ExecutionOrchestrator:
    """统一执行编排器.

    消除 worker/tasks.py 和 api/routers/executions.py 中的重复代码。
    所有执行入口（Celery Worker、本地模式、API 触发）统一调用本编排器。

    支持 Suite Setup 自动预解析：
    - 执行单用例/批量用例时，自动查找所属套件的 setup 并执行
    - setup 结果（如 access_token）缓存 TTL，避免重复登录

    Attributes:
        ctx: 执行上下文，封装 runner + repos + 环境配置
    """

    def __init__(self, ctx: ExecutionContext) -> None:
        """初始化编排器.

        Args:
            ctx: 执行上下文
        """
        self._ctx = ctx

    # ── 变量初始化 ──────────────────────────────────────

    def _init_suite_variables(self) -> dict[str, Any]:
        """构建初始套件级变量（包含环境配置、base_url 等）.

        与 runner._build_suite_variables() 等价，但不依赖 TestSuite 对象。
        确保 {{env.xxx}} 模板变量可解析。

        Returns:
            初始 suite_variables 字典。
        """
        runner = self._ctx.runner
        env_config = runner._env  # EnvConfig
        env_vars: dict[str, Any] = {**env_config.variables}
        env_vars["base_url"] = env_config.base_url
        env_vars["ws_url"] = env_config.ws_url
        return {"env": env_vars, "base_url": env_config.base_url}

    # ── Suite Setup 自动预解析（T2-8）──────────────────

    def _parse_suite_setup_from_yaml(
        self, yaml_content: str, suite_name: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """从套件 YAML 中提取 setup 动作列表和 variables.

        解析 YAML 顶层 `setup` 和 `variables` 块，
        将 raw setup 转换为 FixtureAction 可识别的 dict 列表。

        Args:
            yaml_content: 套件级 YAML 内容（含 setup/variables 顶层块）
            suite_name: 套件名称（用于日志）

        Returns:
            (setup_actions_raw, suite_variables) 元组。
            setup_actions_raw 是可直接传给 fixture_loader 的 dict 列表。
        """
        raw = yaml.safe_load(yaml_content)
        if not isinstance(raw, dict):
            return [], {}

        suite_vars: dict[str, Any] = {}
        raw_vars = raw.get("variables")
        if isinstance(raw_vars, dict):
            suite_vars = {**raw_vars}

        raw_setup = raw.get("setup")
        if not isinstance(raw_setup, list):
            return [], suite_vars

        # 将 YAML setup 列表转为 FixtureAction 可识别的 dict 格式
        actions: list[dict[str, Any]] = []
        for item in raw_setup:
            if not isinstance(item, dict):
                continue
            for action_type, config in item.items():
                if action_type in ("api_call", "db_execute", "wait", "shell",
                                   "mock_setup", "mock_teardown"):
                    actions.append({"action_type": action_type, "config": config or {}})

        _log.info(
            "suite_setup_parsed",
            suite_name=suite_name,
            action_count=len(actions),
            var_count=len(suite_vars),
        )
        return actions, suite_vars

    async def _resolve_and_run_suite_setups(
        self,
        case_ids: list[str],
        session: AsyncSession,
        suite_variables: dict[str, Any],
    ) -> None:
        """解析并执行所有涉及套件的 setup，结果合并到 suite_variables.

        流程：
        1. 收集所有 case 的 suite_name
        2. 对每个唯一 suite_name：
           a. 查缓存（suite_name + env_name）
           b. 缓存命中 → 直接合并变量
           c. 缓存未命中 → 查找 suite → 解析 setup → 执行 → 写缓存 → 合并变量

        Args:
            case_ids: 用例 ID 列表
            session: 数据库会话
            suite_variables: 套件变量字典（会被原地修改）
        """
        # 1. 收集 suite_names
        suite_names: set[str] = set()
        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                continue
            row = (
                await session.execute(
                    select(TestCaseModel.suite_name).where(
                        TestCaseModel.id == case_uuid
                    )
                )
            ).first()
            if row and row.suite_name:
                suite_names.add(row.suite_name)

        if not suite_names:
            _log.debug("no_suite_names_found", case_count=len(case_ids))
            return

        env_name = self._ctx.env_name

        for suite_name in suite_names:
            cache_key = (suite_name, env_name)

            # 2a. 查缓存
            async with _suite_setup_cache_lock:
                cached = _suite_setup_cache.get(cache_key)
                if cached is not None and cached.expires_at > time.time():
                    _log.info(
                        "suite_setup_cache_hit",
                        suite_name=suite_name,
                        env=env_name,
                        var_count=len(cached.variables),
                    )
                    suite_variables.update(cached.variables)
                    continue

            # 2b. 缓存未命中 — 查找套件
            suite_row = (
                await session.execute(
                    select(TestSuiteModel).where(TestSuiteModel.name == suite_name)
                )
            ).scalar_one_or_none()

            # 解析 setup：优先从 suite cache 中的 config JSON，
            # 其次尝试从套件关联用例的 yaml_content 中提取
            setup_actions: list[dict[str, Any]] = []
            suite_extra_vars: dict[str, Any] = {}

            if suite_row is not None and suite_row.config:
                try:
                    suite_config = json.loads(suite_row.config)
                    raw_setup = suite_config.get("setup")
                    if isinstance(raw_setup, list):
                        for item in raw_setup:
                            if isinstance(item, dict):
                                for action_type, cfg in item.items():
                                    if action_type in (
                                        "api_call", "db_execute", "wait", "shell",
                                        "mock_setup", "mock_teardown",
                                    ):
                                        setup_actions.append(
                                            {"action_type": action_type, "config": cfg or {}}
                                        )
                    raw_vars = suite_config.get("variables")
                    if isinstance(raw_vars, dict):
                        suite_extra_vars = {**raw_vars}
                except (json.JSONDecodeError, TypeError):
                    _log.debug(
                        "suite_config_parse_failed",
                        suite_name=suite_name,
                        fallback="yaml_content",
                    )

            # 若 config 中没有 setup，从套件关联用例的 yaml_content 提取
            if not setup_actions:
                if suite_row is not None:
                    case_row = (
                        await session.execute(
                            select(TestCaseModel.yaml_content).where(
                                TestCaseModel.suite_name == suite_name
                            ).limit(1)
                        )
                    ).first()
                    if case_row and case_row.yaml_content:
                        try:
                            raw = yaml.safe_load(case_row.yaml_content)
                            if isinstance(raw, dict):
                                setup_actions, suite_extra_vars_cl = (
                                    self._parse_suite_setup_from_yaml(
                                        case_row.yaml_content, suite_name
                                    )
                                )
                                if not suite_extra_vars:
                                    suite_extra_vars = suite_extra_vars_cl
                        except yaml.YAMLError:
                            _log.warning(
                                "suite_yaml_parse_failed",
                                suite_name=suite_name,
                            )
                else:
                    # 无套件记录时，直接从当前执行用例的 yaml_content 提取 setup
                    _log.debug(
                        "no_suite_row_fallback_to_case_yaml",
                        suite_name=suite_name,
                    )
                    for cid in case_ids:
                        try:
                            case_uuid = uuid.UUID(cid)
                        except ValueError:
                            continue
                        c_row = (
                            await session.execute(
                                select(TestCaseModel.yaml_content).where(
                                    TestCaseModel.id == case_uuid
                                )
                            )
                        ).first()
                        if c_row and c_row.yaml_content:
                            try:
                                raw = yaml.safe_load(c_row.yaml_content)
                                if isinstance(raw, dict):
                                    actions, vars_cl = (
                                        self._parse_suite_setup_from_yaml(
                                            c_row.yaml_content, suite_name
                                        )
                                    )
                                    if actions:
                                        setup_actions = actions
                                    if not suite_extra_vars and vars_cl:
                                        suite_extra_vars = vars_cl
                                    if setup_actions:
                                        break
                            except yaml.YAMLError:
                                continue

            # 合并套件级 variables
            if suite_extra_vars:
                suite_variables.update(suite_extra_vars)

            # 2c. 执行 setup
            if not setup_actions:
                _log.debug("no_setup_actions", suite_name=suite_name)
                # 即使无 setup 也缓存（避免重复查询）
                async with _suite_setup_cache_lock:
                    _suite_setup_cache[cache_key] = _CachedSetup(
                        variables={},
                        expires_at=time.time() + _DEFAULT_SETUP_CACHE_TTL,
                    )
                continue

            try:
                # 将 raw dict 转换为 FixtureAction
                actions = [
                    FixtureAction(
                        action_type=a["action_type"],
                        config=a.get("config", {}),
                    )
                    for a in setup_actions
                ]

                extracted = self._ctx.runner._fixture_loader.run_setup(
                    actions, suite_variables
                )
                suite_variables.update(extracted)

                _log.info(
                    "suite_setup_executed",
                    suite_name=suite_name,
                    env=env_name,
                    extracted_keys=list(extracted.keys()),
                )

                # 2d. 写缓存
                async with _suite_setup_cache_lock:
                    _suite_setup_cache[cache_key] = _CachedSetup(
                        variables={**extracted},
                        expires_at=time.time() + _DEFAULT_SETUP_CACHE_TTL,
                    )

            except Exception as e:
                _log.error(
                    "suite_setup_execution_failed",
                    suite_name=suite_name,
                    env=env_name,
                    error=str(e),
                )
                # 标记为已尝试（避免无限重试），但缓存空结果
                async with _suite_setup_cache_lock:
                    _suite_setup_cache[cache_key] = _CachedSetup(
                        variables={},
                        expires_at=time.time() + _DEFAULT_SETUP_CACHE_TTL,
                    )

    async def execute_case_list(
        self,
        case_ids: list[str],
        session: AsyncSession,
        variables: dict[str, object] | None = None,
    ) -> ExecutionResult:
        """批量执行用例列表.

        从数据库加载每个用例的 YAML 内容，解析后依次调用 runner.arun_case() 执行，
        结果持久化到 DB，最后汇总统计并更新执行记录状态和创建报告。

        自动预解析套件级 setup：在执行第一个用例前，查找用例所属套件
        的 setup 并执行，确保 {{access_token}} 等变量可用。

        Args:
            case_ids: 用例 ID 列表
            session: 数据库会话（用于加载用例和持久化结果）
            variables: 额外变量注入（未使用，保留扩展性）

        Returns:
            ExecutionResult: 聚合执行结果
        """
        exec_uuid: uuid.UUID | None = None

        start_time = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []
        suite_variables: dict[str, Any] = self._init_suite_variables()

        # ── 预解析套件级 setup（T2-8）──
        await self._resolve_and_run_suite_setups(case_ids, session, suite_variables)

        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id", case_id=cid)
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": f"用例 ID 格式无效: {cid}",
                    "elapsed_ms": 0,
                })
                continue

            case_row_result = await session.execute(
                select(TestCaseModel.yaml_content, TestCaseModel.name).where(
                    TestCaseModel.id == case_uuid
                )
            )
            case_row = case_row_result.first()
            if case_row is None:
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": "用例未找到",
                    "elapsed_ms": 0,
                })
                continue

            yaml_content = case_row.yaml_content
            case_name = case_row.name

            if not yaml_content:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(case_name, "yaml_content 为空"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": "yaml_content 为空",
                    "elapsed_ms": 0,
                })
                continue

            try:
                test_case = self._parse_yaml_case(yaml_content)
            except yaml.YAMLError as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(case_name, f"YAML 解析失败: {e}"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": f"YAML 解析失败: {e}",
                    "elapsed_ms": 0,
                })
                continue

            try:
                case_result = await self._ctx.runner.arun_case(test_case, suite_variables)
            except Exception as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                    case_result=_make_error_case_result(test_case.name, str(e)),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": test_case.name,
                    "status": "ERROR",
                    "error": str(e),
                    "elapsed_ms": 0,
                })
                continue

            # 将提取的变量传递给后续用例（与 runner.run_suite() 行为一致）
            if case_result.extracted_vars:
                suite_variables.update(case_result.extracted_vars)

            await self._ctx.result_repo.save_result(
                execution_id=exec_uuid if exec_uuid else uuid.uuid4(),
                case_result=case_result,
                case_id=case_uuid,
            )

            results.append({
                "case_id": cid,
                "case_name": case_result.case_name,
                "status": case_result.status.value,
                "error": case_result.error,
                "elapsed_ms": round(case_result.elapsed_ms, 2),
            })

        # 汇总
        summary = _compute_summary(results)
        final_status = _execution_status_from_summary(summary)

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return ExecutionResult(
            execution_id="",
            status=final_status,
            duration_ms=duration_ms,
            case_count=summary["total"],
            passed_count=summary["passed"],
            failed_count=summary["failed"],
            error_count=summary["error"],
            skipped_count=summary["skipped"],
        )

    async def execute_single_case(
        self,
        case_id: str,
        session: AsyncSession,
        variables: dict[str, object] | None = None,
    ) -> ExecutionResult:
        """执行单个用例.

        Args:
            case_id: 用例 ID
            session: 数据库会话
            variables: 额外变量注入

        Returns:
            ExecutionResult: 统一执行结果
        """
        result = await self.execute_case_list([case_id], session, variables)
        return result

    async def execute_case_list_for_execution(
        self,
        exec_uuid: uuid.UUID,
        case_ids: list[str],
        session: AsyncSession,
    ) -> dict[str, Any]:
        """为指定执行记录批量执行用例列表（完整流程）.

        包含完整的执行生命周期管理：
        1. 更新执行状态为 RUNNING
        2. 预解析套件级 setup（自动获取 token 等认证变量）
        3. 依次执行所有用例
        4. 持久化结果
        5. 更新执行状态为终态
        6. 创建报告

        Args:
            exec_uuid: 执行记录 UUID
            case_ids: 用例 ID 列表
            session: 数据库会话

        Returns:
            执行摘要字典，包含 total/passed/failed/error/skipped 和 status
        """
        # 更新状态为 RUNNING
        exec_model = await self._ctx.execution_repo.get(exec_uuid)
        if exec_model is None:
            _log.error("execution_not_found", exec_id=str(exec_uuid))
            return {"error": "execution_not_found", "total": 0}

        exec_model.status = "RUNNING"
        exec_model.started_at = datetime.now(timezone.utc)
        await self._ctx.execution_repo.update(exec_model)

        results: list[dict[str, Any]] = []
        suite_variables: dict[str, Any] = self._init_suite_variables()

        # ── 预解析套件级 setup（T2-8）──
        await self._resolve_and_run_suite_setups(case_ids, session, suite_variables)

        for cid in case_ids:
            try:
                case_uuid = uuid.UUID(cid)
            except ValueError:
                _log.warning("invalid_case_id", case_id=cid)
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": f"用例 ID 格式无效: {cid}",
                    "elapsed_ms": 0,
                })
                continue

            case_row_result = await session.execute(
                select(TestCaseModel.yaml_content, TestCaseModel.name).where(
                    TestCaseModel.id == case_uuid
                )
            )
            case_row = case_row_result.first()
            if case_row is None:
                results.append({
                    "case_id": cid,
                    "case_name": "unknown",
                    "status": "ERROR",
                    "error": "用例未找到",
                    "elapsed_ms": 0,
                })
                continue

            yaml_content = case_row.yaml_content
            case_name = case_row.name

            if not yaml_content:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(case_name, "yaml_content 为空"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": "yaml_content 为空",
                    "elapsed_ms": 0,
                })
                continue

            try:
                test_case = self._parse_yaml_case(yaml_content)
            except yaml.YAMLError as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(case_name, f"YAML 解析失败: {e}"),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": case_name,
                    "status": "ERROR",
                    "error": f"YAML 解析失败: {e}",
                    "elapsed_ms": 0,
                })
                continue

            try:
                case_result = await self._ctx.runner.arun_case(test_case, suite_variables)
            except Exception as e:
                await self._ctx.result_repo.save_result(
                    execution_id=exec_uuid,
                    case_result=_make_error_case_result(test_case.name, str(e)),
                    case_id=case_uuid,
                )
                results.append({
                    "case_id": cid,
                    "case_name": test_case.name,
                    "status": "ERROR",
                    "error": str(e),
                    "elapsed_ms": 0,
                })
                continue

            # 将提取的变量传递给后续用例（与 runner.run_suite() 行为一致）
            if case_result.extracted_vars:
                suite_variables.update(case_result.extracted_vars)

            await self._ctx.result_repo.save_result(
                execution_id=exec_uuid,
                case_result=case_result,
                case_id=case_uuid,
            )

            results.append({
                "case_id": cid,
                "case_name": case_result.case_name,
                "status": case_result.status.value,
                "error": case_result.error,
                "elapsed_ms": round(case_result.elapsed_ms, 2),
            })

        # 汇总
        summary = _compute_summary(results)
        final_status = _execution_status_from_summary(summary)

        now = datetime.now(timezone.utc)
        exec_model = await self._ctx.execution_repo.get(exec_uuid)
        if exec_model is not None:
            exec_model.status = final_status
            exec_model.finished_at = now
            await self._ctx.execution_repo.update(exec_model)

        # 创建报告
        report = ReportModel(
            execution_id=exec_uuid,
            summary=json.dumps(summary, ensure_ascii=False),
            detail_data=json.dumps(results, ensure_ascii=False, default=str),
        )
        session.add(report)
        await session.commit()

        _log.info(
            "execution_completed",
            exec_id=str(exec_uuid),
            status=final_status,
            total=summary["total"],
            passed=summary["passed"],
        )

        return {
            "exec_id": str(exec_uuid),
            "status": final_status,
            **summary,
        }

    def _parse_yaml_case(self, yaml_content: str) -> Any:
        """解析 YAML 内容为 TestCase 对象.

        Args:
            yaml_content: YAML 格式的测试用例内容

        Returns:
            解析后的 TestCase 对象

        Raises:
            yaml.YAMLError: YAML 解析失败
            ValueError: 无法解析时抛出
        """
        from api.dependencies import parse_yaml_case

        return parse_yaml_case(yaml_content)


def build_orchestrator(
    runner: TestRunner,
    session: AsyncSession,
    env_name: str = "default",
) -> ExecutionOrchestrator:
    """构建 ExecutionOrchestrator 的工厂函数.

    Args:
        runner: 测试执行引擎
        session: 数据库会话
        env_name: 环境名称

    Returns:
        配置好的 ExecutionOrchestrator 实例
    """
    ctx = ExecutionContext(
        runner=runner,
        execution_repo=ExecutionRepository(session),
        result_repo=ExecutionResultRepository(session),
        env_name=env_name,
    )
    return ExecutionOrchestrator(ctx)
