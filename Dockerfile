FROM python:3.12-slim

WORKDIR /app

# ── 系统依赖层（变动频率极低，优先缓存） ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖层（仅 pyproject.toml / requirements.lock 变更时重建） ──
# 方案 A: 从 lockfile 安装（推荐 CI，确定性构建）
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# ── 项目源码层（日常最频繁变更，放在最后） ──
COPY . .

# ── 可编辑安装（使框架能作为包被 import） ──
RUN pip install --no-cache-dir -e ".[all]"

# ── 运行时目录 ──
RUN mkdir -p reports logs

# ── 入口 ──
ENTRYPOINT ["pytest"]
CMD ["--env=dev", "-m", "smoke", "--alluredir=/app/reports/allure-results"]
