"""录制管理器 — 控制录制生命周期（启动/停止/状态查询）

提供单例模式的录制管理器，支持：
- 启动/停止录制
- 录制状态查询
- 会话历史管理
- 与 HttpClient 拦截器链集成

使用方式::

    from framework.recorder import RecorderManager

    manager = RecorderManager()

    # 开始录制
    session_id = manager.start("回归测试会话", client=http_client)

    # ... 执行 HTTP 请求 ...

    # 停止并保存
    har_path = manager.stop(save_dir="recordings/")

    # 查询状态
    status = manager.status()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from framework.recorder.har_models import HAR
from framework.recorder.har_recorder import HARRecorder
from framework.utils.logger import Logger

logger = Logger.get("recorder.manager")


class RecorderState:
    """录制状态常量"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


@dataclass
class RecordingSession:
    """录制会话信息

    Attributes:
        session_id: 会话 ID。
        name: 会话名称。
        state: 当前状态（idle/recording/paused）。
        started_at: 启动时间（ISO 8601）。
        stopped_at: 停止时间（ISO 8601）。
        entry_count: 已录制的请求/响应对数量。
        har_file: 保存的 HAR 文件路径（停止后）。
        metadata: 用户自定义元数据。
    """

    session_id: str
    name: str = ""
    state: str = RecorderState.IDLE
    started_at: str = ""
    stopped_at: str = ""
    entry_count: int = 0
    har_file: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """录制持续时间（秒）。"""
        if not self.started_at:
            return 0.0
        start = datetime.fromisoformat(self.started_at)
        if self.stopped_at:
            end = datetime.fromisoformat(self.stopped_at)
        else:
            end = datetime.now(timezone.utc)
        return (end - start).total_seconds()


class RecorderManager:
    """录制管理器（单例模式）

    控制录制生命周期，管理 HAR 录制拦截器的安装和卸载。

    特性：
    - 线程安全的单例访问
    - 录制会话历史记录
    - 自动与 HttpClient 拦截器链集成
    - 支持暂停/恢复（通过移除/添加拦截器实现）
    """

    _instance: RecorderManager | None = None

    def __new__(cls) -> RecorderManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._recorder: HARRecorder | None = None
        self._current_session: RecordingSession | None = None
        self._history: list[RecordingSession] = []
        self._client_ref: Any = None  # HttpClient 引用（用于安装/卸载拦截器）
        self._save_dir: Path = Path("recordings")

    # ---------- 公开 API ----------

    @property
    def is_recording(self) -> bool:
        """是否正在录制。"""
        return (
            self._current_session is not None
            and self._current_session.state == RecorderState.RECORDING
        )

    @property
    def current_session(self) -> RecordingSession | None:
        """当前会话信息。"""
        return self._current_session

    @property
    def history(self) -> list[RecordingSession]:
        """录制历史会话列表（按时间倒序）。"""
        return list(reversed(self._history))

    def start(
        self,
        session_name: str = "",
        client: Any = None,
        metadata: dict[str, Any] | None = None,
        save_dir: str | None = None,
    ) -> str:
        """启动录制会话。

        Args:
            session_name: 会话名称，用于 HAR 文件命名。
            client: HttpClient 实例，用于安装录制拦截器。
            metadata: 用户自定义元数据。
            save_dir: HAR 文件保存目录（默认 recordings/）。

        Returns:
            session_id 字符串。

        Raises:
            RuntimeError: 已有录制会话在运行中。
        """
        if self.is_recording:
            raise RuntimeError(
                f"已有录制会话在运行中: {self._current_session.session_id if self._current_session else 'unknown'}"
            )

        import uuid

        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        if save_dir:
            self._save_dir = Path(save_dir)

        name = session_name or f"session_{session_id}"

        session = RecordingSession(
            session_id=session_id,
            name=name,
            state=RecorderState.RECORDING,
            started_at=now,
            metadata=metadata or {},
        )

        # 安装录制拦截器到 HttpClient
        self._client_ref = client
        self._recorder = HARRecorder(HAR.create(session_name=name))

        if client is not None:
            client.add_interceptor(self._recorder)
            logger.info("recorder_interceptor_installed")

        self._current_session = session

        logger.info(
            "recording_started",
            session_id=session_id,
            session_name=name,
        )
        return session_id

    def stop(self, save_dir: str | None = None) -> str:
        """停止录制并保存 HAR 文件。

        Args:
            save_dir: HAR 文件保存目录（覆盖启动时设置的目录）。

        Returns:
            保存的 HAR 文件路径。

        Raises:
            RuntimeError: 没有正在运行的录制会话。
        """
        if not self._current_session or not self._recorder:
            raise RuntimeError("没有正在运行的录制会话")

        # 卸载录制拦截器
        if self._client_ref is not None and self._recorder is not None:
            self._remove_interceptor(self._client_ref, self._recorder)

        # 保存 HAR 文件
        target_dir = Path(save_dir) if save_dir else self._save_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _safe_filename(self._current_session.name)
        har_filename = f"{safe_name}_{self._current_session.session_id}.har"
        har_path = target_dir / har_filename

        self._recorder.save(str(har_path))

        # 更新会话信息
        now = datetime.now(timezone.utc).isoformat()
        self._current_session.state = RecorderState.IDLE
        self._current_session.stopped_at = now
        self._current_session.entry_count = self._recorder.entry_count
        self._current_session.har_file = str(har_path)

        # 归档到历史
        self._history.append(self._current_session)

        entry_count = self._recorder.entry_count

        # 重置状态
        current = self._current_session
        self._recorder = None
        self._current_session = None
        self._client_ref = None

        logger.info(
            "recording_stopped",
            session_id=current.session_id,
            entry_count=entry_count,
            har_path=str(har_path),
            duration_s=round(current.duration_seconds, 2),
        )

        return str(har_path)

    def pause(self) -> None:
        """暂停录制（卸载拦截器，保留已录制数据）。

        Raises:
            RuntimeError: 没有正在运行的录制会话。
        """
        if not self.is_recording:
            raise RuntimeError("没有正在运行的录制会话")

        if self._client_ref is not None and self._recorder is not None:
            self._remove_interceptor(self._client_ref, self._recorder)

        if self._current_session:
            self._current_session.state = RecorderState.PAUSED

        logger.info("recording_paused")

    def resume(self) -> None:
        """恢复录制（重新安装拦截器）。

        Raises:
            RuntimeError: 没有暂停状态的录制会话。
        """
        if not self._current_session or self._current_session.state != RecorderState.PAUSED:
            raise RuntimeError("没有暂停状态的录制会话")

        if self._client_ref is not None and self._recorder is not None:
            self._client_ref.add_interceptor(self._recorder)
            self._current_session.state = RecorderState.RECORDING

        logger.info("recording_resumed")

    def status(self) -> dict[str, Any]:
        """获取当前录制状态。

        Returns:
            包含状态信息的字典。
        """
        result: dict[str, Any] = {
            "state": (
                self._current_session.state
                if self._current_session
                else RecorderState.IDLE
            ),
            "is_recording": self.is_recording,
            "current_session": None,
            "total_entries": self._recorder.entry_count if self._recorder else 0,
        }

        if self._current_session:
            result["current_session"] = _session_to_dict(self._current_session)

        return result

    def get_history(self) -> list[dict[str, Any]]:
        """获取录制会话历史。

        Returns:
            会话信息字典列表（按时间倒序）。
        """
        return [_session_to_dict(s) for s in self.history]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """按 ID 获取会话详情。

        Args:
            session_id: 会话 ID。

        Returns:
            会话信息字典，未找到返回 None。
        """
        for s in self._history:
            if s.session_id == session_id:
                return _session_to_dict(s)
        if self._current_session and self._current_session.session_id == session_id:
            return _session_to_dict(self._current_session)
        return None

    # ---------- 私有方法 ----------

    def _remove_interceptor(self, client: Any, interceptor: Any) -> None:
        """从 HttpClient 的拦截器链中移除指定拦截器。

        由于拦截器链是基于 list 的，通过遍历找到对应实例并移除。

        Args:
            client: HttpClient 实例。
            interceptor: 要移除的拦截器。
        """
        interceptors = getattr(client, "_interceptors", [])
        if interceptor in interceptors:
            interceptors.remove(interceptor)


def _session_to_dict(session: RecordingSession) -> dict[str, Any]:
    """将会话信息转换为字典。"""
    return {
        "session_id": session.session_id,
        "name": session.name,
        "state": session.state,
        "started_at": session.started_at,
        "stopped_at": session.stopped_at,
        "entry_count": session.entry_count,
        "har_file": session.har_file,
        "duration_seconds": round(session.duration_seconds, 2),
        "metadata": session.metadata,
    }


def _safe_filename(name: str) -> str:
    """将名称转换为安全的文件名。"""
    import re

    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"_{2,}", "_", safe)
    return safe.strip("_") or "recording"


# 便捷函数：获取全局单例
def get_recorder_manager() -> RecorderManager:
    """获取 RecorderManager 全局单例。

    Returns:
        RecorderManager 实例。
    """
    return RecorderManager()
