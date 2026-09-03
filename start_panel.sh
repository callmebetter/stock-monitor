#!/bin/bash
cd /var/www/stock-monitor
# 加载环境变量
set -a
source .env
set +a
exec uv run uvicorn main:app --host 127.0.0.1 --port 8000
