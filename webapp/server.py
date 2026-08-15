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
import signal
import subprocess
import sys
import glob
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
JOBS_DIR = os.path.join(ROOT, "jobs")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
MATERIALS_DIR = os.path.join(ROOT, "materials")
DATA_DIR = os.path.join(ROOT, "data", "stats")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FLYWHEEL_DIR = os.path.join(ROOT, "data", "flywheel")
VIRAL_FILE = os.path.join(FLYWHEEL_DIR, "viral_videos.json")
VIRAL_CANDIDATES_FILE = os.path.join(FLYWHEEL_DIR, "viral_candidates.json")
PLATFORM_VIRALS_FILE = os.path.join(FLYWHEEL_DIR, "platform_virals.json")
BREAKDOWN_BATCH_FILE = os.path.join(FLYWHEEL_DIR, "breakdown_batch.json")
LESSONS_FILE = os.path.join(FLYWHEEL_DIR, "lessons.json")
FEEDBACK_FILE = os.path.join(FLYWHEEL_DIR, "pipeline_feedback.md")
PRODUCTION_FILE = os.path.join(ROOT, "data", "production", "queue.json")
AGENTS_DIR = os.path.join(ROOT, "agents")
ENV_FILE = os.path.join(ROOT, ".env")
RUN_PRODUCTION = os.path.join(SCRIPTS, "run_production.py")
RUN_VIRAL_ANALYSIS = os.path.join(SCRIPTS, "run_viral_analysis.py")
COLLECT_VIRAL = os.path.join(SCRIPTS, "collect_viral_candidates.py")
COLLECT_PLATFORM_VIRALS = os.path.join(SCRIPTS, "collect_platform_virals.py")
RUN_VIRAL_BREAKDOWN_DAILY = os.path.join(SCRIPTS, "run_viral_breakdown_daily.py")
AGGREGATE_VIRAL = os.path.join(SCRIPTS, "aggregate_viral_lessons.py")
RETENTION_LOG = os.path.join(ROOT, "data", "retention_log.json")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import data_stats  # noqa: E402
import dashboard_analysis  # noqa: E402
import upgrade_agent_docs  # noqa: E402
import security_utils  # noqa: E402
import retention as RT  # noqa: E402
from license import license_gate as LG  # noqa: E402
import llm_engine  # noqa: E402


def _require_job_id(job_id: str):
    """job_id 白名单校验（防路径穿越/命令参数注入），失败转 400。"""
    job_id = (job_id or "").strip()
    try:
        security_utils.require_job_id(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return job_id


def _license_guard(feature: str):
    """Pro 功能门禁：未授权返回 403 + 升级原因（前端 toast 展示）。"""
    ok, reason, _ = LG.check_feature(feature)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)


def _engine_status():
    try:
        import run_production as prod_runner
        codex = bool(prod_runner.codex_bin())
    except Exception:
        codex = False
    api_ok, api_reason, _ = llm_engine.engine_status()
    mode = "codex" if codex else ("api" if api_ok else "none")
    return {"codex": codex, "api": api_ok, "api_reason": api_reason, "mode": mode}


def _read_env():
    """读取项目根 .env（不存在返回 {}）。"""
    out = {}
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        # .env 不存在时按空配置处理（首次运行）
        pass
    return out


def _write_env(updates):
    """把更新项写入 .env（保留其他行与注释；文件权限 600）。"""
    lines = []
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        # .env 不存在时从空行开始写入（首次运行）
        lines = []
    keys = set(updates)
    written = set()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in keys:
                out.append(f"{k}={updates[k]}\n" if updates[k] else f"{k}=\n")
                written.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in written:
            out.append(f"{k}={v}\n" if v else f"{k}=\n")
    os.makedirs(ROOT, exist_ok=True)
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        os.chmod(ENV_FILE, 0o600)
        f.writelines(out)


def _mask(value):
    value = (value or "").strip()
    if not value:
        return ""
    return value[:4] + "****" if len(value) > 8 else "****"

app = FastAPI(title="自媒体运营中心看板", version="2.1.0")

# ---------- Agent 流水线元数据（静态职责 + 动态状态关联） ----------
AGENTS_ROSTER = [
    {
        "role": "总编", "en": "Orchestrator", "emoji": "🧭",
        "responsibility": "选题决策、流程调度、人机确认卡点",
        "state_keys": ["topic"],
        "doc": "agents/orchestrator-总编.md",
    },
    {
        "role": "资深采编", "en": "Senior Researcher", "emoji": "🔎",
        "responsibility": "热点雷达、素材包（真实数据/用户投喂双标注）",
        "state_keys": ["materials"],
        "doc": "agents/researcher-资深采编.md",
    },
    {
        "role": "小红书主编", "en": "XHS Editor", "emoji": "📕",
        "responsibility": "小红书文案、3:4 卡片、标签与互动引导",
        "state_keys": ["draft"],
        "doc": "agents/xhs-editor-小红书主编.md",
    },
    {
        "role": "公众号主编", "en": "WeChat Editor", "emoji": "📰",
        "responsibility": "公众号深度长文、排版 HTML、参考来源",
        "state_keys": ["draft"],
        "doc": "agents/gzh-editor-公众号主编.md",
    },
    {
        "role": "短视频导演", "en": "Video Director", "emoji": "🎬",
        "responsibility": "120s 黄金分镜脚本（五段式）",
        "state_keys": ["draft"],
        "doc": "agents/video-director-短视频导演.md",
    },
    {
        "role": "美术总监", "en": "Visual Director", "emoji": "🎨",
        "responsibility": "3:4 视觉卡片与封面渲染",
        "state_keys": ["visual"],
        "doc": "agents/visual-director-美术总监.md",
    },
    {
        "role": "资深校对排版", "en": "Chief Reviewer", "emoji": "🛡️",
        "responsibility": "契约校验、harsh-critic 评分、移动端审核",
        "state_keys": ["review"],
        "doc": "agents/reviewer-资深校对排版.md",
    },
    {
        "role": "内容合规审核", "en": "Compliance Reviewer", "emoji": "⚖️",
        "responsibility": "发布前合规硬门槛：广告法/平台红线/特殊行业资质/AI标识",
        "state_keys": ["review", "archive"],
        "doc": "agents/compliance-内容合规审核.md",
    },
    {
        "role": "归档发布员", "en": "Distro Ops", "emoji": "📦",
        "responsibility": "三级目录落盘、清扫、草稿箱同步",
        "state_keys": ["archive", "publish", "recycle"],
        "doc": "agents/distro-归档发布员.md",
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


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}"


def _load_flywheel(path: str, default: dict) -> dict:
    return read_json(path) or default


def _save_flywheel(path: str, data: dict) -> None:
    """原子写 JSON（先落临时文件再替换），避免半截文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _atomic_write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------- 生产队列（一键全自动） ----------
_RUNNERS: dict = {}


def _load_queue() -> list:
    data = read_json(PRODUCTION_FILE) or {}
    return data.get("items", [])


def _save_queue(items: list) -> None:
    _atomic_write_json(PRODUCTION_FILE, {"items": items, "updated_at": _now_str()})


def _enqueue_job(job_id: str) -> list:
    items = _load_queue()
    if any(it["job_id"] == job_id and it["status"] in ("queued", "running") for it in items):
        return items
    items.append({
        "job_id": job_id, "status": "queued", "created_at": _now_str(),
        "started_at": "", "finished_at": "", "pid": None, "error": "",
    })
    _save_queue(items)
    return items


def _running_item(items: list):
    return next((it for it in items if it.get("status") == "running"), None)


def _kick_production():
    """串行启动：当前无运行任务时，从队列取第一个 queued 交给 run_production.py。"""
    items = _load_queue()
    if _running_item(items):
        return None
    nxt = next((it for it in items if it.get("status") == "queued"), None)
    if not nxt:
        return None
    job_id = nxt["job_id"]
    log_path = os.path.join(JOBS_DIR, job_id, "production.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        proc = subprocess.Popen(
            [sys.executable, RUN_PRODUCTION, "--run", job_id],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        nxt["status"] = "failed"
        nxt["finished_at"] = _now_str()
        nxt["error"] = str(e)
        _save_queue(items)
        return None
    nxt["status"] = "running"
    nxt["started_at"] = _now_str()
    nxt["pid"] = proc.pid
    nxt["error"] = ""
    _RUNNERS[job_id] = proc
    _save_queue(items)
    return job_id


def _finalize_stale(items: list) -> list:
    """探测已结束的运行任务并落最终状态（含服务重启后的孤儿进程）。"""
    changed = False
    for it in items:
        if it.get("status") != "running":
            continue
        job_id = it["job_id"]
        proc = _RUNNERS.get(job_id)
        rc = proc.poll() if proc is not None else None
        if rc is None and proc is not None:
            continue
        if proc is None:
            # 服务重启：按 pid 存活探测
            pid = it.get("pid")
            try:
                if pid:
                    os.kill(int(pid), 0)
                continue
            except (OSError, ValueError, TypeError):
                pass
        st = (read_json(os.path.join(JOBS_DIR, job_id, "state.json")) or {}).get("state", "")
        if rc == 0 or st == "archive":
            it["status"] = "done"
            it["error"] = ""
        else:
            it["status"] = "failed"
            it["error"] = f"exit={rc}" if rc is not None else "进程已退出（服务重启后无法捕获退出码）"
        it["finished_at"] = _now_str()
        _RUNNERS.pop(job_id, None)
        changed = True
    if changed:
        _save_queue(items)
    return items


def _own_hits() -> list:
    """从 jobs/*/publish_log.json 汇总自家爆款（hit=true 的回填记录）。"""
    hits = []
    for d in sorted(os.listdir(JOBS_DIR)):
        lg = read_json(os.path.join(JOBS_DIR, d, "publish_log.json"))
        if not lg:
            continue
        st = read_json(os.path.join(JOBS_DIR, d, "state.json")) or {}
        for rec in lg.get("records", []):
            if not rec.get("hit"):
                continue
            hits.append({
                "job_id": st.get("job_id", d),
                "title": rec.get("title") or lg.get("title") or st.get("theme", ""),
                "theme": st.get("theme", ""),
                "platform": rec.get("platform", ""),
                "reads": rec.get("reads", 0),
                "likes": rec.get("likes", 0),
                "collects": rec.get("collects", 0),
                "comments": rec.get("comments", 0),
                "engagement": rec.get("engagement", 0.0),
                "collected_at": rec.get("collected_at", ""),
                "url": rec.get("url", ""),
                "followers_gained": rec.get("followers_gained", 0),
            })
    return sorted(hits, key=lambda h: h.get("reads", 0), reverse=True)


def _market_snapshot() -> dict:
    """市场数据快照：最近热点雷达 / 选题推荐 / 质量周报（作为学习输入）。"""
    radar_path = latest_matching("materials/*/*_热点雷达.md")
    suggest_path = latest_matching("materials/*/*_选题推荐.md")
    weekly_path = latest_matching("jobs/weekly_report/*_质量周报.md")

    radar = {"path": radar_path, "sources": 0, "items": 0}
    if radar_path:
        text = read_text(radar_path)
        radar["sources"] = sum(1 for ln in text.splitlines() if ln.startswith("## "))
        radar["items"] = sum(1 for ln in text.splitlines() if re.match(r"\s*\d+[\.、．]", ln))

    suggest = {"path": suggest_path, "items": 0}
    if suggest_path:
        suggest["items"] = len(re.findall(r"^## 候选 \d+", read_text(suggest_path), re.M))

    return {"radar": radar, "suggest": suggest, "weekly": weekly_path}


def _build_feedback_md() -> str:
    """生成反哺流水线 Agent 的经验指令包：账户数据 + 市场快照 + 经验 + 爆款公式。"""
    stats = data_stats.build_summary(jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR)
    lessons = _load_flywheel(LESSONS_FILE, {"lessons": []}).get("lessons", [])
    videos = _load_flywheel(VIRAL_FILE, {"videos": []}).get("videos", [])
    market = _market_snapshot()

    formula_cnt = Counter()
    for v in videos:
        for f in re.split(r"[、,，/]", v.get("formula") or ""):
            f = f.strip()
            if f:
                formula_cnt[f] += 1

    best = stats.get("best", {}) or {}
    top = (best.get("by_reads") or [])[:3]
    top_lines = "\n".join(
        f"  - {r.get('title') or r.get('job_id')}（{r.get('platform')}）阅读 {fmt(r.get('reads', 0))} ｜ 互动率 {pctv(r.get('engagement', 0))}" + (" ｜ 🔥爆款" if r.get("hit") else "")
        for r in top) or "  - 暂无回填数据"

    lesson_lines = "\n".join(
        f"- [{'x' if l.get('applied') else ' '}] {l.get('title')}：{l.get('conclusion')}（证据：{l.get('evidence') or '—'}；适用：{l.get('apply_to') or '—'}）"
        for l in lessons) or "- 暂无沉淀经验"

    formula_lines = "\n".join(
        f"- {f} × {n} 条跟踪案例" for f, n in formula_cnt.most_common(8)) or "- 暂无爆款公式"

    return "\n".join([
        "# 数据飞轮 · 流水线反哺指令包",
        f"> 生成时间：{_now_str()}",
        "> 用法：开工新任务前，把本文件内容粘贴给 Codex，作为写作经验增强上下文。",
        "",
        "## 一、账户数据反馈（最新口径）",
        f"- 发布动作 {stats.get('publish_events', 0)} 次 ｜ 回填/导入 {stats.get('backfill_records', 0)} 条 ｜ 总阅读 {fmt(stats.get('total_reads', 0))} ｜ 平均互动率 {pctv(stats.get('avg_engagement', 0))}",
        f"- 爆款 {stats.get('hits', 0)} 个 ｜ 小红书累计涨粉 {stats.get('xhs_followers_gained', 0)}",
        f"- 最佳表现 TOP3：",
        top_lines,
        "",
        "## 二、市场数据快照",
        f"- 热点雷达：{market['radar']['path'] or '无'}（{market['radar']['sources']} 源 / {market['radar']['items']} 条）",
        f"- 选题推荐：{market['suggest']['path'] or '无'}（{market['suggest']['items']} 条）",
        f"- 最新质量周报：{market['weekly'] or '无'}",
        "",
        "## 三、已沉淀经验（写稿必须遵守）",
        lesson_lines,
        "",
        "## 四、爆款公式参考（跟踪中）",
        formula_lines,
        "",
        "## 五、给流水线 Agent 的要求",
        "1. 先读「已沉淀经验」，命中适用场景的必须执行，不得与既有结论冲突。",
        "2. 标题与结构优先复用「爆款公式参考」中验证过的公式。",
        "3. 完成后在汇报里注明：本次应用了哪条经验/公式；效果回填后再更新飞轮。",
    ])


def fmt(n):
    n = int(n or 0)
    return f"{n/10000:.1f}w" if n >= 10000 else str(n)


def pctv(v):
    return f"{float(v or 0) * 100:.1f}%"


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
def api_stats(platforms: str = ""):
    """自有数据统计：实时扫描 jobs/ + outputs/，聚合 KPI/平台/主题/趋势/内容特征。"""
    plats = _parse_platforms(platforms)
    return data_stats.build_summary(
        jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR, data_dir=DATA_DIR, platforms=plats)


@app.get("/api/dashboard")
def api_dashboard(range: int = 7, period: str = "day", platforms: str = ""):
    """平台看板：period=day|week|month|year，platforms=逗号分隔的平台过滤。"""
    if period not in dashboard_analysis.PERIOD_DAYS:
        raise HTTPException(status_code=400, detail="period 仅支持 day/week/month/year")
    plats = _parse_platforms(platforms)
    return dashboard_analysis.build_dashboard(
        period=period, platforms=plats,
        jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR, data_dir=DATA_DIR)


def _parse_platforms(platforms: str):
    """解析逗号分隔的平台白名单；空串返回 None（全部平台）。"""
    if not platforms.strip():
        return None
    names = [p.strip() for p in platforms.split(",") if p.strip()]
    allowed = set(dashboard_analysis.PLATFORM_ORDER)
    bad = [p for p in names if p not in allowed]
    if bad:
        raise HTTPException(status_code=400, detail=f"平台不合法: {bad}")
    return names


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


def _agent_doc_meta(doc: str):
    text = read_text(os.path.join(ROOT, doc))
    if not text:
        return {"doc": doc, "version": "", "updated_at": "", "patches": 0}
    vm = re.search(r"- version:\s*(\S+)", text)
    um = re.search(r"- updated_at:\s*(\S+)", text)
    return {
        "doc": doc,
        "version": vm.group(1) if vm else "",
        "updated_at": um.group(1) if um else "",
        "patches": text.count("- [经验]"),
    }


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
            "doc": _agent_doc_meta(a.get("doc", "")),
            "active_jobs": [{
                "job_id": j["job_id"],
                "theme": j["theme"],
                "state": j["state"],
                "updated_at": j["updated_at"],
                "outputs": _agent_outputs(j["job_id"]),
            } for j in active[-3:]],
        })
    return {"agents": agents}


@app.get("/api/agents/doc")
def api_agent_doc(role: str = ""):
    """返回某个 Agent 的 SOP 文档全文（供弹窗查看）。"""
    if not role.strip():
        raise HTTPException(status_code=400, detail="role 不能为空")
    hit = next((a for a in AGENTS_ROSTER if a["role"] == role.strip()), None)
    if hit is None:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {role}")
    doc = hit.get("doc", "")
    text = read_text(os.path.join(ROOT, doc))
    if not text:
        raise HTTPException(status_code=404, detail=f"文档不存在或为空: {doc}")
    return {"role": hit["role"], "doc": doc, "content": text,
            "version": _agent_doc_meta(doc).get("version", "")}


@app.get("/api/skills/anti-ai-flavor")
def api_anti_ai_flavor_skill():
    """返回去 AI 味规范 Skill 全文（供成品库质检区弹窗查看）。"""
    path = os.path.join(ROOT, "skills", "anti-ai-flavor-skill", "SKILL.md")
    text = read_text(path)
    if not text:
        raise HTTPException(status_code=404, detail="去 AI 味 Skill 文档不存在")
    return {"name": "anti-ai-flavor-skill", "path": "skills/anti-ai-flavor-skill/SKILL.md", "content": text}


@app.get("/api/themes")
def api_themes():
    """返回引流内容主题库（选题方向预设）。"""
    return {"themes": CONTENT_THEMES, "count": len(CONTENT_THEMES)}


# ---------- 爆款视频跟踪 ----------
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


@app.get("/api/viral")
def api_viral(date: str = ""):
    """爆款跟踪：外部爆款 + 自家爆款（publish_log 命中自动汇总）。"""
    data = _load_flywheel(VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    candidates = _load_flywheel(VIRAL_CANDIDATES_FILE, {"candidates": []}).get("candidates", [])
    platform_store = _load_flywheel(PLATFORM_VIRALS_FILE, {"days": {}, "source_status": {}, "updated_at": ""})
    today = date if date else datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(today, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD")
    day = (platform_store.get("days") or {}).get(today, {})
    vid_map = {v["id"]: v for v in videos}
    def _has_report(vid):
        return (os.path.exists(os.path.join(FLYWHEEL_DIR, "breakdowns", f"{vid}.json"))
                or os.path.exists(os.path.join(FLYWHEEL_DIR, "breakdowns", f"{vid}.md")))
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
        "own_hits": _own_hits(),
        "candidates": candidates,
        "daily": daily,
        "source_status": platform_store.get("source_status", {}),
        "breakdown_batch": _load_flywheel(BREAKDOWN_BATCH_FILE, {"running": False, "total": 0}),
        "counts": {
            "total": len(videos),
            "tracked": sum(1 for v in videos if v.get("status") == "tracked"),
            "analyzing": sum(1 for v in videos if v.get("status") == "analyzing"),
            "analyzed": sum(1 for v in videos if v.get("status") == "analyzed"),
            "applied": sum(1 for v in videos if v.get("status") == "applied"),
        },
    }


@app.post("/api/viral")
def api_viral_save(payload: ViralVideo):
    _validate_viral(payload)
    data = _load_flywheel(VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    item = payload.model_dump()
    if payload.id:
        idx = next((i for i, v in enumerate(videos) if v.get("id") == payload.id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"爆款记录不存在: {payload.id}")
        item["id"] = payload.id
        item["created_at"] = videos[idx].get("created_at", "")
        item["updated_at"] = _now_str()
        videos[idx] = item
        action = "updated"
    else:
        item["id"] = _new_id("v")
        item["created_at"] = _now_str()
        item["updated_at"] = _now_str()
        videos.insert(0, item)
        action = "created"
    data["videos"] = videos
    data["updated_at"] = _now_str()
    _save_flywheel(VIRAL_FILE, data)
    return {"ok": True, "action": action, "video": item}


@app.delete("/api/viral/{vid}")
def api_viral_delete(vid: str):
    data = _load_flywheel(VIRAL_FILE, {"videos": []})
    before = len(data.get("videos", []))
    data["videos"] = [v for v in data.get("videos", []) if v.get("id") != vid]
    if len(data["videos"]) == before:
        raise HTTPException(status_code=404, detail=f"爆款记录不存在: {vid}")
    data["updated_at"] = _now_str()
    _save_flywheel(VIRAL_FILE, data)
    return {"ok": True}


class ViralAnalyze(BaseModel):
    id: str = ""
    title: str
    content: str = ""
    link: str = ""
    platform: str = "小红书"
    note: str = ""


_ANALYZERS: dict = {}
_BREAKDOWN_RUNNERS: dict = {}


def _breakdown_batch_running() -> bool:
    proc = _BREAKDOWN_RUNNERS.get("batch")
    if proc is None:
        return False
    if proc.poll() is not None:
        _BREAKDOWN_RUNNERS.pop("batch", None)
        return False
    return True


@app.post("/api/viral/analyze")
def api_viral_analyze(payload: ViralAnalyze):
    """AI 拆解：后台调 codex CLI 按 viral-breakdown-skill 拆解并回写记录。"""
    _license_guard("viral_breakdown")
    title = payload.title.strip()
    if not title or len(title) > 120:
        raise HTTPException(status_code=400, detail="标题不能为空且不超过 120 字符")
    if len(payload.content) > 6000 or len(payload.link) > 500 or len(payload.note) > 500:
        raise HTTPException(status_code=400, detail="字段过长")
    if payload.platform not in ("小红书", "抖音", "视频号", "B站", "快手", "X", "公众号", "其他"):
        raise HTTPException(status_code=400, detail=f"平台不合法: {payload.platform}")
    if payload.link.strip() and not security_utils.safe_http_url(payload.link):
        raise HTTPException(status_code=400, detail="链接不合法：仅允许公网 http/https，禁止内网/元数据地址")

    data = _load_flywheel(VIRAL_FILE, {"videos": []})
    videos = data.get("videos", [])
    vid = payload.id
    if vid:
        idx = next((i for i, v in enumerate(videos) if v.get("id") == vid), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"爆款记录不存在: {vid}")
        item = videos[idx]
        item["status"] = "analyzing"
        item["updated_at"] = _now_str()
        videos[idx] = item
    else:
        vid = _new_id("v")
        videos.insert(0, {
            "id": vid, "platform": payload.platform, "title": title,
            "author": "", "url": payload.link, "published_at": "",
            "reads": 0, "likes": 0, "collects": 0, "comments": 0,
            "theme": "", "hook": "", "structure": "", "why_viral": "",
            "formula": "", "status": "analyzing", "notes": payload.note,
            "created_at": _now_str(), "updated_at": _now_str(),
        })
    data["videos"] = videos
    data["updated_at"] = _now_str()
    _save_flywheel(VIRAL_FILE, data)

    try:
        import run_production as prod_runner
        if not prod_runner.codex_bin():
            return {
                "ok": False, "fallback": True, "viral_id": vid,
                "prompt": _viral_fallback_prompt(payload, vid),
            }
        proc = subprocess.Popen(
            [sys.executable, RUN_VIRAL_ANALYSIS, "--id", vid, "--title", title,
             "--content", payload.content, "--link", payload.link,
             "--platform", payload.platform],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _ANALYZERS[vid] = proc
    except Exception as e:
        item["status"] = "tracked"
        item["notes"] = (item.get("notes") or "") + f"\nAI 拆解启动失败: {e}"
        data["videos"] = videos
        _save_flywheel(VIRAL_FILE, data)
        return {"ok": False, "error": str(e), "viral_id": vid}
    return {"ok": True, "viral_id": vid, "status": "analyzing"}


def _viral_fallback_prompt(payload: ViralAnalyze, vid: str) -> str:
    return "\n".join([
        "请按 skills/viral-breakdown-skill/SKILL.md 拆解以下爆款（viral_id=" + vid + "）：",
        f"标题：{payload.title}",
        f"平台：{payload.platform}",
        f"链接：{payload.link or '无'}",
        f"原文/逐字稿：\n{payload.content or '（未提供）'}",
        "拆解完成后把 JSON 写到 data/flywheel/breakdowns/" + vid + ".json。",
    ])


@app.post("/api/viral/candidates/collect")
def api_viral_candidates_collect():
    r = run_script(["collect_viral_candidates.py", "--json", "--limit", "10"], timeout=90)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


class CandidateIgnore(BaseModel):
    id: str


@app.post("/api/viral/candidates/ignore")
def api_viral_candidate_ignore(payload: CandidateIgnore):
    data = _load_flywheel(VIRAL_CANDIDATES_FILE, {"candidates": []})
    changed = False
    for c in data.get("candidates", []):
        if c.get("id") == payload.id:
            c["status"] = "ignored"
            changed = True
    if not changed:
        raise HTTPException(status_code=404, detail=f"候选不存在: {payload.id}")
    data["updated_at"] = _now_str()
    _save_flywheel(VIRAL_CANDIDATES_FILE, data)
    return {"ok": True}


class CandidateStatus(BaseModel):
    id: str
    status: str


@app.post("/api/viral/candidates/status")
def api_viral_candidate_status(payload: CandidateStatus):
    """更新候选状态（pending/tracked/analyzed/ignored），用于“开始拆解”等自动化流转。"""
    if payload.status not in ("pending", "tracked", "analyzed", "ignored"):
        raise HTTPException(status_code=400, detail=f"候选状态不合法: {payload.status}")
    data = _load_flywheel(VIRAL_CANDIDATES_FILE, {"candidates": []})
    changed = False
    for c in data.get("candidates", []):
        if c.get("id") == payload.id:
            c["status"] = payload.status
            c["last_seen_at"] = _now_str()
            changed = True
    if not changed:
        raise HTTPException(status_code=404, detail=f"候选不存在: {payload.id}")
    data["updated_at"] = _now_str()
    _save_flywheel(VIRAL_CANDIDATES_FILE, data)
    return {"ok": True, "status": payload.status}


@app.post("/api/viral/platform-collect")
def api_viral_platform_collect():
    """立即采集三平台今日爆款榜单（小红书/抖音/公众号各 Top10）。"""
    r = run_script(["collect_platform_virals.py", "--json", "--limit", "10"], timeout=120)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


@app.post("/api/viral/breakdown-top")
def api_viral_breakdown_top():
    """后台启动每平台 Top5 批量自动拆解（串行 codex CLI，进度轮询可见）。"""
    _license_guard("viral_top5")
    if _breakdown_batch_running():
        raise HTTPException(status_code=409, detail="批量自动拆解已在运行，请稍候")
    try:
        import run_production as prod_runner
        if not prod_runner.codex_bin() and not llm_engine.engine_status()[0]:
            raise HTTPException(status_code=503, detail="未找到 codex CLI 且未配置 LLM_API_KEY，无法自动拆解")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"codex CLI 探测失败: {e}")
    try:
        proc = subprocess.Popen(
            [sys.executable, RUN_VIRAL_BREAKDOWN_DAILY, "--json"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _BREAKDOWN_RUNNERS["batch"] = proc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量拆解启动失败: {e}")
    return {"ok": True, "pid": proc.pid}


@app.get("/api/viral/breakdown/{vid}")
def api_viral_breakdown(vid: str):
    """返回单条拆解 JSON 与 Markdown 报告。"""
    bd_path = os.path.join(FLYWHEEL_DIR, "breakdowns", f"{vid}.json")
    md_path = os.path.join(FLYWHEEL_DIR, "breakdowns", f"{vid}.md")
    bd = read_json(bd_path)
    md = read_text(md_path)
    if not bd and not md:
        raise HTTPException(status_code=404, detail=f"拆解报告不存在: {vid}")
    return {"id": vid, "breakdown": bd or {}, "report_md": md}


@app.post("/api/flywheel/aggregate-viral")
def api_flywheel_aggregate_viral():
    """聚合近 7 天爆款拆解为周经验包：写经验库 + 生成周报 + 自动升级 Agent SOP。"""
    _license_guard("flywheel")
    r = run_script(["aggregate_viral_lessons.py", "--json"], timeout=120)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False))
    return json.loads(r["stdout"])


# ---------- 数据飞轮 ----------
class LessonEntry(BaseModel):
    id: str = ""
    title: str
    conclusion: str
    evidence: str = ""
    apply_to: str = ""
    source: str = "manual"
    applied: bool = False


def _validate_lesson(l: LessonEntry):
    if not l.title.strip() or len(l.title.strip()) > 120:
        raise HTTPException(status_code=400, detail="经验标题不能为空且不超过 120 字符")
    if not l.conclusion.strip() or len(l.conclusion.strip()) > 2000:
        raise HTTPException(status_code=400, detail="结论不能为空且不超过 2000 字符")
    if len(l.evidence) > 500 or len(l.apply_to) > 200:
        raise HTTPException(status_code=400, detail="字段过长")


@app.get("/api/flywheel")
def api_flywheel():
    """数据飞轮总览：发布 → 反馈 → 市场学习 → 经验 → 反哺 全链路数据。"""
    stats = data_stats.build_summary(jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR)
    lessons = _load_flywheel(LESSONS_FILE, {"lessons": []}).get("lessons", [])
    videos = _load_flywheel(VIRAL_FILE, {"videos": []}).get("videos", [])
    return {
        "stats": stats,
        "lessons": lessons,
        "videos": videos,
        "own_hits": _own_hits(),
        "market": _market_snapshot(),
        "feedback": read_text(FEEDBACK_FILE),
        "feedback_path": FEEDBACK_FILE,
        "generated_at": _now_str(),
    }


@app.post("/api/flywheel/lessons")
def api_lesson_save(payload: LessonEntry):
    _validate_lesson(payload)
    data = _load_flywheel(LESSONS_FILE, {"lessons": []})
    lessons = data.get("lessons", [])
    item = payload.model_dump()
    if payload.id:
        idx = next((i for i, l in enumerate(lessons) if l.get("id") == payload.id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"经验不存在: {payload.id}")
        item["id"] = payload.id
        item["created_at"] = lessons[idx].get("created_at", "")
        item["updated_at"] = _now_str()
        lessons[idx] = item
        action = "updated"
    else:
        item["id"] = _new_id("l")
        item["created_at"] = _now_str()
        item["updated_at"] = _now_str()
        lessons.insert(0, item)
        action = "created"
    data["lessons"] = lessons
    data["updated_at"] = _now_str()
    _save_flywheel(LESSONS_FILE, data)
    return {"ok": True, "action": action, "lesson": item}


@app.delete("/api/flywheel/lessons/{lid}")
def api_lesson_delete(lid: str):
    data = _load_flywheel(LESSONS_FILE, {"lessons": []})
    before = len(data.get("lessons", []))
    data["lessons"] = [l for l in data.get("lessons", []) if l.get("id") != lid]
    if len(data["lessons"]) == before:
        raise HTTPException(status_code=404, detail=f"经验不存在: {lid}")
    data["updated_at"] = _now_str()
    _save_flywheel(LESSONS_FILE, data)
    return {"ok": True}


@app.post("/api/flywheel/regenerate")
def api_flywheel_regenerate():
    """重新生成反哺指令包（账户数据 + 市场快照 + 经验 + 爆款公式）。"""
    _license_guard("flywheel")
    text = _build_feedback_md()
    os.makedirs(FLYWHEEL_DIR, exist_ok=True)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    agents = upgrade_agent_docs.upgrade_agents(AGENTS_DIR, FLYWHEEL_DIR)
    return {"ok": True, "path": FEEDBACK_FILE, "feedback": text, "agents": agents}


@app.get("/api/retention/status")
def api_retention_status():
    """数据体检：各模块存储占用与可清理项（不删除任何文件）。"""
    try:
        r = RT.scan()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据体检失败: {exc}")
    log = read_json(RETENTION_LOG) or {}
    runs = log.get("runs", [])
    return {
        "ok": True,
        "plan": {k: len(v) for k, v in r["plan"].items()},
        "space": r["space"],
        "last_run": runs[-1] if runs else None,
    }


@app.post("/api/retention/apply")
def api_retention_apply():
    """执行数据清理：删除过期日志/快照/候选/未出爆款的旧图片，并归档旧任务。"""
    r = RT.scan()
    applied = RT.apply_plan(r)
    log = read_json(RETENTION_LOG) or {"runs": []}
    runs = log.setdefault("runs", [])
    runs.append({
        "ran_at": _now_str(),
        "applied": applied.get("applied", {}),
        "scanned_mb": r["space"]["scanned_mb"],
        "reclaimable_mb": r["space"]["reclaimable_mb"],
    })
    log["runs"] = runs[-10:]
    os.makedirs(os.path.dirname(RETENTION_LOG), exist_ok=True)
    with open(RETENTION_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return {
        "ok": True,
        "applied": applied.get("applied", {}),
        "space": r["space"],
        "ran_at": runs[-1]["ran_at"],
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
        for ln in read_text(suggest_path).splitlines():
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
                       "source": "", "view": "", "formulas": "", "pool_scores": ""}
                continue
            if cur is not None and pool:
                m2 = re.match(r"^- (主题方向|命中热点|建议视角|建议标题公式|评分构成|池内排序)[：:]\s*(.*)$", ln)
                if m2:
                    cur[{"主题方向": "title", "命中热点": "source",
                         "建议视角": "view", "建议标题公式": "formulas",
                         "评分构成": "breakdown",
                         "池内排序": "pool_scores"}[m2.group(1)]] = m2.group(2).strip()
        if cur is not None and pool:
            suggest[pool].append(cur)
        # 把「评分构成」字符串拆成结构化字段，前端横向渲染维度条
        for c in suggest["daily"] + suggest["weekly"]:
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
        header = next((ln for ln in read_text(radar_path).splitlines()
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


@app.get("/api/jobs")
def api_jobs():
    rows = []
    for d in sorted(os.listdir(JOBS_DIR)):
        sf = os.path.join(JOBS_DIR, d, "state.json")
        data = read_json(sf)
        if not data:
            continue
        lg = read_json(os.path.join(JOBS_DIR, d, "publish_log.json")) or {}
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
            "archived": os.path.exists(os.path.join(JOBS_DIR, d, ".archived")),
        })
    return {"jobs": rows}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job_id = _require_job_id(job_id)
    jdir = os.path.join(JOBS_DIR, job_id)
    if not os.path.isdir(jdir):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    return {
        "state": read_json(os.path.join(jdir, "state.json")),
        "validate_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "validate_report.json")),
        "harsh_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "harsh_report.json")),
        "ai_flavor_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "ai_flavor_report.json")),
        "compliance_report": read_json(os.path.join(OUTPUTS_DIR, job_id, "compliance_report.json")),
        "publish_log": read_json(os.path.join(jdir, "publish_log.json")),
    }


# ---------- 操作端点 ----------
class AdoptTopic(BaseModel):
    title: str
    link: str = ""
    notes: str = ""


@app.post("/api/topics/adopt")
def api_adopt(payload: AdoptTopic):
    _license_guard("production")
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题为空")
    title = title[:60]  # 超长标题自动截断，避免长选题无法建任务
    if len(payload.link) > 500 or len(payload.notes) > 500:
        raise HTTPException(status_code=400, detail="link/notes 过长")
    safe_slug = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fa5]", "", title[:12]) or "未命名选题"
    job_id = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_slug[:12]}"
    _require_job_id(job_id)
    r = run_script(["job_state.py", "init", job_id, "--theme", title], timeout=15)
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
    with open(os.path.join(JOBS_DIR, job_id, "brief.md"), "w", encoding="utf-8") as f:
        f.write(brief)
    _enqueue_job(job_id)
    started = _kick_production()
    return {"job_id": job_id, "result": r, "production_started": started}


@app.get("/api/production/status")
def api_production_status():
    """生产队列与当前任务进度（含日志尾部），同时自动收尾/续跑。"""
    items = _finalize_stale(_load_queue())
    _kick_production()
    items = _load_queue()
    running = _running_item(items)
    log = ""
    if running:
        log = read_text(os.path.join(JOBS_DIR, running["job_id"], "production.log"))[-3000:]
    return {
        "running": running,
        "queue": items,
        "log": log,
        "updated_at": _now_str(),
    }


@app.post("/api/production/{job_id}/cancel")
def api_production_cancel(job_id: str):
    job_id = _require_job_id(job_id)
    items = _load_queue()
    it = next((x for x in items if x["job_id"] == job_id), None)
    if not it:
        raise HTTPException(status_code=404, detail=f"队列中无此任务: {job_id}")
    if it["status"] == "running":
        proc = _RUNNERS.get(job_id)
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
        _RUNNERS.pop(job_id, None)
    elif it["status"] != "queued":
        raise HTTPException(status_code=400, detail=f"当前状态 {it['status']} 不可取消")
    it["status"] = "canceled"
    it["finished_at"] = _now_str()
    _save_queue(items)
    return {"ok": True, "job_id": job_id}


@app.post("/api/production/{job_id}/rerun")
def api_production_rerun(job_id: str):
    _license_guard("production")
    job_id = _require_job_id(job_id)
    if not os.path.isdir(os.path.join(JOBS_DIR, job_id)):
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    items = _load_queue()
    it = next((x for x in items if x["job_id"] == job_id), None)
    if it:
        it.update(status="queued", started_at="", finished_at="", error="", pid=None)
    else:
        items.append({
            "job_id": job_id, "status": "queued", "created_at": _now_str(),
            "started_at": "", "finished_at": "", "pid": None, "error": "",
        })
    _save_queue(items)
    started = _kick_production()
    return {"ok": True, "job_id": job_id, "started": started}


@app.get("/api/license/status")
def api_license_status():
    """授权与引擎状态：免费/Pro/owner、到期时间、可用引擎（codex/api）。"""
    lic = LG._read_license()
    mode = (lic or {}).get("mode", "none")
    token = (lic or {}).get("token", "")
    payload = LG.LL.verify_token(token) if token else None
    tier = "owner" if mode == "owner" else (payload.get("tier") if payload else "free")
    return {
        "mode": mode,
        "tier": tier,
        "exp": payload.get("exp", "") if payload else "",
        "features": payload.get("features", []) if payload else [],
        "engine": _engine_status(),
        "upgrade_url": LG.UPGRADE_URL,
        "quota_left": {
            "viral_breakdown": LG.quota_left("viral_breakdown", LG.QUOTA_FEATURES.get("viral_breakdown", 3)),
        },
        "fingerprint": LG.LL.device_fingerprint(),
    }


class SettingsRequest(BaseModel):
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    gzh_app_id: Optional[str] = None
    gzh_app_secret: Optional[str] = None


class GzhDraftRequest(BaseModel):
    job_id: str
    title: str = ""
    digest: str = ""


class LicenseActivateRequest(BaseModel):
    token: str


@app.get("/api/settings")
def api_settings():
    """读取配置状态（密钥只显示掩码，不返回明文）。"""
    env = _read_env()
    api_ok, api_reason, _ = llm_engine.engine_status()
    return {
        "llm": {
            "configured": bool(env.get("LLM_API_KEY", "").strip()),
            "api_key_masked": _mask(env.get("LLM_API_KEY", "")),
            "base_url": env.get("LLM_BASE_URL", llm_engine.DEFAULT_BASE_URL),
            "model": env.get("LLM_MODEL", llm_engine.DEFAULT_MODEL),
            "status_ok": api_ok,
            "status_reason": api_reason,
        },
        "gzh": {
            "configured": bool(env.get("GZH_APP_ID", "").strip() and env.get("GZH_APP_SECRET", "").strip()),
            "app_id_masked": _mask(env.get("GZH_APP_ID", "")),
            "secret_masked": _mask(env.get("GZH_APP_SECRET", "")),
        },
        "engine": _engine_status(),
    }


@app.post("/api/settings")
def api_save_settings(payload: SettingsRequest):
    """保存配置到项目根 .env（本地单机文件，权限 600）。"""
    updates = {}
    if payload.llm_api_key is not None:
        updates["LLM_API_KEY"] = payload.llm_api_key.strip()
    if payload.llm_base_url is not None:
        updates["LLM_BASE_URL"] = payload.llm_base_url.strip()
    if payload.llm_model is not None:
        updates["LLM_MODEL"] = payload.llm_model.strip()
    if payload.gzh_app_id is not None:
        updates["GZH_APP_ID"] = payload.gzh_app_id.strip()
    if payload.gzh_app_secret is not None:
        updates["GZH_APP_SECRET"] = payload.gzh_app_secret.strip()
    if updates:
        _write_env(updates)
        for k, v in updates.items():
            os.environ[k] = v
    return api_settings()


@app.post("/api/license/activate")
def api_license_activate(payload: LicenseActivateRequest):
    """粘贴 token 即激活：验签 + 设备绑定校验，写入本地授权文件。"""
    token = payload.token.strip()
    pl = LG.LL.verify_token(token)
    if pl is None:
        raise HTTPException(status_code=400, detail="token 无效或验签失败，请检查是否复制完整")
    bind = pl.get("bind", "")
    if pl.get("tier") != "owner" and bind and bind != LG.LL.device_fingerprint():
        fp = LG.LL.device_fingerprint()
        raise HTTPException(
            status_code=403,
            detail=f"该 token 绑定的是其他设备（本机指纹 {fp} 不匹配）；请把本机指纹发给卖家重签",
        )
    LG._save(LG.LICENSE_FILE, {
        "mode": "token", "token": token, "installed_at": LG.LL.iso_today(),
    })
    return {"ok": True, "tier": pl.get("tier"), "exp": pl.get("exp", ""),
            "message": f"授权激活成功（{pl.get('tier')}，到期 {pl.get('exp')}）"}


@app.post("/api/settings/llm-test")
def api_llm_test():
    """测试 LLM 连接：发一条极短消息，返回模型回复。"""
    ok, reason, _ = llm_engine.engine_status()
    if not ok:
        return {"ok": False, "message": reason}
    try:
        reply = llm_engine.chat(
            [{"role": "user", "content": "请只回复两个字：正常"}],
            max_tokens=16, timeout=30,
        )
        return {"ok": True, "message": "连接成功，模型回复：" + (reply or "")[:50]}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _gzh_artifacts(job_id):
    """返回该任务公众号排版 HTML 与封面图片路径（无则 None）。"""
    gzh_dir = os.path.join(OUTPUTS_DIR, job_id, "公众号")
    html, preview = None, None
    if os.path.isdir(gzh_dir):
        for n in sorted(os.listdir(gzh_dir)):
            if n.lower().endswith(".html"):
                if "_预览" in n or "_preview" in n.lower():
                    preview = os.path.join(gzh_dir, n)
                elif html is None:
                    html = os.path.join(gzh_dir, n)
    cover = None
    xhs_dir = os.path.join(OUTPUTS_DIR, job_id, "小红书")
    if os.path.isdir(xhs_dir):
        for n in sorted(os.listdir(xhs_dir)):
            if n.lower().startswith("封面") and n.lower().endswith((".png", ".jpg", ".jpeg")):
                cover = os.path.join(xhs_dir, n)
                break
        if cover is None:
            for n in sorted(os.listdir(xhs_dir)):
                if n.lower().endswith(".png"):
                    cover = os.path.join(xhs_dir, n)
                    break
    return html or preview, cover


@app.post("/api/publish/gzh-draft")
def api_gzh_draft(payload: GzhDraftRequest):
    """把公众号排版 HTML 推送到已认证公众号的草稿箱（需配置 AppID/Secret）。"""
    _license_guard("gzh_push")
    job_id = _require_job_id(payload.job_id)
    env = _read_env()
    if not env.get("GZH_APP_ID", "").strip() or not env.get("GZH_APP_SECRET", "").strip():
        raise HTTPException(
            status_code=400,
            detail="未配置公众号 AppID/Secret：请先在左下角 ⚙ 设置 中填写（需要已认证的公众号，个人订阅号暂不支持 API；获取与 IP 白名单步骤见成品库『发布指引』）",
        )
    html, cover = _gzh_artifacts(job_id)
    if not html:
        raise HTTPException(status_code=400, detail="该任务没有公众号排版产物（.html），无法推送草稿")
    title = payload.title.strip() or (read_json(os.path.join(JOBS_DIR, job_id, "state.json")) or {}).get("theme", job_id)
    args = [
        "gzh_draft_api.py", "--title", title[:64],
        "--content-file", html, "--job-id", job_id,
    ]
    if cover:
        args += ["--cover", cover]
    if payload.digest.strip():
        args += ["--digest", payload.digest.strip()[:120]]
    r = run_script(args, timeout=180)
    if not r["ok"]:
        raise HTTPException(status_code=500, detail=json.dumps(r, ensure_ascii=False)[:1000])
    return {"ok": True, "job_id": job_id, "output": r.get("stdout", "")[-500:]}


@app.get("/api/docs/publish-guide")
def api_publish_guide():
    """发布操作手册全文（成品库弹窗查看）。"""
    path = os.path.join(ROOT, "docs", "发布与后台配置.md")
    text = read_text(path)
    if not text:
        raise HTTPException(status_code=404, detail="发布手册不存在")
    return {"title": "发布与后台配置手册", "path": "docs/发布与后台配置.md", "content": text}


class QaRequest(BaseModel):
    output_dir: str


@app.post("/api/qa")
def api_qa(payload: QaRequest):
    out_dir = payload.output_dir.strip().strip("/")
    full = os.path.normpath(os.path.join(ROOT, out_dir))
    if not full.startswith(os.path.normpath(OUTPUTS_DIR)) or not os.path.isdir(full):
        raise HTTPException(status_code=400, detail=f"output_dir 无效: {payload.output_dir}")
    _require_job_id(os.path.basename(full))
    r1 = run_script(["validate_materials_contract.py", out_dir, "--out", os.path.join(out_dir, "validate_report.json")], timeout=60)
    r2 = run_script(["harsh_critic_score.py", out_dir, "--out", os.path.join(out_dir, "harsh_report.json")], timeout=60)
    r3 = run_script(["ai_flavor_check.py", out_dir, "--out", os.path.join(out_dir, "ai_flavor_report.json")], timeout=60)
    return {
        "contract": read_json(os.path.join(OUTPUTS_DIR, os.path.basename(full), "validate_report.json")),
        "harsh": read_json(os.path.join(OUTPUTS_DIR, os.path.basename(full), "harsh_report.json")),
        "ai_flavor": read_json(os.path.join(OUTPUTS_DIR, os.path.basename(full), "ai_flavor_report.json")),
        "contract_run": r1, "harsh_run": r2, "ai_flavor_run": r3,
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


class AccountSnapshot(BaseModel):
    followers: int = 0
    following: int = 0
    likes_collects: int = 0


@app.post("/api/stats/account-snapshot")
def api_account_snapshot(payload: AccountSnapshot):
    """保存账号快照（小红书总粉丝数等；导出表不含总粉丝，需手动维护）。"""
    for name, val in (("followers", payload.followers), ("following", payload.following),
                      ("likes_collects", payload.likes_collects)):
        if not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=400, detail=f"{name} 必须是非负整数")
    path = os.path.join(DATA_DIR, "xhs_account.json")
    data = read_json(path) or {}
    data.update({
        "followers": payload.followers,
        "following": payload.following,
        "likes_collects": payload.likes_collects,
        "updated_at": _now_str(),
        "period": data.get("period", ""),
    })
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "followers": payload.followers}


@app.post("/api/publish/manual")
def api_publish_manual(payload: ManualPublishRequest):
    """人工发布完成后标记记录：追加 mode=manual 的发布动作，保住 48h 回收闭环。"""
    job_id = _require_job_id(payload.job_id)
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
    job_id = _require_job_id(payload.job_id)
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
        r = run_script(["import_xhs_notes.py", "--file", tmp, "--json"], timeout=120)
        if not r["ok"]:
            detail = (r["stderr"] or r["stdout"]).strip() or "导入失败"
            raise HTTPException(400, detail=detail[-800:])
        return json.loads(r["stdout"])
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@app.post("/api/stats/import-xhs")
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
        r = run_script(args, timeout=60)
        if not r["ok"]:
            detail = (r["stderr"] or r["stdout"]).strip() or "导入失败"
            raise HTTPException(400, detail=detail[-800:])
        return json.loads(r["stdout"])
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@app.post("/api/stats/import-dashboard")
async def api_stats_import_dashboard(request: Request, filename: str = "", kind: str = ""):
    """导入小红书数据看板导出 xlsx（自动识别页签，可 ?kind= 手工指定）。"""
    if kind and kind not in ("publish", "watch", "interact", "follower"):
        raise HTTPException(400, detail=f"kind 不合法: {kind}")
    return _import_dashboard_xlsx(filename, await request.body(), kind)


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
