"""ORM 模型集合入口。

导入所有模型以确保 Base.metadata 能发现所有表。
"""

from framework.persistence.models.base import Base
from framework.persistence.models.environment import EnvironmentModel
from framework.persistence.models.execution import ExecutionModel, ExecutionResultModel
from framework.persistence.models.report import ReportModel
from framework.persistence.models.schedule import ScheduleModel
from framework.persistence.models.test_case import TestCaseModel
from framework.persistence.models.test_suite import TestSuiteModel
from framework.persistence.models.user import ProjectModel, UserModel, UserProjectModel

__all__ = [
    "Base",
    "EnvironmentModel",
    "ExecutionModel",
    "ExecutionResultModel",
    "ProjectModel",
    "ReportModel",
    "ScheduleModel",
    "TestCaseModel",
    "TestSuiteModel",
    "UserModel",
    "UserProjectModel",
]
