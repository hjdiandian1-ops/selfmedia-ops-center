# -*- coding: utf-8 -*-
"""
自媒体运营中心 · 核心共享模块 (Core)
===================================
集中管理路径常量、子进程封装、状态文件读写、授权门禁与安全工具。
"""
import glob
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request

sys.modules["core"] = sys.modules[__name__]
sys.modules["webapp.core"] = sys.modules[__name__]

logger = logging.getLogger("selfmedia")

# ---------- 路径常量 ----------
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
TOPICS_DIR = os.path.join(ROOT, "data", "topics")
TEMPLATES_FILE = os.path.join(ROOT, "data", "templates.json")
USER_PREFS_FILE = os.path.join(ROOT, "data", "user_prefs.json")
COVER_TEMPLATES_DIR = os.path.join(ROOT, "data", "cover_templates")
COVER_TEMPLATES_FILE = os.path.join(COVER_TEMPLATES_DIR, "templates.json")
COVER_TEMPLATES_IMAGES = os.path.join(COVER_TEMPLATES_DIR, "images")
CRAWL_COVER_TEMPLATES_SCRIPT = os.path.join(SCRIPTS, "crawl_getbeav_templates.py")

SKILLS_REPO_DIR = os.path.join(ROOT, "data", "skills_repo")
SKILLS_REPO_FILE = os.path.join(SKILLS_REPO_DIR, "skills.json")
SKILLS_REPO_AVATARS = os.path.join(SKILLS_REPO_DIR, "avatars")
CRAWL_SKILLS_REPO_SCRIPT = os.path.join(SCRIPTS, "crawl_getbeav_skills.py")

PIPELINE_SLOTS_FILE = os.path.join(ROOT, "data", "pipeline_slots.json")

MATRIX_DIR = os.path.join(ROOT, "data", "matrix")
MATRIX_ACCOUNTS_FILE = os.path.join(MATRIX_DIR, "accounts.json")
DAILY_SCHEDULE_FILE = os.path.join(MATRIX_DIR, "schedule.json")

COMMERCIAL_DIR = os.path.join(ROOT, "data", "commercial")
COMMERCIAL_OFFERS_FILE = os.path.join(COMMERCIAL_DIR, "offers.json")
COMMERCIAL_LEDGER_FILE = os.path.join(COMMERCIAL_DIR, "ledger.json")


STYLE_DOCS = [
    ("skills/personal-style-guide.md", "个人文风指南"),
    ("agent.md", "总入口 Agent 指令"),
    ("agents/xhs-editor-小红书主编.md", "小红书主编 SOP"),
    ("agents/gzh-editor-公众号主编.md", "公众号主编 SOP"),
    ("agents/video-director-短视频导演.md", "短视频导演 SOP"),
    ("workflows/自媒体运营工厂.md", "自媒体运营工厂工作流"),
    ("skills/anti-ai-flavor-skill/SKILL.md", "去 AI 味规则"),
]
STYLE_DOC_ALLOWED_PREFIXES = ("skills/", "agents/", "workflows/", "agent.md")
STYLE_DOC_DEFAULTS = {
    "skills/personal-style-guide.md": os.path.join("data", "templates", "style_docs", "personal-style-guide.template.md"),
}

STYLE_PRESETS = [
    {"id": "xiaowuliao-style", "name": "👑 小吴聊专属风（极客/实战操盘/审美优先）", "file": os.path.join("data", "templates", "style_docs", "xiaowuliao-style.template.md")},
    {"id": "tech-hands-on", "name": "科技实战风（极客评测/提效）", "file": os.path.join("data", "templates", "style_docs", "tech-hands-on.template.md")},
    {"id": "business-deep-dive", "name": "深度商业风（商业观察/尽调拆解）", "file": os.path.join("data", "templates", "style_docs", "business-deep-dive.template.md")},
    {"id": "xhs-lifestyle", "name": "小红书轻快风（视觉种草/好物干货）", "file": os.path.join("data", "templates", "style_docs", "xhs-lifestyle.template.md")},
    {"id": "career-growth", "name": "职场认知风（避坑指南/效率跃迁）", "file": os.path.join("data", "templates", "style_docs", "career-growth.template.md")},
    {"id": "default-template", "name": "通用填空向导（基础骨架）", "file": os.path.join("data", "templates", "style_docs", "personal-style-guide.template.md")},
]

# ---------- 外部与内部模块引入 ----------
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import data_stats  # noqa: E402
import dashboard_analysis  # noqa: E402
import upgrade_agent_docs  # noqa: E402
import security_utils  # noqa: E402
import retention as RT  # noqa: E402
from license import license_gate as LG  # noqa: E402
import llm_engine  # noqa: E402

# ---------- Agent 流水线元数据 ----------
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

# ---------- 引流内容主题库 ----------
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

# ---------- 全局运行进程状态 ----------
_RUNNERS: dict = {}
_ANALYZERS: dict = {}
_BREAKDOWN_RUNNERS: dict = {}


# ---------- 安全与授权校验 ----------
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
    api_ok, api_reason, cfg = llm_engine.engine_status()
    preferred = llm_engine.engine_mode()  # auto | api | codex | workbuddy
    if preferred == "codex":
        mode = "codex" if codex else ("api" if api_ok else "none")
    elif preferred == "workbuddy":
        mode = "workbuddy" if codex or api_ok else "none"
    elif preferred == "api":
        mode = "api" if api_ok else "none"
    else:  # auto：优先 codex，其次 api
        mode = "codex" if codex else ("api" if api_ok else "none")
    return {
        "codex": codex, "api": api_ok, "api_reason": api_reason, "mode": mode,
        "preferred": preferred,
        "model": cfg.get("model", "") if api_ok else "",
    }


# ---------- 环境配置读写 ----------
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
        pass
    return out


def _write_env(updates):
    """把更新项写入 .env（保留其他行与注释；文件权限 600）。"""
    lines = []
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
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


# ---------- 子进程与文件工具 ----------
def run_script(args: List[str], timeout: int = 60, extra_env: Optional[Dict[str, str]] = None) -> dict:
    """白名单脚本执行封装：返回结构化结果（支持子进程隔离环境变量 extra_env，避免污染全局 os.environ）。"""
    cmd = [sys.executable, os.path.join(SCRIPTS, args[0])] + args[1:]
    env = dict(os.environ)
    env["SELFMEDIA_JOBS_DIR"] = JOBS_DIR
    env["JOBS_DIR"] = JOBS_DIR
    if extra_env:
        for k, v in extra_env.items():
            if v is not None:
                env[str(k)] = str(v)
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
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
    hits = sorted([p for p in glob.glob(os.path.join(ROOT, pattern)) if not os.path.basename(p).startswith("样例_")])
    return hits[-1] if hits else None


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}"


def _load_flywheel(path: str, default: dict) -> dict:
    return read_json(path) or default


def _atomic_write_json(path: str, data: dict) -> None:
    """并发安全的原子写 JSON：使用带随机后缀的独立临时文件再 os.replace，避免多线程并发写同一 .tmp 冲突。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{os.urandom(4).hex()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _save_flywheel(path: str, data: dict) -> None:
    """原子写 JSON（先落临时文件再替换），避免半截文件。"""
    _atomic_write_json(path, data)


# ---------- 生产队列支持函数 ----------
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


def _breakdown_batch_running() -> bool:
    proc = _BREAKDOWN_RUNNERS.get("batch")
    if proc is None:
        return False
    if proc.poll() is not None:
        _BREAKDOWN_RUNNERS.pop("batch", None)
        return False
    return True


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


def _resolve_radar_path() -> Optional[str]:
    p = latest_matching("materials/*/*_热点雷达.md")
    if not p:
        sample = os.path.join(ROOT, "materials", "样例_热点雷达.md")
        if os.path.exists(sample):
            return sample
    return p


def _resolve_suggest_path() -> Optional[str]:
    p = latest_matching("materials/*/*_选题推荐.md")
    if not p:
        sample = os.path.join(ROOT, "materials", "样例_选题推荐.md")
        if os.path.exists(sample):
            return sample
    return p


def _market_snapshot() -> dict:
    """市场数据快照：最近热点雷达 / 选题推荐 / 质量周报（作为学习输入）。"""
    radar_path = _resolve_radar_path()
    suggest_path = _resolve_suggest_path()
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

    ledger_entries = _load_commercial_ledger().get("entries", [])
    total_rev = sum(float(e.get("revenue_yuan") or 0.0) for e in ledger_entries)
    total_leads = sum(int(e.get("leads") or 0) for e in ledger_entries)
    total_convs = sum(int(e.get("conversions") or 0) for e in ledger_entries)
    top_comm = sorted(ledger_entries, key=lambda x: (float(x.get("revenue_yuan") or 0.0), int(x.get("leads") or 0)), reverse=True)[:3]
    comm_lines = "\n".join(
        f"  - {c.get('title') or c.get('job_id')}（账号:{c.get('account_name') or '默认'}）线索 {c.get('leads', 0)} ｜ 转化 {c.get('conversions', 0)} ｜ 变现 ¥{float(c.get('revenue_yuan') or 0):.0f}"
        for c in top_comm
    ) or "  - 暂无商业化转化记录（建议在创作时挂载私域钩子/转化组件并回填线索与营收）"

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
        "",
        "## 六、商业化闭环与矩阵变现反馈",
        f"- 累计变现营收：¥{total_rev:.2f} ｜ 累计私域线索：{total_leads} 条 ｜ 成交转化：{total_convs} 单",
        "- 高变现内容 TOP3：",
        comm_lines,
        "- 商业化写稿准则：拒绝无转化的自嗨流量，文末或卡片尾页自然嵌入利他型行动召唤（评论区关键词领 SOP / 关注公众号领工具包），严守平台合规红线（禁止硬留微信号与绝对化收益承诺）。",
    ])


def _default_matrix_accounts() -> list:
    return [
        {
            "id": "acc_main",
            "name": "小吴聊AI（主号·深度旗舰）",
            "handle": "@xiaowuliao",
            "platforms": ["公众号", "小红书", "短视频"],
            "niche": "AI大模型与一人公司实战",
            "persona": "极客技术+内容操盘手，擅长把前沿模型、Agent工作流和商业账本拆解得通透接地气",
            "angle_hint": "深度商业洞察 + 架构实操拆解 + 真实成本收益账本",
            "style_preset": "xiaowuliao-style",
            "daily_target": 1,
            "default_offer_id": "offer_pro_workbench",
            "gzh_app_id": "",
            "gzh_app_secret": "",
            "enabled": True,
            "created_at": "2026-08-01 08:00:00",
        },
        {
            "id": "acc_side_hustle",
            "name": "AI副业拆解局（副号·搞钱实操）",
            "handle": "@ai_side_hustle",
            "platforms": ["小红书", "短视频"],
            "niche": "AI副业变现与轻资产创业",
            "persona": "实战派搞钱课代表，只讲普通人能抄作业的低成本AI变现路径与避坑指南",
            "angle_hint": "普通人零门槛实操 + 投入产出比对比 + 变现路径拆解",
            "style_preset": "business-deep-dive",
            "daily_target": 1,
            "default_offer_id": "offer_private_community",
            "gzh_app_id": "",
            "gzh_app_secret": "",
            "enabled": True,
            "created_at": "2026-08-01 08:00:00",
        },
        {
            "id": "acc_geek_tools",
            "name": "极客效率工具控（垂直号·工具评测）",
            "handle": "@geek_tools_lab",
            "platforms": ["小红书", "公众号"],
            "niche": "开源项目与AI生产力工具实测",
            "persona": "硬核工具测评员，每天实测最新GitHub开源项目与效率神器，给出一针见血的红黑榜",
            "angle_hint": "一手实测对比 + 核心参数横评 + 保姆级配置避坑清单",
            "style_preset": "tech-hands-on",
            "daily_target": 1,
            "default_offer_id": "offer_lead_magnet",
            "gzh_app_id": "",
            "gzh_app_secret": "",
            "enabled": True,
            "created_at": "2026-08-01 08:00:00",
        },
    ]


def _load_matrix_accounts() -> list:
    data = read_json(MATRIX_ACCOUNTS_FILE)
    if isinstance(data, dict) and isinstance(data.get("accounts"), list) and data["accounts"]:
        return data["accounts"]
    defaults = _default_matrix_accounts()
    _save_matrix_accounts(defaults)
    return defaults


def _save_matrix_accounts(accounts: list) -> None:
    _atomic_write_json(MATRIX_ACCOUNTS_FILE, {"accounts": accounts, "updated_at": _now_str()})


def _default_commercial_offers() -> list:
    return [
        {
            "id": "offer_lead_magnet",
            "name": "🎁 私域引流钩子 · AI自动化SOP蓝图包",
            "type": "lead_magnet",
            "type_label": "私域引流",
            "price_yuan": 0.0,
            "lead_value_yuan": 15.0,
            "keyword": "SOP",
            "cta_xhs": "想要我整理的《AI内容工厂全自动SOP+提示词库》？评论区聊聊「SOP」或看主页置顶直接领！",
            "cta_gzh": "📦 读者福利：在公众号后台回复关键词【SOP】，免费获取本文配套的《AI自动化工作流蓝图与完整配置包》。",
            "cta_video": "想要同款自动化配置模板的朋友，评论区打个「SOP」，我把全套流程图和资料包发你！",
            "enabled": True,
        },
        {
            "id": "offer_pro_workbench",
            "name": "👑 自媒体运营中台 Pro 旗舰版订阅",
            "type": "product",
            "type_label": "SaaS产品",
            "price_yuan": 199.0,
            "lead_value_yuan": 25.0,
            "keyword": "工作台",
            "cta_xhs": "这套9大Agent全自动自媒体运营中台已开放体验，评论区聊聊「工作台」或看置顶笔记解锁 Pro 旗舰版！",
            "cta_gzh": "🚀 本文由「自媒体运营中台 Pro」9大Agent流水线协同生成。点击阅读原文或后台回复【工作台】获取同款工业级内容工厂。",
            "cta_video": "一个人活成一个内容团队，秘密就在这套开源运营工作台，看主页置顶一键部署！",
            "enabled": True,
        },
        {
            "id": "offer_private_community",
            "name": "🚀 一人公司AI实战陪伴社群",
            "type": "course",
            "type_label": "社群专栏",
            "price_yuan": 299.0,
            "lead_value_yuan": 35.0,
            "keyword": "一人公司",
            "cta_xhs": "每天拆解1个跑通闭环的AI搞钱案例，评论区聊聊「一人公司」领取近30个高毛利AI副业拆解合集！",
            "cta_gzh": "💡 欢迎加入「小吴聊·一人公司AI实战营」，与500+实战操盘手一起跑通从选题、矩阵日更到商业变现的完整闭环。",
            "cta_video": "想系统跑通一人公司AI商业闭环？评论区回复「一人公司」，进实战交流群一起拿结果！",
            "enabled": True,
        },
        {
            "id": "offer_brand_sponsor",
            "name": "💼 科技品牌商单软广合作组件",
            "type": "sponsor",
            "type_label": "品牌商单",
            "price_yuan": 3000.0,
            "lead_value_yuan": 50.0,
            "keyword": "实测",
            "cta_xhs": "本期硬核实测工具入口及专属福利已整理在评论区置顶，建议先收藏再实操！",
            "cta_gzh": "📌 声明：本文基于真实环境独立实测，配套测试脚本与体验福利见文末置顶留言。",
            "cta_video": "实测参数和免费体验入口我放在评论区置顶了，大家按需自取！",
            "enabled": True,
        },
    ]


def _load_commercial_offers() -> list:
    data = read_json(COMMERCIAL_OFFERS_FILE)
    if isinstance(data, dict) and isinstance(data.get("offers"), list) and data["offers"]:
        return data["offers"]
    defaults = _default_commercial_offers()
    _save_commercial_offers(defaults)
    return defaults


def _save_commercial_offers(offers: list) -> None:
    _atomic_write_json(COMMERCIAL_OFFERS_FILE, {"offers": offers, "updated_at": _now_str()})


def _load_commercial_ledger() -> dict:
    data = read_json(COMMERCIAL_LEDGER_FILE)
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data
    return {"entries": [], "updated_at": ""}


def _save_commercial_ledger(entries: list) -> None:
    _atomic_write_json(COMMERCIAL_LEDGER_FILE, {"entries": entries, "updated_at": _now_str()})



def fmt(n):
    n = int(n or 0)
    return f"{n/10000:.1f}w" if n >= 10000 else str(n)


def pctv(v):
    return f"{float(v or 0) * 100:.1f}%"


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


def _safe_style_path(path):
    p = os.path.normpath(path or "")
    if p.startswith("/") or ".." in p:
        raise HTTPException(status_code=400, detail="path 不合法")
    if p == "agent.md" or p.startswith(STYLE_DOC_ALLOWED_PREFIXES):
        return os.path.join(ROOT, p)
    raise HTTPException(status_code=400, detail=f"path 不在可编辑白名单: {p}")


def _default_style_content(rel: str) -> str:
    tpl = STYLE_DOC_DEFAULTS.get(rel)
    if not tpl:
        return ""
    p = os.path.join(ROOT, tpl)
    return read_text(p) if os.path.exists(p) else ""


def _style_is_default(rel: str) -> bool:
    default = _default_style_content(rel)
    if not default:
        return False
    p = os.path.join(ROOT, rel)
    return read_text(p).strip() == default.strip() if os.path.exists(p) else True


def _ensure_style_default(rel: str) -> bool:
    """文档不存在时用默认模板初始化（小白开箱即用）。"""
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        return False
    content = _default_style_content(rel)
    if not content:
        return False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def _backup_style_doc(p: str) -> None:
    if not os.path.exists(p):
        return
    backup_dir = os.path.join(ROOT, "data", "style_backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"{stamp}-{os.path.basename(p)}")
    try:
        shutil.copy2(p, backup_path)
    except OSError as e:
        logger.warning("备份旧文风文档失败: %s", e)


def _gzh_artifacts(job_id):
    """返回该任务公众号排版 HTML 与封面图片路径（优先取公众号目录封面，再回退小红书目录封面）。"""
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
    for search_dir in (gzh_dir, xhs_dir):
        if not os.path.isdir(search_dir):
            continue
        for n in sorted(os.listdir(search_dir)):
            if n.lower().startswith(("封面", "cover")) and n.lower().endswith((".png", ".jpg", ".jpeg")):
                cover = os.path.join(search_dir, n)
                break
        if cover:
            break
    if cover is None:
        for search_dir in (gzh_dir, xhs_dir):
            if not os.path.isdir(search_dir):
                continue
            for n in sorted(os.listdir(search_dir)):
                if n.lower().endswith((".png", ".jpg", ".jpeg")) and "mobile_check" not in n.lower():
                    cover = os.path.join(search_dir, n)
                    break
            if cover:
                break
    return html or preview, cover
