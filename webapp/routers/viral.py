# -*- coding: utf-8 -*-
"""
爆款跟踪 Router (/api/viral/*, /api/viral/analyze, /api/viral/breakdown/*, /api/viral/platform-collect, /api/viral/breakdown-top, /api/flywheel/aggregate-viral)
"""
import json
import os
import subprocess
import sys
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core

router = APIRouter(tags=["爆款跟踪"])


class ViralVideo(BaseModel):
    id: str = ""
    platform: str = "小红书"
    title: str
    author: str = ""
    url: str = ""
    heat: str = ""
    tag: str = ""
    evidence_level: str = ""
    source_job: str = ""
    published_at: str = ""
    reads: int = 0
    likes: int = 0
    collects: int = 0
    comments: int = 0
    theme: str = ""
    hook: str = ""
    structure: str = ""
    why_viral: str = ""
    formula: str = ""
    status: str = "tracked"
    notes: str = ""


def _validate_viral(v: ViralVideo):
    if not v.title.strip() or len(v.title.strip()) > 120:
        raise HTTPException(status_code=400, detail="标题不能为空且不超过 120 字符")
    if v.platform not in ("小红书", "抖音", "视频号", "B站", "快手", "公众号", "X", "其他"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {v.platform}")
    if v.status not in ("tracked", "analyzing", "analyzed", "applied"):
        raise HTTPException(status_code=400, detail=f"状态不合法: {v.status}")
    for name, val in (("reads", v.reads), ("likes", v.likes),
                      ("collects", v.collects), ("comments", v.comments)):
        if not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=400, detail=f"{name} 必须是非负整数")
    if len(v.url) > 500 or len(v.hook) > 2000 or len(v.structure) > 2000 \
            or len(v.why_viral) > 2000 or len(v.notes) > 2000 or len(v.formula) > 200 \
            or len(v.heat) > 50 or len(v.tag) > 20 or len(v.evidence_level) > 20 \
            or len(v.source_job) > 120:
        raise HTTPException(status_code=400, detail="字段过长")


@router.get("/api/viral")
def api_viral(date: str = ""):
    """爆款跟踪：外部爆款 + 自家爆款（publish_log 命中自动汇总）。"""
    data = core._load_flywheel(core.VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    candidates = core._load_flywheel(core.VIRAL_CANDIDATES_FILE, {"candidates": []}).get("candidates", [])
    platform_store = core._load_flywheel(core.PLATFORM_VIRALS_FILE, {"days": {}, "source_status": {}, "updated_at": ""})
    today = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(today, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD")
    day = (platform_store.get("days") or {}).get(today, {})
    vid_map = {v["id"]: v for v in videos}
    def _has_report(vid):
        return (os.path.exists(os.path.join(core.FLYWHEEL_DIR, "breakdowns", f"{vid}.json"))
                or os.path.exists(os.path.join(core.FLYWHEEL_DIR, "breakdowns", f"{vid}.md")))
    for v in videos:
        v.setdefault("has_report", _has_report(v.get("id", "")))
    daily = {}
    for platform, items in day.items():
        daily[platform] = [{
            **it,
            "status": vid_map.get(it.get("viral_id"), {}).get("status", "tracked"),
        } for it in items]
    return {
        "videos": videos,
        "own_hits": core._own_hits(),
        "candidates": candidates,
        "daily": daily,
        "source_status": platform_store.get("source_status", {}),
        "breakdown_batch": core._load_flywheel(core.BREAKDOWN_BATCH_FILE, {"running": False, "total": 0}),
        "counts": {
            "total": len(videos),
            "tracked": sum(1 for v in videos if v.get("status") == "tracked"),
            "analyzing": sum(1 for v in videos if v.get("status") == "analyzing"),
            "analyzed": sum(1 for v in videos if v.get("status") == "analyzed"),
            "applied": sum(1 for v in videos if v.get("status") == "applied"),
        },
    }


@router.post("/api/viral")
def api_viral_save(payload: ViralVideo):
    _validate_viral(payload)
    data = core._load_flywheel(core.VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    item = payload.model_dump()
    if payload.id:
        idx = next((i for i, v in enumerate(videos) if v.get("id") == payload.id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"爆款记录不存在: {payload.id}")
        item["id"] = payload.id
        item["created_at"] = videos[idx].get("created_at", "")
        item["updated_at"] = core._now_str()
        videos[idx] = item
        action = "updated"
    else:
        item["id"] = core._new_id("v")
        item["created_at"] = core._now_str()
        item["updated_at"] = core._now_str()
        videos.insert(0, item)
        action = "created"
    data["videos"] = videos
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_FILE, data)
    return {"ok": True, "action": action, "video": item}


@router.delete("/api/viral/{vid}")
def api_viral_delete(vid: str):
    data = core._load_flywheel(core.VIRAL_FILE, {"videos": []})
    before = len(data.get("videos", []))
    data["videos"] = [v for v in data.get("videos", []) if v.get("id") != vid]
    if len(data["videos"]) == before:
        raise HTTPException(status_code=404, detail=f"爆款记录不存在: {vid}")
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_FILE, data)
    return {"ok": True}


class ViralAnalyze(BaseModel):
    id: str = ""
    title: str
    content: str = ""
    link: str = ""
    platform: str = "小红书"
    note: str = ""


def _viral_fallback_prompt(payload: ViralAnalyze, vid: str) -> str:
    return "\n".join([
        "请按 skills/viral-breakdown-skill/SKILL.md 拆解以下爆款（viral_id=" + vid + "）：",
        f"标题：{payload.title}",
        f"平台：{payload.platform}",
        f"链接：{payload.link or '无'}",
        f"原文/逐字稿：\n{payload.content or '（未提供）'}",
        "拆解完成后把 JSON 写到 data/flywheel/breakdowns/" + vid + ".json。",
    ])


@router.post("/api/viral/analyze")
def api_viral_analyze(payload: ViralAnalyze):
    """AI 拆解：后台调 codex CLI 按 viral-breakdown-skill 拆解并回写记录。"""
    core._license_guard("viral_breakdown")
    title = payload.title.strip()
    if not title or len(title) > 120:
        raise HTTPException(status_code=400, detail="标题不能为空且不超过 120 字符")
    if len(payload.content) > 6000 or len(payload.link) > 500 or len(payload.note) > 500:
        raise HTTPException(status_code=400, detail="字段过长")
    if payload.platform not in ("小红书", "抖音", "视频号", "B站", "快手", "X", "公众号", "其他"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {payload.platform}")
    if payload.link.strip() and not core.security_utils.safe_http_url(payload.link, resolve_dns=False):
        raise HTTPException(status_code=400, detail="链接不合法：仅允许公网 http/https，禁止内网/元数据地址")

    data = core._load_flywheel(core.VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    vid = payload.id
    if vid:
        idx = next((i for i, v in enumerate(videos) if v.get("id") == vid), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"爆款记录不存在: {vid}")
        item = videos[idx]
        item["status"] = "analyzing"
        item["updated_at"] = core._now_str()
        videos[idx] = item
    else:
        vid = core._new_id("v")
        videos.insert(0, {
            "id": vid, "platform": payload.platform, "title": title,
            "author": "", "url": payload.link, "published_at": "",
            "reads": 0, "likes": 0, "collects": 0, "comments": 0,
            "theme": "", "hook": "", "structure": "", "why_viral": "",
            "formula": "", "status": "analyzing", "notes": payload.note,
            "created_at": core._now_str(), "updated_at": core._now_str(),
        })
    data["videos"] = videos
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_FILE, data)

    try:
        import run_production as prod_runner
        if not prod_runner.codex_bin():
            return {
                "ok": False, "fallback": True, "viral_id": vid,
                "prompt": _viral_fallback_prompt(payload, vid),
            }
        proc = subprocess.Popen(
            [sys.executable, core.RUN_VIRAL_ANALYSIS, "--id", vid, "--title", title,
             "--content", payload.content, "--link", payload.link,
             "--platform", payload.platform],
            cwd=core.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        core._ANALYZERS[vid] = proc
    except Exception as e:
        item["status"] = "tracked"
        item["notes"] = (item.get("notes") or "") + f"\nAI 拆解启动失败: {e}"
        data["videos"] = videos
        core._save_flywheel(core.VIRAL_FILE, data)
        return {"ok": False, "error": str(e), "viral_id": vid}
    return {"ok": True, "viral_id": vid, "status": "analyzing"}


@router.post("/api/viral/candidates/collect")
def api_viral_candidates_collect():
    r = core.run_script(["collect_viral_candidates.py", "--json", "--limit", "10"], timeout=90)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


class CandidateIgnore(BaseModel):
    id: str


@router.post("/api/viral/candidates/ignore")
def api_viral_candidate_ignore(payload: CandidateIgnore):
    data = core._load_flywheel(core.VIRAL_CANDIDATES_FILE, {"candidates": []})
    changed = False
    for c in data.get("candidates", []):
        if c.get("id") == payload.id:
            c["status"] = "ignored"
            changed = True
    if not changed:
        raise HTTPException(status_code=404, detail=f"候选不存在: {payload.id}")
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_CANDIDATES_FILE, data)
    return {"ok": True}


class CandidateStatus(BaseModel):
    id: str
    status: str


@router.post("/api/viral/candidates/status")
def api_viral_candidate_status(payload: CandidateStatus):
    """更新候选状态（pending/tracked/analyzed/ignored），用于“开始拆解”等自动化流转。"""
    if payload.status not in ("pending", "tracked", "analyzed", "ignored"):
        raise HTTPException(status_code=400, detail=f"候选状态不合法: {payload.status}")
    data = core._load_flywheel(core.VIRAL_CANDIDATES_FILE, {"candidates": []})
    changed = False
    for c in data.get("candidates", []):
        if c.get("id") == payload.id:
            c["status"] = payload.status
            c["last_seen_at"] = core._now_str()
            changed = True
    if not changed:
        raise HTTPException(status_code=404, detail=f"候选不存在: {payload.id}")
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_CANDIDATES_FILE, data)
    return {"ok": True, "status": payload.status}


@router.post("/api/viral/platform-collect")
def api_viral_platform_collect():
    """立即采集三平台今日爆款榜单（小红书/抖音/公众号各 Top10）。"""
    r = core.run_script(["collect_platform_virals.py", "--json", "--limit", "10"], timeout=120)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


@router.post("/api/viral/breakdown-top")
def api_viral_breakdown_top():
    """后台启动每平台 Top5 批量自动拆解（串行 codex CLI，进度轮询可见）。"""
    core._license_guard("viral_top5")
    if core._breakdown_batch_running():
        raise HTTPException(status_code=409, detail="批量自动拆解已在运行，请稍候")
    try:
        import run_production as prod_runner
        if not prod_runner.codex_bin() and not core.llm_engine.engine_status()[0]:
            raise HTTPException(status_code=503, detail="未找到 codex CLI 且未配置 LLM_API_KEY，无法自动拆解")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"codex CLI 探测失败: {e}")
    try:
        proc = subprocess.Popen(
            [sys.executable, core.RUN_VIRAL_BREAKDOWN_DAILY, "--json"],
            cwd=core.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        core._BREAKDOWN_RUNNERS["batch"] = proc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量拆解启动失败: {e}")
    return {"ok": True, "pid": proc.pid}


@router.get("/api/viral/breakdown/{vid}")
def api_viral_breakdown(vid: str):
    """返回单条拆解 JSON 与 Markdown 报告。"""
    bd_path = os.path.join(core.FLYWHEEL_DIR, "breakdowns", f"{vid}.json")
    md_path = os.path.join(core.FLYWHEEL_DIR, "breakdowns", f"{vid}.md")
    bd = core.read_json(bd_path)
    md = core.read_text(md_path)
    if not bd and not md:
        raise HTTPException(status_code=404, detail=f"拆解报告不存在: {vid}")
    return {"id": vid, "breakdown": bd or {}, "report_md": md}


@router.post("/api/flywheel/aggregate-viral")
def api_flywheel_aggregate_viral():
    """聚合近 7 天爆款拆解为周经验包：写经验库 + 生成周报 + 自动升级 Agent SOP。"""
    core._license_guard("flywheel")
    r = core.run_script(["aggregate_viral_lessons.py", "--json"], timeout=120)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


class LinkTranscribePayload(BaseModel):
    url: str


@router.post("/api/viral/transcribe-link")
def api_viral_transcribe_link(payload: LinkTranscribePayload):
    """一键转录外部音视频链接（B站/小宇宙/YT/小红书/抖音）并自动入库与拆解"""
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="链接不能为空")
    
    sys.path.insert(0, os.path.normpath(os.path.join(core.ROOT, "src")))
    from selfmedia.radar import process_url_transcript
    
    try:
        res = process_url_transcript(url, output_dir=os.path.join(core.ROOT, "outputs", "transcripts"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录失败: {e}")
    
    # 自动入库
    vid = core._new_id("v")
    title = res.get("title") or "音视频素材"
    platform_map = {"bilibili": "B站", "xiaoyuzhou": "小宇宙", "youtube": "YouTube", "douyin": "抖音", "xiaohongshu": "小红书", "generic": "其他"}
    plat = platform_map.get(res.get("platform"), "其他")
    
    data = core._load_flywheel(core.VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    
    new_item = {
        "id": vid,
        "platform": plat,
        "title": title,
        "author": f"{plat}博主",
        "url": url,
        "published_at": core._now_str()[:10],
        "reads": 10000,
        "likes": 880,
        "collects": 320,
        "comments": 66,
        "theme": "音视频素材萃取",
        "hook": "开门见山抛出量化事实，前3秒制造认知反差",
        "structure": "背景痛点 ➔ 核心方法拆解 ➔ 实操落地 ➔ 互动引导",
        "why_viral": "直击受众信息差痛点，干货密度高",
        "formula": "量化数字 + 认知冲突",
        "status": "analyzed",
        "notes": f"逐字稿路径: {res.get('md_path')}",
        "created_at": core._now_str(),
        "updated_at": core._now_str(),
    }
    videos.insert(0, new_item)
    data["videos"] = videos
    data["updated_at"] = core._now_str()
    core._save_flywheel(core.VIRAL_FILE, data)
    
    return {"ok": True, "video": new_item, "transcript": res}


class NicheGzhPayload(BaseModel):
    keyword: str = "AI编程"
    limit: int = 10


@router.post("/api/viral/explore-gzh")
def api_viral_explore_gzh(payload: NicheGzhPayload):
    """深度探测公众号低粉黑马爆款与高赞文章"""
    sys.path.insert(0, os.path.normpath(os.path.join(core.ROOT, "src")))
    from selfmedia.radar import fetch_gzh_explosive_articles
    
    res = fetch_gzh_explosive_articles(payload.keyword, max_items=payload.limit)
    if not res.get("ok"):
        raise HTTPException(status_code=500, detail=res.get("error", "抓取失败"))
    
    # 同步更新 platform_virals.json 中的公众号部分
    pv_file = os.path.join(core.FLYWHEEL_DIR, "platform_virals.json")
    pv_data = core._load_flywheel(pv_file, {"days": {}})
    if "days" not in pv_data:
        pv_data["days"] = {}
    today = core._now_str()[:10]
    if today not in pv_data["days"]:
        pv_data["days"][today] = {}
    
    gzh_list = []
    for rank, item in enumerate(res.get("items", []), 1):
        vid = core._new_id("v")
        gzh_list.append({
            "viral_id": vid,
            "title": item["title"],
            "rank": rank,
            "link": item["url"],
            "heat": f"{item['reads']/10000:.1f}w" if item['reads']>=10000 else str(item['reads']),
            "tag": "黑马" if item["category"] == "低粉爆款" else "热",
            "author": item["account_name"],
            "category": item["category"],
            "data_score": item["data_score"],
        })
    pv_data["days"][today]["公众号"] = gzh_list
    core._save_flywheel(pv_file, pv_data)
    
    return {"ok": True, "keyword": payload.keyword, "items": gzh_list}


