# -*- coding: utf-8 -*-
"""
选题 Router (/api/topics, /api/topics/preferences, /api/topics/adopt)
"""
import json
import os
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core

router = APIRouter(tags=["选题"])


class PrefPayload(BaseModel):
    platforms: dict = {}


@router.get("/api/topics/preferences")
def api_topics_preferences():
    prefs = core.read_json(os.path.join(core.TOPICS_DIR, "preferences.json")) or {}
    niches = core.read_json(os.path.join(core.TOPICS_DIR, "niches.json")) or {}
    return {"preferences": prefs, "niches": niches}


@router.post("/api/topics/preferences")
def api_topics_preferences_save(payload: PrefPayload):
    """保存选题偏好：平台→赛道列表（无选择=默认模式）。"""
    niches = core.read_json(os.path.join(core.TOPICS_DIR, "niches.json")) or {}
    cleaned = {}
    for platform, names in (payload.platforms or {}).items():
        if platform not in niches:
            continue
        valid = [n for n in names if n in niches[platform]]
        if valid:
            cleaned[platform] = valid
    data = {"platforms": cleaned, "updated_at": core._now_str()}
    os.makedirs(core.TOPICS_DIR, exist_ok=True)
    with open(os.path.join(core.TOPICS_DIR, "preferences.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "preferences": data}


@router.get("/api/topics")
def api_topics():
    radar_path = core._resolve_radar_path()
    suggest_path = core._resolve_suggest_path()

    radar = {"path": radar_path, "sources": []}
    if radar_path:
        source, rows = "", []
        for ln in core.read_text(radar_path).splitlines():
            if ln.startswith("## "):
                if rows:
                    radar["sources"].append({"source": source, "items": rows})
                source, rows = ln[3:].strip(), []
            m = re.match(r"\s*(\d+)[\.、．]\s*(.*?)\s*（\[链接\]\((.*?)\)）(.*)$", ln)
            if not m:
                m = re.match(r"\s*(\d+)[\.、．]\s*(.+?)\s*$", ln)
            if m and source:
                title = m.group(2).strip()
                title = re.sub(r"\s*（发布于[^）]*）\s*$", "", title)
                title = re.sub(r"\s*｜\s*⚠️.*$", "", title)
                rows.append({"rank": int(m.group(1)), "title": title,
                             "link": m.group(3).strip() if m.lastindex >= 3 and m.group(3) else ""})
        if rows:
            radar["sources"].append({"source": source, "items": rows})

    suggest = {"path": suggest_path, "daily": [], "weekly": [], "candidates": []}
    if suggest_path:
        pool, cur = None, None
        for ln in core.read_text(suggest_path).splitlines():
            pm = re.match(r"^## (日选题|周选题)", ln)
            if pm:
                if cur is not None and pool:
                    suggest[pool].append(cur)
                pool = "daily" if pm.group(1) == "日选题" else "weekly"
                cur = None
                continue
            cm = re.match(r"^### 候选 \d+ ⭐(日分|周分) ([\d.]+)", ln)
            if cm:
                if cur is not None and pool:
                    suggest[pool].append(cur)
                cur = {"rank": 0, "pool_score": float(cm.group(2)), "score": None, "title": "",
                       "link": "", "source": "", "view": "", "formulas": "", "pool_scores": ""}
                continue
            if cur is not None and pool:
                m2 = re.match(r"^- (主题方向|命中热点|建议视角|建议标题公式|评分构成|池内排序|原文链接)[：:]\s*(.*)$", ln)
                if m2:
                    cur[{"主题方向": "title", "命中热点": "source",
                         "建议视角": "view", "建议标题公式": "formulas",
                         "评分构成": "breakdown", "池内排序": "pool_scores",
                         "原文链接": "link"}[m2.group(1)]] = m2.group(2).strip()
        if cur is not None and pool:
            suggest[pool].append(cur)
        # 清理标题 Markdown 加粗与【出处】前缀，拆分「评分构成」结构化字段
        for c in suggest["daily"] + suggest["weekly"]:
            t = c.get("title", "")
            t = re.sub(r"^\s*\*+\s*", "", t)
            t = re.sub(r"\s*\*+\s*$", "", t)
            t = re.sub(r"^【[^】]+】\s*", "", t)
            c["title"] = t.strip()
            if not c.get("breakdown"):
                continue
            parts = {}
            for seg in c["breakdown"].split("｜"):
                mm = re.match(r"^\s*(IP|时效|热度|表达|搜索|持久|独特|跨源)\s*([+-]?[\d.]+)(?:\s*=\s*[\d.]+)?\s*$", seg.strip())
                if mm:
                    key = {"IP": "ip", "时效": "freshness", "热度": "heat", "表达": "impact",
                           "搜索": "search", "持久": "durable", "独特": "unique",
                           "跨源": "cross_source"}[mm.group(1)]
                    parts[key] = float(mm.group(2))
            c["breakdown_parts"] = parts
            mm_total = re.search(r"合计 ([\d.]+)", c["breakdown"])
            c["score"] = float(mm_total.group(1)) if mm_total else c.get("pool_score")
        suggest["candidates"] = suggest["daily"]  # 兼容旧调用

    # 信息源状态：配置源 + 雷达实际出现源 + 头部失败列表
    configured = [
        "微博热搜", "知乎热榜", "36氪快讯", "华尔街见闻", "金十数据",
        "少数派热门", "B站热门", "掘金趋势", "谷歌趋势", "X热点",
        "今日热榜AI", "推楼1号小时热点",
    ]
    failed_names = []
    if radar_path:
        header = next((ln for ln in core.read_text(radar_path).splitlines()
                       if ln.startswith("> 来源")), "")
        fm = re.search(r"失败 \d+ 源[：:]\s*(.+)", header)
        if fm:
            failed_names = [x.strip() for x in fm.group(1).split("、") if x.strip()]
    sources = []
    for name in configured:
        hit = next((s for s in radar["sources"] if s["source"] == name), None)
        sources.append({
            "name": name,
            "ok": bool(hit) and name not in failed_names,
            "items": len(hit["items"]) if hit else 0,
        })
    for s in radar["sources"]:
        if s["source"] not in configured:
            sources.append({"name": s["source"], "ok": True, "items": len(s["items"])})

    return {"radar": radar, "suggest": suggest, "sources": sources}


class AdoptTopic(BaseModel):
    title: str
    link: str = ""
    notes: str = ""


@router.post("/api/topics/adopt")
def api_adopt(payload: AdoptTopic):
    core._license_guard("production")
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题为空")
    title = title[:60]  # 超长标题自动截断，避免长选题无法建任务
    if len(payload.link) > 500 or len(payload.notes) > 500:
        raise HTTPException(status_code=400, detail="link/notes 过长")
    safe_slug = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]", "", title[:12]) or "未命名选题"
    job_id = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_slug[:12]}"
    core._require_job_id(job_id)
    r = core.run_script(["job_state.py", "init", job_id, "--theme", title], timeout=15)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    brief = "\n".join([
        f"# 生产简报",
        f"- Job：{job_id}",
        f"- 主题：{title}",
        f"- 采纳来源：{payload.link.strip() or '工作台选题推荐'}",
        f"- 附加说明：{payload.notes.strip() or '无'}",
        "",
    ])
    with open(os.path.join(core.JOBS_DIR, job_id, "brief.md"), "w", encoding="utf-8") as f:
        f.write(brief)
    core._enqueue_job(job_id)
    started = core._kick_production()
    return {"job_id": job_id, "result": r, "production_started": started}


@router.post("/api/topics/calibrate")
def api_topics_calibrate():
    """触发选题评分模型动态权重校准。"""
    try:
        import topic_feedback
        res = topic_feedback.calibrate_weights()
        return {"ok": True, "calibration": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/topics/feedback-report")
def api_topics_feedback_report():
    """获取选题表现复盘与模型校准报告。"""
    try:
        import topic_feedback
        rep = topic_feedback.generate_report()
        return {"ok": True, "report": rep}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

