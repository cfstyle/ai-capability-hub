#!/bin/sh
set -e

# 第三层保障：若有特殊 requirements.txt，优先从离线 /wheels 自动补装
if [ -f "/app/requirements.txt" ] && [ -d "/wheels" ]; then
    echo "[mcp-runner] Checking and installing custom dependencies from /wheels..."
    pip install --no-index --find-links=/wheels -r /app/requirements.txt 2>/dev/null || true
fi

# 执行容器命令（默认 python server.py）
exec "$@"
