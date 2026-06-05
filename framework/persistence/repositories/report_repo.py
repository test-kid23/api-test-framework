"""报告 Repository"""

from __future__ import annotations

from framework.persistence.models.report import ReportModel
from framework.persistence.repositories.base import BaseRepository


class ReportRepository(BaseRepository[ReportModel]):
    """测试报告数据访问层。"""

    model_class = ReportModel
