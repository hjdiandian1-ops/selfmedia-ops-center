#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体工作台 WebUI · 后端 (FastAPI)
====================================
集中展示选题/Job/质检/发布数据,并提供一键操作(采纳选题/跑质检/触发流水线/发布)。
仅绑定 127.0.0.1,操作端点仅 POST + 白名单参数,子进程统一超时。

启动:
    uvicorn server:app --host 127.0.0.1 --port 8787
    # 或 bash start.sh
"""
import json
import os
import re
import subprocess
import sys
import glob
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
JOBS_DIR = os.path.join(ROOT, "jobs")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
MATERIALS_DIR = os.path.join(ROOT, "materials")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="自媒体工作台", version="1.0.0")


# ---------- 子进程封装 ----------
def run_script(args: List[str], timeout: int = 60) -> dict:
    """白名单脚本执行封装：返回结构化结果。"""
    cmd = [sys.executable, os.path.join(SCRIPTS, args[0])] + args[1:]
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "exit": r.returncode,
                "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": -1, "stdout": "", "stderr": f"执行超时(>{timeout}s)"}
    except Exception as e:
        return {"ok": False, "exit": -1, "stdout": "", "stderr": str(e)}


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def latest_matching(pattern: str):
    hits = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return hits[-1] if hits else None


# ---------- 只读端点 ----------
@app.get("/api/overview")
def api_overview():
    from collections import Counter
    by_state, total, reject_total, scores = Counter(), 0, 0, []
    for sf in glob.glob(os.path.join(JOBS_DIR, "*", "state.json")):
        d = read_json(sf)
        if not d:
            continue
        total += 1
        by_state[d.get("state", "?")] += 1
        reject_total += d.get("reject_count", 0)
        for st, sc in (d.get("scores") or {}).items():
            scores.append(sc)

    # 待回收: publish/archive 态 + publish_log 存在 + records 空 + 距今 ≥48h
    pending_recycle, hits = 0, 0
    for lg in glob.glob(os.path.join(JOBS_DIR, "*", "publish_log.json")):
        log = read_json(lg)
        if not log:
            continue
        for rec in log.get("records", []):
            if rec.get("hit"):
                hits += 1
        if log.get("records"):
            continue
        sf = os.path.join(os.path.dirname(lg), "state.json")
        st = (read_json(sf) or {}).get("state", "")
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


@app.get("/api/topics")
def api_topics():
    radar_path = latest_matching("materials/*/*_热点雷达.md")
    suggest_path = latest_matching("materials/*/*_选题推荐.md")

    radar = {"path": radar_path, "sources": []}
    if radar_path:
        source, rows = "", []
        for ln in read_text(radar_path).splitlines():
            if ln.startswith("## "):
                if rows:
                    radar["sources"].append({"source": source, "items": rows})
                source, rows = ln[3:].strip(), []
            m = re.match(r"\s*(\d+)[\.、．]\s*(.+?)(?:（\[链接\]\((.*?)\)）)?\s*$", ln)
            if m and source:
                rows.append({"rank": int(m.group(1)), "title": m.group(2).strip(), "link": m.group(3) or ""})
        if rows:
            radar["sources"].append({"source": source, "items": rows})

    suggest = {"path": suggest_path, "candidates": []}
    if suggest_path:
        cur = {}
        for ln in read_text(suggest_path).splitlines():
            m = re.match(r"## 候选 (\d+) ⭐热度 ([\d.]+)", ln)
            if m:
                if cur:
                    suggest["candidates"].append(cur)
                cur = {"rank": int(m.group(1)), "score": float(m.group(2)), "title": "", "source": "", "view": "", "formulas": ""}
                continue
            if cur:
                m2 = re.match(r"^- (主题方向|命中热点|建议视角|建议标题公式)[：:]\s*(.*)$", ln)
                if m2:
                    cur[{"主题方向": "title", "命中热点": "source",
                         "建议视角": "view", "建议标题公式": "formulas"}[m2.group(1)]] = m2.group(2).strip()
        if cur:
            suggest["candidates"].append(cur)
    return {"radar": radar, "suggest": suggest}


@app.get("/api/jobs")
def api_jobs():
    rows = []
    for d in sorted(os.listdir(JOBS_DIR)):
        sf = os.path.join(JOBS_DIR, d, "state.json")
        data = read_json(sf)
        if not data:
            continue
        rows.append({
            "job_id": data["job_id"], "theme": data.get("theme", ""),
            "state": data.get("state"), "reject_count": data.get("reject_count", 0),
            "scores": data.get("scores", {}), "updated_at": data.get("updated_at"),
        })
    return {"jobs": rows}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    jdir = os.path.join(JOBS_DIR, job_id)
    if not os.path.isdir(jdir):
        raise HTTPException(status_code=404, detail=f"Job 不存在: {job_id}")
    return {
        "state": read_json(os.path.join(jdir, "state.json")),
        "validate_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "validate_report.json")),
        "harsh_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "harsh_report.json")),
        "publish_log": read_json(os.path.join(jdir, "publish_log.json")),
    }


# ---------- 操作端点 ----------
class AdoptTopic(BaseModel):
    title: str


@app.post("/api/topics/adopt")
def api_adopt(payload: AdoptTopic):
    title = payload.title.strip()
    if not title or len(title) > 60:
        raise HTTPException(status_code=400, detail="标题为空或过长")
    job_id = f"{datetime.now().strftime('%Y-%m-%d')}_{title[:12]}"
    r = run_script(["job_state.py", "init", job_id, "--theme", title], timeout=15)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return {"job_id": job_id, "result": r}


class QaRequest(BaseModel):
    output_dir: str


@app.post("/api/qa")
def api_qa(payload: QaRequest):
    out_dir = payload.output_dir.strip().strip("/")
    full = os.path.normpath(os.path.join(ROOT, out_dir))
    if not full.startswith(os.path.normpath(OUTPUTS_DIR)) or not os.path.isdir(full):
        raise HTTPException(status_code=400, detail=f"output_dir 无效: {payload.output_dir}")
    r1 = run_script(["validate_materials_contract.py", out_dir, "--out", os.path.join(out_dir, "validate_report.json")], timeout=60)
    r2 = run_script(["harsh_critic_score.py", out_dir, "--out", os.path.join(out_dir, "harsh_report.json")], timeout=60)
    return {
        "contract": read_json(os.path.join(OUTPUTS_DIR, os.path.basename(full), "validate_report.json")),
        "harsh": read_json(os.path.join(OUTPUTS_DIR, os.path.basename(full), "harsh_report.json")),
        "contract_run": r1, "harsh_run": r2,
    }


class PipelineRequest(BaseModel):
    action: str  # topics | recycle | weekly | qa
    output_dir: Optional[str] = ""


@app.post("/api/pipeline/run")
def api_pipeline(payload: PipelineRequest):
    action = payload.action.strip()
    if action == "qa":
        if not payload.output_dir:
            raise HTTPException(status_code=400, detail="qa 需要 output_dir")
        return api_qa(QaRequest(output_dir=payload.output_dir))
    if action not in ("topics", "recycle", "weekly"):
        raise HTTPException(status_code=400, detail=f"不支持的 action: {action}")
    r = run_script(["run_daily_pipeline.py", f"--{action}"], timeout=180)
    return r


class PublishRequest(BaseModel):
    title: str
    content: str = ""
    gzh_html: str = ""
    images: List[str] = []
    tags: List[str] = []
    job_id: str = ""


@app.post("/api/publish")
def api_publish(payload: PublishRequest):
    """一键发布(调 publish_to_n8n.py → NAS)。发布前请确认 NAS 在线、.env 凭据已配置。"""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="标题为空")
    args = ["publish_to_n8n.py", "--title", payload.title]
    if payload.content:
        args += ["--content", payload.content]
    if payload.gzh_html:
        args += ["--gzh-html", payload.gzh_html]
    if payload.images:
        args += ["--images"] + payload.images
    if payload.tags:
        args += ["--tags"] + payload.tags
    if payload.job_id:
        args += ["--job-id", payload.job_id]
    r = run_script(args, timeout=180)
    return r


# ---------- 静态前端 ----------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


app.mount("/assets/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs-assets")


@app.get("/api/outputs/{job_id}")
def api_outputs(job_id: str):
    """列出 outputs/<job_id>/ 下的产出文件树（md/html/png/jpg 等）。"""
    jdir = os.path.join(OUTPUTS_DIR, job_id)
    if not os.path.isdir(jdir):
        return {"job_id": job_id, "files": []}
    files = []
    for root, _dirs, names in os.walk(jdir):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, jdir)
            files.append({
                "rel": rel.replace(os.sep, "/"),
                "size": os.path.getsize(p),
                "kind": ("img" if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                         else "html" if n.lower().endswith((".html", ".htm"))
                         else "md" if n.lower().endswith(".md")
                         else "other"),
            })
    return {"job_id": job_id, "files": files}


@app.get("/api/outputs/{job_id}/file")
def api_output_file(job_id: str, rel: str):
    """读取产出文件文本内容（md/txt 等）。图片与 html 用 /assets/outputs/... 静态 URL。"""
    rel = rel.replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        raise HTTPException(status_code=400, detail="非法路径")
    jdir = os.path.join(OUTPUTS_DIR, job_id)
    full = os.path.normpath(os.path.join(jdir, rel))
    if not full.startswith(os.path.normpath(jdir)) or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        return {"job_id": job_id, "rel": rel, "content": read_text(full)[:8000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)
