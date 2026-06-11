"""API 路由模块"""

from api.routers import (
    analytics,
    assertions,
    auth,
    cases,
    coverage,
    environments,
    executions,
    mocks,
    recorder,
    reports,
    schedules,
    suites,
    users,
    workers,
)

__all__ = [
    "analytics",
    "assertions",
    "auth",
    "cases",
    "coverage",
    "environments",
    "executions",
    "mocks",
    "recorder",
    "reports",
    "schedules",
    "suites",
    "users",
    "workers",
]
