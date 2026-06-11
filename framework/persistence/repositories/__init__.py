"""Repository 集合入口"""

from framework.persistence.repositories.base import BaseRepository
from framework.persistence.repositories.case_repo import CaseRepository
from framework.persistence.repositories.environment_repo import EnvironmentRepository
from framework.persistence.repositories.execution_repo import (
    ExecutionRepository,
    ExecutionResultRepository,
)
from framework.persistence.repositories.mock_rule_repo import MockRuleRepository
from framework.persistence.repositories.report_repo import ReportRepository
from framework.persistence.repositories.schedule_repo import ScheduleRepository
from framework.persistence.repositories.suite_repo import SuiteRepository
from framework.persistence.repositories.user_repo import ProjectRepository, UserRepository

__all__ = [
    "BaseRepository",
    "CaseRepository",
    "EnvironmentRepository",
    "ExecutionRepository",
    "ExecutionResultRepository",
    "MockRuleRepository",
    "ProjectRepository",
    "ReportRepository",
    "ScheduleRepository",
    "SuiteRepository",
    "UserRepository",
]
