@echo off
chcp 65001 >nul
echo ==================================================
echo   自媒体运营工厂 (SelfMedia Ops Center) · Windows
echo ==================================================

REM 1. 检查 Python 环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先前往 https://www.python.org/ 安装 Python 3.9+ 并勾选 "Add Python to PATH"！
    pause
    exit /b 1
)

REM 2. 检查并清理 8787 端口残留的僵尸进程（防止端口占用冲突）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8787" ^| findstr "LISTENING"') do (
    echo [提示] 检测到 8787 端口已有残留进程 (PID: %%a)，正在释放...
    taskkill /F /PID %%a >nul 2>nul
)

REM 3. 初始化虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] 正在初始化环境与依赖 (首次需 1-2 分钟)...
    python scripts\workbench_install.py
)

REM 4. 启动服务与唤起浏览器
echo [2/2] 正在启动自媒体工厂 Web 工作台...
start http://127.0.0.1:8787
.venv\Scripts\python.exe -m uvicorn webapp.server:app --host 127.0.0.1 --port 8787
pause
