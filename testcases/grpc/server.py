"""gRPC 示例服务 — Greeter 问候服务

用于测试 GrpcStepExecutor，提供多个 RPC 方法。
启动：python testcases/grpc/server.py

依赖：pip install auto-test-framework[grpc]
"""

from __future__ import annotations

import sys
import time
from concurrent import futures
from pathlib import Path

import grpc

# 将 proto 目录加入 path 以支持动态 import
_PROTO_DIR = str(Path(__file__).resolve().parent)
if _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)

# 动态导入生成的 pb2 模块（需要先编译 proto）
try:
    import greet_pb2
    import greet_pb2_grpc
except ImportError:
    print("错误：未找到 greet_pb2 / greet_pb2_grpc 模块")
    print("请先编译 proto 文件：")
    print(f"  cd {_PROTO_DIR}")
    print("  python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. greet.proto")
    sys.exit(1)


# ── 模拟用户数据 ──────────────────────────────────────

_MOCK_USERS = [
    {"user_id": 1, "name": "Alice", "email": "alice@example.com", "age": 28},
    {"user_id": 2, "name": "Bob", "email": "bob@example.com", "age": 35},
    {"user_id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 42},
]


class GreeterServicer(greet_pb2_grpc.GreeterServicer):
    """Greeter 服务实现"""

    def SayHello(self, request: greet_pb2.HelloRequest, context: grpc.ServicerContext) -> greet_pb2.HelloReply:
        greeting = request.greeting or "Hello"
        name = request.name or "World"
        return greet_pb2.HelloReply(
            message=f"{greeting}, {name}!",
            timestamp=int(time.time()),
        )

    def SayHelloAgain(self, request: greet_pb2.HelloRequest, context: grpc.ServicerContext) -> greet_pb2.HelloReply:
        return greet_pb2.HelloReply(
            message=f"Hello again, {request.name or 'World'}!",
            timestamp=int(time.time()),
        )

    def GetUser(self, request: greet_pb2.UserRequest, context: grpc.ServicerContext) -> greet_pb2.UserResponse:
        for user in _MOCK_USERS:
            if user["user_id"] == request.user_id:
                return greet_pb2.UserResponse(**user)
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"User {request.user_id} not found")
        return greet_pb2.UserResponse()

    def ListUsers(self, request: greet_pb2.ListUsersRequest, context: grpc.ServicerContext) -> greet_pb2.ListUsersResponse:
        page = request.page if request.page > 0 else 1
        page_size = request.page_size if request.page_size > 0 else 10
        start = (page - 1) * page_size
        end = start + page_size

        users = [
            greet_pb2.UserResponse(**u)
            for u in _MOCK_USERS[start:end]
        ]
        return greet_pb2.ListUsersResponse(
            users=users,
            total=len(_MOCK_USERS),
        )

    def HealthCheck(self, request: greet_pb2.HealthCheckRequest, context: grpc.ServicerContext) -> greet_pb2.HealthCheckResponse:
        return greet_pb2.HealthCheckResponse(
            status="SERVING",
            version="1.0.0",
        )


def serve(port: int = 50051) -> None:
    """启动 gRPC 服务"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    greet_pb2_grpc.add_GreeterServicer_to_server(GreeterServicer(), server)

    # 启用服务反射
    try:
        from grpc_reflection.v1alpha import reflection
        SERVICE_NAMES = (
            greet_pb2.DESCRIPTOR.services_by_name["Greeter"].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(SERVICE_NAMES, server)
        print("[reflection] 服务反射已启用")
    except ImportError:
        print("[reflection] grpc_reflection 未安装，跳过反射启用")

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC Greeter 服务启动在 [::]:{port}")
    print("可用方法：")
    print("  - greet.Greeter/SayHello")
    print("  - greet.Greeter/SayHelloAgain")
    print("  - greet.Greeter/GetUser")
    print("  - greet.Greeter/ListUsers")
    print("  - greet.Greeter/HealthCheck")
    print()
    print("按 Ctrl+C 停止...")
    server.wait_for_termination()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="gRPC Greeter 示例服务")
    parser.add_argument("--port", type=int, default=50051, help="监听端口 (默认: 50051)")
    args = parser.parse_args()
    serve(port=args.port)
