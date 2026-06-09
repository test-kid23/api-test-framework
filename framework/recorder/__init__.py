"""流量录制与回放模块

提供 HTTP(S) 流量的录制、回放、差异对比和用例生成能力：

- HARRecorder: 作为 RequestInterceptor 拦截所有 HTTP 流量，记录为 HAR 格式
- RecorderManager: 录制会话管理器（单例），控制录制生命周期
- HARPlayer: 回放引擎，读取 HAR 文件重放请求并对响应做差异对比
- DiffEngine: 结构化差异计算引擎（状态码、响应头、响应体三级比较）
- CaseGenerator: 基于 HAR 录制文件生成 YAML 测试用例

使用方式::

    from framework.recorder import RecorderManager

    # 获取管理器
    manager = RecorderManager()

    # 开始录制
    manager.start(session_name="回归测试录制", client=http_client)

    # ... 执行测试 ...

    # 停止录制
    har_path = manager.stop()

    # 回放
    from framework.recorder import HARPlayer
    player = HARPlayer(client=http_client)
    report = player.replay(har_path)

    # 生成用例
    from framework.recorder import CaseGenerator
    generator = CaseGenerator()
    generator.generate(har_path, output_dir="testcases/regression/")
"""

from __future__ import annotations

from framework.recorder.case_generator import CaseGenerator
from framework.recorder.differ import DiffEngine, DiffReport, DiffResult, DiffSeverity
from framework.recorder.har_models import (
    HAR,
    HARCreator,
    HAREntry,
    HARLog,
    HARNameValue,
    HARPageTimings,
    HARPostData,
    HARRequest,
    HARResponse,
    HARTimings,
)
from framework.recorder.har_recorder import HARRecorder
from framework.recorder.player import HARPlayer, PlaybackReport, PlaybackResult
from framework.recorder.recorder_manager import RecorderManager

__all__ = [
    # 录制管理
    "HARRecorder",
    "RecorderManager",
    # HAR 数据模型
    "HAR",
    "HARLog",
    "HAREntry",
    "HARRequest",
    "HARResponse",
    "HARCreator",
    "HARNameValue",
    "HARPostData",
    "HARTimings",
    "HARPageTimings",
    # 回放引擎
    "HARPlayer",
    "PlaybackReport",
    "PlaybackResult",
    # 差异引擎
    "DiffEngine",
    "DiffReport",
    "DiffResult",
    "DiffSeverity",
    # 用例生成
    "CaseGenerator",
]
