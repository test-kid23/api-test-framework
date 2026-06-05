"""用例 Repository"""

from __future__ import annotations

from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.repositories.base import BaseRepository


class CaseRepository(BaseRepository[TestCaseModel]):
    """测试用例数据访问层。"""

    model_class = TestCaseModel
