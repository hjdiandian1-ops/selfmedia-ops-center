#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体运营中心看板 · 主服务入口 (FastAPI)
启动: uvicorn server:app --host 127.0.0.1 --port 8787 或 bash start.sh
"""
import os
import sys
import types

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
if WEBAPP_DIR not in sys.path:
    sys.path.insert(0, WEBAPP_DIR)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import core
from routers import (
    agents, flywheel, outputs, overview,
    production, publish, scheduler, settings, topics, viral,
)

app = FastAPI(title="自媒体运营中心看板", version="2.1.0")

# ---------- 挂载业务模块 Router ----------
for router_mod in (overview, agents, viral, flywheel, topics, production, settings, publish, outputs, scheduler):
    app.include_router(router_mod.router)

# ---------- 启动内置定时调度器（配置默认关闭，用户可在设置中开启） ----------
@app.on_event("startup")
def _start_scheduler():
    try:
        scheduler.start_scheduler()
    except Exception as e:
        core.logger.warning("定时调度器启动失败: %s", e)

# ---------- 静态前端与资源挂载 ----------
@app.get("/")
def index():
    return FileResponse(os.path.join(core.STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=core.STATIC_DIR), name="static")
app.mount("/assets/outputs", StaticFiles(directory=core.OUTPUTS_DIR), name="outputs-assets")

# ---------- 动态属性代理：确保单测与旧调用无缝兼容 ----------
class _ServerModule(types.ModuleType):
    def __getattr__(self, name):
        if hasattr(core, name):
            return getattr(core, name)
        for r in (overview, agents, viral, flywheel, topics, production, settings, publish, outputs):
            if hasattr(r, name):
                return getattr(r, name)
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if hasattr(core, name):
            setattr(core, name, value)

sys.modules[__name__].__class__ = _ServerModule

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)
