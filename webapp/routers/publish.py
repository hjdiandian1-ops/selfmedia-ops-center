# -*- coding: utf-8 -*-
"""
发布与数据回收 Router (/api/publish/*, /api/qa, /api/pipeline/run, /api/stats/import-*, /api/stats/backfill, /api/stats/refresh)
"""
import json
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import core

router = APIRouter(tags=["发布与数据回收"])


class GzhDraftRequest(BaseModel):
    job_id: str
    title: str = ""
    digest: str = ""
    account_id: str = ""


@router.post("/api/publish/gzh-draft")
def api_gzh_draft(payload: GzhDraftRequest):
    """把公众号排版 HTML 推送到已认证公众号的草稿箱（优先读取矩阵号专属凭据，回退全局 .env 配置）。"""
    core._license_guard("gzh_push")
    job_id = core._require_job_id(payload.job_id)
    env = core._read_env()
    app_id = env.get("GZH_APP_ID", "").strip()
    app_secret = env.get("GZH_APP_SECRET", "").strip()

    # 优先检查任务绑定的矩阵号专属公众号凭据
    pcfg = core.read_json(os.path.join(core.JOBS_DIR, job_id, "pipeline_config.json")) or {}
    acc_id = (payload.account_id or pcfg.get("account_id") or "").strip()
    if acc_id:
        for acc in core._load_matrix_accounts():
            if acc.get("id") == acc_id:
                if (acc.get("gzh_app_id") or "").strip() and (acc.get("gzh_app_secret") or "").strip():
                    app_id = acc["gzh_app_id"].strip()
                    app_secret = acc["gzh_app_secret"].strip()
                break

    if not app_id or not app_secret:
        raise HTTPException(
            status_code=400,
            detail="未配置公众号 AppID/Secret：请先在左下角 ⚙ 设置 或矩阵号配置中填写（需要已认证的公众号，个人订阅号暂不支持 API；获取与 IP 白名单步骤见成品库『发布指引』）",
        )
    html, cover = core._gzh_artifacts(job_id)
    if not html:
        raise HTTPException(status_code=400, detail="该任务没有公众号排版产物（.html），无法推送草稿")
    title = payload.title.strip() or (core.read_json(os.path.join(core.JOBS_DIR, job_id, "state.json")) or {}).get("theme", job_id)
    args = [
        "gzh_draft_api.py", "--title", title[:64],
        "--content-file", html, "--job-id", job_id,
    ]
    if cover:
        args += ["--cover", cover]
    if payload.digest.strip():
        args += ["--digest", payload.digest.strip()[:120]]
    extra_env = {"GZH_APP_ID": app_id, "GZH_APP_SECRET": app_secret}
    try:
        r = core.run_script(args, timeout=180, extra_env=extra_env)
    except TypeError:
        r = core.run_script(args, timeout=180)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False)[:1000])
    return {"ok": True, "job_id": job_id, "account_id": acc_id, "output": r.get("stdout", "")[-500:]}



@router.get("/api/docs/publish-guide")
def api_publish_guide():
    """发布操作手册全文（成品库弹窗查看）。"""
    path = os.path.join(core.ROOT, "docs", "发布与后台配置.md")
    text = core.read_text(path)
    if not text:
        raise HTTPException(status_code=404, detail="发布手册不存在")
    return {"title": "发布与后台配置手册", "path": "docs/发布与后台配置.md", "content": text}


class QaRequest(BaseModel):
    output_dir: str


@router.post("/api/qa")
def api_qa(payload: QaRequest):
    out_dir = payload.output_dir.strip().strip("/")
    full = os.path.normpath(os.path.join(core.ROOT, out_dir))
    if not full.startswith(os.path.normpath(core.OUTPUTS_DIR)) or not os.path.isdir(full):
        raise HTTPException(status_code=400, detail=f"output_dir 无效: {payload.output_dir}")
    core._require_job_id(os.path.basename(full))
    r1 = core.run_script(["validate_materials_contract.py", out_dir, "--out", os.path.join(out_dir, "validate_report.json")], timeout=60)
    r2 = core.run_script(["harsh_critic_score.py", out_dir, "--out", os.path.join(out_dir, "harsh_report.json")], timeout=60)
    r3 = core.run_script(["ai_flavor_check.py", out_dir, "--out", os.path.join(out_dir, "ai_flavor_report.json")], timeout=60)
    return {
        "contract": core.read_json(os.path.join(core.OUTPUTS_DIR, os.path.basename(full), "validate_report.json")),
        "harsh": core.read_json(os.path.join(core.OUTPUTS_DIR, os.path.basename(full), "harsh_report.json")),
        "ai_flavor": core.read_json(os.path.join(core.OUTPUTS_DIR, os.path.basename(full), "ai_flavor_report.json")),
        "contract_run": r1, "harsh_run": r2, "ai_flavor_run": r3,
    }


class PipelineRequest(BaseModel):
    action: str  # topics | recycle | weekly | qa
    output_dir: Optional[str] = ""


@router.post("/api/pipeline/run")
def api_pipeline(payload: PipelineRequest):
    action = payload.action.strip()
    if action == "qa":
        if not payload.output_dir:
            raise HTTPException(status_code=400, detail="qa 需要 output_dir")
        return api_qa(QaRequest(output_dir=payload.output_dir))
    if action not in ("topics", "recycle", "weekly"):
        raise HTTPException(status_code=400, detail=f"不支持的 action: {action}")
    r = core.run_script(["run_daily_pipeline.py", f"--{action}"],
                        timeout=300 if action == "topics" else 180)
    return r


class ManualPublishRequest(BaseModel):
    job_id: str
    platform: str
    title: str = ""
    note: str = ""


class StatsBackfill(BaseModel):
    job_id: str
    platform: str
    reads: int = 0
    likes: int = 0
    collects: int = 0
    comments: int = 0
    url: str = ""
    leads: int = 0
    conversions: int = 0
    revenue_yuan: float = 0.0
    account_id: str = ""
    offer_id: str = ""
    revenue_type: str = "lead_magnet"


class AccountSnapshot(BaseModel):
    followers: int = 0
    following: int = 0
    likes_collects: int = 0


@router.post("/api/stats/account-snapshot")
def api_account_snapshot(payload: AccountSnapshot):
    """保存账号快照（小红书总粉丝数等；导出表不含总粉丝，需手动维护）。"""
    for name, val in (("followers", payload.followers), ("following", payload.following),
                      ("likes_collects", payload.likes_collects)):
        if not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=400, detail=f"{name} 必须是非负整数")
    path = os.path.join(core.DATA_DIR, "xhs_account.json")
    data = core.read_json(path) or {}
    data.update({
        "followers": payload.followers,
        "following": payload.following,
        "likes_collects": payload.likes_collects,
        "updated_at": core._now_str(),
        "period": data.get("period", ""),
    })
    os.makedirs(core.DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "followers": payload.followers}


@router.post("/api/publish/manual")
def api_publish_manual(payload: ManualPublishRequest):
    """人工发布完成后标记记录：追加 mode=manual 的发布动作，保住 48h 回收闭环。"""
    job_id = core._require_job_id(payload.job_id)
    if not os.path.isdir(os.path.join(core.JOBS_DIR, job_id)):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    if payload.platform not in ("小红书", "公众号", "短视频"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {payload.platform}")
    if len(payload.note) > 200:
        raise HTTPException(status_code=400, detail="note 过长（≤200 字符）")
    if len(payload.title) > 120:
        raise HTTPException(status_code=400, detail="title 过长（≤120 字符）")

    args = ["record_manual_publish.py", job_id, "--platform", payload.platform]
    if payload.title.strip():
        args += ["--title", payload.title.strip()]
    if payload.note.strip():
        args += ["--note", payload.note.strip()]
    r = core.run_script(args, timeout=30)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    st_file = os.path.join(core.JOBS_DIR, job_id, "state.json")
    st_data = core.read_json(st_file)
    if isinstance(st_data, dict) and st_data.get("state") in ("archive", "review"):
        st_data["state"] = "publish"
        st_data["updated_at"] = core._now_str()
        st_data.setdefault("history", []).append({"state": "publish", "at": core._now_str(), "note": f"{payload.platform}已发布登记"})
        core._atomic_write_json(st_file, st_data)
    return r


@router.post("/api/stats/backfill")
def api_stats_backfill(payload: StatsBackfill):
    """平台数据回填：校验后调用 collect_post_stats.py 落盘 publish_log.json，若附带私域/营收数据则同步写入商业化台账。"""
    job_id = core._require_job_id(payload.job_id)
    if not os.path.isdir(os.path.join(core.JOBS_DIR, job_id)):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    if payload.platform not in ("小红书", "公众号", "短视频"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {payload.platform}")
    for name, val in (("reads", payload.reads), ("likes", payload.likes),
                      ("collects", payload.collects), ("comments", payload.comments),
                      ("leads", payload.leads), ("conversions", payload.conversions)):
        if not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=400, detail=f"{name} 必须是非负整数")
    if payload.revenue_yuan < 0:
        raise HTTPException(status_code=400, detail="revenue_yuan 不能为负数")
    if len(payload.url) > 500:
        raise HTTPException(status_code=400, detail="url 过长（≤500 字符）")

    args = [
        "collect_post_stats.py", job_id, "--platform", payload.platform,
        "--reads", str(payload.reads), "--likes", str(payload.likes),
        "--collects", str(payload.collects), "--comments", str(payload.comments),
    ]
    if payload.url.strip():
        args += ["--url", payload.url.strip()]
    r = core.run_script(args, timeout=30)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))

    st_file = os.path.join(core.JOBS_DIR, job_id, "state.json")
    st_data = core.read_json(st_file)
    if isinstance(st_data, dict) and st_data.get("state") in ("archive", "publish", "review"):
        st_data["state"] = "recycle"
        st_data["updated_at"] = core._now_str()
        st_data.setdefault("history", []).append({"state": "recycle", "at": core._now_str(), "note": f"{payload.platform} 48h数据回收完成"})
        core._atomic_write_json(st_file, st_data)

    if payload.leads > 0 or payload.conversions > 0 or payload.revenue_yuan > 0:
        from webapp.routers import matrix_commercial
        comm_entry = matrix_commercial.record_commercial_entry(
            matrix_commercial.CommercialLedgerPayload(
                job_id=job_id,
                account_id=payload.account_id,
                platform=payload.platform,
                offer_id=payload.offer_id,
                revenue_type=payload.revenue_type or "lead_magnet",
                reads=payload.reads,
                leads=payload.leads,
                conversions=payload.conversions,
                revenue_yuan=payload.revenue_yuan,
                note=f"来自 48h 数据回填 ({payload.platform})",
            )
        )
        r = dict(r, commercial_entry=comm_entry)
    return r


def _import_xhs_xlsx(filename, data: bytes) -> dict:
    """小红书导出明细表导入核心：校验 → 临时落盘 → 调 import_xhs_notes.py。"""
    if not (filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, detail="仅支持小红书「笔记管理 → 导出」的 .xlsx 明细表")
    if not data:
        raise HTTPException(400, detail="上传文件为空")
    fd, tmp = tempfile.mkstemp(prefix="xhs_export_", suffix=".xlsx")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        r = core.run_script(["import_xhs_notes.py", "--file", tmp, "--json"], timeout=120)
        if not r["ok"]:
            detail = (r["stderr"] or r["stdout"]).strip() or "导入失败"
            raise HTTPException(400, detail=detail[-800:])
        return json.loads(r["stdout"])
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@router.post("/api/stats/import-xhs")
async def api_stats_import_xhs(request: Request, filename: str = ""):
    """导入小红书笔记导出明细表（xlsx），免手工回填。
    前端以原始字节 POST（?filename=…），避免 python-multipart 依赖。"""
    return _import_xhs_xlsx(filename, await request.body())


def _import_dashboard_xlsx(filename, data: bytes, kind: str = "") -> dict:
    """小红书数据看板导出 xlsx 导入（发布/观看/互动/涨粉 四页签）。"""
    if not (filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, detail="仅支持 .xlsx 看板导出文件")
    if not data:
        raise HTTPException(400, detail="上传文件为空")
    fd, tmp = tempfile.mkstemp(prefix="dashboard_", suffix=".xlsx")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        args = ["import_dashboard_xlsx.py", "--file", tmp, "--json"]
        if kind:
            args += ["--kind", kind]
        r = core.run_script(args, timeout=60)
        if not r["ok"]:
            detail = (r["stderr"] or r["stdout"]).strip() or "导入失败"
            raise HTTPException(400, detail=detail[-800:])
        return json.loads(r["stdout"])
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@router.post("/api/stats/import-dashboard")
async def api_stats_import_dashboard(request: Request, filename: str = "", kind: str = ""):
    """导入小红书数据看板导出 xlsx（自动识别页签，可 ?kind= 手工指定）。"""
    if kind and kind not in ("publish", "watch", "interact", "follower"):
        raise HTTPException(400, detail=f"kind 不合法: {kind}")
    return _import_dashboard_xlsx(filename, await request.body(), kind)


@router.post("/api/stats/refresh")
def api_stats_refresh():
    """重新扫描仓库，落盘 data/stats/summary.json + 数据统计报告。"""
    r = core.run_script(["data_stats.py", "collect"], timeout=90)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return {
        "ok": True,
        "result": r,
        "summary": core.data_stats.build_summary(jobs_dir=core.JOBS_DIR, outputs_dir=core.OUTPUTS_DIR),
    }
