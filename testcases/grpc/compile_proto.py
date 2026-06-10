"""编译 gRPC proto 文件生成 Python stub

用法：
    python testcases/grpc/compile_proto.py

将在 testcases/grpc/ 下生成 greet_pb2.py 和 greet_pb2_grpc.py。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    proto_dir = Path(__file__).resolve().parent
    proto_file = proto_dir / "greet.proto"

    if not proto_file.exists():
        print(f"错误：proto 文件不存在: {proto_file}")
        sys.exit(1)

    print(f"编译 proto: {proto_file}")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            str(proto_file),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"编译失败:\n{result.stderr}")
        sys.exit(1)

    pb2_file = proto_dir / "greet_pb2.py"
    pb2_grpc_file = proto_dir / "greet_pb2_grpc.py"

    if pb2_file.exists() and pb2_grpc_file.exists():
        print(f"编译成功:")
        print(f"  {pb2_file}")
        print(f"  {pb2_grpc_file}")
    else:
        print("警告：生成文件未找到，但 protoc 返回成功")

    # 修复生成的 pb2_grpc.py 中的 import 路径（Windows 兼容）
    if pb2_grpc_file.exists():
        content = pb2_grpc_file.read_text(encoding="utf-8")
        # 确保 import 使用相对路径
        if f"import {proto_file.stem}_pb2 as {proto_file.stem}" not in content:
            content = content.replace(
                f"import {proto_file.stem}_pb2",
                f"from . import {proto_file.stem}_pb2 as {proto_file.stem}__pb2",
            )
            pb2_grpc_file.write_text(content, encoding="utf-8")
            print("  已修复 import 路径")


if __name__ == "__main__":
    main()
