#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体运营中心看板 · 后端 (FastAPI)
====================================
结果导向的运营看板:数据大盘 / 选题 / Agent 流水线 / 成品预览 / 平台数据回收。
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

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import data_stats  # noqa: E402

app = FastAPI(title="自媒体运营中心看板", version="2.0.0")

# ---------- Agent 流水线元数据（静态职责 + 动态状态关联） ----------
AGENTS_ROSTER = [
    {
        "role": "总编", "en": "Orchestrator", "emoji": "🧭",
        "responsibility": "选题决策、流程调度、人机确认卡点",
        "state_keys": ["topic"],
    },
    {
        "role": "资深采编", "en": "Senior Researcher", "emoji": "🔎",
        "responsibility": "热点雷达、素材包（真实数据/用户投喂双标注）",
        "state_keys": ["materials"],
    },
    {
        "role": "小红书主编", "en": "XHS Editor", "emoji": "📕",
        "responsibility": "小红书文案、3:4 卡片、标签与互动引导",
        "state_keys": ["draft"],
    },
    {
        "role": "公众号主编", "en": "WeChat Editor", "emoji": "📰",
        "responsibility": "公众号深度长文、排版 HTML、参考来源",
        "state_keys": ["draft"],
    },
    {
        "role": "短视频导演", "en": "Video Director", "emoji": "🎬",
        "responsibility": "120s 黄金分镜脚本（五段式）",
        "state_keys": ["draft"],
    },
    {
        "role": "美术总监", "en": "Visual Director", "emoji": "🎨",
        "responsibility": "3:4 视觉卡片与封面渲染",
        "state_keys": ["visual"],
    },
    {
        "role": "资深校对排版", "en": "Chief Reviewer", "emoji": "🛡️",
        "responsibility": "契约校验、harsh-critic 评分、移动端审核",
        "state_keys": ["review"],
    },
    {
        "role": "归档发布员", "en": "Distro Ops", "emoji": "📦",
        "responsibility": "三级目录落盘、清扫、草稿箱同步",
        "state_keys": ["archive", "publish", "recycle"],
    },
]

# ---------- 引流内容主题库（选题方向预设） ----------
CONTENT_THEMES = [
    {
        "id": "ai-frontier",
        "name": "AI 前沿拆解",
        "emoji": "🤖",
        "slogan": "把最新模型、工具、价格战翻译成人话",
        "audience": "技术从业者 / AI 兴趣者 / 效率党",
        "hooks": ["新品发布", "价格对比", "能力实测"],
        "samples": [
            "MiniMax H3 把 2K 视频价格打到主流 1/3",
            "DeepSeek V4 Flash 实测：Agent 场景到底够不够用",
            "开源模型一周三个新版本，该追还是该等",
        ],
        "traffic": "时效热点 + 搜索流量",
        "formulas": ["dbs-hook", "数字冲击", "悬念好奇"],
    },
    {
        "id": "one-person-company",
        "name": "一人公司实战",
        "emoji": "🏢",
        "slogan": "一个人用系统替代团队的落地案例",
        "audience": "自由职业 / 副业者 / 小团队",
        "hooks": ["成本账", "自动化流水线", "真实工作流"],
        "samples": [
            "我的 NAS 内容工厂：每天三档无人值守怎么跑",
            "一个人运营双平台：从选题到草稿箱的 8 个环节",
            "用 n8n 把重复工作交给机器人后，我多出来 3 小时",
        ],
        "traffic": "共鸣强 + 收藏率高",
        "formulas": ["身份代入", "冲突对比", "干货清单"],
    },
    {
        "id": "cost-account",
        "name": "成本账本",
        "emoji": "🧮",
        "slogan": "把行业新闻拆成能算的账",
        "audience": "商业观察者 / 创业者 / 投资者",
        "hooks": ["30元 vs 500万", "95%渗透率 vs 10%存活率"],
        "samples": [
            "30 块钱、5 小时、500 万播放：AI 视频门槛拆了",
            "95% 的微短剧是 AI 做的，为什么赚钱的还是少数",
            "AI 算力剪刀差：降价到底利好谁",
        ],
        "traffic": "数字冲击 + 转发率高",
        "formulas": ["数字冲击", "反常识", "冲突对比"],
    },
    {
        "id": "tool-field-test",
        "name": "工具实测避坑",
        "emoji": "🛠️",
        "slogan": "真实部署与使用记录，不吹不黑",
        "audience": "开发者 / 数码爱好者 / 效率党",
        "hooks": ["踩坑清单", "部署实录", "性能对比"],
        "samples": [
            "RSSHub 路由实测：哪些源稳定、哪些被风控",
            "本地部署 LLM 的真实成本与显存账",
            "n8n 搭自媒体工作流：我从零到跑通的 6 个坑",
        ],
        "traffic": "搜索流量 + 长尾持久",
        "formulas": ["干货清单", "避坑实战", "身份代入"],
    },
    {
        "id": "data-storytelling",
        "name": "数据可视化拆解",
        "emoji": "📊",
        "slogan": "把枯燥数据变成图表和故事",
        "audience": "内容创作者 / 运营 / 分析师",
        "hooks": ["一张图看懂", "数据背后的真相"],
        "samples": [
            "公众号文章如何用 4 个数据组件提升说服力",
            "小红书卡片的数据可视化规范：条形图怎么用",
            "从 AI 视频成本数据里读出的三个信号",
        ],
        "traffic": "收藏 + 转载",
        "formulas": ["干货清单", "数字冲击", "实操教学"],
    },
    {
        "id": "viral-autopsy",
        "name": "爆款解剖",
        "emoji": "🔬",
        "slogan": "拆解爆款为什么火、钱归谁",
        "audience": "自媒体从业者 / 营销人",
        "hooks": ["为什么偏偏是它", "生产与分发分离"],
        "samples": [
            "中式天庭 34 秒爆火：景观 vs 故事",
            "作者没账号，500 万播放的钱被谁赚走了",
            "“AI 全民制作人”如何从梗变成产业现实",
        ],
        "traffic": "蹭热点 + 行业讨论",
        "formulas": ["悬念好奇", "反常识", "社会证明"],
    },
]


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


def _collect_job_rows():
    """读取 jobs/ 下所有 Job 的 state.json + publish_log.json。"""
    rows = []
    for d in sorted(os.listdir(JOBS_DIR)):
        sf = os.path.join(JOBS_DIR, d, "state.json")
        data = read_json(sf)
        if not data:
            continue
        rows.append({
            "job_id": data.get("job_id", d),
            "dir": d,
            "theme": data.get("theme", ""),
            "state": data.get("state", "?"),
            "scores": data.get("scores", {}),
            "reject_count": data.get("reject_count", 0),
            "updated_at": data.get("updated_at", ""),
            "log": read_json(os.path.join(JOBS_DIR, d, "publish_log.json")) or {},
        })
    return rows


@app.get("/api/stats")
def api_stats():
    """自有数据统计：实时扫描 jobs/ + outputs/，聚合 KPI/平台/主题/趋势/内容特征。"""
    return data_stats.build_summary(jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR)


def _agent_outputs(job_id: str, limit: int = 3):
    """取某个 Job 产出目录里的代表性文件（优先三平台子目录）。"""
    jdir = os.path.join(OUTPUTS_DIR, job_id)
    if not os.path.isdir(jdir):
        return []
    out = []
    for sub in ("小红书", "公众号", "短视频"):
        subdir = os.path.join(jdir, sub)
        if not os.path.isdir(subdir):
            continue
        names = sorted(n for n in os.listdir(subdir)
                       if n.lower().endswith((".png", ".jpg", ".jpeg", ".html", ".md")))
        for n in names[:limit]:
            out.append({"platform": sub, "file": n, "url": f"/assets/outputs/{job_id}/{sub}/{n}"})
    return out[:6]


@app.get("/api/agents")
def api_agents():
    """返回 Agent 职责元数据 + 当前活跃 Job 与最近产出。"""
    jobs = _collect_job_rows()
    agents = []
    for a in AGENTS_ROSTER:
        active = [j for j in jobs if j["state"] in a["state_keys"]]
        agents.append({
            "role": a["role"],
            "en": a["en"],
            "emoji": a["emoji"],
            "responsibility": a["responsibility"],
            "state_keys": a["state_keys"],
            "active_count": len(active),
            "active_jobs": [{
                "job_id": j["job_id"],
                "theme": j["theme"],
                "state": j["state"],
                "updated_at": j["updated_at"],
                "outputs": _agent_outputs(j["job_id"]),
            } for j in active[-3:]],
        })
    return {"agents": agents}


@app.get("/api/themes")
def api_themes():
    """返回引流内容主题库（选题方向预设）。"""
    return {"themes": CONTENT_THEMES, "count": len(CONTENT_THEMES)}


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
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
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

@app.post("/api/publish/manual")
def api_publish_manual(payload: ManualPublishRequest):
    """人工发布完成后标记记录：追加 mode=manual 的发布动作，保住 48h 回收闭环。"""
    job_id = payload.job_id.strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id 不能为空")
    if not os.path.isdir(os.path.join(JOBS_DIR, job_id)):
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
    r = run_script(args, timeout=30)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return r


@app.post("/api/stats/backfill")
def api_stats_backfill(payload: StatsBackfill):
    """平台数据回填：校验后调用 collect_post_stats.py 落盘 publish_log.json。"""
    job_id = payload.job_id.strip()
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id 不能为空")
    if not os.path.isdir(os.path.join(JOBS_DIR, job_id)):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    if payload.platform not in ("小红书", "公众号", "短视频"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {payload.platform}")
    for name, val in (("reads", payload.reads), ("likes", payload.likes),
                      ("collects", payload.collects), ("comments", payload.comments)):
        if not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=400, detail=f"{name} 必须是非负整数")
    if len(payload.url) > 500:
        raise HTTPException(status_code=400, detail="url 过长（≤500 字符）")

    args = [
        "collect_post_stats.py", job_id, "--platform", payload.platform,
        "--reads", str(payload.reads), "--likes", str(payload.likes),
        "--collects", str(payload.collects), "--comments", str(payload.comments),
    ]
    if payload.url.strip():
        args += ["--url", payload.url.strip()]
    r = run_script(args, timeout=30)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return r


@app.post("/api/stats/refresh")
def api_stats_refresh():
    """重新扫描仓库，落盘 data/stats/summary.json + 数据统计报告。"""
    r = run_script(["data_stats.py", "collect"], timeout=90)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return {
        "ok": True,
        "result": r,
        "summary": data_stats.build_summary(jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR),
    }


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
