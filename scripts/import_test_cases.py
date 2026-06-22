"""
批量导入 test_sim_api.yaml 中的用例到平台数据库。
运行方式: python scripts/import_test_cases.py

通过 POST /api/v1/cases 逐个创建用例。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import yaml

# ── 配置 ──────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "admin123"
YAML_PATH = Path(__file__).resolve().parent.parent / "testcases" / "local" / "test_sim_api.yaml"


def login(client: httpx.Client) -> str:
    """登录平台 API 获取 access_token。"""
    resp = client.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"登录失败 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    token = None
    # 尝试多种 API 响应格式
    token_container = data.get("data", data)
    if isinstance(token_container, dict):
        # {"data": {"token": {"access_token": "..."}}}
        token = token_container.get("token", {}).get("access_token") if isinstance(token_container.get("token"), dict) else None
        if not token:
            # {"data": {"access_token": "..."}}
            token = token_container.get("access_token")
    if not token:
        token = data.get("token", {}).get("access_token") if isinstance(data.get("token"), dict) else data.get("access_token")
    if not token:
        raise RuntimeError(f"Login response has no token: {data}")
    print(f"[OK] Login success, Token: {token[:20]}...")
    return token


def _yaml_value_str(val: object) -> str:
    """将值转为 YAML 安全的字符串表示。"""
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    return f'"{val}"'


def _write_yaml_dict(buf, data: dict, indent: int):
    """递归写入 YAML 字典。"""
    prefix = "  " * indent
    for k, v in data.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            buf.write(f"{key}:\n")
            _write_yaml_dict(buf, v, indent + 1)
        elif isinstance(v, list):
            buf.write(f"{key}:\n")
            for item in v:
                if isinstance(item, dict):
                    buf.write(f"{prefix}  -\n")
                    _write_yaml_dict(buf, item, indent + 2)
                elif isinstance(item, str):
                    buf.write(f'{prefix}  - "{item}"\n')
                else:
                    buf.write(f"{prefix}  - {_yaml_value_str(item)}\n")
        elif isinstance(v, str):
            buf.write(f'{key}: "{v}"\n')
        elif isinstance(v, bool):
            buf.write(f"{key}: {'true' if v else 'false'}\n")
        elif v is not None:
            buf.write(f"{key}: {v}\n")


def _write_fixture_actions(buf, actions: list, indent: int, title: str):
    """写入 setup/teardown 动作列表。"""
    if not actions:
        return
    buf.write(f"{'  ' * indent}{title}:\n")
    for item in actions:
        if isinstance(item, dict):
            for action_type, config in item.items():
                buf.write(f"{'  ' * indent}  - {action_type}:\n")
                if isinstance(config, dict):
                    _write_yaml_dict(buf, config, indent + 2)


def generate_yaml_content(case: dict, suite: dict) -> str:
    """为单个用例生成完整的 YAML 内容（包含套件元数据、setup、teardown）。"""
    import io

    buf = io.StringIO()

    # 套件元数据
    buf.write(f'name: "{suite.get("name", "unnamed")}"\n')
    desc = suite.get("description", "")
    if desc:
        for line in desc.strip().split("\n"):
            if line:
                buf.write(f'description: "{line.strip()}"\n')

    base_url = suite.get("base_url", "{{env.base_url}}")
    buf.write(f'base_url: "{base_url}"\n')

    # 全局变量
    variables = suite.get("variables", {})
    if variables:
        buf.write("variables:\n")
        for k, v in variables.items():
            buf.write(f'  {k}: {_yaml_value_str(v)}\n')

    # 标签
    suite_tags = suite.get("tags", [])
    if suite_tags:
        tag_str = ", ".join(suite_tags)
        buf.write(f"tags: [{tag_str}]\n")

    # ── setup / teardown 块（关键修复！）──
    _write_fixture_actions(buf, suite.get("setup", []), 0, "setup")
    _write_fixture_actions(buf, suite.get("teardown", []), 0, "teardown")

    buf.write("cases:\n")

    # 单个用例
    case_name = case.get("name", "unnamed")
    buf.write(f'  - name: "{case_name}"\n')
    desc_c = case.get("description", "")
    if desc_c:
        buf.write(f'    description: "{desc_c}"\n')

    case_tags = case.get("tags", [])
    if case_tags:
        tag_str = ", ".join(case_tags)
        buf.write(f"    tags: [{tag_str}]\n")

    buf.write(f'    priority: {case.get("priority", "P1")}\n')

    # request
    request = case.get("request", {})
    buf.write("    request:\n")
    method = request.get("method", "GET")
    buf.write(f"      method: {method}\n")
    path = request.get("path", "/")
    buf.write(f'      path: "{path}"\n')

    headers = request.get("headers", {})
    if headers:
        buf.write("      headers:\n")
        for hk, hv in headers.items():
            if isinstance(hv, str) and ("{{" in hv):
                # 模板变量需要引号保护
                hv_escaped = hv.replace('"', '')
                buf.write(f'        {hk}: "{hv_escaped}"\n')
            elif isinstance(hv, str):
                buf.write(f'        {hk}: "{hv}"\n')
            else:
                buf.write(f"        {hk}: {hv}\n")

    params = request.get("params", {})
    if params:
        buf.write("      params:\n")
        for pk, pv in params.items():
            buf.write(f'        {pk}: {_yaml_value_str(pv)}\n')

    body = request.get("body")
    if body is not None:
        buf.write("      body:\n")
        if isinstance(body, dict):
            _write_yaml_dict(buf, body, 4)
        elif isinstance(body, str):
            buf.write(f'        "{body}"\n')

    # expect
    expect = case.get("expect", {})
    buf.write("    expect:\n")
    status_code = expect.get("status_code")
    if status_code is not None:
        buf.write(f"      status_code: {status_code}\n")

    jsonpath = expect.get("jsonpath", {})
    if jsonpath:
        buf.write("      jsonpath:\n")
        _write_yaml_dict(buf, jsonpath, 4)

    # extract
    extract = case.get("extract", {})
    if extract:
        buf.write("    extract:\n")
        for ek, ev in extract.items():
            buf.write(f'      {ek}: "{ev}"\n')

    # case-level setup/teardown
    _write_fixture_actions(buf, case.get("setup", []), 2, "setup")
    _write_fixture_actions(buf, case.get("teardown", []), 2, "teardown")

    # variables (case-level)
    cvars = case.get("variables", {})
    if cvars:
        buf.write("    variables:\n")
        for ck, cv in cvars.items():
            buf.write(f'      {ck}: {_yaml_value_str(cv)}\n')

    return buf.getvalue()


def import_cases():
    """主流程：读取 YAML → 遍历 cases → POST API。"""
    if not YAML_PATH.exists():
        print(f"[ERROR] File not found: {YAML_PATH}")
        sys.exit(1)

    raw = YAML_PATH.read_text(encoding="utf-8")
    suite = yaml.safe_load(raw)
    cases = suite.get("cases", [])

    if not cases:
        print("[ERROR] No cases found in YAML")
        sys.exit(1)

    print(f"[INFO] Found {len(cases)} cases\n")

    with httpx.Client(timeout=30) as client:
        token = login(client)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        success = 0
        skipped = 0
        failed = 0

        for i, case in enumerate(cases, 1):
            name = case.get("name", f"case_{i}")
            desc = case.get("description", "")
            tags = case.get("tags", [])
            priority = case.get("priority", "P1")

            # 生成单个用例的 YAML 内容
            try:
                yaml_content = generate_yaml_content(case, suite)
            except Exception as e:
                print(f"[WARN] [{i:2d}] YAML gen failed: {name} - {e}")
                skipped += 1
                continue

            payload = {
                "name": name,
                "description": desc,
                "tags": tags,
                "priority": priority,
                "yaml_content": yaml_content,
                "suite_name": suite.get("name", ""),
            }

            try:
                resp = client.post(
                    f"{API_BASE}/api/v1/cases",
                    json=payload,
                    headers=headers,
                )

                if resp.status_code in (200, 201):
                    resp_data = resp.json()
                    case_id = resp_data.get("data", {}).get("id", "?")
                    print(f"[OK] [{i:2d}] Imported: {name}  (id={case_id[:8]}...)")
                    success += 1
                elif resp.status_code == 409:
                    print(f"[SKIP] [{i:2d}] Already exists: {name}")
                    skipped += 1
                else:
                    detail = resp.text[:200]
                    print(f"[FAIL] [{i:2d}] Import failed: {name}  HTTP {resp.status_code} - {detail}")
                    failed += 1
            except Exception as e:
                print(f"[FAIL] [{i:2d}] Request error: {name} - {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"[DONE] Import: success={success} skip={skipped} fail={failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    import_cases()
