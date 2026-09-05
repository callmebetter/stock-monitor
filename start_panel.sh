#!/bin/bash
cd /var/www/stock-monitor
# 加载环境变量
set -a
source .env
set +a
# --no-sync: 启动时不隐式执行 uv sync（避免进程启动路径联网拉包导致 PM2 重启风暴）。
# 依赖同步由 deploy.sh 在发布阶段完成；若环境与 lock 不一致则 uv 直接报错退出，
# 由 PM2 上报失败，而不是静默触发联网下载。
exec uv run --no-sync uvicorn main:app --host 127.0.0.1 --port 8000
