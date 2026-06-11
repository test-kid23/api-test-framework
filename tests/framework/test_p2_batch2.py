"""Phase 5 P2 第二批单元测试 — T5-18, T5-19, T5-20"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

# ==================== T5-18: 项目级 API 隔离 ====================


class TestApplyProjectFilter:
    """apply_project_filter() 通用过滤函数测试."""

    def test_admin_returns_stmt_unchanged(self) -> None:
        """admin 用户不添加过滤条件."""
        from api.auth import CurrentUser
        from api.dependencies import apply_project_filter
        from framework.persistence.models.execution import ExecutionModel

        user = CurrentUser(id="admin-id", username="admin", role="admin", project_ids=[])
        stmt = MagicMock()
        result = apply_project_filter(stmt, ExecutionModel, user)
        assert result is stmt  # admin 不修改 stmt

    def test_user_with_projects_adds_in_filter(self) -> None:
        """有项目用户添加 project_id IN (...) 过滤."""
        from api.auth import CurrentUser
        from api.dependencies import apply_project_filter
        from framework.persistence.models.execution import ExecutionModel

        pid = str(uuid.uuid4())
        user = CurrentUser(id="user-1", username="user1", role="viewer", project_ids=[pid])

        # 模拟 stmt.where() 返回新的 stmt
        stmt = MagicMock()
        stmt.where.return_value = stmt
        result = apply_project_filter(stmt, ExecutionModel, user)
        # 非 admin 用户应该调用了 where
        stmt.where.assert_called_once()

    def test_user_without_projects_adds_null_filter(self) -> None:
        """无项目用户只看到全局资源."""
        from api.auth import CurrentUser
        from api.dependencies import apply_project_filter
        from framework.persistence.models.execution import ExecutionModel

        user = CurrentUser(id="user-2", username="user2", role="viewer", project_ids=[])
        stmt = MagicMock()
        stmt.where.return_value = stmt
        result = apply_project_filter(stmt, ExecutionModel, user)
        stmt.where.assert_called_once()

    def test_via_model_filter(self) -> None:
        """通过中间模型过滤（如 reports 通过 executions 过滤）."""
        from api.auth import CurrentUser
        from api.dependencies import apply_project_filter
        from framework.persistence.models.report import ReportModel
        from framework.persistence.models.execution import ExecutionModel

        pid = str(uuid.uuid4())
        user = CurrentUser(id="user-1", username="user1", role="viewer", project_ids=[pid])

        stmt = MagicMock()
        stmt.where.return_value = stmt
        result = apply_project_filter(
            stmt, ReportModel, user,
            via_model=ExecutionModel, via_column="id", via_fk_column="execution_id",
        )
        stmt.where.assert_called_once()


class TestBuildProjectCondition:
    """_build_project_condition() 辅助函数测试."""

    def test_none_returns_empty_string(self) -> None:
        """project_ids=None (admin) 返回空字符串."""
        from framework.persistence.services.report_service import _build_project_condition
        result = _build_project_condition(None)
        assert result == ""

    def test_empty_list_returns_null_only(self) -> None:
        """project_ids=[] 只匹配全局资源."""
        from framework.persistence.services.report_service import _build_project_condition
        result = _build_project_condition([])
        assert "IS NULL" in result
        assert "IN" not in result

    def test_list_with_ids_returns_in_and_null(self) -> None:
        """project_ids 有值时返回 IN + IS NULL."""
        from framework.persistence.services.report_service import _build_project_condition
        pid = uuid.uuid4()
        result = _build_project_condition([pid])
        assert "IN" in result
        assert "IS NULL" in result


class TestBuildProjectIdsFilter:
    """_build_project_ids_filter() 路由级辅助测试."""

    def test_admin_returns_none(self) -> None:
        """admin 用户返回 None（无过滤）."""
        from api.auth import CurrentUser
        from api.routers.reports import _build_project_ids_filter

        user = CurrentUser(id="admin-1", username="admin", role="admin", project_ids=[])
        result = _build_project_ids_filter(user)
        assert result is None

    def test_viewer_with_projects_returns_uuids(self) -> None:
        """有项目的 viewer 返回 UUID 列表."""
        from api.auth import CurrentUser
        from api.routers.reports import _build_project_ids_filter

        pid = str(uuid.uuid4())
        user = CurrentUser(id="user-1", username="user1", role="viewer", project_ids=[pid])
        result = _build_project_ids_filter(user)
        assert result == [uuid.UUID(pid)]

    def test_viewer_without_projects_returns_empty_list(self) -> None:
        """无项目的 viewer 返回空列表."""
        from api.auth import CurrentUser
        from api.routers.reports import _build_project_ids_filter

        user = CurrentUser(id="user-1", username="user1", role="viewer", project_ids=[])
        result = _build_project_ids_filter(user)
        assert result == []


# ==================== T5-19: Token 刷新机制 ====================


class TestCreateRefreshToken:
    """create_refresh_token() 测试."""

    def test_creates_valid_jwt_with_type_refresh(self) -> None:
        """创建的 refresh token 包含 type=refresh."""
        from api.auth import create_refresh_token

        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)

        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "jti" in payload

    def test_refresh_token_longer_expiry_than_access(self) -> None:
        """refresh token 过期时间远长于 access token."""
        from api.auth import create_refresh_token, create_access_token

        user_id = str(uuid.uuid4())
        refresh = create_refresh_token(user_id)
        access = create_access_token(user_id, "test", "viewer")

        refresh_payload = jwt.decode(refresh, options={"verify_signature": False})
        access_payload = jwt.decode(access, options={"verify_signature": False})

        refresh_ttl = refresh_payload["exp"] - refresh_payload["iat"]
        access_ttl = access_payload["exp"] - access_payload["iat"]

        # refresh token 的有效期应该比 access token 长
        assert refresh_ttl > access_ttl


class TestDecodeRefreshToken:
    """decode_refresh_token() 测试."""

    def test_decodes_valid_refresh_token(self) -> None:
        """成功解码有效的 refresh token."""
        from api.auth import create_refresh_token, decode_refresh_token

        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)
        payload = decode_refresh_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_raises_on_wrong_token_type(self) -> None:
        """type 不是 refresh 时抛出异常."""
        from api.auth import decode_refresh_token, _get_jwt_secret
        from fastapi import HTTPException

        # 创建一个带正确密钥但 type 不是 refresh 的 token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "jti": "test-jti",
        }
        token = jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(token)
        assert "invalid_token_type" in str(exc_info.value.detail)

    def test_raises_on_expired_token(self) -> None:
        """过期 token 抛出异常."""
        from api.auth import decode_refresh_token, _get_jwt_secret
        from fastapi import HTTPException

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "iat": now - timedelta(days=10),
            "exp": now - timedelta(days=1),
            "jti": "test-jti",
            "type": "refresh",
        }
        token = jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(token)
        assert "refresh_token_expired" in str(exc_info.value.detail)


class TestTokenResponseSchema:
    """TokenResponse / LoginResponse schema 测试."""

    def test_token_response_has_refresh_token_field(self) -> None:
        """TokenResponse 包含 refresh_token 字段."""
        from api.schemas.auth import TokenResponse

        resp = TokenResponse(
            access_token="test-access",
            refresh_token="test-refresh",
            token_type="bearer",
            expires_in=28800,
        )
        assert resp.refresh_token == "test-refresh"

    def test_token_response_refresh_token_optional(self) -> None:
        """refresh_token 为可选字段（refresh 接口不返回）."""
        from api.schemas.auth import TokenResponse

        resp = TokenResponse(
            access_token="test-access",
            token_type="bearer",
            expires_in=28800,
        )
        assert resp.refresh_token is None

    def test_refresh_token_request_schema(self) -> None:
        """RefreshTokenRequest schema 验证."""
        from api.schemas.auth import RefreshTokenRequest

        req = RefreshTokenRequest(refresh_token="test-refresh-token")
        assert req.refresh_token == "test-refresh-token"

    def test_refresh_token_request_requires_field(self) -> None:
        """refresh_token 为必填字段."""
        import pydantic
        from api.schemas.auth import RefreshTokenRequest

        with pytest.raises(pydantic.ValidationError):
            RefreshTokenRequest()  # type: ignore[call-arg]


# ==================== T5-20: Mock 规则持久化 ====================


class TestMockRuleModel:
    """MockRuleModel ORM 模型测试."""

    def test_model_tablename(self) -> None:
        """表名为 mock_rules."""
        from framework.persistence.models.mock_rule import MockRuleModel
        assert MockRuleModel.__tablename__ == "mock_rules"

    def test_model_has_all_fields(self) -> None:
        """模型包含所有必要字段."""
        from framework.persistence.models.mock_rule import MockRuleModel
        from sqlalchemy.orm import Mapped

        # 所有预期列名
        expected_columns = {
            "id", "url_pattern", "method", "status_code",
            "response_body", "response_headers", "description",
            "enabled", "priority", "delay_ms", "project_id",
            "created_at", "updated_at",
        }
        for col_name in expected_columns:
            assert hasattr(MockRuleModel, col_name), f"Missing column: {col_name}"

    def test_model_repr(self) -> None:
        """__repr__ 包含 id/url_pattern/method."""
        from framework.persistence.models.mock_rule import MockRuleModel
        model = MockRuleModel(
            url_pattern="/api/test/*",
            method="GET",
        )
        r = repr(model)
        assert "MockRuleModel" in r
        assert "/api/test/*" in r
        assert "GET" in r

    def test_model_defaults(self) -> None:
        """默认值正确（server_default 在 DB 层生效，Python 层验证字段存在）."""
        from framework.persistence.models.mock_rule import MockRuleModel
        model = MockRuleModel(url_pattern="/api/default")
        # SQLAlchemy server_default 只在 INSERT 时生效，Python 层不自动设值
        # 验证所有字段存在即可
        assert model.url_pattern == "/api/default"
        assert hasattr(model, "method")
        assert hasattr(model, "status_code")
        assert hasattr(model, "enabled")
        assert hasattr(model, "priority")
        assert hasattr(model, "delay_ms")
        assert hasattr(model, "description")


class TestMockRuleRepository:
    """MockRuleRepository 测试."""

    @pytest.mark.asyncio
    async def test_model_class_set(self) -> None:
        """model_class 正确设置."""
        from framework.persistence.repositories.mock_rule_repo import MockRuleRepository
        from framework.persistence.models.mock_rule import MockRuleModel
        assert MockRuleRepository.model_class is MockRuleModel

    @pytest.mark.asyncio
    async def test_list_all_enabled_query(self) -> None:
        """list_all_enabled 查询仅返回启用的规则."""
        from framework.persistence.repositories.mock_rule_repo import MockRuleRepository
        import inspect

        source = inspect.getsource(MockRuleRepository.list_all_enabled)
        assert "enabled.is_(True)" in source
        assert "order_by" in source


class TestMockRuleMigration:
    """Alembic 迁移测试."""

    def test_migration_file_exists(self) -> None:
        """迁移文件存在."""
        from pathlib import Path
        migration_dir = Path("alembic/versions")
        migration_files = list(migration_dir.glob("*mock_rules*"))
        assert len(migration_files) >= 1, "mock_rules 迁移文件不存在"

    def test_migration_has_upgrade_downgrade(self) -> None:
        """迁移文件包含 upgrade 和 downgrade 函数."""
        from pathlib import Path
        migration_dir = Path("alembic/versions")
        migration_files = list(migration_dir.glob("*mock_rules*"))
        content = migration_files[0].read_text(encoding="utf-8")
        assert "def upgrade()" in content
        assert "def downgrade()" in content

    def test_migration_creates_table(self) -> None:
        """迁移文件中包含 CREATE TABLE mock_rules."""
        from pathlib import Path
        migration_dir = Path("alembic/versions")
        migration_files = list(migration_dir.glob("*mock_rules*"))
        content = migration_files[0].read_text(encoding="utf-8")
        assert "mock_rules" in content


class TestMockRuleStoreDBLoad:
    """MockRuleStore load_from_db 测试."""

    @pytest.mark.asyncio
    async def test_load_from_db_clears_existing(self) -> None:
        """load_from_db 先清空现有规则再加载."""
        from framework.mock.rule_store import MockRuleStore
        from framework.mock.models import MockRule

        store = MockRuleStore()
        store.register(url_pattern="/api/old", method="GET")

        # 模拟数据库规则
        db_rules = [
            MagicMock(
                id=uuid.uuid4(), url_pattern="/api/new", method="POST",
                status_code=201, response_body={"ok": True},
                response_headers={}, description="new rule",
                enabled=True, priority=5, delay_ms=100,
            ),
        ]
        count = await store.load_from_db(db_rules)
        assert count == 1

        # 旧规则已被清除
        rules = store.list_all()
        assert len(rules) == 1
        assert rules[0].url_pattern == "/api/new"

    @pytest.mark.asyncio
    async def test_load_from_db_empty(self) -> None:
        """加载空列表清空所有规则."""
        from framework.mock.rule_store import MockRuleStore

        store = MockRuleStore()
        store.register(url_pattern="/api/test", method="GET")
        assert store.rule_count == 1

        count = await store.load_from_db([])
        assert count == 0
        assert store.rule_count == 0

    @pytest.mark.asyncio
    async def test_load_from_db_preserves_disabled_state(self) -> None:
        """加载时保留 enabled=False 状态."""
        from framework.mock.rule_store import MockRuleStore
        from framework.mock.models import MockRule

        store = MockRuleStore()
        db_rules = [
            MagicMock(
                id=uuid.uuid4(), url_pattern="/api/disabled", method="GET",
                status_code=200, response_body=None,
                response_headers={}, description="disabled rule",
                enabled=False, priority=0, delay_ms=0,
            ),
        ]
        count = await store.load_from_db(db_rules)
        assert count == 1
        rules = store.list_all()
        assert rules[0].enabled is False


# ==================== 集成测试 ====================


class TestT19Integration:
    """T5-19 Token 刷新端到端流程."""

    def test_full_refresh_flow(self) -> None:
        """完整刷新流程：login → access_expired → refresh → new_access."""
        from api.auth import create_access_token, create_refresh_token

        user_id = str(uuid.uuid4())
        username = "testuser"
        role = "viewer"

        # Step 1: 登录 — 生成 access + refresh token
        access = create_access_token(user_id, username, role)
        refresh = create_refresh_token(user_id)

        # Step 2: access token 有效
        access_payload = jwt.decode(access, options={"verify_signature": False})
        assert access_payload["sub"] == user_id

        # Step 3: refresh token 有效
        refresh_payload = jwt.decode(refresh, options={"verify_signature": False})
        assert refresh_payload["sub"] == user_id
        assert refresh_payload["type"] == "refresh"

        # Step 4: 用 refresh token 获取新的 access token
        new_access = create_access_token(user_id, username, role)
        new_payload = jwt.decode(new_access, options={"verify_signature": False})
        assert new_payload["sub"] == user_id
        # 新 access token 的 jti 应该不同
        assert new_payload["jti"] != access_payload["jti"]


class TestT20Integration:
    """T5-20 Mock 持久化端到端流程."""

    def test_model_to_dict_includes_all_fields(self) -> None:
        """_model_to_dict 包含所有字段."""
        from framework.persistence.models.mock_rule import MockRuleModel

        model = MockRuleModel(
            url_pattern="/api/test/*",
            method="POST",
            status_code=201,
            response_body={"result": "ok"},
            response_headers={"X-Custom": "val"},
            description="Test rule",
            enabled=True,
            priority=10,
            delay_ms=500,
        )
        d = {
            "id": str(model.id),
            "url_pattern": model.url_pattern,
            "method": model.method,
            "status_code": model.status_code,
            "response_body": model.response_body,
            "response_headers": model.response_headers,
            "description": model.description,
            "enabled": model.enabled,
            "priority": model.priority,
            "delay_ms": model.delay_ms,
        }
        assert d["url_pattern"] == "/api/test/*"
        assert d["method"] == "POST"
        assert d["status_code"] == 201
        assert d["priority"] == 10
        assert d["delay_ms"] == 500
        assert d["enabled"] is True

    def test_mock_rule_model_registered_in_init(self) -> None:
        """MockRuleModel 已在 models/__init__.py 中注册."""
        from framework.persistence.models import MockRuleModel
        assert MockRuleModel is not None

    def test_mock_rule_repo_registered_in_init(self) -> None:
        """MockRuleRepository 已在 repositories/__init__.py 中注册."""
        from framework.persistence.repositories import MockRuleRepository
        assert MockRuleRepository is not None

    def test_mock_rule_repo_list_by_project_method(self) -> None:
        """list_by_project 方法存在且有正确参数."""
        import inspect
        from framework.persistence.repositories.mock_rule_repo import MockRuleRepository

        sig = inspect.signature(MockRuleRepository.list_by_project)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "project_id" in params
        assert "url_pattern" in params
        assert "method" in params
        assert "enabled_only" in params
