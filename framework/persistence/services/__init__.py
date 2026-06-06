"""服务层入口 — 封装跨 Repository 的业务逻辑和聚合查询。

提供：
- ReportService: 趋势分析、Top N 失败等报告聚合查询
"""

from framework.persistence.services.report_service import ReportService

__all__ = [
    "ReportService",
]
