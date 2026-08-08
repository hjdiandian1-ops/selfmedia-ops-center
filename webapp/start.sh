#!/usr/bin/env bash
# 自媒体工作台 · 一键启动（仅绑定 127.0.0.1）
set -e
cd "$(dirname "$0")/.."
PORT="${1:-8787}"
echo "🚀 启动自媒体工作台 → http://127.0.0.1:${PORT}"
echo "   (Ctrl+C 停止；公众号草稿走官方 API，小红书为人工素材包发布)"
exec python3 -m uvicorn server:app --host 127.0.0.1 --port "${PORT}" --app-dir webapp
