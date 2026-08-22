# -*- coding: utf-8 -*-
"""
定时任务 Router (/api/scheduler)
"""
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core
import scheduler

router = APIRouter(tags=["定时任务"])


class SchedulerTask(BaseModel):
    enabled: bool = False
    times: list = []


class SchedulerPayload(BaseModel):
    enabled: bool = False
    tasks: dict = {}


class SchedulerRunNow(BaseModel):
    task: str


@router.get("/api/scheduler")
def api_scheduler_get():
    cfg = scheduler.load_config()
    return {"ok": True, "config": cfg, "tasks_meta": scheduler.TASKS_META}


@router.post("/api/scheduler")
def api_scheduler_save(payload: SchedulerPayload):
    cfg = scheduler.save_config({"enabled": payload.enabled, "tasks": payload.tasks})
    return {"ok": True, "config": cfg}


@router.post("/api/scheduler/run-now")
def api_scheduler_run_now(payload: SchedulerRunNow):
    task = payload.task.strip()
    if task not in scheduler.TASKS_META:
        raise HTTPException(status_code=400, detail=f"不支持的调度动作: {task}")
    # 后台执行，避免长耗时脚本阻塞 HTTP 响应（批量拆解可运行数十分钟）
    threading.Thread(target=scheduler.run_action, args=(task,), daemon=True).start()
    return {"ok": True, "task": task, "status": "started", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
