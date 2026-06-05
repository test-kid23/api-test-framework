"""套件 Repository"""

from __future__ import annotations

from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.repositories.base import BaseRepository


class SuiteRepository(BaseRepository[TestSuiteModel]):
    """测试套件数据访问层。"""

    model_class = TestSuiteModel
