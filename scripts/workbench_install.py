#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键安装器（小白部署）
======================
自动完成：检查 Python → 创建虚拟环境 → 安装依赖 → 生成 .env 模板。

用法：
    python3 scripts/workbench_install.py

装完后用 ./start.sh 启动工作台，浏览器会自动打开 http://127.0.0.1:8787
"""
import os
import subprocess  # nosec B404  # 固定命令列表 + 无 shell
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VENV = os.path.join(ROOT, ".venv")
ENV_FILE = os.path.join(ROOT, ".env")

ENV_TEMPLATE = """# 自媒体运营工厂 · 本地配置
# 复制本文件为 .env 后填写；不配置 AI 也能使用免费功能（选题/质检），
# 配置后即可使用 AI 拆解与一键生产（支持 DeepSeek 等任何 OpenAI 兼容 API）。
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
"""


def step(msg):
    print(f"▶ {msg}")


def main():
    step(f"项目目录：{ROOT}")
    if sys.version_info < (3, 9):
        print(f"❌ Python 版本过低：{sys.version.split()[0]}，需要 3.9 以上")
        return 1
    print(f"✅ Python {sys.version.split()[0]}")

    venv_python = os.path.join(VENV, "bin", "python")
    if not os.path.isfile(venv_python):
        step("创建虚拟环境 .venv")
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)  # nosec B603  # 固定命令
    step("安装依赖（首次约 1-3 分钟）")
    subprocess.run([venv_python, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=False)  # nosec B603
    lock_file = os.path.join(ROOT, "requirements.lock")
    in_file = os.path.join(ROOT, "requirements.in")
    res = subprocess.run([venv_python, "-m", "pip", "install", "-r", lock_file], check=False)  # nosec B603
    if res.returncode != 0 and os.path.isfile(in_file):
        print("ℹ️ requirements.lock 存在跨 Python 版本约束，自动使用 requirements.in 解析安装兼容版本...")
        subprocess.run([venv_python, "-m", "pip", "install", "-r", in_file], check=True)  # nosec B603

    if not os.path.isfile(ENV_FILE):
        step("生成 .env 模板")
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(ENV_TEMPLATE)
        print("   请编辑 .env，填入 LLM_API_KEY（可选；不填也能用免费功能）")
    else:
        print("ℹ️ .env 已存在，跳过")

    print()
    print("✅ 安装完成！启动方式：")
    print("   ./start.sh")
    print("   浏览器会自动打开 http://127.0.0.1:8787")
    print("   （也可手动运行：cd webapp && ../.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8787）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
