"""数据持久化层集成验证测试"""

import pytest

from framework.persistence.database import create_async_engine, create_async_session_factory
from framework.persistence.models import TestCaseModel
from framework.persistence.repositories import CaseRepository


@pytest.mark.asyncio(loop_scope="module")
async def test_create_and_query_case():
    """验证：创建用例 → 查询 → 删除 全流程"""
    engine = create_async_engine(
        {"driver": "sqlite", "database": "data/autotest.db"}, echo=False
    )
    session_factory = create_async_session_factory(engine)

    async with session_factory() as session:
        repo = CaseRepository(session)

        # 1. 插入
        case = TestCaseModel(
            name="验证登录接口",
            description="对 /api/login 的 POST 请求进行功能验证",
            yaml_content="name: login_test\nmethod: POST\npath: /api/login",
            tags='["smoke","auth","login"]',
            priority="P0",
        )
        created = await repo.create(case)
        await session.commit()
        assert created.id is not None
        assert created.name == "验证登录接口"

        # 2. 主键查询
        found = await repo.get(created.id)
        assert found is not None
        assert found.name == "验证登录接口"
        assert found.priority == "P0"

        # 3. 列表查询（分页 + 过滤）
        items, total = await repo.list(limit=10, priority="P0")
        assert total >= 1
        assert len(items) >= 1

        # 4. 删除
        deleted = await repo.delete_by_id(created.id)
        await session.commit()
        assert deleted is True

        # 5. 确认已删除
        gone = await repo.get(created.id)
        assert gone is None

    await engine.dispose()
