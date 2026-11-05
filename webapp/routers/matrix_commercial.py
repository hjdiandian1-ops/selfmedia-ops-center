# -*- coding: utf-8 -*-
"""
矩阵号运营、日更排期 SLA 与商业化闭环 Router
================================================
覆盖工业级自媒体运营中台三大核心支柱：
1. 日更引擎 (/api/ops/daily-sla, /api/ops/daily-autopilot, /api/ops/schedule*)
2. 矩阵号管理与一鱼多吃裂变分发 (/api/matrix/accounts*, /api/matrix/dispatch)
3. 商业化闭环与 ROI 漏斗台账 (/api/commercial/offers*, /api/commercial/ledger*, /api/commercial/overview)
"""
import glob
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core

router = APIRouter(tags=["矩阵号与商业化闭环"])

ALLOWED_PLATFORMS = ("小红书", "公众号", "短视频", "X", "B站", "抖音", "视频号")
ALLOWED_OFFER_TYPES = {
    "lead_magnet": "私域引流",
    "product": "SaaS/电商带货",
    "course": "社群/知识付费",
    "sponsor": "品牌商单",
    "ad_share": "平台流量主分成",
    "course_community": "付费社群/专栏",
    "affiliate_saas": "工具带货/SaaS",
    "brand_sponsor": "品牌商单合作",
    "consulting": "企业咨询/内训",
}


# =========================================================================
# Pydantic Schemas
# =========================================================================
class MatrixAccountPayload(BaseModel):
    id: str = ""
    name: str
    handle: str = ""
    platforms: List[str] = ["小红书", "公众号"]
    niche: str = ""
    persona: str = ""
    target_audience: str = ""
    angle: str = ""
    angle_hint: str = ""
    style_preset: str = "xiaowuliao-style"
    daily_target: int = 1
    default_offer_id: str = ""
    gzh_app_id: Optional[str] = None
    gzh_app_secret: Optional[str] = None
    enabled: bool = True


class MatrixDispatchPayload(BaseModel):
    title: str
    link: str = ""
    notes: str = ""
    account_ids: List[str] = []
    offer_id: str = ""
    cover_template_id: str = ""
    auto_start: bool = True


class DailyAutopilotPayload(BaseModel):
    account_ids: List[str] = []
    force: bool = False
    max_jobs: int = 3


class ScheduleSlotPayload(BaseModel):
    id: str = ""
    date: str = ""
    time: str = "09:00"
    account_id: str = "acc_main"
    title: str
    platform: str = "小红书"
    offer_id: str = ""
    notes: str = ""
    status: str = "planned"  # planned | queued | published


class CommercialOfferPayload(BaseModel):
    id: str = ""
    name: str
    type: str = "lead_magnet"
    price_yuan: float = 0.0
    lead_value_yuan: float = 15.0
    keyword: str = ""
    cta_xhs: str = ""
    cta_gzh: str = ""
    cta_video: str = ""
    enabled: bool = True


class CommercialLedgerPayload(BaseModel):
    id: str = ""
    job_id: str = ""
    title: str = ""
    account_id: str = "acc_main"
    platform: str = "小红书"
    offer_id: str = ""
    revenue_type: str = "lead_magnet"
    reads: int = 0
    leads: int = 0
    conversions: int = 0
    revenue_yuan: float = 0.0
    note: str = ""
    recorded_at: str = ""


# =========================================================================
# Helper Functions
# =========================================================================
def _job_date_str(job_id: str, state_data: dict) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", job_id or "")
    if m:
        return m.group(1)
    created = (state_data or {}).get("created_at") or (state_data or {}).get("updated_at") or ""
    if len(created) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", created[:10]):
        return created[:10]
    return ""


def _job_account_and_offer(job_id: str) -> tuple:
    cfg = core.read_json(os.path.join(core.JOBS_DIR, job_id, "pipeline_config.json")) or {}
    return cfg.get("account_id") or "acc_main", cfg.get("offer_id") or ""


def _create_job_for_account(
    title: str,
    account: dict,
    link: str = "",
    notes: str = "",
    offer_id: str = "",
    cover_template_id: str = "",
    Differentiated: bool = False,
) -> dict:
    """为指定矩阵号创建生产任务、落盘 pipeline_config.json 与 brief.md 并入队。"""
    clean_title = re.sub(r"[\r\n\t]+", " ", (title or "").strip())
    if not clean_title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    acc_id = account.get("id") or "acc_main"
    acc_name = account.get("name") or acc_id
    angle_hint = account.get("angle_hint") or account.get("angle") or account.get("persona") or ""
    effective_offer_id = offer_id or account.get("default_offer_id") or ""

    # 若为一鱼多吃裂变模式，结合账号定位生成差异化主题后缀
    if Differentiated and angle_hint:
        short_angle = angle_hint.split("+")[0].strip()[:10]
        full_theme = f"{clean_title[:42]}（{short_angle}）"
    else:
        full_theme = clean_title[:60]

    safe_slug = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]", "", clean_title[:10]) or "矩阵任务"
    acc_tag = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]", "", acc_id.replace("acc_", ""))[:6]
    today = datetime.now().strftime("%Y-%m-%d")
    base_id = f"{today}_{acc_tag}_{safe_slug}" if acc_tag else f"{today}_{safe_slug}"
    base_id = base_id[:36]
    job_id = base_id
    counter = 1
    while os.path.exists(os.path.join(core.JOBS_DIR, job_id)):
        job_id = f"{base_id}_{counter}"
        counter += 1

    core._require_job_id(job_id)
    r = core.run_script(["job_state.py", "init", job_id, "--theme", full_theme], timeout=15)
    jdir = os.path.join(core.JOBS_DIR, job_id)
    if not r.get("ok") or not os.path.isfile(os.path.join(jdir, "state.json")):
        os.makedirs(jdir, exist_ok=True)
        now_s = core._now_str()
        core._atomic_write_json(os.path.join(jdir, "state.json"), {
            "job_id": job_id,
            "theme": full_theme,
            "state": "topic",
            "created_at": now_s,
            "updated_at": now_s,
            "history": [{"state": "topic", "at": now_s, "note": f"矩阵号[{acc_name}]任务创建"}],
            "reject_count": 0,
            "scores": {},
        })

    slots_data = core.read_json(core.PIPELINE_SLOTS_FILE) or {"slots": {}}
    active_slots = dict(slots_data.get("slots", {}))
    if cover_template_id:
        active_slots["cover_template"] = {"template_id": cover_template_id}

    offers_map = {o["id"]: o for o in core._load_commercial_offers()}
    bound_offer = offers_map.get(effective_offer_id, {})

    pipeline_cfg = {
        "job_id": job_id,
        "theme": full_theme,
        "base_topic": clean_title[:60],
        "account_id": acc_id,
        "account_name": acc_name,
        "account_persona": account.get("persona", ""),
        "account_angle": angle_hint,
        "platforms": account.get("platforms", ["小红书", "公众号"]),
        "style_preset": account.get("style_preset", "xiaowuliao-style"),
        "offer_id": effective_offer_id,
        "offer_name": bound_offer.get("name", ""),
        "cover_template_id": cover_template_id or active_slots.get("cover_template", {}).get("template_id", ""),
        "slots": active_slots,
        "created_at": core._now_str(),
    }
    os.makedirs(jdir, exist_ok=True)
    core._atomic_write_json(os.path.join(jdir, "pipeline_config.json"), pipeline_cfg)

    brief_lines = [
        "# 生产简报（矩阵号专属定制）",
        f"- Job：{job_id}",
        f"- 主题：{full_theme}",
        f"- 所属矩阵号：{acc_name} ({acc_id})",
        f"- 账号人设与定位：{account.get('persona') or account.get('niche') or '默认极客操盘手'}",
        f"- 差异化切入视角：{angle_hint or '深度拆解与实操闭环'}",
        f"- 目标分发平台：{' / '.join(account.get('platforms') or ['小红书', '公众号'])}",
        f"- 商业化挂载组件：{bound_offer.get('name') or '默认关注引导'}",
        f"- 采纳来源：{link.strip() or '矩阵运营中台分发'}",
        f"- 附加说明：{notes.strip() or '无'}",
        "",
    ]
    with open(os.path.join(jdir, "brief.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(brief_lines))

    core._enqueue_job(job_id)
    return {
        "job_id": job_id,
        "account_id": acc_id,
        "account_name": acc_name,
        "theme": full_theme,
        "angle": angle_hint,
        "offer_id": effective_offer_id,
    }


# =========================================================================
# 1. 矩阵号管理与一鱼多吃裂变分发 (/api/matrix/*)
# =========================================================================
@router.get("/api/matrix/accounts")
def api_matrix_accounts():
    """获取矩阵号列表及各账号的实时生产、流量与商业化表现聚合。"""
    accounts = core._load_matrix_accounts()
    offers_map = {o["id"]: o for o in core._load_commercial_offers()}
    ledger_entries = core._load_commercial_ledger().get("entries", [])
    today = datetime.now().strftime("%Y-%m-%d")

    # 聚合每个账号的 Job 指标
    acc_stats = {
        a["id"]: {
            "jobs_total": 0,
            "total_jobs": 0,
            "published_total": 0,
            "today_produced": 0,
            "today_jobs": 0,
            "today_published": 0,
            "reads": 0,
            "likes": 0,
            "collects": 0,
            "leads": 0,
            "conversions": 0,
            "revenue_yuan": 0.0,
        }
        for a in accounts
    }
    default_acc_id = accounts[0]["id"] if accounts else "acc_main"

    if os.path.isdir(core.JOBS_DIR):
        for d in sorted(os.listdir(core.JOBS_DIR)):
            sf = os.path.join(core.JOBS_DIR, d, "state.json")
            st = core.read_json(sf)
            if not st:
                continue
            acc_id, _ = _job_account_and_offer(d)
            if acc_id not in acc_stats:
                acc_id = default_acc_id
            bucket = acc_stats.setdefault(acc_id, {
                "jobs_total": 0, "total_jobs": 0, "published_total": 0, "today_produced": 0,
                "today_jobs": 0, "today_published": 0, "reads": 0, "likes": 0, "collects": 0,
                "leads": 0, "conversions": 0, "revenue_yuan": 0.0,
            })
            bucket["jobs_total"] += 1
            bucket["total_jobs"] += 1
            jdate = _job_date_str(d, st)
            if jdate == today:
                bucket["today_produced"] += 1
                bucket["today_jobs"] += 1

            lg = core.read_json(os.path.join(core.JOBS_DIR, d, "publish_log.json")) or {}
            is_pub = bool(lg.get("publish")) or st.get("state") in ("publish", "recycle")
            if is_pub:
                bucket["published_total"] += 1
                pub_at = lg.get("published_at") or ""
                if pub_at.startswith(today) or jdate == today:
                    bucket["today_published"] += 1
            for rec in lg.get("records", []):
                bucket["reads"] += int(rec.get("reads") or 0)
                bucket["likes"] += int(rec.get("likes") or 0)
                bucket["collects"] += int(rec.get("collects") or 0)

    for entry in ledger_entries:
        aid = entry.get("account_id") or default_acc_id
        if aid not in acc_stats:
            aid = default_acc_id
        bucket = acc_stats[aid]
        bucket["leads"] += int(entry.get("leads") or 0)
        bucket["conversions"] += int(entry.get("conversions") or 0)
        bucket["revenue_yuan"] = round(bucket["revenue_yuan"] + float(entry.get("revenue_yuan") or 0.0), 2)

    enriched = []
    for a in accounts:
        aid = a["id"]
        st = acc_stats.get(aid, {})
        offer = offers_map.get(a.get("default_offer_id", ""), {})
        raw_dt = a.get("daily_target")
        daily_target = max(0, int(raw_dt)) if raw_dt is not None else 1
        item = dict(a)
        item["angle"] = item.get("angle") or item.get("angle_hint") or ""
        item["gzh_secret_masked"] = core._mask(a.get("gzh_app_secret", ""))
        item["gzh_configured"] = bool((a.get("gzh_app_id") or "").strip() and (a.get("gzh_app_secret") or "").strip())
        item.pop("gzh_app_secret", None)
        item["default_offer_name"] = offer.get("name", "未绑定")
        item["stats"] = st
        item["quota_met"] = st.get("today_produced", 0) >= daily_target
        enriched.append(item)

    return {
        "ok": True,
        "accounts": enriched,
        "total": len(enriched),
        "enabled_count": sum(1 for x in enriched if x.get("enabled", True)),
    }


@router.post("/api/matrix/accounts")
def api_matrix_account_save(payload: MatrixAccountPayload):
    """新增或更新矩阵号配置。"""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="账号名称不能为空")
    if payload.daily_target < 0 or payload.daily_target > 50:
        raise HTTPException(status_code=400, detail="日更目标篇数需在 0~50 之间")
    raw_platforms = [p.strip() for p in (payload.platforms or []) if p.strip()]
    invalid_platforms = [p for p in raw_platforms if p not in ALLOWED_PLATFORMS]
    if invalid_platforms:
        raise HTTPException(status_code=400, detail=f"存在不支持的平台: {', '.join(invalid_platforms)}")
    platforms = raw_platforms or ["小红书", "公众号"]

    angle_val = (payload.angle_hint or payload.angle or "").strip()[:200]
    accounts = core._load_matrix_accounts()
    acc_id = (payload.id or "").strip()
    existing = next((a for a in accounts if a.get("id") == acc_id), None) if acc_id else None

    if existing:
        existing["name"] = name[:60]
        existing["handle"] = (payload.handle or "").strip()[:40]
        existing["platforms"] = platforms
        existing["niche"] = (payload.niche or "").strip()[:80]
        existing["persona"] = (payload.persona or "").strip()[:300]
        existing["target_audience"] = (payload.target_audience or existing.get("target_audience") or "").strip()[:120]
        existing["angle_hint"] = angle_val or existing.get("angle_hint", "")
        existing["angle"] = existing["angle_hint"]
        existing["style_preset"] = (payload.style_preset or "xiaowuliao-style").strip()
        existing["daily_target"] = int(payload.daily_target)
        existing["default_offer_id"] = (payload.default_offer_id or "").strip()
        existing["enabled"] = bool(payload.enabled)
        if payload.gzh_app_id is not None:
            existing["gzh_app_id"] = payload.gzh_app_id.strip()
        if payload.gzh_app_secret is not None and payload.gzh_app_secret.strip():
            existing["gzh_app_secret"] = payload.gzh_app_secret.strip()
        action = "updated"
        target = existing
    else:
        slug = re.sub(r"[^a-zA-Z0-9_]", "", acc_id) if acc_id else ""
        if not slug:
            slug = f"acc_{datetime.now().strftime('%m%d%H%M%S')}_{os.urandom(2).hex()}"
        if any(a.get("id") == slug for a in accounts):
            raise HTTPException(status_code=400, detail=f"账号 ID 已存在: {slug}")
        target = {
            "id": slug,
            "name": name[:60],
            "handle": (payload.handle or "").strip()[:40],
            "platforms": platforms,
            "niche": (payload.niche or "").strip()[:80],
            "persona": (payload.persona or "").strip()[:300],
            "target_audience": (payload.target_audience or "").strip()[:120],
            "angle_hint": angle_val,
            "angle": angle_val,
            "style_preset": (payload.style_preset or "xiaowuliao-style").strip(),
            "daily_target": int(payload.daily_target),
            "default_offer_id": (payload.default_offer_id or "").strip(),
            "gzh_app_id": (payload.gzh_app_id or "").strip(),
            "gzh_app_secret": (payload.gzh_app_secret or "").strip(),
            "enabled": bool(payload.enabled),
            "created_at": core._now_str(),
        }
        accounts.append(target)
        action = "created"

    core._save_matrix_accounts(accounts)
    safe_target = dict(target)
    safe_target["gzh_secret_masked"] = core._mask(target.get("gzh_app_secret", ""))
    safe_target["gzh_configured"] = bool((target.get("gzh_app_id") or "").strip() and (target.get("gzh_app_secret") or "").strip())
    safe_target.pop("gzh_app_secret", None)
    return {"ok": True, "action": action, "account": safe_target}


@router.delete("/api/matrix/accounts/{account_id}")
def api_matrix_account_delete(account_id: str):
    """删除矩阵号（至少保留 1 个主账号）。"""
    accounts = core._load_matrix_accounts()
    if len(accounts) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留 1 个矩阵账号")
    filtered = [a for a in accounts if a.get("id") != account_id]
    if len(filtered) == len(accounts):
        raise HTTPException(status_code=404, detail=f"未找到矩阵号: {account_id}")
    core._save_matrix_accounts(filtered)
    return {"ok": True, "deleted": account_id, "remaining": len(filtered)}


@router.post("/api/matrix/dispatch")
def api_matrix_dispatch(payload: MatrixDispatchPayload):
    """一鱼多吃 · 矩阵裂变分发：同一母题按各矩阵号人设与变现组件自动裂变出多个差异化生产任务。"""
    core._license_guard("production")
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="裂变母题不能为空")

    accounts = core._load_matrix_accounts()
    if payload.account_ids:
        selected = [a for a in accounts if a.get("id") in payload.account_ids]
    else:
        selected = [a for a in accounts if a.get("enabled", True)]

    if not selected:
        raise HTTPException(status_code=400, detail="未匹配到可用的目标矩阵账号")

    dispatched = []
    differentiate = len(selected) > 1
    for acc in selected:
        job_info = _create_job_for_account(
            title=title,
            account=acc,
            link=payload.link,
            notes=payload.notes,
            offer_id=payload.offer_id,
            cover_template_id=payload.cover_template_id,
            Differentiated=differentiate,
        )
        dispatched.append(job_info)

    started = core._kick_production() if payload.auto_start else None
    return {
        "ok": True,
        "topic": title,
        "dispatched_count": len(dispatched),
        "jobs": dispatched,
        "production_started": started,
    }


# =========================================================================
# 2. 日更排期与 SLA 监控 (/api/ops/*)
# =========================================================================
def _load_schedule_slots() -> list:
    data = core.read_json(core.DAILY_SCHEDULE_FILE)
    if isinstance(data, dict) and isinstance(data.get("slots"), list):
        return data["slots"]
    return []


def _save_schedule_slots(slots: list) -> None:
    core._atomic_write_json(core.DAILY_SCHEDULE_FILE, {"slots": slots, "updated_at": core._now_str()})


@router.get("/api/ops/daily-sla")
def api_daily_sla():
    """日更 SLA 监控大盘：连续日更天数、今日配额达成率、30 天日更热力图与排期表。"""
    accounts = core._load_matrix_accounts()
    enabled_accounts = [a for a in accounts if a.get("enabled", True)]
    daily_target_total = sum(max(0, int(a.get("daily_target") or 0)) for a in enabled_accounts) or 1

    today_dt = datetime.now().date()
    today_str = today_dt.isoformat()
    days_30 = [(today_dt - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    day_map = {
        d: {"date": d, "produced": 0, "published": 0, "jobs": []}
        for d in days_30
    }
    all_active_dates = set()
    acc_today = {a["id"]: {"produced": 0, "published": 0} for a in accounts}
    default_acc_id = accounts[0]["id"] if accounts else "acc_main"

    if os.path.isdir(core.JOBS_DIR):
        for d in sorted(os.listdir(core.JOBS_DIR)):
            sf = os.path.join(core.JOBS_DIR, d, "state.json")
            st = core.read_json(sf)
            if not st:
                continue
            jdate = _job_date_str(d, st)
            acc_id, offer_id = _job_account_and_offer(d)
            if acc_id not in acc_today:
                acc_id = default_acc_id

            lg = core.read_json(os.path.join(core.JOBS_DIR, d, "publish_log.json")) or {}
            is_pub = bool(lg.get("publish")) or st.get("state") in ("publish", "recycle")
            pub_date = (lg.get("published_at") or "")[:10]

            if jdate:
                all_active_dates.add(jdate)
            if pub_date and re.match(r"^\d{4}-\d{2}-\d{2}$", pub_date):
                all_active_dates.add(pub_date)

            if jdate in day_map:
                day_map[jdate]["produced"] += 1
                day_map[jdate]["jobs"].append({
                    "job_id": st.get("job_id", d),
                    "theme": st.get("theme", d),
                    "state": st.get("state", ""),
                    "account_id": acc_id,
                    "offer_id": offer_id,
                    "published": is_pub,
                })
                if is_pub and not pub_date:
                    day_map[jdate]["published"] += 1
            if pub_date in day_map:
                day_map[pub_date]["published"] += 1

            if jdate == today_str:
                acc_today[acc_id]["produced"] += 1
            if is_pub and (pub_date == today_str or (not pub_date and jdate == today_str)):
                acc_today[acc_id]["published"] += 1

    # 计算连续日更 Streak（若今日已产出则从今日算起，否则从昨日起算连续不断更天数）
    streak = 0
    cursor = today_dt if today_str in all_active_dates else (today_dt - timedelta(days=1))
    while cursor.isoformat() in all_active_dates:
        streak += 1
        cursor -= timedelta(days=1)

    today_bucket = day_map.get(today_str, {"produced": 0, "published": 0, "jobs": []})
    today_produced = today_bucket["produced"]
    today_published = today_bucket["published"]
    completion_rate = round(min(1.0, today_produced / max(1, daily_target_total)), 2)

    if today_produced >= daily_target_total:
        sla_status = "achieved"
        sla_label = "✅ 今日日更已达标"
    elif today_produced > 0:
        sla_status = "in_progress"
        sla_label = f"⏳ 日更进行中 ({today_produced}/{daily_target_total})"
    else:
        sla_status = "at_risk"
        sla_label = f"⚠️ 今日待日更 (缺口 {daily_target_total} 篇)"

    account_quotas = []
    for a in enabled_accounts:
        aid = a["id"]
        raw_dt = a.get("daily_target")
        target_n = max(0, int(raw_dt)) if raw_dt is not None else 1
        prod_n = acc_today.get(aid, {}).get("produced", 0)
        pub_n = acc_today.get(aid, {}).get("published", 0)
        account_quotas.append({
            "account_id": aid,
            "name": a.get("name", aid),
            "platforms": a.get("platforms", []),
            "daily_target": target_n,
            "today_produced": prod_n,
            "today_published": pub_n,
            "gap": max(0, target_n - prod_n),
            "met": prod_n >= target_n,
        })

    active_days_30d = sum(1 for d in day_map.values() if d["produced"] > 0 or d["published"] > 0)
    slots = sorted(_load_schedule_slots(), key=lambda s: (s.get("date") or "", s.get("time") or ""))

    return {
        "ok": True,
        "today": today_str,
        "daily_target_total": daily_target_total,
        "today_produced": today_produced,
        "today_published": today_published,
        "completion_rate": completion_rate,
        "sla_status": sla_status,
        "sla_label": sla_label,
        "streak_days": streak,
        "active_days_30d": active_days_30d,
        "calendar_30d": list(day_map.values()),
        "account_quotas": account_quotas,
        "schedule_slots": slots,
    }


def _extract_candidate_topics(limit: int = 10) -> List[dict]:
    """从最近选题推荐或热点雷达中提取候选选题，若均不存在则回退高转化常青母题池。"""
    candidates = []
    suggest_path = core._resolve_suggest_path()
    if suggest_path and os.path.exists(suggest_path):
        for ln in core.read_text(suggest_path).splitlines():
            if ln.startswith("- 主题方向"):
                raw = ln.split("：", 1)[1].strip() if "：" in ln else ln.split(":", 1)[1].strip()
                raw = re.sub(r"^\s*\*+\s*|\s*\*+\s*$|^【[^】]+】\s*", "", raw).strip()
                if raw and not any(c["title"] == raw for c in candidates):
                    candidates.append({"title": raw[:60], "source": "选题推荐池"})
    radar_path = core._resolve_radar_path()
    if len(candidates) < limit and radar_path and os.path.exists(radar_path):
        for ln in core.read_text(radar_path).splitlines():
            m = re.match(r"\s*\d+[\.、．]\s*(.+?)(?:（\[链接\]|$)", ln)
            if m:
                t = re.sub(r"\s*（发布于[^）]*）\s*|\s*｜\s*⚠️.*$", "", m.group(1)).strip()
                if t and not any(c["title"] == t for c in candidates):
                    candidates.append({"title": t[:60], "source": "热点雷达池"})
    if not candidates:
        for theme_group in core.CONTENT_THEMES:
            for sample in theme_group.get("samples", []):
                candidates.append({"title": sample, "source": f"常青母题·{theme_group['name']}"})
    return candidates[:limit]


@router.post("/api/ops/daily-autopilot")
def api_daily_autopilot(payload: DailyAutopilotPayload):
    """一键日更无人值守补齐：自动检测今日各矩阵号日更缺口，智能匹配高分选题建任务并入队生产。"""
    core._license_guard("production")
    sla = api_daily_sla()
    accounts = core._load_matrix_accounts()
    acc_map = {a["id"]: a for a in accounts}

    target_quotas = sla["account_quotas"]
    if payload.account_ids:
        target_quotas = [q for q in target_quotas if q["account_id"] in payload.account_ids]

    # 筛选今日尚未达标的账号（若 force=True 或全部已达标且用户主动点击，则为第一个启用账号补 1 篇）
    unmet = [q for q in target_quotas if q["gap"] > 0 or payload.force]
    if not unmet and target_quotas:
        unmet = [dict(target_quotas[0], gap=1)]

    candidates = _extract_candidate_topics(limit=20)
    # 过滤今日已建过的同名主题（兼顾完整标题、剥离裂变切角后缀后的母题以及 pipeline_config.json 的 base_topic）
    today_themes = set()
    for d in sla["calendar_30d"]:
        if d["date"] != sla["today"]:
            continue
        for j in d.get("jobs", []):
            th = (j.get("theme") or "").strip()
            if th:
                today_themes.add(th)
                today_themes.add(re.sub(r"（[^）]*）$", "", th).strip())
            jid = j.get("job_id") or ""
            if jid:
                pcfg = core.read_json(os.path.join(core.JOBS_DIR, jid, "pipeline_config.json")) or {}
                bt = (pcfg.get("base_topic") or "").strip()
                if bt:
                    today_themes.add(bt)
    fresh_candidates = [
        c for c in candidates
        if c["title"] not in today_themes and c["title"][:42] not in today_themes
    ] or candidates

    created_jobs = []
    cand_idx = 0
    max_jobs = max(1, min(10, int(payload.max_jobs or 3)))

    for q in unmet:
        if len(created_jobs) >= max_jobs:
            break
        acc = acc_map.get(q["account_id"])
        if not acc:
            continue
        need = max(1, q["gap"]) if not payload.force else 1
        for _ in range(need):
            if len(created_jobs) >= max_jobs or not fresh_candidates:
                break
            chosen = fresh_candidates[cand_idx % len(fresh_candidates)]
            cand_idx += 1
            job_info = _create_job_for_account(
                title=chosen["title"],
                account=acc,
                notes=f"日更无人值守自动投产（来源：{chosen['source']}）",
                Differentiated=True,
            )
            created_jobs.append(job_info)

    started = core._kick_production()
    return {
        "ok": True,
        "created_count": len(created_jobs),
        "jobs": created_jobs,
        "production_started": started,
    }


@router.post("/api/ops/schedule")
def api_schedule_save(payload: ScheduleSlotPayload):
    """新增或修改一条日更排期计划。"""
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="排期选题标题不能为空")
    date_str = (payload.date or datetime.now().strftime("%Y-%m-%d")).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="日期格式需为 YYYY-MM-DD")

    slots = _load_schedule_slots()
    slot_id = (payload.id or "").strip()
    existing = next((s for s in slots if s.get("id") == slot_id), None) if slot_id else None

    accounts_map = {a["id"]: a for a in core._load_matrix_accounts()}
    acc = accounts_map.get(payload.account_id) or next(iter(accounts_map.values()), {"id": "acc_main", "name": "主号"})

    if existing:
        existing.update({
            "date": date_str,
            "time": (payload.time or "09:00").strip(),
            "account_id": acc["id"],
            "account_name": acc.get("name", acc["id"]),
            "title": title[:80],
            "platform": payload.platform if payload.platform in ALLOWED_PLATFORMS else "小红书",
            "offer_id": (payload.offer_id or acc.get("default_offer_id") or "").strip(),
            "notes": (payload.notes or "").strip()[:200],
            "status": payload.status if payload.status in ("planned", "queued", "published") else "planned",
        })
        target = existing
    else:
        target = {
            "id": core._new_id("slot"),
            "date": date_str,
            "time": (payload.time or "09:00").strip(),
            "account_id": acc["id"],
            "account_name": acc.get("name", acc["id"]),
            "title": title[:80],
            "platform": payload.platform if payload.platform in ALLOWED_PLATFORMS else "小红书",
            "offer_id": (payload.offer_id or acc.get("default_offer_id") or "").strip(),
            "notes": (payload.notes or "").strip()[:200],
            "status": "planned",
            "job_id": "",
            "created_at": core._now_str(),
        }
        slots.append(target)

    _save_schedule_slots(slots)
    return {"ok": True, "slot": target, "slots": slots}


@router.post("/api/ops/schedule/{slot_id}/execute")
def api_schedule_execute(slot_id: str):
    """将排期日历中的某个计划槽位一键转为生产任务并启动流水线。"""
    core._license_guard("production")
    slots = _load_schedule_slots()
    slot = next((s for s in slots if s.get("id") == slot_id), None)
    if not slot:
        raise HTTPException(status_code=404, detail=f"排期项不存在: {slot_id}")

    accounts_map = {a["id"]: a for a in core._load_matrix_accounts()}
    acc = accounts_map.get(slot.get("account_id")) or next(iter(accounts_map.values()), {"id": "acc_main", "name": "主号"})

    job_info = _create_job_for_account(
        title=slot["title"],
        account=acc,
        notes=slot.get("notes") or f"排期日历触发 ({slot.get('date')} {slot.get('time')})",
        offer_id=slot.get("offer_id", ""),
        Differentiated=False,
    )
    slot["status"] = "queued"
    slot["job_id"] = job_info["job_id"]
    _save_schedule_slots(slots)
    started = core._kick_production()
    return {"ok": True, "slot": slot, "job": job_info, "production_started": started}


@router.delete("/api/ops/schedule/{slot_id}")
def api_schedule_delete(slot_id: str):
    slots = _load_schedule_slots()
    filtered = [s for s in slots if s.get("id") != slot_id]
    if len(filtered) == len(slots):
        raise HTTPException(status_code=404, detail=f"排期项不存在: {slot_id}")
    _save_schedule_slots(filtered)
    return {"ok": True, "deleted": slot_id}


# =========================================================================
# 3. 商业化闭环与 ROI 漏斗台账 (/api/commercial/*)
# =========================================================================
@router.get("/api/commercial/offers")
def api_commercial_offers():
    """获取商业化挂载组件库（私域钩子 / 社群课程 / SaaS带货 / 品牌商单）。"""
    offers = core._load_commercial_offers()
    return {"ok": True, "offers": offers, "types": ALLOWED_OFFER_TYPES}


@router.post("/api/commercial/offers")
def api_commercial_offer_save(payload: CommercialOfferPayload):
    """新增或更新商业化挂载组件（CTA & 转化产品）。"""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="组件名称不能为空")
    if payload.type not in ALLOWED_OFFER_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的商业化类型: {payload.type}")
    if payload.price_yuan < 0 or payload.lead_value_yuan < 0:
        raise HTTPException(status_code=400, detail="客单价与单线索价值不能为负数")

    offers = core._load_commercial_offers()
    oid = (payload.id or "").strip()
    existing = next((o for o in offers if o.get("id") == oid), None) if oid else None

    if existing:
        existing.update({
            "name": name[:80],
            "type": payload.type,
            "type_label": ALLOWED_OFFER_TYPES[payload.type],
            "price_yuan": round(float(payload.price_yuan), 2),
            "lead_value_yuan": round(float(payload.lead_value_yuan), 2),
            "keyword": (payload.keyword or "").strip()[:30],
            "cta_xhs": (payload.cta_xhs or "").strip()[:300],
            "cta_gzh": (payload.cta_gzh or "").strip()[:300],
            "cta_video": (payload.cta_video or "").strip()[:300],
            "enabled": bool(payload.enabled),
        })
        target = existing
        action = "updated"
    else:
        slug = re.sub(r"[^a-zA-Z0-9_]", "", oid) if oid else core._new_id("offer")
        target = {
            "id": slug,
            "name": name[:80],
            "type": payload.type,
            "type_label": ALLOWED_OFFER_TYPES[payload.type],
            "price_yuan": round(float(payload.price_yuan), 2),
            "lead_value_yuan": round(float(payload.lead_value_yuan), 2),
            "keyword": (payload.keyword or "").strip()[:30],
            "cta_xhs": (payload.cta_xhs or "").strip()[:300],
            "cta_gzh": (payload.cta_gzh or "").strip()[:300],
            "cta_video": (payload.cta_video or "").strip()[:300],
            "enabled": bool(payload.enabled),
        }
        offers.append(target)
        action = "created"

    core._save_commercial_offers(offers)
    return {"ok": True, "action": action, "offer": target, "offers": offers}


@router.delete("/api/commercial/offers/{offer_id}")
def api_commercial_offer_delete(offer_id: str):
    offers = core._load_commercial_offers()
    if len(offers) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留 1 个商业化转化组件")
    filtered = [o for o in offers if o.get("id") != offer_id]
    if len(filtered) == len(offers):
        raise HTTPException(status_code=404, detail=f"未找到商业化组件: {offer_id}")
    core._save_commercial_offers(filtered)
    return {"ok": True, "deleted": offer_id}


def record_commercial_entry(payload: CommercialLedgerPayload) -> dict:
    """内部/外部共用的商业化转化与营收记账函数，同时回写对应 Job 的 publish_log.json。"""
    if payload.reads < 0 or payload.leads < 0 or payload.conversions < 0 or payload.revenue_yuan < 0:
        raise HTTPException(status_code=400, detail="阅读/线索/转化/营收数值不能为负数")
    if payload.revenue_type not in ALLOWED_OFFER_TYPES:
        raise HTTPException(status_code=400, detail=f"revenue_type 不合法: {payload.revenue_type}")

    accounts_map = {a["id"]: a for a in core._load_matrix_accounts()}
    offers_map = {o["id"]: o for o in core._load_commercial_offers()}

    job_id = (payload.job_id or "").strip()
    title = (payload.title or "").strip()
    acc_id = (payload.account_id or "").strip()
    offer_id = (payload.offer_id or "").strip()

    if job_id:
        core._require_job_id(job_id)
        st = core.read_json(os.path.join(core.JOBS_DIR, job_id, "state.json")) or {}
        if not title:
            title = st.get("theme") or job_id
        j_acc, j_off = _job_account_and_offer(job_id)
        if not acc_id:
            acc_id = j_acc
        if not offer_id:
            offer_id = j_off

    if not acc_id or acc_id not in accounts_map:
        acc_id = next(iter(accounts_map.keys()), "acc_main")
    acc_name = accounts_map.get(acc_id, {}).get("name", acc_id)

    offer = offers_map.get(offer_id, {})
    rev_yuan = round(float(payload.revenue_yuan or 0.0), 2)
    # 若未手填直接营收但填了成交单数且绑定了有定价的组件，自动按组件单价核算营收
    if rev_yuan == 0.0 and payload.conversions > 0 and float(offer.get("price_yuan") or 0) > 0:
        rev_yuan = round(payload.conversions * float(offer["price_yuan"]), 2)

    entries = core._load_commercial_ledger().get("entries", [])
    eid = (payload.id or "").strip() or core._new_id("comm")
    entry = {
        "id": eid,
        "job_id": job_id,
        "title": (title or "日常私域/商单转化")[:80],
        "account_id": acc_id,
        "account_name": acc_name,
        "platform": payload.platform if payload.platform in ALLOWED_PLATFORMS else "小红书",
        "offer_id": offer_id,
        "offer_name": offer.get("name", ""),
        "revenue_type": payload.revenue_type,
        "revenue_type_label": ALLOWED_OFFER_TYPES.get(payload.revenue_type, payload.revenue_type),
        "reads": int(payload.reads),
        "leads": int(payload.leads),
        "conversions": int(payload.conversions),
        "revenue_yuan": rev_yuan,
        "note": (payload.note or "").strip()[:200],
        "recorded_at": (payload.recorded_at or "").strip() or core._now_str(),
    }

    idx = next((i for i, e in enumerate(entries) if e.get("id") == eid), None)
    if idx is not None:
        entries[idx] = entry
    else:
        entries.insert(0, entry)
    core._save_commercial_ledger(entries)

    # 同步回写到 jobs/<job_id>/publish_log.json（按 id 幂等更新，防止编辑时重复追加）
    if job_id and os.path.isdir(os.path.join(core.JOBS_DIR, job_id)):
        lg_path = os.path.join(core.JOBS_DIR, job_id, "publish_log.json")
        lg = core.read_json(lg_path) or {"job_id": job_id, "records": [], "publish": []}
        comm_list = lg.setdefault("commercial", [])
        comm_item = {
            "id": eid,
            "platform": entry["platform"],
            "leads": entry["leads"],
            "conversions": entry["conversions"],
            "revenue_yuan": entry["revenue_yuan"],
            "revenue_type": entry["revenue_type"],
            "recorded_at": entry["recorded_at"],
        }
        c_idx = next((i for i, c in enumerate(comm_list) if c.get("id") == eid), None)
        if c_idx is not None:
            comm_list[c_idx] = comm_item
        else:
            comm_list.append(comm_item)
        core._atomic_write_json(lg_path, lg)

    return entry


@router.post("/api/commercial/ledger")
def api_commercial_ledger_add(payload: CommercialLedgerPayload):
    """新增一条商业化转化与营收记录。"""
    entry = record_commercial_entry(payload)
    return {"ok": True, "entry": entry}


@router.get("/api/commercial/ledger")
def api_commercial_ledger_list(account_id: str = "", revenue_type: str = ""):
    entries = core._load_commercial_ledger().get("entries", [])
    if account_id:
        entries = [e for e in entries if e.get("account_id") == account_id]
    if revenue_type:
        entries = [e for e in entries if e.get("revenue_type") == revenue_type]
    return {"ok": True, "entries": entries, "count": len(entries)}


@router.delete("/api/commercial/ledger/{entry_id}")
def api_commercial_ledger_delete(entry_id: str):
    entries = core._load_commercial_ledger().get("entries", [])
    removed = [e for e in entries if e.get("id") == entry_id]
    filtered = [e for e in entries if e.get("id") != entry_id]
    if len(filtered) == len(entries):
        raise HTTPException(status_code=404, detail=f"未找到台账记录: {entry_id}")
    core._save_commercial_ledger(filtered)
    for rem in removed:
        jid = (rem.get("job_id") or "").strip()
        if jid and os.path.isdir(os.path.join(core.JOBS_DIR, jid)):
            lg_path = os.path.join(core.JOBS_DIR, jid, "publish_log.json")
            lg = core.read_json(lg_path)
            if isinstance(lg, dict) and isinstance(lg.get("commercial"), list):
                lg["commercial"] = [c for c in lg["commercial"] if c.get("id") != entry_id]
                core._atomic_write_json(lg_path, lg)
    return {"ok": True, "deleted": entry_id}


@router.get("/api/commercial/overview")
def api_commercial_overview():
    """商业化闭环全景大盘：转化漏斗、RPM千次阅读收益、矩阵号营收贡献、组件转化率与算力ROI。"""
    stats = core.data_stats.build_summary(jobs_dir=core.JOBS_DIR, outputs_dir=core.OUTPUTS_DIR, data_dir=core.DATA_DIR)
    accounts = core._load_matrix_accounts()
    offers = core._load_commercial_offers()
    offers_map = {o["id"]: o for o in offers}
    entries = core._load_commercial_ledger().get("entries", [])

    total_reads_stats = int(stats.get("total_reads") or 0)
    total_engagements = int(stats.get("total_likes") or 0) + int(stats.get("total_collects") or 0) + int(stats.get("total_comments") or 0)

    ledger_reads = sum(int(e.get("reads") or 0) for e in entries)
    effective_reads = max(total_reads_stats, ledger_reads)

    total_leads = sum(int(e.get("leads") or 0) for e in entries)
    total_conversions = sum(int(e.get("conversions") or 0) for e in entries)
    total_revenue = round(sum(float(e.get("revenue_yuan") or 0.0) for e in entries), 2)

    # 私域线索潜在价值估算
    pipeline_value = 0.0
    for e in entries:
        off = offers_map.get(e.get("offer_id", ""), {})
        lv = float(off.get("lead_value_yuan") or 15.0)
        pipeline_value += int(e.get("leads") or 0) * lv
    pipeline_value = round(pipeline_value, 2)

    rpm_yuan = round((total_revenue / effective_reads) * 1000, 2) if effective_reads > 0 else 0.0
    lead_rate = round(total_leads / effective_reads, 4) if effective_reads > 0 else 0.0
    order_rate = round(total_conversions / total_leads, 4) if total_leads > 0 else 0.0

    # AI Token 算力成本与净 ROI 核算（按 ¥2.0 / 百万 Tokens 折算，最低保底 ¥0.10 防止除零）
    usage = core.llm_engine.get_usage()
    total_tokens = int(usage.get("total_tokens") or 0)
    token_cost_yuan = round(max(0.01, (total_tokens / 1_000_000.0) * 2.0), 2) if total_tokens > 0 else 0.0
    net_roi_multiple = round(total_revenue / max(0.1, token_cost_yuan), 1) if total_revenue > 0 else 0.0

    # 按矩阵号聚合
    by_account_map = {
        a["id"]: {
            "account_id": a["id"],
            "name": a.get("name", a["id"]),
            "niche": a.get("niche", ""),
            "leads": 0,
            "conversions": 0,
            "revenue_yuan": 0.0,
            "entries_count": 0,
        }
        for a in accounts
    }
    default_acc_id = accounts[0]["id"] if accounts else "acc_main"
    for e in entries:
        aid = e.get("account_id") or default_acc_id
        if aid not in by_account_map:
            aid = default_acc_id
        b = by_account_map[aid]
        b["leads"] += int(e.get("leads") or 0)
        b["conversions"] += int(e.get("conversions") or 0)
        b["revenue_yuan"] = round(b["revenue_yuan"] + float(e.get("revenue_yuan") or 0.0), 2)
        b["entries_count"] += 1

    # 按变现类型聚合
    by_type_map = {
        k: {"type": k, "label": label, "leads": 0, "conversions": 0, "revenue_yuan": 0.0, "count": 0}
        for k, label in ALLOWED_OFFER_TYPES.items()
    }
    for e in entries:
        rt = e.get("revenue_type") or "lead_magnet"
        if rt in by_type_map:
            by_type_map[rt]["leads"] += int(e.get("leads") or 0)
            by_type_map[rt]["conversions"] += int(e.get("conversions") or 0)
            by_type_map[rt]["revenue_yuan"] = round(by_type_map[rt]["revenue_yuan"] + float(e.get("revenue_yuan") or 0.0), 2)
            by_type_map[rt]["count"] += 1

    # 按转化组件 Offer 聚合
    by_offer_map = {
        o["id"]: {
            "offer_id": o["id"],
            "name": o.get("name", o["id"]),
            "type_label": o.get("type_label", ""),
            "leads": 0,
            "conversions": 0,
            "revenue_yuan": 0.0,
        }
        for o in offers
    }
    for e in entries:
        oid = e.get("offer_id") or ""
        if oid in by_offer_map:
            by_offer_map[oid]["leads"] += int(e.get("leads") or 0)
            by_offer_map[oid]["conversions"] += int(e.get("conversions") or 0)
            by_offer_map[oid]["revenue_yuan"] = round(by_offer_map[oid]["revenue_yuan"] + float(e.get("revenue_yuan") or 0.0), 2)

    top_jobs = sorted(
        entries,
        key=lambda x: (float(x.get("revenue_yuan") or 0.0), int(x.get("leads") or 0)),
        reverse=True,
    )[:10]

    return {
        "ok": True,
        "funnel": {
            "reads": effective_reads,
            "engagements": total_engagements,
            "leads": total_leads,
            "conversions": total_conversions,
            "revenue_yuan": total_revenue,
        },
        "kpis": {
            "total_revenue_yuan": total_revenue,
            "pipeline_value_yuan": pipeline_value,
            "total_leads": total_leads,
            "total_conversions": total_conversions,
            "rpm_yuan": rpm_yuan,
            "lead_conversion_rate": lead_rate,
            "order_conversion_rate": order_rate,
            "total_tokens": total_tokens,
            "token_cost_yuan": token_cost_yuan,
            "net_roi_multiple": net_roi_multiple,
        },
        "by_account": sorted(by_account_map.values(), key=lambda x: x["revenue_yuan"], reverse=True),
        "by_type": list(by_type_map.values()),
        "by_offer": sorted(by_offer_map.values(), key=lambda x: (x["revenue_yuan"], x["leads"]), reverse=True),
        "top_jobs": top_jobs,
        "recent_entries": entries[:20],
    }
