"""GrpcStepExecutor — gRPC 协议执行器

基于策略模式实现 StepExecutor 接口，支持：
- 通过 proto 文件动态加载服务定义
- 通过 gRPC 服务反射获取服务定义
- 模板变量渲染请求参数
- 响应断言和变量提取（通过框架内置的 AssertionEngine / Extractor）

依赖：grpcio, grpcio-tools, protobuf（通过 [grpc] extra 安装）
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from framework.assertion import AssertionEngine
from framework.context import TestContext
from framework.executors.base import StepExecutor
from framework.exceptions import (
    GrpcConnectionError,
    GrpcError,
    GrpcProtoError,
    GrpcReflectionError,
)
from framework.models import CaseResult, GrpcConfig, GrpcResult, TestCase
from framework.report.base import ReportAdapter
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("executor.grpc")


class GrpcStepExecutor(StepExecutor):
    """gRPC 协议执行器

    职责：
    1. 加载 proto 定义或通过反射获取服务描述
    2. 模板渲染 gRPC 请求参数（host / body / metadata）
    3. 构造 protobuf 消息并发送 gRPC 调用
    4. 将响应转为 dict 格式，供断言引擎和提取器使用
    5. 执行断言和变量提取

    支持两种服务发现模式：
    - proto_file 模式：指定 .proto 文件路径，按 service + method 定位
    - reflection 模式：向 gRPC 服务发起反射查询获取服务描述
    """

    def __init__(
        self,
        template_engine: TemplateEngine,
        assertion_engine: AssertionEngine,
        report_adapter: ReportAdapter,
        plugin_manager: Any = None,
    ) -> None:
        self._template = template_engine
        self._assertion_engine = assertion_engine
        self._report_adapter = report_adapter
        self._plugin_manager = plugin_manager

        # 懒加载：proto 文件描述符池缓存
        self._proto_pool: dict[str, Any] = {}

    # ── StepExecutor 接口 ──────────────────────────────

    def supports(self, case: TestCase) -> bool:
        return case.grpc_config is not None

    def execute(
        self,
        case: TestCase,
        context: TestContext,
        variables: dict[str, Any],
    ) -> CaseResult:
        grpc_cfg = case.grpc_config
        assert grpc_cfg is not None

        case_result = CaseResult(case_name=case.name, passed=True)
        start_time = time.time()

        try:
            # 模板渲染 gRPC 配置
            rendered_cfg = self._render_config(grpc_cfg, variables)

            # 解析服务描述（proto 文件或反射）
            service_desc, method_desc = self._resolve_service(rendered_cfg)

            # 构造请求消息
            request_msg = self._build_request(service_desc, method_desc, rendered_cfg.body)

            # 发起 gRPC 调用
            grpc_result = self._invoke(
                rendered_cfg,
                service_desc,
                method_desc,
                request_msg,
            )

            case_result.request = rendered_cfg
            case_result.response = grpc_result
            context.set_request(rendered_cfg)
            context.set_response(grpc_result)

            self._report_adapter.attach_request(rendered_cfg, rendered_cfg.host)

            # 将 gRPC 结果适配为类似 HTTP 的格式供断言引擎使用
            grpc_response_for_assert = self._to_assertable(grpc_result)

            # 执行断言
            if case.assertions:
                assertion_report = self._assertion_engine.assert_response(
                    grpc_response_for_assert, case.assertions, variables
                )
                case_result.assertion_report = assertion_report
                self._report_adapter.attach_assertions(assertion_report)

                if self._plugin_manager:
                    self._plugin_manager.dispatch(
                        "assertion", case=case, report=assertion_report
                    )

                if not assertion_report.passed:
                    case_result.passed = False
                    case_result.error = assertion_report.summary()

            # 提取变量（从 gRPC 响应 body 中）
            if case.extracts:
                from framework.extractor import Extractor

                extractor = Extractor()
                extracted = extractor.extract(
                    grpc_response_for_assert, case.extracts, variables
                )
                case_result.extracted_vars.update(extracted)
                context.get_variables().update(extracted)

                if self._plugin_manager:
                    self._plugin_manager.dispatch(
                        "extract", case=case, extracted=extracted
                    )

                logger.info("variables_extracted", var_names=list(extracted.keys()))

        except GrpcError:
            case_result.passed = False
            case_result.error = str(GrpcError) if False else ""
            raise
        except Exception as e:
            logger.error(
                "grpc_execution_error",
                case_name=case.name,
                error=str(e),
                exc_info=True,
            )
            case_result.passed = False
            case_result.error = str(e)
            if self._plugin_manager:
                self._plugin_manager.dispatch("error", error=e, case=case)

        case_result.elapsed_ms = (time.time() - start_time) * 1000
        return case_result

    # ── 内部方法：配置渲染 ─────────────────────────────

    def _render_config(self, cfg: GrpcConfig, variables: dict[str, Any]) -> GrpcConfig:
        """对 gRPC 配置做模板变量替换"""
        return GrpcConfig(
            service=self._template.render(cfg.service, variables),
            method=self._template.render(cfg.method, variables),
            proto_file=self._template.render(cfg.proto_file, variables),
            proto_dir=self._template.render(cfg.proto_dir, variables),
            host=self._template.render(cfg.host, variables),
            body=self._template.render_value(cfg.body, variables) if cfg.body else {},
            metadata=self._template.render_dict(cfg.metadata, variables),
            timeout=cfg.timeout,
            tls=cfg.tls,
            tls_ca_cert=self._template.render(cfg.tls_ca_cert, variables),
            reflection=cfg.reflection,
        )

    # ── 内部方法：服务解析 ─────────────────────────────

    def _resolve_service(
        self, cfg: GrpcConfig
    ) -> tuple[Any, Any]:
        """解析 gRPC 服务和方法描述符

        Args:
            cfg: 渲染后的 gRPC 配置。

        Returns:
            (service_descriptor, method_descriptor) 元组。

        Raises:
            GrpcProtoError: proto 文件加载失败。
            GrpcReflectionError: 反射查询失败。
        """
        if cfg.reflection:
            return self._resolve_by_reflection(cfg)
        else:
            return self._resolve_by_proto(cfg)

    def _resolve_by_proto(self, cfg: GrpcConfig) -> tuple[Any, Any]:
        """通过 proto 文件解析服务描述

        使用 grpc_tools.protoc 编译 proto → 临时的 pb2 文件描述符池，
        然后从中查找指定的 service 和 method。
        """
        import os
        import sys
        import tempfile

        proto_file = cfg.proto_file
        if not proto_file:
            raise GrpcProtoError("", "proto_file 未指定且 reflection 未启用")

        proto_path = Path(proto_file)
        if not proto_path.is_absolute():
            raise GrpcProtoError(
                proto_file,
                "proto_file 必须是绝对路径（或相对于项目根目录）",
            )

        if not proto_path.exists():
            raise GrpcProtoError(proto_file, "proto 文件不存在")

        proto_dir = cfg.proto_dir or str(proto_path.parent)

        # 缓存 key
        cache_key = f"{proto_file}:{cfg.service}:{cfg.method}"
        if cache_key in self._proto_pool:
            return self._proto_pool[cache_key]

        try:
            from grpc_tools import protoc

            # 编译 proto 到临时目录
            with tempfile.TemporaryDirectory(prefix="grpc_pb2_") as tmp_dir:
                proto_args = [
                    "protoc",
                    f"--proto_path={proto_dir}",
                    f"--python_out={tmp_dir}",
                    f"--grpc_python_out={tmp_dir}",
                    str(proto_path),
                ]

                # 抑制 protoc 的 stderr 输出
                import subprocess

                result = subprocess.run(
                    [sys.executable, "-m", "grpc_tools.protoc"] + proto_args[1:],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    raise GrpcProtoError(
                        proto_file,
                        f"protoc 编译失败: {result.stderr.strip()}",
                    )

                # 将临时目录加入 sys.path 以支持动态 import
                if tmp_dir not in sys.path:
                    sys.path.insert(0, tmp_dir)

                try:
                    # 动态 import 生成的 pb2 模块
                    proto_stem = proto_path.stem
                    pb2_module_name = f"{proto_stem}_pb2"
                    pb2_grpc_module_name = f"{proto_stem}_pb2_grpc"

                    pb2_module = __import__(pb2_module_name)
                    pb2_grpc_module = __import__(pb2_grpc_module_name)

                    # 查找 service 描述符
                    service_desc = self._find_service_descriptor(
                        pb2_module, pb2_grpc_module, cfg.service
                    )

                    # 查找 method 描述符
                    method_desc = self._find_method_descriptor(
                        service_desc, cfg.method
                    )

                    result_desc = (service_desc, method_desc)
                    self._proto_pool[cache_key] = result_desc
                    return result_desc

                finally:
                    if tmp_dir in sys.path:
                        sys.path.remove(tmp_dir)

        except ImportError as e:
            raise GrpcProtoError(
                proto_file,
                f"无法导入生成的 pb2 模块（请确认已安装 grpcio-tools）: {e}",
            ) from e

    def _resolve_by_reflection(self, cfg: GrpcConfig) -> tuple[Any, Any]:
        """通过 gRPC 服务反射获取服务描述

        使用 grpc 的 channelz / reflection API 从运行中的服务获取
        服务和方法描述符。
        """
        try:
            import grpc
            from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
            from google.protobuf import descriptor_pool, symbol_database

            channel = self._create_channel(cfg)

            # 反射查询服务列表
            stub = reflection_pb2_grpc.ServerReflectionStub(channel)

            def _reflection_request():
                request = reflection_pb2.ServerReflectionRequest(
                    file_containing_symbol=cfg.service,
                )
                responses = stub.ServerReflectionInfo(iter([request]))
                for resp in responses:
                    if resp.HasField("file_descriptor_response"):
                        return resp.file_descriptor_response.file_descriptor_proto
                return None

            file_descriptors = _reflection_request()
            if not file_descriptors:
                raise GrpcReflectionError(
                    cfg.host,
                    f"未找到服务: {cfg.service}",
                )

            # 将文件描述符注册到全局池
            from google.protobuf import descriptor_pool as _dp
            pool = _dp.Default()

            for fd_proto in file_descriptors:
                try:
                    pool.Add(fd_proto)
                except TypeError:
                    # 描述符已存在，忽略
                    pass

            # 查找 service 和 method 描述符
            service_desc = pool.FindServiceByName(cfg.service)
            if service_desc is None:
                raise GrpcReflectionError(
                    cfg.host,
                    f"服务描述符未找到: {cfg.service}",
                )

            method_desc = service_desc.FindMethodByName(cfg.method)
            if method_desc is None:
                raise GrpcReflectionError(
                    cfg.host,
                    f"方法描述符未找到: {cfg.service}.{cfg.method}",
                )

            channel.close()
            return service_desc, method_desc

        except GrpcReflectionError:
            raise
        except ImportError as e:
            raise GrpcReflectionError(
                cfg.host,
                f"缺少 grpc_reflection 依赖: {e}",
            ) from e
        except Exception as e:
            raise GrpcReflectionError(cfg.host, str(e)) from e

    @staticmethod
    def _find_service_descriptor(
        pb2_module: Any,
        pb2_grpc_module: Any,
        service_name: str,
    ) -> Any:
        """从 pb2 模块中查找 service 描述符

        Args:
            pb2_module: _pb2 模块。
            pb2_grpc_module: _pb2_grpc 模块。
            service_name: 完整服务名（package.ServiceName）。

        Returns:
            ServiceDescriptor 对象。

        Raises:
            GrpcProtoError: 未找到服务描述符。
        """
        # 遍历 pb2_grpc 模块，找到匹配的 Servicer 类
        for attr_name in dir(pb2_grpc_module):
            cls = getattr(pb2_grpc_module, attr_name)
            if not isinstance(cls, type):
                continue
            # 检查是否包含 service 描述符
            if hasattr(cls, "__call__"):
                continue

        # 方式1：通过 DESCRIPTOR 属性查找
        for attr_name in dir(pb2_module):
            if attr_name == "DESCRIPTOR":
                descriptor = getattr(pb2_module, attr_name)
                for service in descriptor.services_by_name.values():
                    full_name = getattr(service, "full_name", "")
                    if full_name == service_name or service.name == service_name.rsplit(".", 1)[-1]:
                        return service

        # 方式2：通过 _pb2_grpc 中的 Stub 类查找
        for attr_name in dir(pb2_grpc_module):
            if attr_name.endswith("Stub"):
                stub_cls = getattr(pb2_grpc_module, attr_name)
                # 获取 stub 对应的 service 名称
                stub_service_name = attr_name[:-4]  # 去掉 "Stub"
                for svc_name in dir(pb2_module):
                    svc = getattr(pb2_module, svc_name)
                    if hasattr(svc, "services_by_name"):
                        for svc_desc in svc.services_by_name.values():
                            if svc_desc.name == stub_service_name or svc_desc.name == service_name.rsplit(".", 1)[-1]:
                                return svc_desc

        raise GrpcProtoError(
            pb2_module.__name__,
            f"未找到服务描述符: {service_name}",
        )

    @staticmethod
    def _find_method_descriptor(service_desc: Any, method_name: str) -> Any:
        """从服务描述符中查找方法描述符

        Args:
            service_desc: ServiceDescriptor 对象。
            method_name: 方法名。

        Returns:
            MethodDescriptor 对象。

        Raises:
            GrpcProtoError: 未找到方法描述符。
        """
        for method in service_desc.methods:
            if method.name == method_name:
                return method

        raise GrpcProtoError(
            service_desc.full_name,
            f"未找到方法: {method_name}",
        )

    # ── 内部方法：请求构造与调用 ──────────────────────

    @staticmethod
    def _build_request(
        service_desc: Any,
        method_desc: Any,
        body: dict[str, Any],
    ) -> Any:
        """根据方法描述符构造 protobuf 请求消息

        Args:
            service_desc: ServiceDescriptor。
            method_desc: MethodDescriptor。
            body: 请求体字段映射（dict）。

        Returns:
            protobuf Message 实例。
        """
        from google.protobuf import json_format

        # 获取请求消息类
        input_type = method_desc.input_type
        # 通过 descriptor pool 创建消息实例
        request_msg = _create_message_instance(input_type)
        if request_msg is None:
            # fallback: 使用 empty message
            from google.protobuf import empty_pb2
            return empty_pb2.Empty()

        # 将 dict 解析为 protobuf 消息
        try:
            json_format.ParseDict(body, request_msg, ignore_unknown_fields=False)
        except json_format.ParseError as e:
            logger.warning(
                "grpc_body_parse_warning",
                error=str(e),
                body_keys=list(body.keys()),
            )
            # 忽略未知字段后重试
            json_format.ParseDict(body, request_msg, ignore_unknown_fields=True)

        return request_msg

    def _invoke(
        self,
        cfg: GrpcConfig,
        service_desc: Any,
        method_desc: Any,
        request_msg: Any,
    ) -> GrpcResult:
        """执行 gRPC 调用

        Args:
            cfg: 渲染后的 gRPC 配置。
            service_desc: 服务描述符。
            method_desc: 方法描述符。
            request_msg: 构造好的 protobuf 请求消息。

        Returns:
            GrpcResult 调用结果。
        """
        import grpc
        from google.protobuf import json_format

        channel = self._create_channel(cfg)

        try:
            # 构造方法路径: /package.ServiceName/MethodName
            method_path = f"/{service_desc.full_name}/{method_desc.name}"

            # 序列化请求
            request_bytes = request_msg.SerializeToString()

            # 构造元数据
            metadata_list = []
            for k, v in cfg.metadata.items():
                metadata_list.append((k, v))

            # 创建 unary-unary 调用
            timeout = cfg.timeout if cfg.timeout else 30

            start = time.time()

            # 使用 grpc 的 unary_unary 调用
            call = channel.unary_unary(
                method_path,
                request_serializer=lambda msg: msg.SerializeToString(),
                response_deserializer=lambda data: _deserialize_response(
                    method_desc.output_type, data
                ),
            )

            # 构造 future 并等待结果
            future = call.future(
                request_msg,
                timeout=timeout,
                metadata=metadata_list,
            )

            try:
                response_msg = future.result()
                elapsed_ms = (time.time() - start) * 1000

                # 获取 trailing metadata 和状态码
                code = future.code()
                details = future.details()
                trailing_metadata = dict(future.trailing_metadata())

                # 将响应转为 dict
                if response_msg is not None:
                    response_dict = json_format.MessageToDict(
                        response_msg,
                        preserving_proto_field_name=True,
                    )
                else:
                    response_dict = {}

                return GrpcResult(
                    service=cfg.service,
                    method=cfg.method,
                    host=cfg.host,
                    request_body=cfg.body,
                    response_body=response_dict,
                    elapsed_ms=elapsed_ms,
                    status_code=int(code.value[0]) if code else 0,
                    status_detail=details or "",
                    metadata=trailing_metadata,
                    success=code == grpc.StatusCode.OK if code else True,
                )

            except grpc.RpcError as e:
                elapsed_ms = (time.time() - start) * 1000
                code = e.code() if e.code() else grpc.StatusCode.UNKNOWN
                details = e.details() or str(e)

                return GrpcResult(
                    service=cfg.service,
                    method=cfg.method,
                    host=cfg.host,
                    request_body=cfg.body,
                    response_body={"error": details},
                    elapsed_ms=elapsed_ms,
                    status_code=int(code.value[0]),
                    status_detail=details,
                    metadata={},
                    success=False,
                )

        finally:
            channel.close()

    def _create_channel(self, cfg: GrpcConfig) -> Any:
        """创建 gRPC channel

        Args:
            cfg: 渲染后的 gRPC 配置。

        Returns:
            grpc.Channel 实例。

        Raises:
            GrpcConnectionError: 连接参数无效。
        """
        import grpc

        try:
            if cfg.tls:
                creds = grpc.ssl_channel_credentials()
                if cfg.tls_ca_cert:
                    with open(cfg.tls_ca_cert, "rb") as f:
                        creds = grpc.ssl_channel_credentials(root_certificates=f.read())
                channel = grpc.secure_channel(cfg.host, creds)
            else:
                channel = grpc.insecure_channel(cfg.host)
            return channel
        except Exception as e:
            raise GrpcConnectionError(cfg.host, str(e)) from e

    # ── 内部方法：结果适配 ────────────────────────────

    @staticmethod
    def _to_assertable(grpc_result: GrpcResult) -> Any:
        """将 GrpcResult 转换为断言引擎可用的类似 HTTP 响应的对象

        创建一个兼容 HttpResponse 接口的简单包装对象，
        使断言引擎的 assert_response 能直接处理。

        Returns:
            具有 status_code / headers / body / elapsed_ms 属性的对象。
        """
        from types import SimpleNamespace

        # 映射 gRPC 状态码（grpc.StatusCode 的 value[0]）到 HTTP-like 状态码
        # 0=OK → 200, 非 OK → 对应的错误码
        grpc_code = grpc_result.status_code
        http_like_status = 200 if grpc_code == 0 else (400 + min(grpc_code, 99))

        return SimpleNamespace(
            status_code=http_like_status,
            headers=grpc_result.metadata,
            body=grpc_result.response_body,
            elapsed_ms=grpc_result.elapsed_ms,
            url=f"grpc://{grpc_result.host}/{grpc_result.service}/{grpc_result.method}",
            request_body=grpc_result.request_body,
        )


# ── 辅助函数 ──────────────────────────────────────────


def _create_message_instance(descriptor: Any) -> Any:
    """根据描述符创建 protobuf 消息实例

    尝试多种方式创建消息实例，兼容不同的 protobuf 版本。

    Args:
        descriptor: protobuf Descriptor 对象。

    Returns:
        protobuf Message 实例或 None。
    """
    from google.protobuf import descriptor_pb2, message_factory, symbol_database

    # 方式1：通过 symbol_database 获取消息类
    try:
        db = symbol_database.Default()
        # 尝试获取消息类
        msg_cls = db.GetPrototype(descriptor)
        return msg_cls()
    except (KeyError, TypeError):
        pass

    # 方式2：通过 message_factory 创建
    try:
        factory = message_factory.MessageFactory()
        msg_cls = factory.GetPrototype(descriptor)
        return msg_cls()
    except Exception:
        pass

    # 方式3：通过 descriptor_pb2 手动构造
    try:
        from google.protobuf import descriptor as _descriptor
        from google.protobuf import message as _message

        # 使用 reflection 创建
        return _message.Message()
    except Exception:
        pass

    return None


def _deserialize_response(output_type: Any, data: bytes) -> Any:
    """将 gRPC 响应字节反序列化为 protobuf 消息

    Args:
        output_type: 输出消息的描述符。
        data: 序列化后的响应数据。

    Returns:
        反序列化后的 protobuf Message 实例。
    """
    msg = _create_message_instance(output_type)
    if msg is not None and data:
        msg.ParseFromString(data)
    return msg
