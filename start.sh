#!/usr/bin/env bash
# 自媒体运营工厂 · 一键启动（仅绑定 127.0.0.1）
set -e
cd "$(dirname "$0")"
PORT="${1:-8787}"

if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

echo "🚀 启动自媒体运营工厂工作台 → http://127.0.0.1:${PORT}"
echo "   (Ctrl+C 停止；公众号草稿走官方 API，小红书为人工素材包发布)"

if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port "${PORT}" --app-dir webapp
else
  exec python3 -m uvicorn server:app --host 127.0.0.1 --port "${PORT}" --app-dir webapp
fi
