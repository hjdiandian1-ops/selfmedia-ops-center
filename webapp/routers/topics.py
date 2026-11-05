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


class KolItem(BaseModel):
    handle: str
    name: str = ""
    category: str = "AI大模型"
    enabled: bool = True
    note: str = ""


class KolUpdate(BaseModel):
    name: str = None
    category: str = None
    enabled: bool = None
    note: str = None


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


@router.get("/api/topics/kols")
def api_get_kols():
    """获取关注大V列表及最新监控推文缓存。"""
    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    posts_file = os.path.join(core.TOPICS_DIR, "kol_posts.json")
    kols = core.read_json(kols_file) or []
    posts = core.read_json(posts_file) or []
    return {"ok": True, "kols": kols, "posts": posts}


@router.post("/api/topics/kols")
def api_add_kol(item: KolItem):
    """手动添加关注大V。"""
    handle = item.handle.strip().lstrip("@")
    if not handle:
        raise HTTPException(status_code=400, detail="大V Handle 不能为空")
    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    kols = core.read_json(kols_file) or []
    for k in kols:
        if k.get("handle", "").lower() == handle.lower():
            raise HTTPException(status_code=400, detail=f"大V @{handle} 已在关注列表中")
    new_kol = {
        "handle": handle,
        "name": item.name.strip() or handle,
        "category": item.category.strip() or "AI大模型",
        "enabled": item.enabled,
        "note": item.note.strip(),
        "added_at": core._now_str(),
        "last_fetched_at": None,
    }
    kols.append(new_kol)
    os.makedirs(core.TOPICS_DIR, exist_ok=True)
    with open(kols_file, "w", encoding="utf-8") as f:
        json.dump(kols, f, ensure_ascii=False, indent=2)
    return {"ok": True, "kol": new_kol, "kols": kols}


@router.put("/api/topics/kols/{handle}")
def api_update_kol(handle: str, item: KolUpdate):
    """更新关注大V状态（启停、分类、备注等）。"""
    h_clean = handle.strip().lstrip("@").lower()
    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    kols = core.read_json(kols_file) or []
    target = None
    for k in kols:
        if k.get("handle", "").lower() == h_clean:
            target = k
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"未找到大V @{handle}")
    if item.name is not None:
        target["name"] = item.name.strip()
    if item.category is not None:
        target["category"] = item.category.strip()
    if item.enabled is not None:
        target["enabled"] = item.enabled
    if item.note is not None:
        target["note"] = item.note.strip()
    with open(kols_file, "w", encoding="utf-8") as f:
        json.dump(kols, f, ensure_ascii=False, indent=2)
    return {"ok": True, "kol": target}


@router.delete("/api/topics/kols/{handle}")
def api_delete_kol(handle: str):
    """删除关注大V。"""
    h_clean = handle.strip().lstrip("@").lower()
    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    kols = core.read_json(kols_file) or []
    filtered = [k for k in kols if k.get("handle", "").lower() != h_clean]
    if len(filtered) == len(kols):
        raise HTTPException(status_code=404, detail=f"未找到大V @{handle}")
    with open(kols_file, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)
    return {"ok": True, "deleted": handle, "remaining_count": len(filtered)}


@router.post("/api/topics/kols/fetch")
def api_fetch_kols():
    """即时触发大V推文与热点刷新抓取。"""
    r = core.run_script(["fetch_hot_topics.py", "--top", "10"], timeout=30)
    core.run_script(["suggest_topics.py"], timeout=15)
    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    posts_file = os.path.join(core.TOPICS_DIR, "kol_posts.json")
    kols = core.read_json(kols_file) or []
    posts = core.read_json(posts_file) or []
    return {"ok": True, "result": r, "kols": kols, "posts": posts}


@router.get("/api/topics/trends/google")
def api_get_google_trends():
    """获取 Google Trends 科技与赛道飙升热词。"""
    gt_file = os.path.join(core.TOPICS_DIR, "google_trends.json")
    trends = core.read_json(gt_file) or []
    return {"ok": True, "trends": trends, "count": len(trends)}


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
                       "link": "", "source": "", "view": "", "formulas": "", "pool_scores": "",
                       "badge": "", "is_kol": False, "kol_handle": ""}
                continue
            if cur is not None and pool:
                m2 = re.match(r"^- (主题方向|命中热点|建议视角|建议标题公式|评分构成|池内排序|原文链接|关注大V)[：:]\s*(.*)$", ln)
                if m2:
                    k_map = {
                        "主题方向": "title", "命中热点": "source",
                        "建议视角": "view", "建议标题公式": "formulas",
                        "评分构成": "breakdown", "池内排序": "pool_scores",
                        "原文链接": "link", "关注大V": "kol_handle",
                    }
                    cur[k_map[m2.group(1)]] = m2.group(2).strip()
        if cur is not None and pool:
            suggest[pool].append(cur)
        # 清理标题 Markdown 加粗与【出处】前缀，拆分「评分构成」结构化字段，补全高光徽章
        for c in suggest["daily"] + suggest["weekly"]:
            t = c.get("title", "")
            t = re.sub(r"^\s*\*+\s*", "", t)
            t = re.sub(r"\s*\*+\s*$", "", t)
            t = re.sub(r"^【[^】]+】\s*", "", t)
            c["title"] = t.strip()

            badge = ""
            s_field = c.get("source", "")
            if "𝕏 大V精选" in s_field or "X关注大V" in s_field or c.get("title", "").startswith("@") or c.get("kol_handle"):
                badge = "𝕏 大V精选"
                c["is_kol"] = True
            elif "🔥 谷歌暴增" in s_field or "谷歌趋势" in s_field:
                badge = "🔥 谷歌暴增"
            elif "HackerNews" in s_field:
                badge = "🟧 HackerNews"
            elif "GitHubTrending" in s_field or "GitHub" in s_field:
                badge = "🐙 GitHub"
            elif "ProductHunt" in s_field:
                badge = "🚀 ProductHunt"
            elif "Reddit" in s_field:
                badge = "🤖 Reddit AI"
            c["badge"] = badge

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

    # 分区聚合提取：构建 4 大分区海外热点榜
    categories = {
        "x_trends": [],
        "google_trends": [],
        "geek_dev": [],
        "product_community": [],
    }

    # 从雷达 sources 归集
    radar_source_map = {s["source"]: s.get("items", []) for s in radar["sources"]}

    # 1. 𝕏 大V与热点
    kol_posts = core.read_json(os.path.join(core.TOPICS_DIR, "kol_posts.json")) or []
    for p in kol_posts[:8]:
        h = p.get("handle", "")
        author = p.get("author_name") or h
        t = p.get("text", "")
        categories["x_trends"].append({
            "title": f"@{h}（{author}）：{t}"[:120],
            "link": p.get("url", f"https://x.com/{h}"),
            "source": "X关注大V",
            "badge": "𝕏 大V精选",
            "heat": f"{p.get('views', 0)} 阅 / {p.get('likes', 0)} 赞",
            "summary": t[:140],
        })
    for it in radar_source_map.get("X热点", [])[:6]:
        categories["x_trends"].append({
            "title": it["title"],
            "link": it.get("link", ""),
            "source": "X热点",
            "badge": "𝕏 热搜",
            "heat": "实时热议",
            "summary": it.get("summary", ""),
        })

    # 2. 🔥 谷歌趋势
    gt_cache = core.read_json(os.path.join(core.TOPICS_DIR, "google_trends.json")) or []
    for it in (radar_source_map.get("谷歌趋势") or gt_cache)[:12]:
        categories["google_trends"].append({
            "title": it.get("title", ""),
            "link": it.get("link", "https://trends.google.com"),
            "source": "谷歌趋势",
            "badge": it.get("badge") or "🔥 谷歌趋势",
            "heat": it.get("heat") or it.get("traffic") or "暴增",
            "summary": it.get("summary", ""),
        })

    # 3. 💻 极客开发 (Hacker News + GitHub Trending)
    hn_cache = core.read_json(os.path.join(core.TOPICS_DIR, "hackernews_cache.json")) or []
    for it in (radar_source_map.get("HackerNews") or hn_cache)[:8]:
        categories["geek_dev"].append({
            "title": it.get("title", ""),
            "link": it.get("link", ""),
            "source": "HackerNews",
            "badge": it.get("badge") or "🟧 HackerNews",
            "heat": it.get("heat") or "极客热榜",
            "summary": it.get("summary", ""),
        })
    gh_cache = core.read_json(os.path.join(core.TOPICS_DIR, "github_trending_cache.json")) or []
    for it in (radar_source_map.get("GitHubTrending") or gh_cache)[:8]:
        categories["geek_dev"].append({
            "title": it.get("title", ""),
            "link": it.get("link", ""),
            "source": "GitHub",
            "badge": it.get("badge") or "🐙 GitHubTrending",
            "heat": it.get("heat") or "Star 飙升",
            "summary": it.get("summary", ""),
        })

    # 4. 🚀 新产品与社区 (Product Hunt + Reddit AI)
    ph_cache = core.read_json(os.path.join(core.TOPICS_DIR, "producthunt_cache.json")) or []
    for it in (radar_source_map.get("ProductHunt") or ph_cache)[:8]:
        categories["product_community"].append({
            "title": it.get("title", ""),
            "link": it.get("link", ""),
            "source": "ProductHunt",
            "badge": it.get("badge") or "🚀 ProductHunt",
            "heat": it.get("heat") or "当日新品",
            "summary": it.get("summary", ""),
        })
    rd_cache = core.read_json(os.path.join(core.TOPICS_DIR, "reddit_cache.json")) or []
    for it in (radar_source_map.get("RedditAI") or rd_cache)[:8]:
        categories["product_community"].append({
            "title": it.get("title", ""),
            "link": it.get("link", ""),
            "source": "Reddit",
            "badge": it.get("badge") or "🤖 Reddit AI",
            "heat": it.get("heat") or "社区热议",
            "summary": it.get("summary", ""),
        })

    # 信息源状态：纯海外主力源矩阵
    configured = [
        "X关注大V", "X热点", "谷歌趋势", "HackerNews", "GitHubTrending", "ProductHunt", "RedditAI",
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

    kols_file = os.path.join(core.TOPICS_DIR, "kol_subscriptions.json")
    kols = core.read_json(kols_file) or []
    kol_summary = {
        "total": len(kols),
        "enabled": sum(1 for k in kols if k.get("enabled", True)),
    }

    return {
        "radar": radar,
        "suggest": suggest,
        "sources": sources,
        "categories": categories,
        "kol_summary": kol_summary,
    }


@router.post("/api/topics/fetch")
def api_fetch_all_topics():
    """即时触发全网海外热点刷新抓取。"""
    r = core.run_script(["fetch_hot_topics.py", "--top", "10"], timeout=45)
    core.run_script(["suggest_topics.py"], timeout=20)
    return api_topics()


class AdoptTopic(BaseModel):
    title: str
    link: str = ""
    notes: str = ""
    cover_template_id: str = ""
    account_id: str = ""
    offer_id: str = ""
    slots: dict = {}


@router.post("/api/topics/adopt")
def api_adopt(payload: AdoptTopic):
    core._license_guard("production")
    raw_title = payload.title or ""
    title = re.sub(r"[\r\n\t]+", " ", raw_title).strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题为空")
    title = title[:60]  # 超长标题自动截断，避免长选题无法建任务
    if len(payload.link) > 500 or len(payload.notes) > 500:
        raise HTTPException(status_code=400, detail="link/notes 过长")
    safe_slug = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]", "", title[:12]) or "未命名选题"
    base_id = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_slug[:12]}"
    job_id = base_id
    counter = 1
    while os.path.exists(os.path.join(core.JOBS_DIR, job_id)):
        job_id = f"{base_id}_{counter}"
        counter += 1
    core._require_job_id(job_id)
    r = core.run_script(["job_state.py", "init", job_id, "--theme", title], timeout=15)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))

    jdir = os.path.join(core.JOBS_DIR, job_id)
    os.makedirs(jdir, exist_ok=True)
    if not os.path.isfile(os.path.join(jdir, "state.json")):
        now_s = core._now_str()
        core._atomic_write_json(os.path.join(jdir, "state.json"), {
            "job_id": job_id,
            "theme": title,
            "state": "topic",
            "created_at": now_s,
            "updated_at": now_s,
            "history": [{"state": "topic", "at": now_s, "note": "工作台选题采纳"}],
            "reject_count": 0,
            "scores": {},
        })
    
    # 保存任务绑定的封面模板与角色插槽配置
    slots_data = core.read_json(core.PIPELINE_SLOTS_FILE) or {"slots": {}}
    active_slots = dict(slots_data.get("slots", {}))
    if payload.slots:
        active_slots.update(payload.slots)
    if payload.cover_template_id:
        active_slots["cover_template"] = {
            "template_id": payload.cover_template_id,
        }

    acc_id = (payload.account_id or "").strip()
    offer_id = (payload.offer_id or "").strip()
    acc_name = ""
    acc_persona = ""
    acc_angle = ""
    style_preset = ""
    if acc_id:
        for a in core._load_matrix_accounts():
            if a.get("id") == acc_id:
                acc_name = a.get("name", "")
                acc_persona = a.get("persona", "")
                acc_angle = a.get("angle_hint") or a.get("angle") or ""
                style_preset = a.get("style_preset", "")
                if not offer_id:
                    offer_id = a.get("default_offer_id", "")
                break

    pipeline_cfg = {
        "job_id": job_id,
        "theme": title,
        "account_id": acc_id,
        "account_name": acc_name,
        "account_persona": acc_persona,
        "account_angle": acc_angle,
        "style_preset": style_preset,
        "offer_id": offer_id,
        "cover_template_id": payload.cover_template_id or active_slots.get("cover_template", {}).get("template_id", ""),
        "slots": active_slots,
        "created_at": core._now_str(),
    }
    with open(os.path.join(jdir, "pipeline_config.json"), "w", encoding="utf-8") as f:
        json.dump(pipeline_cfg, f, ensure_ascii=False, indent=2)

    brief = "\n".join([
        f"# 生产简报",
        f"- Job：{job_id}",
        f"- 主题：{title}",
        f"- 所属矩阵号：{acc_name or acc_id or '默认主号'}",
        f"- 商业化组件：{offer_id or '默认'}",
        f"- 采纳来源：{payload.link.strip() or '工作台选题推荐'}",
        f"- 封面模板：{pipeline_cfg['cover_template_id'] or '未指定'}",
        f"- 附加说明：{payload.notes.strip() or '无'}",
        "",
    ])
    with open(os.path.join(core.JOBS_DIR, job_id, "brief.md"), "w", encoding="utf-8") as f:
        f.write(brief)
    core._enqueue_job(job_id)
    started = core._kick_production()
    return {"job_id": job_id, "result": r, "production_started": started, "pipeline_config": pipeline_cfg}



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

