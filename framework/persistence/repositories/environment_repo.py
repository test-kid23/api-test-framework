"""环境配置 Repository"""

from __future__ import annotations

import os

from sqlalchemy import func, select

from framework.persistence.models.environment import EnvironmentModel
from framework.persistence.repositories.base import BaseRepository
from framework.utils.field_encryptor import FieldEncryptor
from framework.utils.logger import Logger


# 敏感字段名集合（variables dict 中需要加密的 key）
SENSITIVE_VARIABLE_KEYS: frozenset[str] = frozenset({
    "password",
    "token",
    "api_key",
    "apikey",
    "secret",
    "access_token",
    "refresh_token",
    "private_key",
})


def _get_encryptor() -> FieldEncryptor | None:
    """获取加密器实例.

    若环境变量未设置 AUTOTEST_ENCRYPTION_KEY 则返回 None（降级：明文存储）。

    Returns:
        FieldEncryptor 实例或 None.
    """
    try:
        return FieldEncryptor.from_env()
    except Exception:
        Logger.get("environment_repo").warning("encryptor_init_failed")
        return None


class EnvironmentRepository(BaseRepository[EnvironmentModel]):
    """环境配置数据访问层。"""

    model_class = EnvironmentModel

    def __init__(self, session, *, encryptor: FieldEncryptor | None = None) -> None:
        """初始化.

        Args:
            session: SQLAlchemy 异步会话.
            encryptor: 字段加密器实例，若为 None 则自动从环境变量获取.
        """
        super().__init__(session)
        self._encryptor = encryptor if encryptor is not None else _get_encryptor()
        self._logger = Logger.get("environment_repo")

    async def find_by_name(self, name: str) -> EnvironmentModel | None:
        """按名称查找环境（精确匹配）。

        Args:
            name: 环境名称。

        Returns:
            匹配的 EnvironmentModel，未找到返回 None。
        """
        stmt = select(self.model_class).where(self.model_class.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_name_ignore_case(self, name: str) -> EnvironmentModel | None:
        """按名称查找环境（忽略大小写）。

        作为 find_by_name 的容错补充，在精确匹配未命中时尝试。

        Args:
            name: 环境名称（忽略大小写比较）。

        Returns:
            匹配的 EnvironmentModel，未找到返回 None。
        """
        stmt = select(self.model_class).where(
            func.lower(self.model_class.name) == name.lower()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def name_exists(self, name: str, exclude_id: str | None = None) -> bool:
        """检查环境名称是否已存在。

        Args:
            name: 待检查的名称。
            exclude_id: 排除的环境 ID（用于更新时不校验自身）。

        Returns:
            True 表示名称已存在。
        """
        stmt = select(func.count(self.model_class.id)).where(
            self.model_class.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(self.model_class.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    # ── 加密/解密/脱敏 ──────────────────────────────────────

    def encrypt_variables(self, variables: dict | None) -> dict | None:
        """加密 variables 中的敏感字段.

        对 SENSITIVE_VARIABLE_KEYS 中定义的 key 进行加密处理。
        如果加密器未初始化，原样返回。

        Args:
            variables: 环境变量字典.

        Returns:
            加密后的字典（原地修改 + 返回）.
        """
        if variables is None or self._encryptor is None:
            return variables
        for key in SENSITIVE_VARIABLE_KEYS:
            if key in variables and isinstance(variables[key], str):
                value = variables[key]
                if not FieldEncryptor.is_encrypted(value):
                    variables[key] = self._encryptor.encrypt(value)
        return variables

    def decrypt_variables(self, variables: dict | None) -> dict | None:
        """解密 variables 中的敏感字段.

        供执行引擎在运行时使用，还原明文。

        Args:
            variables: 环境变量字典.

        Returns:
            解密后的字典（原地修改 + 返回）.
        """
        if variables is None or self._encryptor is None:
            return variables
        for key in SENSITIVE_VARIABLE_KEYS:
            if key in variables and isinstance(variables[key], str):
                value = variables[key]
                if FieldEncryptor.is_encrypted(value):
                    try:
                        variables[key] = self._encryptor.decrypt(value)
                    except Exception:
                        self._logger.warning(
                            "decrypt_variable_failed",
                            key=key,
                        )
        return variables

    def mask_variables(self, variables: dict | None) -> dict | None:
        """脱敏 variables 中的敏感字段.

        供 API 查询返回时使用，将加密值或明文值替换为脱敏占位符。

        Args:
            variables: 环境变量字典.

        Returns:
            脱敏后的字典（返回新字典，不修改原始数据）.
        """
        if variables is None:
            return None
        encryptor = self._encryptor
        masked: dict = {}
        for k, v in variables.items():
            if k in SENSITIVE_VARIABLE_KEYS and isinstance(v, str):
                masked[k] = encryptor.mask(v) if encryptor else "***"
            else:
                masked[k] = v
        return masked

    # ── 覆写 CRUD 方法以自动加密 ─────────────────────────

    async def create(self, model: EnvironmentModel) -> EnvironmentModel:
        """创建环境（自动加密敏感字段）.

        Args:
            model: 环境模型实例.

        Returns:
            创建后的模型.
        """
        if model.variables is not None:
            model.variables = self.encrypt_variables(dict(model.variables))
        return await super().create(model)

    async def update(self, model: EnvironmentModel) -> EnvironmentModel:
        """更新环境（自动加密敏感字段）.

        Args:
            model: 环境模型实例.

        Returns:
            更新后的模型.
        """
        if model.variables is not None:
            model.variables = self.encrypt_variables(dict(model.variables))
        return await super().update(model)
