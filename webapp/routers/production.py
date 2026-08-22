# -*- coding: utf-8 -*-
"""
生产流水线 Router (/api/jobs, /api/jobs/{job_id}, /api/production/*)
"""
import os
import re
import shutil
import signal
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

import core


router = APIRouter(tags=["生产流水线"])


@router.get("/api/jobs")
def api_jobs():
    rows = []
    for d in sorted(os.listdir(core.JOBS_DIR)):
        sf = os.path.join(core.JOBS_DIR, d, "state.json")
        data = core.read_json(sf)
        if not data:
            continue
        lg = core.read_json(os.path.join(core.JOBS_DIR, d, "publish_log.json")) or {}
        published = bool(lg.get("publish")) or data.get("state") in ("publish", "recycle")
        published_at = lg.get("published_at") or ""
        if not published_at and published:
            pub = lg.get("publish") or []
            if pub:
                published_at = pub[0].get("at") or ""
            if not published_at:
                published_at = data.get("updated_at") or ""
        rows.append({
            "job_id": data["job_id"], "theme": data.get("theme", ""),
            "state": data.get("state"), "reject_count": data.get("reject_count", 0),
            "scores": data.get("scores", {}), "updated_at": data.get("updated_at"),
            "published": published,
            "published_at": published_at,
            "month": published_at[:7] if published_at else "",
            "archived": os.path.exists(os.path.join(core.JOBS_DIR, d, ".archived")),
        })
    # 最新更新在前（配合流水线/成品库「最新生产放前面」的诉求）
    rows.sort(key=lambda r: _ts(r.get("updated_at") or ""), reverse=True)
    return {"jobs": rows}


@router.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job_id = core._require_job_id(job_id)
    jdir = os.path.join(core.JOBS_DIR, job_id)
    if not os.path.isdir(jdir):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    return {
        "state": core.read_json(os.path.join(jdir, "state.json")),
        "validate_report": core.read_json(os.path.join(core.OUTPUTS_DIR, job_id, "validate_report.json")),
        "harsh_report": core.read_json(os.path.join(core.OUTPUTS_DIR, job_id, "harsh_report.json")),
        "ai_flavor_report": core.read_json(os.path.join(core.OUTPUTS_DIR, job_id, "ai_flavor_report.json")),
        "compliance_report": core.read_json(os.path.join(core.OUTPUTS_DIR, job_id, "compliance_report.json")),
        "publish_log": core.read_json(os.path.join(jdir, "publish_log.json")),
    }


def _ts(s):
    try:
        return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return 0.0


@router.get("/api/production/status")
def api_production_status():
    """生产队列与当前任务进度（含日志尾部），同时自动收尾/续跑。

    队列排序规则：运行中 > 排队中 > 其余按创建时间倒序（最新在前）；
    超过 7 天的历史任务标记 archived=True，供前端折叠不再挤占主页。
    """
    items = core._finalize_stale(core._load_queue())
    core._kick_production()
    items = core._load_queue()
    running = core._running_item(items)
    now_ts = datetime.now().timestamp()
    week_ts = 7 * 24 * 3600

    for it in items:
        created = it.get("created_at") or it.get("started_at") or ""
        age_days = round((now_ts - _ts(created)) / 86400, 1) if _ts(created) else 0.0
        it["age_days"] = age_days
        it["archived"] = age_days > 7 and it.get("status") in ("done", "failed", "canceled")

    def _sort_key(it):
        status_rank = {"running": 0, "queued": 1}.get(it.get("status"), 2)
        created_ts = _ts(it.get("created_at") or "")
        return (status_rank, -created_ts)

    items = sorted(items, key=_sort_key)

    log = ""
    if running:
        log = core.read_text(os.path.join(core.JOBS_DIR, running["job_id"], "production.log"))[-3000:]
    return {
        "running": running,
        "queue": items,
        "log": log,
        "updated_at": core._now_str(),
    }


@router.post("/api/production/{job_id}/cancel")
def api_production_cancel(job_id: str):
    job_id = core._require_job_id(job_id)
    items = core._load_queue()
    it = next((x for x in items if x["job_id"] == job_id), None)
    if not it:
        raise HTTPException(status_code=404, detail=f"队列中无此任务: {job_id}")
    if it["status"] == "running":
        proc = core._RUNNERS.get(job_id)
        pid = it.get("pid")
        try:
            if proc is not None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            elif pid:
                os.killpg(int(pid), signal.SIGTERM)
        except Exception:
            try:
                if proc is not None:
                    proc.terminate()
                elif pid:
                    os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        core._RUNNERS.pop(job_id, None)
    elif it["status"] != "queued":
        raise HTTPException(status_code=400, detail=f"当前状态 {it['status']} 不可取消")
    it["status"] = "canceled"
    it["finished_at"] = core._now_str()
    core._save_queue(items)
    return {"ok": True, "job_id": job_id}


@router.post("/api/production/{job_id}/rerun")
def api_production_rerun(job_id: str):
    core._license_guard("production")
    job_id = core._require_job_id(job_id)
    if not os.path.isdir(os.path.join(core.JOBS_DIR, job_id)):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    items = core._load_queue()
    it = next((x for x in items if x["job_id"] == job_id), None)
    if it:
        it.update(status="queued", started_at="", finished_at="", error="", pid=None)
    else:
        items.append({
            "job_id": job_id, "status": "queued", "created_at": core._now_str(),
            "started_at": "", "finished_at": "", "pid": None, "error": "",
        })
    core._save_queue(items)
    started = core._kick_production()
    return {"ok": True, "job_id": job_id, "started": started}


@router.delete("/api/production/{job_id}")
def api_production_delete(job_id: str):
    """删除一个生产任务：移出队列、终止运行进程、删除 jobs/ 与 outputs/ 目录。"""
    job_id = core._require_job_id(job_id)
    items = core._load_queue()
    target = next((x for x in items if x["job_id"] == job_id), None)
    # 终止可能正在运行的进程
    proc = core._RUNNERS.pop(job_id, None)
    for pid in (target.get("pid") if target else None, proc.pid if proc else None):
        if not pid:
            continue
        try:
            os.killpg(int(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
    items = [x for x in items if x["job_id"] != job_id]
    core._save_queue(items)
    for p in (os.path.join(core.JOBS_DIR, job_id), os.path.join(core.OUTPUTS_DIR, job_id)):
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    return {"ok": True, "job_id": job_id}


@router.get("/api/qa/history")
def api_qa_history():
    """汇总所有 Job 的自动化质检历史时序数据与趋势指标。"""
    items = []
    issues_counter = {}

    if not os.path.isdir(core.OUTPUTS_DIR):
        return {
            "items": [],
            "trends": {
                "total_inspections": 0, "overall_pass_rate": 0.0,
                "pass_rate_7d": 0.0, "pass_rate_30d": 0.0,
                "avg_harsh_score_7d": 0.0, "avg_harsh_score_30d": 0.0
            },
            "top_issues": [],
            "milestones": []
        }

    now_dt = datetime.now()
    cutoff_7d = now_dt - timedelta(days=7)
    cutoff_30d = now_dt - timedelta(days=30)

    for d in sorted(os.listdir(core.OUTPUTS_DIR)):
        out_dir = os.path.join(core.OUTPUTS_DIR, d)
        if not os.path.isdir(out_dir):
            continue

        vr = core.read_json(os.path.join(out_dir, "validate_report.json")) or {}
        hr = core.read_json(os.path.join(out_dir, "harsh_report.json")) or {}
        ar = core.read_json(os.path.join(out_dir, "ai_flavor_report.json")) or {}
        cr = core.read_json(os.path.join(out_dir, "compliance_report.json")) or {}

        if not (vr or hr or ar or cr):
            continue

        date_str = ""
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", d)
        if m:
            date_str = m.group(1)
        else:
            date_str = datetime.fromtimestamp(os.path.getmtime(out_dir)).strftime("%Y-%m-%d")

        try:
            item_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            item_dt = now_dt

        contract_pass = vr.get("verdict") != "REJECTED" if vr else True
        if vr and not contract_pass:
            for r in vr.get("results", []):
                if r.get("level") == "FAIL":
                    code = r.get("code", "契约错误")
                    issues_counter[code] = issues_counter.get(code, 0) + 1

        harsh_score = int(hr.get("score") or 0)
        harsh_pass = hr.get("verdict") != "REJECTED" if hr else True
        if hr and not harsh_pass:
            for it in hr.get("issues", []) or hr.get("details", []):
                rule = it.get("rule", "Harsh批评")
                issues_counter[rule] = issues_counter.get(rule, 0) + 1

        ai_hits = int(ar.get("total_hits") or ar.get("high_count") or 0)
        ai_pass = ar.get("verdict") != "REJECTED" if ar else True
        if ar and not ai_pass:
            for r in ar.get("rules", []) or ar.get("checks", []):
                rule = r.get("rule", "AI腔违规")
                issues_counter[rule] = issues_counter.get(rule, 0) + 1

        compliance_pass = cr.get("verdict") != "REJECTED" if cr else True
        if cr and not compliance_pass:
            for c in cr.get("checks", []) or c.get("details", []):
                rule = c.get("rule", "合规违规")
                issues_counter[rule] = issues_counter.get(rule, 0) + 1

        overall_pass = bool(contract_pass and harsh_pass and ai_pass and compliance_pass)
        state_data = core.read_json(os.path.join(core.JOBS_DIR, d, "state.json")) or {}
        theme = state_data.get("theme") or d

        items.append({
            "job_id": d,
            "theme": theme,
            "date": date_str,
            "_dt": item_dt,
            "contract_pass": contract_pass,
            "harsh_score": harsh_score if harsh_score > 0 else 85,
            "harsh_pass": harsh_pass,
            "ai_hits": ai_hits,
            "ai_pass": ai_pass,
            "compliance_pass": compliance_pass,
            "overall": overall_pass,
        })

    items.sort(key=lambda x: (x["date"], x["job_id"]))

    total_count = len(items)
    overall_pass_count = sum(1 for it in items if it["overall"])
    overall_pass_rate = round((overall_pass_count / total_count * 100), 1) if total_count else 0.0

    items_7d = [it for it in items if it["_dt"] >= cutoff_7d]
    items_30d = [it for it in items if it["_dt"] >= cutoff_30d]

    pass_rate_7d = round((sum(1 for it in items_7d if it["overall"]) / len(items_7d) * 100), 1) if items_7d else overall_pass_rate
    pass_rate_30d = round((sum(1 for it in items_30d if it["overall"]) / len(items_30d) * 100), 1) if items_30d else overall_pass_rate

    avg_harsh_7d = round(sum(it["harsh_score"] for it in items_7d) / len(items_7d), 1) if items_7d else (round(sum(it["harsh_score"] for it in items) / total_count, 1) if total_count else 0.0)
    avg_harsh_30d = round(sum(it["harsh_score"] for it in items_30d) / len(items_30d), 1) if items_30d else (round(sum(it["harsh_score"] for it in items) / total_count, 1) if total_count else 0.0)

    for it in items:
        it.pop("_dt", None)

    top_issues = []
    for k, v in sorted(issues_counter.items(), key=lambda x: -x[1])[:5]:
        top_issues.append({"rule": k, "count": v})

    milestones = []
    if total_count >= 1:
        milestones.append({"title": "质检闭环", "desc": f"累计完成 {total_count} 次全自动四重质检", "icon": "🛡️"})
    max_score = max((it["harsh_score"] for it in items), default=0)
    if max_score >= 90:
        milestones.append({"title": "品质巅峰", "desc": f"最高 Harsh 评分达到 {max_score} 分", "icon": "⭐"})

    consecutive_pass = 0
    max_consecutive = 0
    for it in items:
        if it["overall"]:
            consecutive_pass += 1
            max_consecutive = max(max_consecutive, consecutive_pass)
        else:
            consecutive_pass = 0
    if max_consecutive >= 3:
        milestones.append({"title": "连通记录", "desc": f"达成连续 {max_consecutive} 次质检全部通过", "icon": "🔥"})

    return {
        "items": items,
        "trends": {
            "total_inspections": total_count,
            "overall_pass_rate": overall_pass_rate,
            "pass_rate_7d": pass_rate_7d,
            "pass_rate_30d": pass_rate_30d,
            "avg_harsh_score_7d": avg_harsh_7d,
            "avg_harsh_score_30d": avg_harsh_30d,
        },
        "top_issues": top_issues,
        "milestones": milestones,
    }

