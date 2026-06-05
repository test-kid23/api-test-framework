"""数据库模块 — 连接管理 + SQL 执行 + 数据库断言"""

from __future__ import annotations

from typing import Any

from framework.models import AssertResult, DBAction, DBAssertItem, ExtractItem
from framework.utils.logger import Logger
from framework.utils.template import TemplateEngine

logger = Logger.get("db")

# 延迟导入 SQLAlchemy（可选依赖）
_has_sqlalchemy = False
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine  # noqa: F401
    from sqlalchemy.pool import QueuePool  # noqa: F401

    _has_sqlalchemy = True
except ImportError:
    pass


class DBConnectionManager:
    """数据库连接管理器 — 支持多数据源"""

    def __init__(self) -> None:
        self._engines: dict[str, Any] = {}

    def get_engine(self, name: str, config: dict[str, Any]) -> Any:
        """获取或创建数据库引擎（连接池）"""
        if not _has_sqlalchemy:
            raise ImportError(
                "SQLAlchemy 未安装，请运行: pip install SQLAlchemy pymysql psycopg2-binary"
            )

        if name not in self._engines:
            url = self._build_url(config)
            self._engines[name] = create_engine(
                url,
                pool_size=config.get("pool_size", 5),
                max_overflow=config.get("max_overflow", 10),
                pool_recycle=config.get("pool_recycle", 3600),
                echo=config.get("echo", False),
            )
            logger.info(f"创建数据库连接: {name} ({config.get('type', 'unknown')})")
        return self._engines[name]

    def close_all(self) -> None:
        """关闭所有连接"""
        for name, engine in self._engines.items():
            engine.dispose()
            logger.debug(f"关闭数据库连接: {name}")
        self._engines.clear()

    @staticmethod
    def _build_url(config: dict[str, Any]) -> str:
        """构建数据库连接 URL"""
        db_type = config.get("type", "mysql")
        if db_type == "mysql":
            return (
                f"mysql+pymysql://{config['user']}:{config['password']}"
                f"@{config['host']}:{config['port']}/{config['database']}"
                f"?charset={config.get('charset', 'utf8mb4')}"
            )
        elif db_type == "postgresql":
            return (
                f"postgresql+psycopg2://{config['user']}:{config['password']}"
                f"@{config['host']}:{config['port']}/{config['database']}"
            )
        elif db_type == "sqlite":
            return f"sqlite:///{config['database']}"
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")


class DBExecutor:
    """数据库操作执行器"""

    def __init__(
        self,
        connection_manager: DBConnectionManager,
        db_configs: dict[str, dict[str, Any]],
        template_engine: TemplateEngine | None = None,
    ) -> None:
        self._conn_mgr = connection_manager
        self._db_configs = db_configs
        self._template = template_engine or TemplateEngine()

    def execute(self, action: DBAction, variables: dict[str, Any]) -> Any:
        """执行数据库操作"""
        engine = self._conn_mgr.get_engine(
            action.connection, self._db_configs.get(action.connection, {})
        )

        # 模板替换
        rendered_sql = self._template.render(action.sql, variables)
        rendered_params = {
            k: self._template.render(str(v), variables) for k, v in action.params.items()
        }

        logger.debug(f"执行 SQL [{action.connection}]: {rendered_sql[:200]}")
        if rendered_params:
            logger.debug(f"SQL 参数: {rendered_params}")

        with engine.connect() as conn:
            result = conn.execute(text(rendered_sql), rendered_params)

            if result.returns_rows:
                if action.fetch_one:
                    row = result.fetchone()
                    return dict(row._mapping) if row else {}
                else:
                    return [dict(row._mapping) for row in result.fetchall()]
            else:
                conn.commit()
                return None

    def execute_and_extract(self, action: DBAction, variables: dict[str, Any]) -> dict[str, Any]:
        """执行 SQL 并提取变量"""
        result = self.execute(action, variables)
        if result is not None and action.extract:
            return self._extract_from_result(result, action.extract)
        return {}

    def _extract_from_result(
        self,
        result: Any,
        extracts: list[ExtractItem],
    ) -> dict[str, Any]:
        """从查询结果中提取变量"""
        extracted: dict[str, Any] = {}
        if isinstance(result, dict):
            for item in extracts:
                if item.source in result:
                    extracted[item.var_name] = result[item.source]
        elif isinstance(result, list) and len(result) > 0:
            for item in extracts:
                if item.source in result[0]:
                    extracted[item.var_name] = result[0][item.source]
        return extracted


class DBAsserter:
    """数据库断言器"""

    def __init__(
        self,
        executor: DBExecutor,
        template_engine: TemplateEngine | None = None,
    ) -> None:
        self._executor = executor
        self._template = template_engine or TemplateEngine()

    def assert_query(
        self,
        db_assert: DBAssertItem,
        variables: dict[str, Any],
    ) -> AssertResult:
        """执行查询并断言结果"""
        from framework.assertion import AssertionEngine

        action = DBAction(
            connection=db_assert.connection,
            sql=self._template.render(db_assert.sql, variables),
            fetch_one=db_assert.fetch_one,
        )

        result = self._executor.execute(action, variables)

        if result is None:
            return AssertResult(
                passed=False,
                path="db",
                expected=db_assert.expect,
                actual=None,
                operator="eq",
                message="数据库查询返回 None",
            )

        # 逐字段断言
        for field_name, expected in db_assert.expect.items():
            actual = result.get(field_name) if isinstance(result, dict) else None

            # 支持操作符语法（如 ">0"）
            if isinstance(expected, str) and expected.startswith((">", "<", "!", "~")):
                op, val = self._parse_operator(expected)
                op_func = AssertionEngine.DEFAULT_OPERATORS.get(op)
                if op_func and not op_func(actual, val):
                    return AssertResult(
                        passed=False,
                        path=f"db.{field_name}",
                        expected=expected,
                        actual=actual,
                        operator=op,
                    )
            else:
                if actual != expected:
                    return AssertResult(
                        passed=False,
                        path=f"db.{field_name}",
                        expected=expected,
                        actual=actual,
                        operator="eq",
                    )

        return AssertResult(
            passed=True,
            path="db",
            expected=db_assert.expect,
            actual=result,
            operator="eq",
        )

    @staticmethod
    def _parse_operator(expr: str) -> tuple[str, Any]:
        """解析操作符表达式，如 '>0' -> ('gt', 0)"""
        import re

        match = re.match(r"^([><=!]+)\s*(.+)$", expr)
        if not match:
            return "eq", expr

        op_str, val_str = match.groups()
        op_map = {
            ">": "gt",
            ">=": "gte",
            "<": "lt",
            "<=": "lte",
            "!=": "ne",
            "==": "eq",
        }
        op = op_map.get(op_str, "eq")

        val: float | int | str
        try:
            val_num: float = float(val_str)
            if val_num == int(val_num):
                val = int(val_num)
            else:
                val = val_num
        except ValueError:
            val = val_str

        return op, val
