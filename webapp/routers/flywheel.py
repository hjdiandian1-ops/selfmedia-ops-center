# -*- coding: utf-8 -*-
"""
数据飞轮 Router (/api/flywheel, /api/flywheel/lessons, /api/flywheel/regenerate, /api/retention/*)
"""
import json
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core

router = APIRouter(tags=["数据飞轮"])


class LessonEntry(BaseModel):
    id: str = ""
    title: str
    conclusion: str
    evidence: str = ""
    apply_to: str = ""
    source: str = "manual"
    applied: bool = False


def _validate_lesson(l: LessonEntry):
    if not l.title.strip() or len(l.title.strip()) > 120:
        raise HTTPException(status_code=400, detail="经验标题不能为空且不超过 120 字符")
    if not l.conclusion.strip() or len(l.conclusion.strip()) > 2000:
        raise HTTPException(status_code=400, detail="结论不能为空且不超过 2000 字符")
    if len(l.evidence) > 500 or len(l.apply_to) > 200:
        raise HTTPException(status_code=400, detail="字段过长")


@router.get("/api/flywheel")
def api_flywheel():
    """数据飞轮总览：发布 → 反馈 → 市场学习 → 经验 → 反哺 全链路数据。"""
    stats = core.data_stats.build_summary(jobs_dir=core.JOBS_DIR, outputs_dir=core.OUTPUTS_DIR)
    lessons = core._load_flywheel(core.LESSONS_FILE, {"lessons": []}).get("lessons", [])
    videos = core._load_flywheel(core.VIRAL_FILE, {"videos": []}).get("videos", [])
    return {
        "stats": stats,
        "lessons": lessons,
        "videos": videos,
        "own_hits": core._own_hits(),
        "market": core._market_snapshot(),
        "feedback": core.read_text(core.FEEDBACK_FILE),
        "feedback_path": core.FEEDBACK_FILE,
        "generated_at": core._now_str(),
    }


@router.post("/api/flywheel/lessons")
def api_lesson_save(payload: LessonEntry):
    _validate_lesson(payload)
    data = core._load_flywheel(core.LESSONS_FILE, {"lessons": []})
    lessons = data.get("lessons", [])
    item = payload.model_dump()
    if payload.id:
        idx = next((i for i, l in enumerate(lessons) if l.get("id") == payload.id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"经验不存在: {payload.id}")
        item["id"] = payload.id
        item["created_at"] = lessons[idx].get("created_at", "")
        item["updated_at"] = core._now_str()
        lessons[idx] = item
        action = "updated"
    else:
        item["id"] = core._new_id("l")
        item["created_at"] = core._now_str()
        item["updated_at"] = core._now_str()
        lessons.insert(0, item)
        action = "created"
    data["lessons"] = lessons
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.LESSONS_FILE, data)
    return {"ok": True, "action": action, "lesson": item}


@router.delete("/api/flywheel/lessons/{lid}")
def api_lesson_delete(lid: str):
    data = core._load_flywheel(core.LESSONS_FILE, {"lessons": []})
    before = len(data.get("lessons", []))
    data["lessons"] = [l for l in data.get("lessons", []) if l.get("id") != lid]
    if len(data["lessons"]) == before:
        raise HTTPException(status_code=404, detail=f"经验不存在: {lid}")
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.LESSONS_FILE, data)
    return {"ok": True}


@router.post("/api/flywheel/regenerate")
def api_flywheel_regenerate():
    """重新生成反哺指令包（账户数据 + 市场快照 + 经验 + 爆款公式）。"""
    core._license_guard("flywheel")
    text = core._build_feedback_md()
    os.makedirs(core.FLYWHEEL_DIR, exist_ok=True)
    with open(core.FEEDBACK_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    agents = core.upgrade_agent_docs.upgrade_agents(core.AGENTS_DIR, core.FLYWHEEL_DIR)
    return {"ok": True, "path": core.FEEDBACK_FILE, "feedback": text, "agents": agents}


@router.get("/api/retention/status")
def api_retention_status():
    """数据体检：各模块存储占用与可清理项（不删除任何文件）。"""
    try:
        r = core.RT.scan()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据体检失败: {exc}")
    log = core.read_json(core.RETENTION_LOG) or {}
    runs = log.get("runs", [])
    return {
        "ok": True,
        "plan": {k: len(v) for k, v in r["plan"].items()},
        "space": r["space"],
        "last_run": runs[-1] if runs else None,
    }


@router.post("/api/retention/apply")
def api_retention_apply():
    """执行数据清理：删除过期日志/快照/候选/未出爆款的旧图片，并归档旧任务。"""
    r = core.RT.scan()
    applied = core.RT.apply_plan(r)
    log = core.read_json(core.RETENTION_LOG) or {"runs": []}
    runs = log.setdefault("runs", [])
    runs.append({
        "ran_at": core._now_str(),
        "applied": applied.get("applied", {}),
        "scanned_mb": r["space"]["scanned_mb"],
        "reclaimable_mb": r["space"]["reclaimable_mb"],
    })
    log["runs"] = runs[-10:]
    os.makedirs(os.path.dirname(core.RETENTION_LOG), exist_ok=True)
    with open(core.RETENTION_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return {
        "ok": True,
        "applied": applied.get("applied", {}),
        "space": r["space"],
        "ran_at": runs[-1]["ran_at"],
    }
