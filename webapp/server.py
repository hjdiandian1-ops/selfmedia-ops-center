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

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import core
from routers import (
    agents, cover_templates, flywheel, matrix_commercial, outputs, overview,
    production, publish, scheduler, settings, skills_repo, topics, viral,
)


def _start_scheduler():
    try:
        import scheduler as sched_runner
        sched_runner.start_scheduler()
    except Exception as e:
        core.logger.warning("定时调度器启动失败: %s", e)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # ---------- 启动内置定时调度器（配置默认关闭，用户可在设置中开启） ----------
    _start_scheduler()
    yield


app = FastAPI(title="自媒体运营中心看板", version="2.2.0", lifespan=_lifespan)

# ---------- 挂载业务模块 Router ----------
for router_mod in (overview, agents, viral, flywheel, topics, production, settings, publish, outputs, scheduler, cover_templates, skills_repo, matrix_commercial):
    app.include_router(router_mod.router)

# ---------- 静态前端与资源挂载 ----------
@app.get("/")
def index():
    return FileResponse(
        os.path.join(core.STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )

app.mount("/static", StaticFiles(directory=core.STATIC_DIR), name="static")
app.mount("/assets/outputs", StaticFiles(directory=core.OUTPUTS_DIR), name="outputs-assets")
COVER_TEMPLATES_IMAGES = os.path.join(core.ROOT, "data", "cover_templates", "images")
os.makedirs(COVER_TEMPLATES_IMAGES, exist_ok=True)
app.mount("/assets/cover_templates", StaticFiles(directory=COVER_TEMPLATES_IMAGES), name="cover-templates-assets")

SKILLS_REPO_AVATARS = os.path.join(core.ROOT, "data", "skills_repo", "avatars")
os.makedirs(SKILLS_REPO_AVATARS, exist_ok=True)
app.mount("/assets/skills_repo", StaticFiles(directory=SKILLS_REPO_AVATARS), name="skills-repo-assets")

# ---------- 动态属性代理：确保单测与旧调用无缝兼容 ----------
class _ServerModule(types.ModuleType):
    def __getattr__(self, name):
        if hasattr(core, name):
            return getattr(core, name)
        for r in (overview, agents, viral, flywheel, topics, production, settings, publish, outputs, cover_templates, skills_repo, matrix_commercial):
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
