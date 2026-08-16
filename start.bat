@echo off
chcp 65001 >nul
echo ==================================================
echo   自媒体运营工厂 (SelfMedia Ops Center) · Windows
echo ==================================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] 正在初始化环境与依赖 (首次需 1-2 分钟)...
    python scripts\workbench_install.py
)

echo [2/2] 正在启动自媒体工厂 Web 工作台...
start http://127.0.0.1:8787
.venv\Scripts\python.exe -m uvicorn webapp.server:app --host 127.0.0.1 --port 8787
pause
