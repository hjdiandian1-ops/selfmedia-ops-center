# -*- coding: utf-8 -*-
"""
封面提示词库 Router (/api/cover-templates)
======================================
提供 Beav 爆款封面提示词模板的检索、分类筛选、详情查询与本地同步功能。
"""
import json
import os
import subprocess
import threading
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import core

router = APIRouter(tags=["封面提示词"])

COVER_TEMPLATES_DIR = os.path.join(core.ROOT, "data", "cover_templates")
COVER_TEMPLATES_FILE = os.path.join(COVER_TEMPLATES_DIR, "templates.json")
COVER_TEMPLATES_IMAGES = os.path.join(COVER_TEMPLATES_DIR, "images")
CRAWL_SCRIPT = os.path.join(core.SCRIPTS, "crawl_getbeav_templates.py")

_sync_lock = threading.Lock()
_is_syncing = False


def _normalize_item(t: dict) -> dict:
    item = dict(t)
    for k in ("local_thumbnail", "local_original"):
        v = item.get(k) or ""
        if v.startswith("/data/cover_templates/images/"):
            item[k] = v.replace("/data/cover_templates/images/", "/assets/cover_templates/")
        elif v and not v.startswith("http") and not v.startswith("/assets/"):
            item[k] = f"/assets/cover_templates/{os.path.basename(v)}"
    return item


def _get_raw_data() -> dict:
    if not os.path.isfile(COVER_TEMPLATES_FILE):
        return {"total_count": 0, "categories": [], "templates": [], "updated_at": None}
    try:
        with open(COVER_TEMPLATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "templates" in data:
                data["templates"] = [_normalize_item(t) for t in data["templates"]]
            return data
    except Exception as e:
        core.logger.error("读取封面模板数据失败: %s", e)
        return {"total_count": 0, "categories": [], "templates": [], "updated_at": None}


@router.get("/api/cover-templates")
def api_cover_templates(
    category: Optional[str] = Query(None, description="分类筛选"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    search: Optional[str] = Query(None, description="关键词搜索"),
):
    """获取封面提示词模板列表，支持分类、标签和关键字过滤。"""
    data = _get_raw_data()
    items = data.get("templates", [])

    if category and category != "全部":
        items = [t for t in items if t.get("category") == category]

    if tag:
        items = [t for t in items if tag in t.get("tags", [])]

    if search:
        s = search.strip().lower()
        items = [
            t for t in items
            if s in t.get("title", "").lower()
            or s in t.get("summary", "").lower()
            or s in t.get("prompt", "").lower()
            or s in t.get("industries", "").lower()
            or any(s in tag.lower() for tag in t.get("tags", []))
        ]

    # 统计分类分布
    all_items = data.get("templates", [])
    cat_counts = {}
    for it in all_items:
        c = it.get("category") or "其他"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    return {
        "ok": True,
        "total": len(items),
        "all_total": len(all_items),
        "source": data.get("source", "https://www.getbeav.com/templates"),
        "crawled_at": data.get("crawled_at"),
        "is_syncing": _is_syncing,
        "category_counts": cat_counts,
        "categories": ["全部"] + sorted(list(cat_counts.keys())),
        "items": items,
    }


@router.get("/api/cover-templates/categories")
def api_cover_templates_categories():
    """获取所有可用分类及模板计数"""
    data = _get_raw_data()
    all_items = data.get("templates", [])
    cat_counts = {}
    for it in all_items:
        c = it.get("category") or "其他"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    return {
        "ok": True,
        "categories": [{"name": k, "count": v} for k, v in sorted(cat_counts.items())],
        "total": len(all_items),
    }


@router.get("/api/cover-templates/{template_id}")
def api_cover_template_detail(template_id: str):
    """获取单张封面提示词模板的完整参数与提示词详情"""
    data = _get_raw_data()
    for t in data.get("templates", []):
        if t.get("id") == template_id:
            return {"ok": True, "template": t}
    raise HTTPException(status_code=404, detail=f"未找到 ID 为 {template_id} 的封面模板")


def _run_sync_worker():
    global _is_syncing
    try:
        core.logger.info("后台开始执行封面提示词库同步: %s", CRAWL_SCRIPT)
        subprocess.run(["python3", CRAWL_SCRIPT], check=True, cwd=core.ROOT)
        core.logger.info("封面提示词库同步完成")
    except Exception as e:
        core.logger.error("封面提示词库同步执行失败: %s", e)
    finally:
        _is_syncing = False


@router.post("/api/cover-templates/sync")
def api_cover_templates_sync():
    """触发后台增量爬虫同步最新封面提示词模板"""
    global _is_syncing
    with _sync_lock:
        if _is_syncing:
            return {"ok": False, "message": "同步任务已在执行中，请稍候"}
        _is_syncing = True

    thread = threading.Thread(target=_run_sync_worker, daemon=True)
    thread.start()
    return {"ok": True, "message": "封面提示词库同步任务已在后台启动"}
