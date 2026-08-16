#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS / 公众号连接配置共享模块（从根 .env 或环境变量读凭据，禁止硬编码）
"""
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [
    os.path.normpath(os.path.join(_DIR, "..", ".env")),
]


def _load_env():
    for path in _CANDIDATES:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    # 后面的 .env（项目根）覆盖前面的 nas-n8n/.env
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")


_load_env()

NAS_IP = os.environ.get("NAS_IP", "localhost")
NAS_SSH_PORT = int(os.environ.get("NAS_SSH_PORT", "233"))
NAS_USER = os.environ.get("NAS_USER", "")
NAS_PASS = os.environ.get("NAS_PASS", "")
GZH_APP_ID = os.environ.get("GZH_APP_ID", "")
GZH_APP_SECRET = os.environ.get("GZH_APP_SECRET", "")
NAS_SHARED_DIR = os.environ.get("NAS_SHARED_DIR", "/volume1/docker/n8n/shared_files")
N8N_BASE_URL = os.environ.get("WEBHOOK_URL", f"http://{NAS_IP}:5678/")


def require_credentials():
    if not NAS_USER or not NAS_PASS:
        raise SystemExit(
            "❌ 缺少 NAS 凭据：请在 nas-n8n/.env 配置 NAS_USER 与 NAS_PASS"
            "（参考 .env.example），或注入同名环境变量。"
        )
