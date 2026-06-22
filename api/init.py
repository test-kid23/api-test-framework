"""应用初始化 — 首次启动时自动创建默认管理员账户和默认项目

在 lifespan 启动阶段调用 init_app()，确保：
1. 所有 ORM 表已创建（Base.metadata.create_all）
2. 默认项目 "default" 存在
3. 默认管理员 "admin" 存在并绑定到默认项目
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from framework.persistence.models.base import Base
from framework.persistence.models.user import ProjectModel, UserModel, UserProjectModel
from framework.utils.logger import Logger

_log = Logger.get("api.init")


async def init_app(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """首次启动初始化：创建表、默认项目和管理员。

    幂等操作 — 多次调用不会重复创建。

    Args:
        engine: SQLAlchemy AsyncEngine（用于 DDL 建表操作）。
        session_factory: SQLAlchemy async session factory（用于业务数据操作）。
    """
    # 1. 确保所有表已创建
    # 注意：使用 AsyncEngine.begin() 而非 session.get_bind()，
    # 因为 session.get_bind() 在 aiosqlite + SQLAlchemy 2.0.41 下返回同步引擎，
    # 导致 await engine.connect() 报 MissingGreenlet 错误。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _log.info("init_db_tables_checked")

    # 2. 创建/获取默认项目和管理员（使用独立 session）
    session = session_factory()
    try:
        from framework.config import ConfigLoader

        loader = ConfigLoader()
        project_config, _ = loader.load()
        auth_config = project_config

        default_admin_user = getattr(auth_config, "jwt_secret", "admin")
        default_admin_pass = "admin123"
        default_project_name = "default"

        # 从配置文件读取（如果配置了 auth.default_admin）
        try:
            config_raw = loader._load_yaml("config.yaml")
            auth_raw = config_raw.get("auth", {})
            default_admin_raw = auth_raw.get("default_admin", {})
            if default_admin_raw:
                default_admin_user = default_admin_raw.get("username", "admin")
                default_admin_pass = default_admin_raw.get("password", "admin123")
                default_project_name = default_admin_raw.get("project", "default")
        except Exception:
            pass

        # 3. 确保默认项目存在
        from sqlalchemy import select

        stmt = select(ProjectModel).where(ProjectModel.name == default_project_name)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            project = ProjectModel(
                name=default_project_name,
                description="默认项目（系统自动创建）",
            )
            session.add(project)
            await session.flush()
            _log.info("init_default_project_created", project_name=default_project_name)

        # 4. 确保默认管理员存在
        from api.auth import hash_password

        stmt = select(UserModel).where(UserModel.username == default_admin_user)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = UserModel(
                username=default_admin_user,
                password_hash=hash_password(default_admin_pass),
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.flush()
            _log.info(
                "init_default_admin_created",
                username=default_admin_user,
                password_hint="请登录后立即修改默认密码",
            )
        else:
            # 仅在哈希前缀不匹配时重新哈希（bcrypt 版本/前缀变更）
            # 避免每次启动都执行昂贵的 verify_password 操作
            if not admin.password_hash.startswith("$2b$") and not admin.password_hash.startswith("$2a$"):
                _log.warning("admin_password_rehash", reason="hash prefix mismatch, regenerating")
                admin.password_hash = hash_password(default_admin_pass)

            # 5. 绑定管理员到默认项目
            stmt = select(UserProjectModel).where(
                UserProjectModel.user_id == admin.id,
                UserProjectModel.project_id == project.id,
            )
            result = await session.execute(stmt)
            assoc = result.scalar_one_or_none()

            if assoc is None:
                assoc = UserProjectModel(user_id=admin.id, project_id=project.id)
                session.add(assoc)
                _log.info(
                    "init_admin_bound_to_project",
                    username=default_admin_user,
                    project=default_project_name,
                )

        # 6. 从 config/env.yaml 同步环境到数据库
        await _seed_environments(session, project.id if project else None)

        await session.commit()
        _log.info("init_app_complete")

    finally:
        await session.close()


async def _seed_environments(session: AsyncSession, project_id: uuid.UUID | None) -> None:
    """从 config/env.yaml 同步环境配置到数据库（幂等操作）。

    Args:
        session: 数据库会话。
        project_id: 默认项目 ID，环境绑定到该项目。
    """
    try:
        from framework.config import ConfigLoader

        loader = ConfigLoader()
        config_raw = loader._load_yaml("config/env.yaml")
        environments = config_raw.get("environments", {})

        if not environments:
            _log.info("env_seed_no_environments_found_in_config")
            return

        from sqlalchemy import select
        from framework.persistence.models.environment import EnvironmentModel

        existing_stmt = select(EnvironmentModel.name)
        existing_result = await session.execute(existing_stmt)
        existing_names = {row[0] for row in existing_result.fetchall()}

        seeded = 0
        for env_name, env_config in environments.items():
            if not isinstance(env_config, dict):
                continue
            if env_name in existing_names:
                continue

            base_url = env_config.get("base_url")
            ws_url = env_config.get("ws_url")
            variables = env_config.get("variables")
            http_config = env_config.get("http")

            env_model = EnvironmentModel(
                name=env_name,
                description=f"{env_name} 环境（从 env.yaml 自动创建）",
                base_url=base_url,
                ws_url=ws_url,
                variables=variables,
                http_config=http_config,
                project_id=project_id,
            )
            session.add(env_model)
            seeded += 1

        if seeded > 0:
            await session.flush()
            _log.info("env_seed_complete", count=seeded, environments=list(environments.keys()))

    except Exception as e:
        _log.warning("env_seed_failed", error=str(e))
