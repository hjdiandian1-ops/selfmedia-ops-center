# -*- coding: utf-8 -*-
"""
Agent 团队 Router (/api/agents, /api/agents/doc, /api/skills/anti-ai-flavor, /api/themes)
"""
import os

from fastapi import APIRouter, HTTPException

import core

router = APIRouter(tags=["Agent团队"])


@router.get("/api/agents")
def api_agents():
    """返回 Agent 职责元数据 + 当前活跃 Job 与最近产出。"""
    jobs = core._collect_job_rows()
    agents = []
    for a in core.AGENTS_ROSTER:
        active = [j for j in jobs if j["state"] in a["state_keys"]]
        agents.append({
            "role": a["role"],
            "en": a["en"],
            "emoji": a["emoji"],
            "responsibility": a["responsibility"],
            "state_keys": a["state_keys"],
            "active_count": len(active),
            "doc": core._agent_doc_meta(a.get("doc", "")),
            "active_jobs": [{
                "job_id": j["job_id"],
                "theme": j["theme"],
                "state": j["state"],
                "updated_at": j["updated_at"],
                "outputs": core._agent_outputs(j["job_id"]),
            } for j in active[-3:]],
        })
    return {"agents": agents}


@router.get("/api/agents/doc")
def api_agent_doc(role: str = ""):
    """返回某个 Agent 的 SOP 文档全文（供弹窗查看）。"""
    if not role.strip():
        raise HTTPException(status_code=400, detail="role 不能为空")
    hit = next((a for a in core.AGENTS_ROSTER if a["role"] == role.strip()), None)
    if hit is None:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {role}")
    doc = hit.get("doc", "")
    text = core.read_text(os.path.join(core.ROOT, doc))
    if not text:
        raise HTTPException(status_code=404, detail=f"文档不存在或为空: {doc}")
    return {"role": hit["role"], "doc": doc, "content": text,
            "version": core._agent_doc_meta(doc).get("version", "")}


@router.get("/api/skills/anti-ai-flavor")
def api_anti_ai_flavor_skill():
    """返回去 AI 味规范 Skill 全文（供成品库质检区弹窗查看）。"""
    path = os.path.join(core.ROOT, "skills", "anti-ai-flavor-skill", "SKILL.md")
    text = core.read_text(path)
    if not text:
        raise HTTPException(status_code=404, detail="去 AI 味 Skill 文档不存在")
    return {"name": "anti-ai-flavor-skill", "path": "skills/anti-ai-flavor-skill/SKILL.md", "content": text}


@router.get("/api/themes")
def api_themes():
    """返回引流内容主题库（选题方向预设）。"""
    return {"themes": core.CONTENT_THEMES, "count": len(core.CONTENT_THEMES)}
