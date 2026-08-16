#!/usr/bin/env bash
# 自媒体运营工厂 · 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "首次运行，先安装依赖…"
  python3 scripts/workbench_install.py
fi

if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

echo "启动工作台：http://127.0.0.1:8787"
(sleep 2
  if command -v open >/dev/null 2>&1; then open http://127.0.0.1:8787
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://127.0.0.1:8787
  fi) &

cd webapp
exec ../.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8787
