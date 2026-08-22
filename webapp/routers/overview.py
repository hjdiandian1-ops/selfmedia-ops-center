# -*- coding: utf-8 -*-
"""
概览与统计 Router (/api/overview, /api/stats, /api/dashboard)
"""
import glob
import os
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, HTTPException

import core

router = APIRouter(tags=["概览与统计"])


@router.get("/api/overview")
def api_overview():
    by_state, total, reject_total, scores = Counter(), 0, 0, []
    for sf in glob.glob(os.path.join(core.JOBS_DIR, "*", "state.json")):
        d = core.read_json(sf)
        if not d:
            continue
        total += 1
        by_state[d.get("state", "?")] += 1
        reject_total += d.get("reject_count", 0)
        for st, sc in (d.get("scores") or {}).items():
            scores.append(sc)

    # 待回收: publish/archive 态 + publish_log 存在 + records 空 + 距今 ≥48h
    pending_recycle, hits = 0, 0
    for lg in glob.glob(os.path.join(core.JOBS_DIR, "*", "publish_log.json")):
        log = core.read_json(lg)
        if not log:
            continue
        for rec in log.get("records", []):
            if rec.get("hit"):
                hits += 1
        if log.get("records"):
            continue
        sf = os.path.join(os.path.dirname(lg), "state.json")
        st = (core.read_json(sf) or {}).get("state", "")
        if st not in ("publish", "archive"):
            continue
        pt = log.get("published_at")
        try:
            age_h = (datetime.now() - datetime.strptime(pt, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
            if age_h >= 48:
                pending_recycle += 1
        except Exception:
            pass

    return {
        "jobs_total": total,
        "by_state": dict(by_state),
        "reject_total": reject_total,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "score_count": len(scores),
        "pending_recycle": pending_recycle,
        "hits": hits,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/api/stats")
def api_stats(platforms: str = ""):
    """自有数据统计：实时扫描 jobs/ + outputs/，聚合 KPI/平台/主题/趋势/内容特征。"""
    plats = core._parse_platforms(platforms)
    return core.data_stats.build_summary(
        jobs_dir=core.JOBS_DIR, outputs_dir=core.OUTPUTS_DIR, data_dir=core.DATA_DIR, platforms=plats)


@router.get("/api/dashboard")
def api_dashboard(range: int = 7, period: str = "day", platforms: str = ""):
    """平台看板：period=day|week|month|year，platforms=逗号分隔的平台过滤。"""
    if period not in core.dashboard_analysis.PERIOD_DAYS:
        raise HTTPException(status_code=400, detail="period 仅支持 day/week/month/year")
    plats = core._parse_platforms(platforms)
    return core.dashboard_analysis.build_dashboard(
        period=period, platforms=plats,
        jobs_dir=core.JOBS_DIR, outputs_dir=core.OUTPUTS_DIR, data_dir=core.DATA_DIR)
