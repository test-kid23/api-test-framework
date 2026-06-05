FROM python:3.12-slim

WORKDIR /app

# ── 系统依赖层（变动频率极低，优先缓存） ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Python 依赖层（仅 requirements.txt 变更时重建） ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 项目源码层（日常最频繁变更，放在最后） ──
COPY . .

# ── 运行时目录 ──
RUN mkdir -p reports logs

# ── 入口 ──
ENTRYPOINT ["pytest"]
CMD ["--env=dev", "-m", "smoke", "--alluredir=/app/reports/allure-results"]
