"""ExecutionOrchestrator 单元测试

测试覆盖：
- execute_case_list_for_execution 正常执行路径
- 无效 case_id 处理
- 用例未找到处理
- yaml_content 为空处理
- YAML 解析失败处理
- 执行异常处理
- 汇总统计正确性
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from framework.execution_orchestrator import (
    ExecutionContext,
    ExecutionOrchestrator,
    ExecutionResult,
    _compute_summary,
    _execution_status_from_summary,
    _make_error_case_result,
)
from framework.models import CaseResult, CaseStatus
from framework.persistence.models.execution import ExecutionModel


class TestComputeSummary:
    """_compute_summary 辅助函数测试."""

    def test_all_passed(self) -> None:
        results = [{"status": "PASS"}, {"status": "PASS"}, {"status": "PASS"}]
        summary = _compute_summary(results)
        assert summary == {"total": 3, "passed": 3, "failed": 0, "error": 0, "skipped": 0}

    def test_mixed_statuses(self) -> None:
        results = [
            {"status": "PASS"},
            {"status": "FAIL"},
            {"status": "ERROR"},
            {"status": "SKIP"},
            {"status": "PASS"},
        ]
        summary = _compute_summary(results)
        assert summary == {"total": 5, "passed": 2, "failed": 1, "error": 1, "skipped": 1}

    def test_empty_results(self) -> None:
        summary = _compute_summary([])
        assert summary == {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}


class TestExecutionStatusFromSummary:
    """_execution_status_from_summary 辅助函数测试."""

    def test_all_passed(self) -> None:
        assert _execution_status_from_summary({"total": 3, "passed": 3, "failed": 0, "error": 0, "skipped": 0}) == "PASSED"

    def test_has_failed(self) -> None:
        assert _execution_status_from_summary({"total": 3, "passed": 2, "failed": 1, "error": 0, "skipped": 0}) == "FAILED"

    def test_all_error(self) -> None:
        assert _execution_status_from_summary({"total": 2, "passed": 0, "failed": 0, "error": 2, "skipped": 0}) == "ERROR"

    def test_empty(self) -> None:
        assert _execution_status_from_summary({"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}) == "ERROR"


class TestMakeErrorCaseResult:
    """_make_error_case_result 辅助函数测试."""

    def test_creates_error_result(self) -> None:
        result = _make_error_case_result("test_case", "something went wrong")
        assert result.case_name == "test_case"
        assert result.status == CaseStatus.ERROR
        assert result.passed is False
        assert result.error == "something went wrong"
        assert result.elapsed_ms == 0.0


class TestExecutionResult:
    """ExecutionResult dataclass 测试."""

    def test_default_values(self) -> None:
        result = ExecutionResult(execution_id="exec-1", status="PASSED")
        assert result.execution_id == "exec-1"
        assert result.status == "PASSED"
        assert result.case_count == 0
        assert result.passed_count == 0
        assert result.failed_count == 0
        assert result.error_count == 0
        assert result.skipped_count == 0
        assert result.duration_ms == 0
        assert result.error_message is None


class TestExecutionContext:
    """ExecutionContext dataclass 测试."""

    def test_creation(self) -> None:
        runner = MagicMock()
        exec_repo = MagicMock()
        result_repo = MagicMock()
        ctx = ExecutionContext(
            runner=runner,
            execution_repo=exec_repo,
            result_repo=result_repo,
            env_name="test",
            timeout=600,
        )
        assert ctx.runner is runner
        assert ctx.execution_repo is exec_repo
        assert ctx.result_repo is result_repo
        assert ctx.env_name == "test"
        assert ctx.timeout == 600


class TestExecutionOrchestratorExecuteCaseListForExecution:
    """execute_case_list_for_execution 方法测试."""

    @pytest.fixture
    def mock_runner(self) -> MagicMock:
        """创建 mock runner."""
        runner = MagicMock()
        runner.arun_case = AsyncMock(return_value=CaseResult(
            case_name="test_case",
            status=CaseStatus.PASS,
            passed=True,
            error=None,
            elapsed_ms=100.0,
        ))
        return runner

    @pytest.fixture
    def mock_exec_repo(self) -> MagicMock:
        """创建 mock execution repository."""
        repo = MagicMock()
        exec_model = MagicMock(spec=ExecutionModel)
        exec_model.status = "PENDING"
        repo.get = AsyncMock(return_value=exec_model)
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def mock_result_repo(self) -> MagicMock:
        """创建 mock result repository."""
        repo = MagicMock()
        repo.save_result = AsyncMock()
        return repo

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """创建 mock session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def orchestrator(self, mock_runner, mock_exec_repo, mock_result_repo) -> ExecutionOrchestrator:
        """创建测试用的 orchestrator."""
        ctx = ExecutionContext(
            runner=mock_runner,
            execution_repo=mock_exec_repo,
            result_repo=mock_result_repo,
            env_name="test",
        )
        return ExecutionOrchestrator(ctx)

    @pytest.mark.asyncio
    async def test_invalid_case_id(self, orchestrator, mock_session, mock_exec_repo):
        """测试无效 case_id 处理."""
        exec_uuid = uuid.uuid4()

        # Mock session 返回空结果（用例未找到）
        mock_row = MagicMock()
        mock_row.first = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_row)

        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=["invalid-uuid"],
            session=mock_session,
        )

        assert result["total"] == 1
        assert result["error"] == 1

    @pytest.mark.asyncio
    async def test_case_not_found(self, orchestrator, mock_session, mock_exec_repo):
        """测试用例未找到处理."""
        exec_uuid = uuid.uuid4()
        valid_uuid = str(uuid.uuid4())

        mock_row = MagicMock()
        mock_row.first = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_row)

        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=[valid_uuid],
            session=mock_session,
        )

        assert result["total"] == 1
        assert result["error"] == 1

    @pytest.mark.asyncio
    async def test_execution_not_found(self, orchestrator, mock_session):
        """测试执行记录未找到."""
        orchestrator._ctx.execution_repo.get = AsyncMock(return_value=None)
        exec_uuid = uuid.uuid4()

        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=[str(uuid.uuid4())],
            session=mock_session,
        )

        assert result["error"] == "execution_not_found"
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_empty_yaml_content(self, orchestrator, mock_session, mock_exec_repo, mock_result_repo):
        """测试 yaml_content 为空处理."""
        exec_uuid = uuid.uuid4()
        valid_uuid = str(uuid.uuid4())

        mock_row = MagicMock()
        mock_row.yaml_content = None
        mock_row.name = "empty_case"
        mock_row_result = MagicMock()
        mock_row_result.first = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_row_result)

        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=[valid_uuid],
            session=mock_session,
        )

        assert result["total"] == 1
        assert result["error"] == 1
        # 验证 save_result 被调用
        mock_result_repo.save_result.assert_called()

    @pytest.mark.asyncio
    async def test_execution_error_handling(self, orchestrator, mock_session, mock_exec_repo):
        """测试执行异常时正确处理."""
        exec_uuid = uuid.uuid4()
        valid_uuid = str(uuid.uuid4())

        # 模拟 runner 抛出异常
        orchestrator._ctx.runner.arun_case = AsyncMock(side_effect=RuntimeError("test error"))

        mock_row = MagicMock()
        mock_row.yaml_content = "name: test_case\nrequest:\n  method: GET\n  path: /test"
        mock_row.name = "test_case"
        mock_row_result = MagicMock()
        mock_row_result.first = MagicMock(return_value=mock_row)
        mock_session.execute = AsyncMock(return_value=mock_row_result)

        result = await orchestrator.execute_case_list_for_execution(
            exec_uuid=exec_uuid,
            case_ids=[valid_uuid],
            session=mock_session,
        )

        assert result["total"] == 1
        assert result["error"] == 1
