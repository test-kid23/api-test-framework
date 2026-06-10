"""GrpcStepExecutor 单元测试

测试覆盖：
- supports() 方法：grpc_config 存在/不存在
- _render_config() 模板渲染
- 未安装 grpc 时的优雅降级
"""

from __future__ import annotations

import pytest

from framework.assertion import AssertionEngine
from framework.executors.grpc_executor import GrpcStepExecutor
from framework.models import GrpcConfig, TestCase
from framework.report.base import NoopReportAdapter
from framework.utils.template import TemplateEngine


@pytest.fixture
def executor() -> GrpcStepExecutor:
    """创建 GrpcStepExecutor 实例"""
    return GrpcStepExecutor(
        template_engine=TemplateEngine(),
        assertion_engine=AssertionEngine(),
        report_adapter=NoopReportAdapter(),
    )


@pytest.fixture
def grpc_case() -> TestCase:
    """创建包含 gRPC 配置的 TestCase"""
    return TestCase(
        name="test_grpc_case",
        description="gRPC 测试用例",
        tags=["grpc"],
        priority="P1",
        grpc_config=GrpcConfig(
            service="greet.Greeter",
            method="SayHello",
            proto_file="testcases/grpc/greet.proto",
            host="localhost:50051",
            body={"name": "Test", "greeting": "Hello"},
            timeout=10,
        ),
    )


@pytest.fixture
def http_case() -> TestCase:
    """创建 HTTP 用例（无 gRPC 配置）"""
    from framework.models import HttpMethod, HttpRequest

    return TestCase(
        name="test_http_case",
        request=HttpRequest(
            method=HttpMethod.GET,
            path="/api/test",
        ),
    )


class TestGrpcStepExecutorSupports:
    """测试 supports() 方法"""

    def test_supports_grpc_case(self, executor: GrpcStepExecutor, grpc_case: TestCase) -> None:
        """grpc_config 不为 None 时应返回 True"""
        assert executor.supports(grpc_case) is True

    def test_supports_http_case(self, executor: GrpcStepExecutor, http_case: TestCase) -> None:
        """无 grpc_config 时应返回 False"""
        assert executor.supports(http_case) is False

    def test_supports_empty_case(self, executor: GrpcStepExecutor) -> None:
        """空用例（无任何配置）"""
        case = TestCase(name="empty")
        assert executor.supports(case) is False


class TestGrpcStepExecutorRenderConfig:
    """测试 _render_config() 模板渲染"""

    def test_render_config_basic(self, executor: GrpcStepExecutor) -> None:
        """基本模板渲染：变量替换 host"""
        cfg = GrpcConfig(
            service="greet.Greeter",
            method="SayHello",
            host="{{grpc_host}}",
            body={"name": "{{user}}"},
        )
        rendered = executor._render_config(cfg, {"grpc_host": "localhost:50051", "user": "Alice"})
        assert rendered.host == "localhost:50051"
        assert rendered.body == {"name": "Alice"}

    def test_render_config_metadata(self, executor: GrpcStepExecutor) -> None:
        """模板渲染 metadata"""
        cfg = GrpcConfig(
            service="greet.Greeter",
            method="SayHello",
            host="localhost:50051",
            metadata={"authorization": "Bearer {{token}}"},
        )
        rendered = executor._render_config(cfg, {"token": "abc123"})
        assert rendered.metadata == {"authorization": "Bearer abc123"}


class TestGrpcStepExecutorErrorHandling:
    """测试错误处理"""

    def test_missing_proto_file(self, executor: GrpcStepExecutor) -> None:
        """proto_file 为空且未启用反射时抛出异常"""
        from framework.exceptions import GrpcProtoError

        cfg = GrpcConfig(
            service="greet.Greeter",
            method="SayHello",
            proto_file="",
            host="localhost:50051",
            reflection=False,
        )
        with pytest.raises(GrpcProtoError, match="proto_file 未指定"):
            executor._resolve_service(cfg)

    def test_proto_file_not_found(self, executor: GrpcStepExecutor) -> None:
        """proto 文件不存在时抛出异常"""
        from framework.exceptions import GrpcProtoError

        cfg = GrpcConfig(
            service="greet.Greeter",
            method="SayHello",
            proto_file="/nonexistent/service.proto",
            host="localhost:50051",
        )
        with pytest.raises(GrpcProtoError, match="proto 文件不存在"):
            executor._resolve_service(cfg)


class TestGrpcStepExecutorToAssertable:
    """测试 _to_assertable() 结果转换"""

    def test_to_assertable_success(self, executor: GrpcStepExecutor) -> None:
        """成功的 gRPC 结果转换"""
        from framework.models import GrpcResult

        result = GrpcResult(
            service="greet.Greeter",
            method="SayHello",
            host="localhost:50051",
            request_body={"name": "Test"},
            response_body={"message": "Hello, Test!"},
            elapsed_ms=12.5,
            status_code=0,  # OK
            status_detail="",
            metadata={"content-type": "application/grpc"},
            success=True,
        )
        assertable = executor._to_assertable(result)
        assert assertable.status_code == 200
        assert assertable.body == {"message": "Hello, Test!"}
        assert assertable.elapsed_ms == 12.5

    def test_to_assertable_error(self, executor: GrpcStepExecutor) -> None:
        """失败的 gRPC 结果转换"""
        from framework.models import GrpcResult

        result = GrpcResult(
            service="greet.Greeter",
            method="SayHello",
            host="localhost:50051",
            response_body={"error": "NOT_FOUND"},
            elapsed_ms=5.0,
            status_code=5,  # NOT_FOUND
            status_detail="User not found",
            success=False,
        )
        assertable = executor._to_assertable(result)
        assert assertable.status_code == 405  # 400 + 5
        assert "error" in assertable.body
