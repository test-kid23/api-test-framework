#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# AutoTest Framework · 容器入口脚本
#
# 职责:
#   1. 等待 PostgreSQL 就绪
#   2. 运行 Alembic 数据库迁移
#   3. 启动应用进程（参数传入）
#
# 用法:
#   ENTRYPOINT ["/app/docker/entrypoint.sh"]
#   CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# ═══════════════════════════════════════════════════════════

set -euo pipefail

# ── 等待 PostgreSQL ──
wait_for_postgres() {
    if [ -z "${PGHOST:-}" ]; then
        echo "[entrypoint] PGHOST 未设置，跳过 PostgreSQL 等待"
        return
    fi

    local PGPORT="${PGPORT:-5432}"
    echo "[entrypoint] 等待 PostgreSQL ${PGHOST}:${PGPORT}..."

    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if python -c "
import asyncio
import asyncpg
import os

async def check():
    try:
        conn = await asyncpg.connect(
            host=os.environ.get('PGHOST', 'postgres'),
            port=int(os.environ.get('PGPORT', 5432)),
            user=os.environ.get('PGUSER', 'autotest'),
            password=os.environ.get('PGPASSWORD', ''),
            database=os.environ.get('PGDATABASE', 'autotest'),
            timeout=5,
        )
        await conn.close()
    except Exception as e:
        raise SystemExit(1)

asyncio.run(check())
" 2>/dev/null; then
            echo "[entrypoint] PostgreSQL 已就绪"
            return
        fi
        attempt=$((attempt + 1))
        echo "[entrypoint] PostgreSQL 未就绪 (${attempt}/${max_attempts}), 2s 后重试..."
        sleep 2
    done

    echo "[entrypoint] ERROR: PostgreSQL 在 ${max_attempts} 次尝试后仍未就绪" >&2
    exit 1
}

# ── 运行数据库迁移 ──
run_migrations() {
    if [ -z "${AUTOTEST_DB_URL:-}" ]; then
        echo "[entrypoint] AUTOTEST_DB_URL 未设置，跳过数据库迁移"
        return
    fi

    echo "[entrypoint] 运行 Alembic 数据库迁移..."
    alembic upgrade head
    echo "[entrypoint] 数据库迁移完成"
}

# ── 主流程 ──
echo "[entrypoint] ===== AutoTest Framework 容器启动 ====="
wait_for_postgres
run_migrations
echo "[entrypoint] ===== 启动应用: $* ====="

exec "$@"
