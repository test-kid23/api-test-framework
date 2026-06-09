"""API 路由模块"""

from api.routers import (
    analytics,
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
    "analytics",
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
