"""Mock 模块 — 轻量级 HTTP Mock 服务

提供内嵌的 Mock 服务器，支持通过 API 动态注册规则，
与测试用例的 fixture 系统联动。

核心组件:
- MockRule: 规则数据模型
- MockRuleStore: 线程安全的规则存储器
- create_mock_app(): 创建 FastAPI Mock 子应用
- MockPlugin: 集成 PluginManager 的插件
- get_mock_store(): 获取全局规则存储器单例

用法:
    # 注册规则
    store = get_mock_store()
    store.register(url_pattern="/api/users/*", method="POST", status_code=201,
                   response_body={"id": 1})

    # 挂载到 FastAPI 主应用
    from framework.mock.server import create_mock_app
    app.mount("/_mock", create_mock_app())
"""

from framework.mock.models import MockRule
from framework.mock.plugin import MockPlugin
from framework.mock.rule_store import MockRuleStore, get_mock_store, reset_mock_store
from framework.mock.server import create_mock_app

__all__ = [
    "MockRule",
    "MockRuleStore",
    "MockPlugin",
    "create_mock_app",
    "get_mock_store",
    "reset_mock_store",
]
