# -*- coding: utf-8 -*-
"""
Skills 技能库 Router (/api/skills-repo)
======================================
提供 Beav 爆款创作与商业诊断 AI Skills 的检索、分类筛选、详情查询、本地 SKILL.md 读取与增量同步功能。
"""
import json
import os
import subprocess
import threading
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import core

router = APIRouter(tags=["Skills 技能库"])

SKILLS_REPO_DIR = os.path.join(core.ROOT, "data", "skills_repo")
SKILLS_REPO_FILE = os.path.join(SKILLS_REPO_DIR, "skills.json")
SKILLS_REPO_AVATARS = os.path.join(SKILLS_REPO_DIR, "avatars")
CRAWL_SCRIPT = os.path.join(core.SCRIPTS, "crawl_getbeav_skills.py")

_sync_lock = threading.Lock()
_is_syncing = False


def _normalize_item(s: dict) -> dict:
    item = dict(s)
    avatar = item.get("local_avatar") or ""
    if avatar.startswith("/data/skills_repo/avatars/"):
        item["local_avatar"] = avatar.replace("/data/skills_repo/avatars/", "/assets/skills_repo/")
    elif avatar and not avatar.startswith("http") and not avatar.startswith("/assets/"):
        item["local_avatar"] = f"/assets/skills_repo/{os.path.basename(avatar)}"
    return item


def _get_raw_data() -> dict:
    if not os.path.isfile(SKILLS_REPO_FILE):
        return {"total_count": 0, "categories": [], "tags": [], "skills": [], "crawled_at": None}
    try:
        with open(SKILLS_REPO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "skills" in data:
                data["skills"] = [_normalize_item(s) for s in data["skills"]]
            return data
    except Exception as e:
        core.logger.error("读取 Skills 技能库数据失败: %s", e)
        return {"total_count": 0, "categories": [], "tags": [], "skills": [], "crawled_at": None}


@router.get("/api/skills-repo")
def api_skills_repo(
    category: Optional[str] = Query(None, description="分类筛选"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    author: Optional[str] = Query(None, description="作者筛选"),
    collection: Optional[str] = Query(None, description="专题合集筛选"),
    search: Optional[str] = Query(None, description="关键词搜索"),
):
    """获取 Skills 列表，支持分类、标签、作者与关键字复合检索"""
    data = _get_raw_data()
    items = data.get("skills", [])

    if category and category != "全部":
        items = [s for s in items if s.get("category") == category]

    if tag:
        items = [s for s in items if tag in s.get("tags", [])]

    if author:
        items = [s for s in items if s.get("author") == author]

    if collection:
        items = [s for s in items if s.get("collection") == collection]

    if search:
        kw = search.strip().lower()
        items = [
            s for s in items
            if kw in s.get("title", "").lower()
            or kw in s.get("slug", "").lower()
            or kw in s.get("summary", "").lower()
            or kw in s.get("author", "").lower()
            or kw in s.get("skill_md", "").lower()
            or any(kw in t.lower() for t in s.get("tags", []))
        ]

    # 统计分类分布
    all_items = data.get("skills", [])
    cat_counts = {}
    for it in all_items:
        c = it.get("category") or "其他"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    return {
        "ok": True,
        "total": len(items),
        "all_total": len(all_items),
        "source": data.get("source", "https://www.getbeav.com/skills"),
        "crawled_at": data.get("crawled_at"),
        "is_syncing": _is_syncing,
        "category_counts": cat_counts,
        "categories": ["全部"] + sorted(list(cat_counts.keys())),
        "tags": data.get("tags", []),
        "items": items,
    }


@router.get("/api/skills-repo/categories")
def api_skills_repo_categories():
    """获取所有可用分类与核心标签统计"""
    data = _get_raw_data()
    all_items = data.get("skills", [])
    cat_counts = {}
    tag_counts = {}
    for it in all_items:
        c = it.get("category") or "其他"
        cat_counts[c] = cat_counts.get(c, 0) + 1
        for t in it.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "ok": True,
        "categories": [{"name": k, "count": v} for k, v in sorted(cat_counts.items())],
        "top_tags": [{"name": k, "count": v} for k, v in sorted_tags[:20]],
        "total": len(all_items),
    }


@router.get("/api/skills-repo/{skill_id}")
def api_skills_repo_detail(skill_id: str):
    """获取单个 Skill 完整详情及全量 SKILL.md"""
    data = _get_raw_data()
    for s in data.get("skills", []):
        if s.get("id") == skill_id or s.get("slug") == skill_id:
            # 如果本地存在独立 .md 文件，则以本地最新文件为准
            local_md_file = os.path.join(SKILLS_REPO_DIR, "skills", f"{s['slug']}.md")
            if os.path.isfile(local_md_file):
                try:
                    with open(local_md_file, "r", encoding="utf-8") as f:
                        s["skill_md"] = f.read()
                        s["char_count"] = len(s["skill_md"])
                except Exception as e:
                    core.logger.warning("读取独立 md 文件异常: %s", e)
            return {"ok": True, "skill": s}
    raise HTTPException(status_code=404, detail=f"未找到 ID 为 {skill_id} 的 Skill")


def _run_sync_worker():
    global _is_syncing
    try:
        core.logger.info("后台开始执行 Skills 技能库同步: %s", CRAWL_SCRIPT)
        subprocess.run(["python3", CRAWL_SCRIPT], check=True, cwd=core.ROOT)
        core.logger.info("Skills 技能库同步完成")
    except Exception as e:
        core.logger.error("Skills 技能库同步执行失败: %s", e)
    finally:
        _is_syncing = False


@router.post("/api/skills-repo/sync")
def api_skills_repo_sync():
    """触发后台增量爬虫同步最新 AI Skills"""
    global _is_syncing
    with _sync_lock:
        if _is_syncing:
            return {"ok": False, "message": "同步任务已在执行中，请稍候"}
        _is_syncing = True

    thread = threading.Thread(target=_run_sync_worker, daemon=True)
    thread.start()
    return {"ok": True, "message": "Skills 技能库同步任务已在后台启动"}
