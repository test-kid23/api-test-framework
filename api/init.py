"""应用初始化 — 首次启动时自动创建默认管理员账户和默认项目

在 lifespan 启动阶段调用 init_app()，确保：
1. 所有 ORM 表已创建（Base.metadata.create_all）
2. 默认项目 "default" 存在
3. 默认管理员 "admin" 存在并绑定到默认项目
"""

from __future__ import annotations

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

        # 4. 确保默认管理员存在（并修复 bcrypt 版本兼容性问题）
        from api.auth import hash_password, verify_password

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
            # 修复：bcrypt 版本升级后旧哈希可能无法验证
            try:
                if not verify_password(default_admin_pass, admin.password_hash):
                    _log.warning("admin_password_rehash", reason="password verification failed (likely bcrypt version mismatch)")
                    admin.password_hash = hash_password(default_admin_pass)
                    _log.info("admin_password_reset_complete")
            except Exception as e:
                _log.warning("admin_password_rehash", reason=str(e))
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

        await session.commit()
        _log.info("init_app_complete")

    finally:
        await session.close()
