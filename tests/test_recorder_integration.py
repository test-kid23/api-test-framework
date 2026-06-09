"""流量录制模块集成测试

验证 HAR 录制、回放、差异计算、用例生成的完整流程。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def test_har_recording_flow() -> None:
    """完整录制→回放→差异→生成流程测试"""
    from framework.models import BodyType, HttpMethod, HttpRequest, HttpResponse
    from framework.recorder.har_models import HAR
    from framework.recorder.har_recorder import HARRecorder
    from framework.recorder.differ import DiffEngine
    from framework.recorder.case_generator import CaseGenerator, GenerateOptions

    # ========== Step 1: 录制 ==========
    har = HAR.create(session_name="integration_test")

    # 录制 GET 请求
    recorder = HARRecorder(har=har)
    req1 = HttpRequest(method=HttpMethod.GET, path="/api/users", params={"page": "1"})
    resp1 = HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body={"users": [{"id": 1, "name": "Alice"}], "total": 100},
        elapsed_ms=150.0,
        size_bytes=256,
        url="/api/users?page=1",
    )
    context1: dict = {}
    recorder.on_request(req1, context1)
    recorder.on_response(resp1, context1)

    # 录制 POST 请求
    req2 = HttpRequest(
        method=HttpMethod.POST,
        path="/api/users",
        body={"name": "Bob", "email": "bob@test.com"},
        body_type=BodyType.JSON,
        headers={"Content-Type": "application/json"},
    )
    resp2 = HttpResponse(
        status_code=201,
        headers={"Content-Type": "application/json"},
        body={"id": 2, "name": "Bob"},
        elapsed_ms=200.0,
        size_bytes=128,
        url="/api/users",
    )
    context2: dict = {}
    recorder.on_request(req2, context2)
    recorder.on_response(resp2, context2)

    assert recorder.entry_count == 2

    # 保存 HAR 文件
    with tempfile.TemporaryDirectory() as tmpdir:
        har_path = Path(tmpdir) / "test.har"
        recorder.save(str(har_path))
        assert har_path.exists()

        # ========== Step 2: 差异引擎 ==========
        engine = DiffEngine()

        # 测试完全匹配
        report = engine.compare(
            entry_index=0,
            url="/api/users",
            method="GET",
            recorded_status=200,
            actual_status=200,
            recorded_headers={"Content-Type": "application/json"},
            actual_headers={"Content-Type": "application/json"},
            recorded_body={"users": [{"id": 1, "name": "Alice"}], "total": 100},
            actual_body={"users": [{"id": 1, "name": "Alice"}], "total": 100},
        )
        assert report.matched, f"Expected match but got: {report.summary}"
        assert report.diff_count == 0

        # 测试不匹配
        report2 = engine.compare(
            entry_index=1,
            url="/api/users",
            method="POST",
            recorded_status=201,
            actual_status=500,
            recorded_headers={},
            actual_headers={},
            recorded_body={"id": 2, "name": "Bob"},
            actual_body={"error": "server error"},
        )
        assert not report2.matched
        assert report2.diff_count >= 1

        # ========== Step 3: HAR 序列化检查 ==========
        har_json = har.to_dict()
        assert "log" in har_json
        assert "entries" in har_json["log"]
        assert len(har_json["log"]["entries"]) == 2

        entry0 = har_json["log"]["entries"][0]
        assert entry0["request"]["method"] == "GET"
        assert entry0["response"]["status"] == 200

        entry1 = har_json["log"]["entries"][1]
        assert entry1["request"]["method"] == "POST"
        assert entry1["response"]["status"] == 201
        assert "postData" in entry1["request"]

        json_str = json.dumps(har_json)
        assert len(json_str) > 0
        # 验证可以再解析回来
        json.loads(json_str)

        # ========== Step 4: 用例生成 ==========
        gen = CaseGenerator(
            GenerateOptions(auto_assert=True, max_assert_fields=2)
        )
        result = gen.generate(
            str(har_path),
            output_dir=tmpdir,
            suite_name="Integration Test Suite",
        )
        assert result.case_count == 2
        assert Path(result.output_file).exists()

        # 验证生成的 YAML 可解析
        import yaml
        yaml_content = Path(result.output_file).read_text(encoding="utf-8")
        parsed = yaml.safe_load(yaml_content)
        assert isinstance(parsed, dict)
        assert parsed.get("name") == "Integration Test Suite"
        assert len(parsed.get("cases", [])) == 2


def test_recorder_manager_flow() -> None:
    """RecorderManager 生命周期测试"""
    from framework.recorder.recorder_manager import RecorderManager

    manager = RecorderManager()

    # 检查初始状态
    assert not manager.is_recording
    status = manager.status()
    assert status["state"] == "idle"

    # 开始录制（无 client 注入）
    session_id = manager.start(session_name="test_session")
    assert manager.is_recording
    status2 = manager.status()
    assert status2["is_recording"]

    # 停止录制
    har_path = manager.stop()
    assert not manager.is_recording
    assert har_path.endswith(".har")
    assert Path(har_path).exists()

    # 验证历史记录
    history = manager.get_history()
    assert len(history) == 1
    assert history[0]["name"] == "test_session"
    assert history[0]["entry_count"] == 0


def test_diff_engine_config() -> None:
    """差异引擎配置测试"""
    from framework.recorder.differ import DiffEngine, DiffSeverity

    # 默认引擎忽略 date/server 等头
    engine = DiffEngine()
    report = engine.compare(
        entry_index=0,
        url="/api/test",
        method="GET",
        recorded_status=200,
        actual_status=200,
        recorded_headers={"Content-Type": "application/json", "date": "Mon, 01 Jan 2024"},
        actual_headers={"Content-Type": "application/json", "date": "Tue, 02 Jan 2024"},
        recorded_body={},
        actual_body={},
    )
    assert report.matched, "date header should be ignored by default"

    # 严格模式：不要忽略 date
    strict_engine = DiffEngine(ignore_headers=[])
    report2 = strict_engine.compare(
        entry_index=0,
        url="/api/test",
        method="GET",
        recorded_status=200,
        actual_status=200,
        recorded_headers={"Content-Type": "application/json", "date": "Mon, 01 Jan 2024"},
        actual_headers={"Content-Type": "application/json", "date": "Tue, 02 Jan 2024"},
        recorded_body={},
        actual_body={},
    )
    assert report2.diff_count == 1, "date header should be compared in strict mode"
    assert report2.diffs[0].severity == "warning"


def test_har_models_serialization() -> None:
    """HAR 模型序列化完整测试"""
    from framework.recorder.har_models import (
        HAR, HAREntry, HARNameValue, HARPostData,
        HARRequest, HARResponse, HARTimings,
    )

    har = HAR.create("test")
    entry = HAREntry(
        startedDateTime="2024-01-01T00:00:00Z",
        time=123.45,
        request=HARRequest(
            method="POST",
            url="http://example.com/api/data",
            headers=[
                HARNameValue(name="Content-Type", value="application/json"),
                HARNameValue(name="Authorization", value="Bearer xxx"),
            ],
            queryString=[
                HARNameValue(name="limit", value="10"),
            ],
            postData=HARPostData(
                mimeType="application/json",
                text='{"key": "value"}',
            ),
            bodySize=16,
        ),
        response=HARResponse(
            status=200,
            statusText="OK",
            headers=[
                HARNameValue(name="Content-Type", value="application/json"),
            ],
            content={
                "size": 256,
                "mimeType": "application/json",
                "text": '{"result": "ok"}',
            },
            bodySize=256,
        ),
        timings=HARTimings(
            send=1.0,
            wait=120.0,
            receive=2.45,
        ),
    )
    har.add_entry(entry)

    # 序列化
    d = har.to_dict()
    assert d["log"]["version"] == "1.2"
    assert d["log"]["creator"]["name"] == "AutoTest Framework"
    assert len(d["log"]["entries"]) == 1

    e = d["log"]["entries"][0]
    assert e["request"]["method"] == "POST"
    assert e["response"]["status"] == 200
    assert len(e["request"]["headers"]) == 2
    assert e["request"]["postData"]["text"] == '{"key": "value"}'
    assert len(e["request"]["queryString"]) == 1

    # 可以序列化为 JSON
    json_str = json.dumps(d)
    JSON_loaded = json.loads(json_str)
    assert JSON_loaded == d
