"""API 路由模块"""

from api.routers import (
    assertions,
    auth,
    cases,
    environments,
    executions,
    mocks,
    recorder,
    reports,
    schedules,
    suites,
    users,
)

__all__ = [
    "assertions",
    "auth",
    "cases",
    "environments",
    "executions",
    "mocks",
    "recorder",
    "reports",
    "schedules",
    "suites",
    "users",
]
