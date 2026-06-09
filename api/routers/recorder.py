"""流量录制与回放 API 路由

接口：
- POST   /api/v1/recorder/start           启动录制
- POST   /api/v1/recorder/stop            停止录制并保存
- POST   /api/v1/recorder/pause           暂停录制
- POST   /api/v1/recorder/resume          恢复录制
- GET    /api/v1/recorder/status          获取录制状态
- GET    /api/v1/recorder/sessions        录制会话列表
- GET    /api/v1/recorder/sessions/{id}   会话详情
- POST   /api/v1/recorder/sessions/{id}/replay  回放并生成差异报告
- POST   /api/v1/recorder/replay          回放 HAR 文件
- POST   /api/v1/recorder/generate        从 HAR 生成 YAML 用例
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import CurrentUser, get_current_user, require_role
from framework.recorder.case_generator import CaseGenerator, GenerateOptions
from framework.recorder.differ import DiffEngine
from framework.recorder.player import HARPlayer
from framework.recorder.recorder_manager import RecorderManager
from framework.utils.logger import Logger

router = APIRouter(prefix="/api/v1/recorder", tags=["recorder"])
_log = Logger.get("api.recorder")


# ==================== 请求/响应模型 ====================


class StartRecordingRequest(BaseModel):
    session_name: str = Field(default="", description="录制会话名称")
    metadata: dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    save_dir: str | None = Field(default=None, description="HAR 文件保存目录")


class StopRecordingRequest(BaseModel):
    save_dir: str | None = Field(default=None, description="HAR 文件保存目录")


class ReplayRequest(BaseModel):
    har_file: str = Field(..., description="HAR 文件路径")
    filter_url: str | None = Field(default=None, description="过滤 URL 子串")
    filter_method: str | None = Field(default=None, description="过滤 HTTP 方法")
    max_entries: int | None = Field(default=None, description="最大回放条目数")
    base_url: str = Field(default="", description="回放时的基础 URL（覆盖 HAR 中的 host）")
    ignore_headers: list[str] = Field(default_factory=list, description="对比时忽略的响应头")
    ignore_body_keys: list[str] = Field(default_factory=list, description="对比时忽略的响应体字段")
    strict_mode: bool = Field(default=False, description="严格模式")


class GenerateRequest(BaseModel):
    har_file: str = Field(..., description="HAR 文件路径")
    output_dir: str = Field(default="testcases/generated/", description="输出目录")
    suite_name: str = Field(default="", description="套件名称")
    auto_assert: bool = Field(default=True, description="自动生成断言")
    assert_status: bool = Field(default=True, description="断言状态码")
    max_assert_fields: int = Field(default=5, description="自动断言时最多验证的字段数")
    strict_assert: bool = Field(default=True, description="严格断言模式")
    priority: str = Field(default="P1", description="用例优先级")
    tags: list[str] = Field(default_factory=list, description="标签列表")


# ==================== 录制控制 ====================


@router.post("/start", summary="启动流量录制")
async def start_recording(
    body: StartRecordingRequest,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """启动一个新的录制会话。

    录制拦截器将在下一次 HTTP 请求发送时自动生效。
    每个会话生成一个 HAR 文件，记录所有请求/响应对。
    """
    manager = RecorderManager()

    if manager.is_recording:
        raise HTTPException(
            status_code=409,
            detail="已有录制会话在运行中，请先停止当前录制",
        )

    # 需要通过依赖注入获取 HttpClient — 这里尝试通过会话管理器
    # 如果有已注入的 client，在首次 start 后即可使用
    session_id = manager.start(
        session_name=body.session_name,
        metadata=body.metadata,
        save_dir=body.save_dir,
    )

    _log.info("recording_started_via_api", session_id=session_id)
    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "message": "录制已启动",
        },
    }


@router.post("/stop", summary="停止流量录制")
async def stop_recording(
    body: StopRecordingRequest | None = None,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """停止当前录制会话并保存 HAR 文件。

    保存后可通过会话列表查找 HAR 文件路径。
    """
    manager = RecorderManager()

    if not manager.is_recording:
        raise HTTPException(status_code=404, detail="没有正在运行的录制会话")

    save_dir = body.save_dir if body else None
    har_path = manager.stop(save_dir=save_dir)

    _log.info("recording_stopped_via_api", har_path=har_path)
    return {
        "success": True,
        "data": {
            "har_file": har_path,
            "message": "录制已停止并保存",
        },
    }


@router.post("/pause", summary="暂停录制")
async def pause_recording(
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """暂停录制（已记录的数据保留，新请求不再记录）。"""
    manager = RecorderManager()

    if not manager.is_recording:
        raise HTTPException(status_code=404, detail="没有正在运行的录制会话")

    manager.pause()
    return {"success": True, "message": "录制已暂停"}


@router.post("/resume", summary="恢复录制")
async def resume_recording(
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """恢复之前暂停的录制会话。"""
    manager = RecorderManager()

    if not manager.current_session or manager.current_session.state != "paused":
        raise HTTPException(status_code=404, detail="没有暂停状态的录制会话")

    manager.resume()
    return {"success": True, "message": "录制已恢复"}


@router.get("/status", summary="查询录制状态")
async def recording_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取当前录制会话的状态信息。"""
    manager = RecorderManager()
    return {"success": True, "data": manager.status()}


# ==================== 会话管理 ====================


@router.get("/sessions", summary="录制会话列表")
async def list_sessions(
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取所有录制会话的历史记录（按时间倒序）。"""
    manager = RecorderManager()
    history = manager.get_history()
    return {"success": True, "data": history, "total": len(history)}


@router.get("/sessions/{session_id}", summary="会话详情")
async def get_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取指定录制会话的详细信息。"""
    manager = RecorderManager()
    session = manager.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    # 如果文件已保存，加载 HAR 文件内容
    har_data = None
    har_file = session.get("har_file", "")
    if har_file:
        try:
            import json
            from pathlib import Path

            har_path = Path(har_file)
            if har_path.exists():
                har_data = json.loads(har_path.read_text(encoding="utf-8"))
                # 只返回概要（条目标题），避免传输超大响应体
                entries = har_data.get("log", {}).get("entries", [])
                har_data["log"]["entries_preview"] = [
                    {
                        "index": i,
                        "method": e.get("request", {}).get("method", ""),
                        "url": e.get("request", {}).get("url", ""),
                        "status": e.get("response", {}).get("status", 0),
                        "time_ms": e.get("time", 0),
                    }
                    for i, e in enumerate(entries)
                ]
                har_data["log"].pop("entries", None)
        except Exception as e:
            _log.warning("load_har_preview_failed", error=str(e))

    session["har_preview"] = har_data
    return {"success": True, "data": session}


# ==================== 回放 ====================


@router.post("/sessions/{session_id}/replay", summary="回放录制会话")
async def replay_session(
    session_id: str,
    body: ReplayRequest | None = None,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """回放指定会话录制的请求，并与录制时的响应做差异比较。

    返回详细的差异报告，包括状态码、响应头、响应体三级对比。
    """
    manager = RecorderManager()
    session = manager.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    har_file = session.get("har_file", "")
    if not har_file:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 没有对应的 HAR 文件")

    return await _do_replay(har_file, body)


@router.post("/replay", summary="回放 HAR 文件")
async def replay_har(
    body: ReplayRequest,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """直接回放指定的 HAR 文件。

    适用于预先录制的 HAR 文件或从外部工具导入的录制文件。
    """
    return await _do_replay(body.har_file, body)


async def _do_replay(har_file: str, body: ReplayRequest | None = None) -> dict[str, Any]:
    """执行回放并返回报告。"""
    from pathlib import Path

    if not Path(har_file).exists():
        raise HTTPException(status_code=404, detail=f"HAR 文件不存在: {har_file}")

    # 构建差异引擎
    ignore_headers = body.ignore_headers if body else []
    ignore_body_keys = body.ignore_body_keys if body else []
    strict_mode = body.strict_mode if body else False

    diff_engine = DiffEngine(
        ignore_headers=ignore_headers or None,
        ignore_body_keys=ignore_body_keys or None,
        strict_mode=strict_mode,
    )

    # 获取 HttpClient（简化：创建独立客户端；生产环境应通过依赖注入获取）
    from framework.config import ConfigLoader
    from framework.client import HttpClient

    loader = ConfigLoader()
    _, env_config = loader.load()
    http_client = HttpClient(env_config.http, base_url=env_config.base_url)

    try:
        player = HARPlayer(
            client=http_client,
            diff_engine=diff_engine,
            base_url=body.base_url if body else "",
        )

        report = player.replay(
            har_file=har_file,
            filter_url=body.filter_url if body else None,
            filter_method=body.filter_method if body else None,
            max_entries=body.max_entries if body else None,
        )

        _log.info(
            "replay_completed_via_api",
            har_file=har_file,
            pass_rate=report.pass_rate,
        )

        return {"success": True, "data": report.to_dict()}

    finally:
        http_client.close()


# ==================== 用例生成 ====================


@router.post("/generate", summary="从 HAR 生成 YAML 测试用例")
async def generate_cases(
    body: GenerateRequest,
    current_user: CurrentUser = Depends(require_role("admin", "editor")),
):
    """从 HAR 录制文件自动生成可执行的 YAML 测试用例。

    生成的用例包含：
    - 请求配置（方法、路径、头部、请求体）
    - 自动推断的断言（状态码 + 关键响应字段）
    - 自动分类的标签
    """
    from pathlib import Path

    if not Path(body.har_file).exists():
        raise HTTPException(status_code=404, detail=f"HAR 文件不存在: {body.har_file}")

    options = GenerateOptions(
        auto_assert=body.auto_assert,
        assert_status=body.assert_status,
        max_assert_fields=body.max_assert_fields,
        strict_assert=body.strict_assert,
        priority=body.priority,
        tags=body.tags,
    )

    generator = CaseGenerator(options=options)

    try:
        result = generator.generate(
            har_file=body.har_file,
            output_dir=body.output_dir,
            suite_name=body.suite_name,
        )

        _log.info(
            "cases_generated_via_api",
            output_file=result.output_file,
            case_count=result.case_count,
        )

        return {
            "success": True,
            "data": {
                "output_file": result.output_file,
                "case_count": result.case_count,
                "skipped_entries": result.skipped_entries,
                "errors": result.errors,
            },
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        _log.error("case_generation_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"用例生成失败: {str(e)}")


# ==================== HAR 文件加载 ====================


@router.get("/har/{session_id}", summary="下载录制会话的 HAR 文件内容")
async def get_har_content(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取指定会话的完整 HAR 文件内容（JSON）。"""
    manager = RecorderManager()
    session = manager.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    har_file = session.get("har_file", "")
    if not har_file:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 没有对应的 HAR 文件")

    from pathlib import Path
    import json

    har_path = Path(har_file)
    if not har_path.exists():
        raise HTTPException(status_code=404, detail=f"HAR 文件不存在: {har_file}")

    har_data = json.loads(har_path.read_text(encoding="utf-8"))
    return {"success": True, "data": har_data}
