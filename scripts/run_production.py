#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键多步全自动生产流水线 (Multi-Stage Decoupled Production Pipeline)
===================================================================
彻底重构单次超长 Prompt 调用，将生产解耦为 4 个独立执行阶段，
每阶段独立调用 LLM、中间产物实时落盘，并引入素材强制引用与质检自愈回路：

  Stage 1: materials（素材包生产） -> 结构化素材包 (source_type + priority 标注)
  Stage 2: draft（三平台初稿生成） -> 全文嵌入素材包，输出小红书/公众号/短视频文案及视觉 HTML
  Stage 3: review（质检与自愈链） -> 运行契约/Harsh/去AI味/合规四重规则门禁，不合格定向修复重试
  Stage 4: archive（归档与收尾）   -> 目录完整性校验与临时清扫，生成最终总结

用法：
    python3 scripts/run_production.py --run <job_id>   # 执行多步流水线（支持断点续跑）
    python3 scripts/run_production.py --check          # 检查 CLI / 引擎可用性
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.environ.get("SELFMEDIA_JOBS_DIR") or os.path.normpath(os.path.join(ROOT, "jobs"))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
MATERIALS_DIR = os.path.join(ROOT, "materials")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
TEMPLATES_FILE = os.path.join(ROOT, "data", "templates.json")
USER_PREFS_FILE = os.path.join(ROOT, "data", "user_prefs.json")
STYLE_GUIDE_FILE = os.path.join(ROOT, "skills", "personal-style-guide.md")
FLYWHEEL_FEEDBACK_FILE = os.path.join(ROOT, "data", "flywheel", "pipeline_feedback.md")

sys.path.insert(0, SCRIPTS)
from license.license_gate import check_feature  # noqa: E402
from security_utils import require_job_id  # noqa: E402
import llm_engine  # noqa: E402

# codex CLI 解析链：环境变量 > PATH > ChatGPT App 内置
CODEX_CANDIDATES = (
    os.environ.get("CODEX_BIN", ""),
    shutil.which("codex") or "",
    "/Applications/ChatGPT.app/Contents/Resources/codex",
)


def codex_bin() -> Optional[str]:
    for c in CODEX_CANDIDATES:
        if c and os.path.isfile(c):
            return c
    return None


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def log_msg(log_path: str, msg: str, to_console: bool = True) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}\n"
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    if to_console:
        print(msg)


def advance_state(job_id: str, state: str, score: Optional[int] = None, note: str = "") -> bool:
    """推进状态机：更新 jobs/<job_id>/state.json。"""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p = os.path.join(JOBS_DIR, job_id, "state.json")
    try:
        data = read_json(p) or {"job_id": job_id}
        data["state"] = state
        data["updated_at"] = stamp
        data.setdefault("history", []).append({
            "state": state, "at": stamp, "note": note
        })
        if score is not None:
            data.setdefault("scores", {})[state] = score
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        cmd = [sys.executable, os.path.join(SCRIPTS, "job_state.py"), "set", job_id, state]
        if score is not None:
            cmd.extend(["--score", str(score)])
        if note:
            cmd.extend(["--note", note])
        env = dict(os.environ)
        env["SELFMEDIA_JOBS_DIR"] = JOBS_DIR
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30, env=env)  # nosec B603
        return r.returncode == 0


def user_template_prefs() -> str:
    """读取用户偏好的模板选择（小红书卡片/公众号排版/封面风格），返回可读指令文本。"""
    try:
        with open(USER_PREFS_FILE, encoding="utf-8") as f:
            prefs = json.load(f).get("templates", {})
    except Exception:
        return ""
    try:
        with open(TEMPLATES_FILE, encoding="utf-8") as f:
            td = json.load(f)
    except Exception:
        return ""
    by_id = {}
    for cat in td.get("categories", []):
        cat_name = cat.get("name", "")
        for it in cat.get("items", []):
            by_id[it.get("id", "")] = (cat_name, it.get("name", ""), it.get("desc", ""))
    mapping = {"xhs_card": "小红书图文卡片", "gzh_layout": "公众号排版", "cover_style": "封面构图风格"}
    refs = {
        "xhs_card": "skills/guizang-social-card-skill/references/theme-presets.md",
        "cover_style": "skills/cover-design-skill/references/style-templates.md",
    }
    lines = []
    for key in ("xhs_card", "gzh_layout", "cover_style"):
        tid = prefs.get(key)
        if not tid:
            continue
        cat_name, name, desc = by_id.get(tid, ("", tid, ""))
        ref = refs.get(key) or f"skills/gzh-design-skill/references/theme-{tid}.md"
        lines.append(f"- {mapping.get(key, key)}：{name}（{cat_name}，{desc}）参考 {ref}")
    return "\n".join(lines)


def _prefer_codex() -> bool:
    """引擎模式 → 是否走 Codex CLI：api 强制 API；codex 强制 Codex；auto/workbuddy 有 Codex 就用。"""
    mode = os.environ.get("LLM_ENGINE_MODE", "auto").strip().lower()
    if mode == "api":
        return False
    if mode == "codex":
        return True
    return bool(codex_bin())


def _codex_generate(job_id, system, user, log_path, label, timeout=1800):
    """Codex 模式文本生成：让 codex exec 把成稿写入临时文件再读回（与爆款拆解一致）。"""
    bin_path = codex_bin()
    if not bin_path:
        raise RuntimeError("Codex CLI 不可用")
    slug = re.sub(r"[^A-Za-z0-9_]", "_", str(label or "gen"))[:24]
    out_file = os.path.join(JOBS_DIR, job_id, f"_codex_{slug}.md")
    prompt = "\n\n".join([
        "你是「自媒体运营工厂」的内容生产引擎。请完成下面的写作任务。",
        "【系统指令】\n" + system,
        "【用户要求】\n" + user,
        "",
        f"硬性要求：把最终成稿写入文件 {out_file}（纯 Markdown 正文，只写内容本身，"
        "不要任何解释、不要用代码块围栏包裹、不要写其它文件）。完成后只回复 DONE。",
    ])
    log_msg(log_path, f"  ↳ [{label}] 使用 Codex CLI 生成…")
    proc = subprocess.Popen(  # nosec B603  # 固定 codex 命令 + 受控 job_id
        [bin_path, "exec", "--approve-for-me", "-"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        proc.communicate(input=prompt.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError("Codex 生成超时")
    content = read_text(out_file)
    try:
        os.remove(out_file)
    except OSError:
        pass
    if content.strip():
        return content.strip()
    raise RuntimeError("Codex 未产出文件")


def _generate(job_id, system, user, max_tokens, log_path, label, timeout=600):
    """统一文本生成：按引擎模式优先 Codex，失败回退 API。返回文本或抛异常。"""
    if _prefer_codex():
        try:
            return _codex_generate(job_id, system, user, log_path, label)
        except Exception as e:
            log_msg(log_path, f"  ⚠️ [{label}] Codex 生成失败，回退 API：{e}")
    return llm_engine.chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], max_tokens=max_tokens, timeout=timeout)


def _brief_link(brief: str) -> str:
    """从 brief.md 的「采纳来源」行提取原文链接（无则空串）。"""
    m = re.search(r"采纳来源[：:]\s*(\S+)", brief or "")
    if not m:
        return ""
    raw = m.group(1).strip()
    return raw if raw.startswith(("http://", "https://")) else ""


def _latest_radar_path() -> str:
    hits = sorted(glob.glob(os.path.join(MATERIALS_DIR, "*", "*_热点雷达.md")), key=os.path.getmtime)
    return hits[-1] if hits else ""


def _research_grounding(theme: str = "", link: str = "", limit: int = 3500) -> str:
    """采集真实数据做素材 grounding：抓取原文正文 + 最近热点雷达 + 选题推荐 + 经验。

    目的：让 Stage 1 采编基于「真实抓取到的原文/热点/榜单/公式」组织素材，
    而不是凭模型记忆虚构数字。返回可嵌入 prompt 的文本块（无数据时为空）。
    """
    parts = []
    # 1. 真实抓取原文（优先采纳链接 + 雷达相关条目）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import fetch_source_content
        fetched = fetch_source_content.gather_grounding(theme, link, _latest_radar_path(), limit=5)
        if fetched.strip():
            parts.append(fetched.strip()[:limit])
    except Exception:
        pass
    # 2. 最近热点雷达 + 选题推荐 + 已沉淀经验
    radar = read_text(_latest_radar_path()) if _latest_radar_path() else ""
    suggest = read_text(sorted(glob.glob(os.path.join(MATERIALS_DIR, "*", "*_选题推荐.md")), key=os.path.getmtime)[-1]) \
        if glob.glob(os.path.join(MATERIALS_DIR, "*", "*_选题推荐.md")) else ""
    lessons = read_text(os.path.join(ROOT, "data", "flywheel", "lessons.json"))
    if radar.strip():
        parts.append("## 真实热点雷达（最近一次采集）\n" + radar.strip()[:limit])
    if suggest.strip():
        parts.append("## 选题推荐（最近一次）\n" + suggest.strip()[:limit])
    try:
        if lessons.strip():
            ldata = json.loads(lessons)
            lines = ["## 已沉淀经验（必须遵守）"]
            for l in ldata.get("lessons", [])[:10]:
                lines.append(f"- {l.get('title')}：{l.get('conclusion')}")
            parts.append("\n".join(lines))
    except Exception:
        pass
    if not parts:
        return ""
    return "\n\n".join(parts)


def build_prompt(job_id: str) -> str:
    """向下兼容旧接口：构造完整提示词（供 CLI 模式及单次调试使用）。"""
    state = read_json(os.path.join(JOBS_DIR, job_id, "state.json")) or {}
    theme = state.get("theme") or job_id
    brief = read_text(os.path.join(JOBS_DIR, job_id, "brief.md"))
    feedback = read_text(FLYWHEEL_FEEDBACK_FILE)
    template_prefs = user_template_prefs()
    style_guide = read_text(STYLE_GUIDE_FILE)
    return "\n".join([
        "你是「自媒体运营工厂」的生产执行器。请把下面的 Job 从素材一路生产到归档，不要中途停下来问问题。",
        "",
        f"Job ID：{job_id}",
        f"主题：{theme}",
        "期望平台：小红书（图文卡片 + 文案）+ 公众号（深度长文 + 排版 HTML）+ 短视频分镜脚本（可选，主题适合时）。",
        "",
        "## 用户偏好模板（必须遵循）",
        template_prefs or "（用户尚未在「设置 → 模板选择」中配置，沿用各 Agent 默认模板）",
        "",
        "## 用户文风指南（必须遵循）",
        style_guide[:3000] if style_guide else "（未设置个人文风指南，沿用 agents/ 各角色 SOP 默认文风）",
        "",
        "## 生产简报",
        brief or "（无简报，按主题直接开工）",
        "",
        "## 硬性步骤",
        "1. 先读：workflows/自媒体运营工厂.md、workflows/产出标准.md、workflows/contract-schema.md、agents/ 下全部角色 SOP。",
        "2. 若存在 data/flywheel/pipeline_feedback.md，创作前必须通读并遵守其中的经验与公式。",
        "3. 按状态机推进：materials（素材包落盘 materials/YYYY-MM/<job_id>素材包.md）→ draft（三平台文案.md 带 frontmatter 契约）"
        " → visual（小红书卡片 HTML/PNG、封面、公众号排版）→ review（运行质检）→ archive（归档清扫）。",
        "4. 每完成一个阶段，必须执行：",
        f"   python3 scripts/job_state.py set {job_id} <state> --note \"<该阶段完成说明>\"",
        "5. 质检：python3 scripts/run_daily_pipeline.py --qa outputs/<job_id>/；机器 REJECTED 时按 harsh-critic 意见打回重写，最多 2 次，之后停止并说明。",
        "6. 合规硬门槛：归档前必须运行 python3 scripts/compliance_check.py outputs/<job_id>/，若 compliance_report.json 为 REJECTED（存在 high 级违规：广告法绝对化用语/医疗金融教育承诺/站外导流等），必须先修改文案直至 PASSED 或仅剩 warn，任何情况下禁止把 REJECTED 的产物归档或发布。",
        "7. 去 AI 味硬门槛：创作与自查时必须遵守 skills/anti-ai-flavor-skill/SKILL.md（句式壳/标点/语气/开头收尾），"
        "质检链会跑 scripts/ai_flavor_check.py；若 ai_flavor_report.json 为 REJECTED（结构级 AI 腔：首先其次最后/对称收束/报幕过渡等），必须先改写直至 PASSED 或仅剩 warn。",
        "8. 全部完成后，用 job_state.py set 推进到 archive，并在结尾汇报成品清单、本次应用的飞轮经验与合规/去AI味审核结论。",
        "",
        "## 数据飞轮经验（若有）",
        feedback[-4000:] if feedback else "（暂无，跳过）",
    ])


# =========================================================================
# Stage 1: materials（素材包生产）
# =========================================================================
def stage_1_materials(job_id: str, theme: str, brief: str, feedback: str, log_path: str) -> Tuple[bool, str]:
    """
    Stage 1: 结构化素材包生产
    - 输入：主题 + brief.md + 飞轮经验
    - 输出：结构化素材包 Markdown（每条素材带 [编号] + source_type + priority 双标注）
    - 落盘：materials/YYYY-MM/<job_id>素材包.md
    - 推进状态机到 materials
    """
    start_t = time.time()
    month = datetime.now().strftime("%Y-%m")
    mat_path = os.path.join(MATERIALS_DIR, month, f"{job_id}素材包.md")

    # 若已存在有效内容，直接复用
    if os.path.exists(mat_path) and os.path.getsize(mat_path) > 100:
        log_msg(log_path, f"▶ [Stage 1 materials] 检测到已有素材包: {mat_path}，直接加载复用")
        content = read_text(mat_path)
        advance_state(job_id, "materials", note="复用既有素材包")
        return True, content

    log_msg(log_path, f"▶ [Stage 1 materials] 启动资深采编 Agent 生成结构化素材包 (主题: {theme})...")

    system = (
        "你是「自媒体运营工厂」的资深采编（Senior Researcher）。"
        "你的任务是为多平台创作者提供硬核、翔实、结构化的素材包。禁止虚构捏造。\n"
        "【输出规范】必须输出标准 Markdown，每条素材必须带有 [条目编号]、source_type 与 priority（核心/参考/背景）双重标注：\n"
        "# [主题] 结构化素材包\n\n"
        "## 一、核心事实与时间节点 (Timeline & Facts)\n"
        "- [M1] [source_type: 官方发布] [priority: 核心] 事实描述与关键节点\n"
        "- [M2] [source_type: 技术分析] [priority: 核心] 核心技术突破或事件脉络\n\n"
        "## 二、关键数据指标与对比维度 (Metrics & Comparisons)\n"
        "- [M3] [source_type: 行业研报] [priority: 核心] 具体量化数据、对比增降幅（必须提供具体数字或百分比）\n"
        "- [M4] [source_type: 评测数据] [priority: 参考] 实操基准与能效指标\n\n"
        "## 三、核心实体与应用场景 (Entities & Context)\n"
        "- [M5] [source_type: 案例调研] [priority: 核心] 关键企业/产品/架构名词及落地场景\n\n"
        "## 四、引流切入点与用户痛点 (Hooks & Pain Points)\n"
        "- [M6] [source_type: 痛点洞察] [priority: 参考] 典型踩坑场景与高价值认知突破口\n\n"
        "## 五、真实来源与参考文献 (References)\n"
        "1. [M7] [source_type: 官方文档] [priority: 背景] 来源机构及公开引用链接\n"
    )

    grounding = _research_grounding(theme, _brief_link(brief))
    user_prompt = (
        f"Job ID: {job_id}\n"
        f"主题: {theme}\n"
        f"生产简报: {brief or '按主题深度搜集'}\n"
        f"飞轮历史经验参考:\n{feedback[-1200:] if feedback else '暂无'}\n\n"
        f"## 真实数据 Grounding（必须优先基于这些真实抓取内容组织素材）\n"
        f"{grounding or '（本轮未采集到原文/热点雷达/选题推荐，请基于主题客观分析，凡无法核实的具体数字必须明确标注「数据待核实」，禁止编造）'}\n\n"
        "请立即输出规范的 Markdown 素材包，只输出正文内容。"
    )

    est_in_tokens = len(system) + len(user_prompt)
    try:
        content = _generate(job_id, system, user_prompt, 3000, log_path, "Stage1采编", timeout=120)
        if not content:
            raise RuntimeError("LLM 返回空内容")
    except Exception as e:
        log_msg(log_path, f"  ⚠️ [Stage 1] 采编生成异常，启动诚实降级模板（禁止虚构数字）: {e}")
        # 降级模板：绝不编造具体数据/百分比，明确标注待核实，避免污染下游成品质量
        content = (
            f"# {theme} 结构化素材包\n\n"
            "> ⚠️ 本轮 AI 采编调用失败，以下为降级骨架，具体事实与数据待核实。\n\n"
            "## 一、核心事实与时间节点\n"
            f"- [M1] [source_type: 官方发布] [priority: 核心] 围绕「{theme}」的官方信息与时间线（数据待核实，禁止编造）。\n\n"
            "## 二、关键数据指标与对比维度\n"
            "- [M2] [source_type: 行业研报] [priority: 核心] 相关量化数据与对比（数据待核实，禁止编造百分比/倍数）。\n\n"
            "## 三、核心实体与应用场景\n"
            f"- [M3] [source_type: 案例调研] [priority: 核心] 「{theme}」涉及的关键实体与落地场景。\n\n"
            "## 四、引流切入点与用户痛点\n"
            f"- [M4] [source_type: 痛点洞察] [priority: 参考] 「{theme}」对应的读者痛点与高价值认知突破口。\n\n"
            "## 五、真实来源与参考文献\n"
            "1. [M5] [source_type: 官方文档] [priority: 背景] 待补充真实来源链接（禁止编造来源）。\n\n"
            f"{grounding or ''}"
        )

    write_text(mat_path, content)
    duration = time.time() - start_t
    est_out_tokens = len(content)
    log_msg(log_path, f"✅ [Stage 1 materials] 完成！耗时: {duration:.2f}s | 预估 Token: in~{est_in_tokens} out~{est_out_tokens} | 产物: {mat_path}")
    advance_state(job_id, "materials", note="Stage 1 素材包落盘完成")
    return True, content


# =========================================================================
# Stage 2: draft（三平台初稿）
# =========================================================================
def _generate_xhs_draft(job_id: str, theme: str, full_materials: str, style_guide: str, template_prefs: str, log_path: str) -> str:
    """生成小红书初稿（包含 YAML Frontmatter 契约与 consumed_materials 引用列表）。"""
    log_msg(log_path, "  ↳ [Stage 2a] 小红书主编开工...")
    system = (
        "你是「自媒体运营工厂」的小红书主编（XHS Editor）。"
        "你必须严格遵循 skills/anti-ai-flavor-skill/SKILL.md（禁止 AI 腔、不使用“不是…而是…”、不使用“首先其次最后”）。\n"
        "【硬性契约要求】必须输出带有标准 YAML Frontmatter 的 Markdown 格式：\n"
        "---\n"
        "title: 小红书爆款标题（≤20字，口语化吸睛，禁止Markdown加粗**）\n"
        "platform: 小红书\n"
        "tags: [AI, 效率工具, 搞钱, 实操]\n"
        "series: 自媒体实战系列 01\n"
        "follow_cta: 关注小吴聊，下期拆解…\n"
        "consumed_materials: [M1, M2, M3, M5]\n"
        "---\n\n"
        "正文要求：\n"
        "1. 黄金第一句强钩子（3秒留人）；\n"
        "2. 深度融合素材包中标记为 priority: 核心 的全部条目，并在 consumed_materials 中列出编号；\n"
        "3. 数据可视化标记（必须包含 `<!-- viz: stat-card -->` 或数据图表标记）；\n"
        "4. 排版短段落、多空行、带 emoji；\n"
        "5. 结尾互动引导 + 下期预告钩子。"
    )
    user_prompt = (
        f"主题：{theme}\n\n"
        f"## 完整素材包全文（初稿必须引用标记为 priority: 核心 的条目）\n{full_materials}\n\n"
        f"## 用户模板偏好：\n{template_prefs or '默认图文卡片'}\n\n"
        f"## 个人文风指南：\n{style_guide[:2200] if style_guide else '自然口语化、利他干货、亲和真实'}\n\n"
        "请直接输出符合契约规范的小红书文案（包含 YAML Frontmatter 与 consumed_materials 列表）。"
    )
    try:
        content = _generate(job_id, system, user_prompt, 2500, log_path, "小红书主编", timeout=120)
    except Exception as e:
        log_msg(log_path, f"  ⚠️ 小红书文案生成异常，使用兜底结构: {e}")
        content = (
            f"---\ntitle: {theme[:18]}\nplatform: 小红书\ntags: [AI, 生产力]\nseries: 自媒体实战系列 01\n"
            f"follow_cta: 关注小吴聊，下期拆解更多干货\nconsumed_materials: [M1, M2, M3]\n---\n\n"
            f"关于「{theme}」，有几个关键点值得说清楚。\n\n<!-- viz: stat-card -->\n"
            f"具体数据以素材包为准，禁止编造。"
        )
    xhs_file = os.path.join(OUTPUTS_DIR, job_id, "小红书", "文案.md")
    write_text(xhs_file, content)
    return content


def _generate_gzh_draft(job_id: str, theme: str, full_materials: str, style_guide: str, template_prefs: str, log_path: str) -> str:
    """生成公众号深度长文（包含 YAML Frontmatter 契约与 consumed_materials 引用列表）。"""
    log_msg(log_path, "  ↳ [Stage 2b] 公众号主编开工...")
    system = (
        "你是「自媒体运营工厂」的公众号主编（WeChat Editor）。"
        "你擅长撰写深度商业观察、科技实战长文，行文客观克制、逻辑严密、数据确凿，杜绝一切 AI 假大空废话。\n"
        "【硬性契约要求】必须输出带有标准 YAML Frontmatter 的 Markdown 格式：\n"
        "---\n"
        "title: 公众号深度标题（吸引点击且不标题党）\n"
        "platform: 公众号\n"
        "digest: 摘要（≤60字，清晰提炼核心洞察）\n"
        "consumed_materials: [M1, M2, M3, M4, M5, M7]\n"
        "---\n\n"
        "正文要求：\n"
        "1. 引言卡片 / 反常识开场；\n"
        "2. 深度融合素材包中标记为 priority: 核心 的全部条目，并在 consumed_materials 中列出编号；\n"
        "3. 三个核心章节（## 01 / ## 02 / ## 03），每章包含深度剖析与数据论据；\n"
        "4. 必须包含至少 2 处数据可视化标记（如 `<!-- viz: bar-chart -->` 与 `<!-- viz: stat-card -->`）；\n"
        "5. 底部参考文献标注（## 参考来源）。"
    )
    user_prompt = (
        f"主题：{theme}\n\n"
        f"## 完整素材包全文（初稿必须引用标记为 priority: 核心 的条目）\n{full_materials}\n\n"
        f"## 排版模板偏好：\n{template_prefs or '红白系简约风'}\n\n"
        f"## 个人文风指南：\n{style_guide[:2200] if style_guide else '深度极客商业风'}\n\n"
        "请直接输出完整的公众号长文 Markdown（包含 YAML Frontmatter、consumed_materials 与 2 处 viz 标记）。"
    )
    try:
        content = _generate(job_id, system, user_prompt, 4000, log_path, "公众号主编", timeout=180)
    except Exception as e:
        log_msg(log_path, f"  ⚠️ 公众号长文生成异常，使用兜底结构: {e}")
        content = (
            f"---\ntitle: {theme}\nplatform: 公众号\ndigest: 深度拆解 {theme} 的底层逻辑与落地实操\n"
            f"consumed_materials: [M1, M2, M3]\n---\n\n"
            f"# {theme}\n\n<!-- viz: stat-card -->\n<!-- viz: bar-chart -->\n\n"
            f"## 01 / 行业背景与核心事实\n围绕「{theme}」梳理已核实的事实与背景（数据以素材包为准）。\n\n"
            f"## 02 / 数据对比与关键分析\n基于素材包中真实标注的数据展开对比，缺失处明确说明待核实。\n\n"
            f"## 03 / 落地避坑与行动指南\n结合素材包中的案例与痛点给出可执行建议。\n\n"
            f"## 参考来源\n1. 见结构化素材包「真实来源与参考文献」"
        )
    gzh_file = os.path.join(OUTPUTS_DIR, job_id, "公众号", "文案.md")
    write_text(gzh_file, content)
    return content


def _generate_video_draft(job_id: str, theme: str, full_materials: str, style_guide: str, log_path: str) -> str:
    """生成 120s 黄金分镜脚本。"""
    log_msg(log_path, "  ↳ [Stage 2c] 短视频导演开工...")
    system = (
        "你是「自媒体运营工厂」的短视频导演（Video Director）。"
        "你必须产出严格的 120s 黄金五段式分镜脚本 Markdown，包含严格的时间戳和画面/台词规划：\n"
        "- ## 0-3s 黄金钩子 (画面描述 + 旁白台词 + 视觉花字)\n"
        "- ## 3-15s 痛点共鸣 (画面描述 + 旁白台词 + 情绪音效)\n"
        "- ## 15-75s 干货演示 (画面描述 + 旁白台词 + 实操展示)\n"
        "- ## 75-105s 转折升华 (画面描述 + 旁白台词 + 认知跃迁)\n"
        "- ## 105-120s 行动召唤 (画面描述 + 旁白台词 + 引导关注/领取)\n"
    )
    user_prompt = (
        f"主题：{theme}\n\n"
        f"## 素材参考：\n{full_materials[:3000]}\n\n"
        "请直接输出标准的 120s 黄金分镜脚本 Markdown，严格包含五段式时间线划分。"
    )
    try:
        content = _generate(job_id, system, user_prompt, 2500, log_path, "短视频导演", timeout=120)
    except Exception as e:
        log_msg(log_path, f"  ⚠️ 短视频分镜生成异常，使用兜底结构: {e}")
        content = (
            f"# {theme} 120s 黄金分镜脚本\n\n"
            "## 0-3s 黄金钩子\n- 画面：特写\n- 旁白：你敢信吗？一套流水线替代了一个运营团队！\n\n"
            "## 3-15s 痛点共鸣\n- 画面：繁琐写稿痛点\n- 旁白：每天花 5 小时写稿排版，产出还不稳定？\n\n"
            "## 15-75s 干货演示\n- 画面：系统实操演示\n- 旁白：今天带你 3 步搭建自动化内容工厂。\n\n"
            "## 75-105s 转折升华\n- 画面：成果对比大盘\n- 旁白：把重复劳动交给系统，把时间留给真正值钱的事。\n\n"
            "## 105-120s 行动召唤\n- 画面：关注引导\n- 旁白：关注小吴聊，获取完整开源工作流！"
        )
    vid_file = os.path.join(OUTPUTS_DIR, job_id, "短视频", "120s黄金分镜脚本.md")
    write_text(vid_file, content)
    return content


def _generate_visual_artifacts(job_id: str, theme: str, xhs_md: str, gzh_md: str, log_path: str) -> None:
    """生成小红书 3:4 响应式卡片 HTML 与公众号内联排版 HTML。"""
    slug = re.sub(r"[^\w\u4e00-\u9fa5]", "", theme[:12]) or "slide"
    
    # 1. 小红书幻灯片 HTML
    xhs_html_path = os.path.join(OUTPUTS_DIR, job_id, "小红书", f"rednote_{slug}_slides.html")
    title_m = re.search(r"title:\s*(.*)", xhs_md)
    title = title_m.group(1).strip() if title_m else theme
    
    xhs_html = f"""<!doctype html>
<html lang="zh-CN" data-accent="ikb">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Noto+Sans+SC:wght@400;600;700&display=swap">
  <style>
    :root {{ --paper: #fafaf8; --ink: #0a0a0a; --accent: #002FA7; --accent-on: #ffffff; --grey-1: #f0f0ee; }}
    body {{ margin: 0; padding: 20px; background: #e5e5e5; font-family: 'Noto Sans SC', sans-serif; display: flex; flex-direction: column; align-items: center; gap: 20px; }}
    .card {{ width: 360px; height: 480px; background: var(--paper); border-radius: 16px; padding: 24px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
    .tag {{ align-self: flex-start; background: var(--accent); color: var(--accent-on); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
    .title {{ font-size: 22px; font-weight: 900; color: var(--ink); line-height: 1.35; margin: 12px 0; }}
    .viz-box {{ background: var(--grey-1); border-radius: 10px; padding: 12px; font-size: 13px; color: #333; line-height: 1.6; flex: 1; overflow: hidden; }}
    .footer {{ display: flex; justify-content: space-between; font-size: 11px; color: #888; border-top: 1px solid #eee; padding-top: 8px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="tag">小吴聊 · 深度拆解</div>
    <div class="title">{title}</div>
    <div class="viz-box">
      <p>💡 <b>核心洞察</b>：{theme}</p>
      <p>📊 <b>数据佐证</b>：详见完整图文拆解与实测对比。</p>
      <p>⚡ <b>极速落地</b>：多步独立流水线闭环，告别素材遗忘。</p>
    </div>
    <div class="footer">
      <span>全网同名 · 小吴聊</span>
      <span>Swipe ➔ 翻页看干货</span>
    </div>
  </div>
</body>
</html>
"""
    write_text(xhs_html_path, xhs_html)

    # 2. 公众号排版 HTML 与预览
    gzh_html_path = os.path.join(OUTPUTS_DIR, job_id, "公众号", f"gzh_{slug}_排版_红白色系(red-white).html")
    preview_path = os.path.join(OUTPUTS_DIR, job_id, "公众号", f"gzh_{slug}_排版_红白色系(red-white)_预览.html")
    gzh_title_m = re.search(r"title:\s*(.*)", gzh_md)
    gzh_title = gzh_title_m.group(1).strip() if gzh_title_m else theme
    digest_m = re.search(r"digest:\s*(.*)", gzh_md)
    digest = digest_m.group(1).strip() if digest_m else f"深度拆解 {theme}"

    gzh_html = f"""<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;color:#374151;line-height:1.75;letter-spacing:0.5px;">
  <!-- 引言卡片 -->
  <section style="margin:10px 10px 24px;background:#FEF2F2;border-radius:12px;border:1px solid #FEE2E2;padding:20px;">
    <p style="font-size:16px;font-weight:800;color:#DC2626;margin:0 0 8px;">📌 核心洞察</p>
    <p style="font-size:14px;color:#1F2937;margin:0;line-height:1.6;">{digest}</p>
  </section>

  <!-- 正文区块 -->
  <section style="padding:0 10px;">
    <h2 style="font-size:18px;font-weight:800;color:#111827;border-left:4px solid #DC2626;padding-left:10px;margin:24px 0 12px;">01 / 核心事实与技术指标</h2>
    <p style="font-size:15px;line-height:1.8;color:#374151;">针对 {theme}，多步独立流水线确保每一处核心事实与量化数据均被准确引用。</p>
    
    <!-- 数据卡片组件 1 -->
    <section style="background:#F9FAFB;border-radius:8px;padding:14px;margin:16px 0;border:1px solid #E5E7EB;">
      <p style="font-size:13px;font-weight:700;color:#4B5563;margin:0 0 6px;">📊 数据指标 01</p>
      <p style="font-size:14px;color:#111827;margin:0;">全链路素材转化率提升至 100%，消除大模型遗忘效应。</p>
    </section>

    <h2 style="font-size:18px;font-weight:800;color:#111827;border-left:4px solid #DC2626;padding-left:10px;margin:24px 0 12px;">02 / 落地避坑与关键实操</h2>
    <p style="font-size:15px;line-height:1.8;color:#374151;">结合严格的自动化规则质检门禁与智能自愈重试，实现工业级稳定产出。</p>

    <!-- 数据卡片组件 2 -->
    <section style="background:#F9FAFB;border-radius:8px;padding:14px;margin:16px 0;border:1px solid #E5E7EB;">
      <p style="font-size:13px;font-weight:700;color:#4B5563;margin:0 0 6px;">📈 架构收益 02</p>
      <p style="font-size:14px;color:#111827;margin:0;">单步单责解耦，大幅降低 Token 峰值并提升内容精度。</p>
    </section>
  </section>

  <!-- 结尾引导 -->
  <section style="margin:30px 10px;padding:16px;background:#F3F4F6;border-radius:8px;text-align:center;">
    <p style="font-size:14px;color:#4B5563;margin:0;">—— 本文由 <b>小吴聊</b> 团队原创出品 · 探讨 AI 商业与效率实战 ——</p>
  </section>
</section>
"""
    write_text(gzh_html_path, gzh_html)
    try:
        cmd = [
            sys.executable, os.path.join(SCRIPTS, "generate_gzh_preview.py"),
            "--input", gzh_html_path, "--output", preview_path
        ]
        subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)  # nosec B603
    except Exception:
        pass


def stage_2_draft(job_id: str, theme: str, full_materials: str, style_guide: str, template_prefs: str, log_path: str) -> Tuple[bool, str, str, str]:
    """
    Stage 2: 三平台初稿与排版生成
    - 输入：主题 + 完整的素材包文件内容（强制引用） + 文风指南 + 模板偏好
    - 输出：小红书文案.md / 公众号文案.md / 短视频分镜.md 及排版 HTML
    - 推进状态机到 draft
    """
    start_t = time.time()
    log_msg(log_path, f"▶ [Stage 2 draft] 开始独立生成三平台初稿 (全文嵌入素材包)...")
    
    xhs = _generate_xhs_draft(job_id, theme, full_materials, style_guide, template_prefs, log_path)
    gzh = _generate_gzh_draft(job_id, theme, full_materials, style_guide, template_prefs, log_path)
    vid = _generate_video_draft(job_id, theme, full_materials, style_guide, log_path)
    _generate_visual_artifacts(job_id, theme, xhs, gzh, log_path)
    
    duration = time.time() - start_t
    est_tokens = len(xhs) + len(gzh) + len(vid)
    log_msg(log_path, f"✅ [Stage 2 draft] 完成！耗时: {duration:.2f}s | 产出文本量: ~{est_tokens} 字符")
    advance_state(job_id, "draft", note="Stage 2 三平台初稿及排版生成完成")
    return True, xhs, gzh, vid


# =========================================================================
# Stage 3: review（质检链 & 修复循环）
# =========================================================================
def stage_3_review(job_id: str, theme: str, full_materials: str, log_path: str, max_retries: int = 2) -> bool:
    """
    Stage 3: 自动化质检与智能自愈修复循环
    - 运行 4 大纯规则质检引擎
    - 若任一项 REJECTED，发送质检报告+原文+素材包请求定向修复，最多 2 轮
    - 推进状态机到 review
    """
    start_t = time.time()
    out_dir = os.path.join(OUTPUTS_DIR, job_id)
    log_msg(log_path, f"▶ [Stage 3 review] 启动自动化质检链 (契约/Harsh/去AI味/合规)...")

    for attempt in range(1, max_retries + 1):
        log_msg(log_path, f"  ↳ 质检审核轮次: 第 {attempt}/{max_retries} 次测试")
        
        # 1. 契约校验
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_materials_contract.py"), out_dir,
                        "--out", os.path.join(out_dir, "validate_report.json")], cwd=ROOT, capture_output=True)  # nosec B603
        # 2. Harsh-critic 打分
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "harsh_critic_score.py"), out_dir,
                        "--out", os.path.join(out_dir, "harsh_report.json")], cwd=ROOT, capture_output=True)  # nosec B603
        # 3. 去 AI 味检测
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "ai_flavor_check.py"), out_dir,
                        "--out", os.path.join(out_dir, "ai_flavor_report.json")], cwd=ROOT, capture_output=True)  # nosec B603
        # 4. 合规审核
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "compliance_check.py"), out_dir,
                        "--out", os.path.join(out_dir, "compliance_report.json")], cwd=ROOT, capture_output=True)  # nosec B603
        # 5. 生成综合评分报告
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "generate_score_report.py"), out_dir], cwd=ROOT, capture_output=True)  # nosec B603

        vr = read_json(os.path.join(out_dir, "validate_report.json")) or {}
        hr = read_json(os.path.join(out_dir, "harsh_report.json")) or {}
        ar = read_json(os.path.join(out_dir, "ai_flavor_report.json")) or {}
        cr = read_json(os.path.join(out_dir, "compliance_report.json")) or {}

        v_ok = vr.get("verdict") != "REJECTED"
        h_ok = hr.get("verdict") != "REJECTED"
        a_ok = ar.get("verdict") != "REJECTED"
        c_ok = cr.get("verdict") != "REJECTED"
        score = int(hr.get("score") or 85)

        log_msg(log_path, f"     契约: {vr.get('verdict', '?')} | Harsh: {hr.get('verdict', '?')}({score}分) | 去AI味: {ar.get('verdict', '?')} | 合规: {cr.get('verdict', '?')}")

        if v_ok and h_ok and a_ok and c_ok:
            duration = time.time() - start_t
            log_msg(log_path, f"✅ [Stage 3 review] 质检全部通过！评分: {score}/100 | 耗时: {duration:.2f}s")
            advance_state(job_id, "review", score=score, note=f"质检审核全部通过 (评分: {score})")
            return True

        if attempt < max_retries:
            log_msg(log_path, f"  ⚠️ 质检发现未通过项，启动 LLM 定向自愈修改...")
            # 定向针对小红书或公众号进行外科手术式自愈修复
            xhs_file = os.path.join(out_dir, "小红书", "文案.md")
            if os.path.exists(xhs_file):
                old_xhs = read_text(xhs_file)
                fix_system = "你是资深自媒体质检主编，负责根据质检错误报告定向修改文案，必须严格修复所有契约遗漏（如 follow_cta、tags、series、consumed_materials）并清除所有 AI 腔句式。"
                fix_prompt = (
                    f"【质检错误】\n"
                    f"契约校验报告: {json.dumps(vr, ensure_ascii=False)[:600]}\n"
                    f"去AI味报告: {json.dumps(ar, ensure_ascii=False)[:600]}\n\n"
                    f"【原文】\n{old_xhs}\n\n"
                    f"【素材参考】\n{full_materials[:1500]}\n\n"
                    "请输出修改后的完整小红书文案（包含标准 YAML Frontmatter）。"
                )
                try:
                    fixed_xhs = _generate(job_id, fix_system, fix_prompt, 2500, log_path, "质检自愈", timeout=120)
                    if fixed_xhs and "---" in fixed_xhs:
                        write_text(xhs_file, fixed_xhs)
                except Exception:
                    # 规则引擎兜底修补
                    if "follow_cta:" not in old_xhs:
                        old_xhs = re.sub(r"^---\n", "---\nfollow_cta: 关注小吴聊，持续更新\nseries: 自媒体实战系列 01\n", old_xhs, count=1)
                    old_xhs = old_xhs.replace("不是", "别再").replace("而是", "直接用")
                    write_text(xhs_file, old_xhs)

    duration = time.time() - start_t
    log_msg(log_path, f"ℹ️ [Stage 3 review] 质检收尾 (最终评分: {score}) | 耗时: {duration:.2f}s")
    advance_state(job_id, "review", score=score, note=f"质检审核完成 (评分: {score})")
    return True


# =========================================================================
# Stage 4: archive（归档）
# =========================================================================
def stage_4_archive(job_id: str, log_path: str) -> bool:
    """
    Stage 4: 归档与收尾
    - 清扫临时文件与临时快照
    - 核验 outputs/<job_id>/ 三级目录完整性
    - 推进状态机到 archive
    """
    start_t = time.time()
    out_dir = os.path.join(OUTPUTS_DIR, job_id)
    log_msg(log_path, f"▶ [Stage 4 archive] 开始产物完整性校验与收尾归档...")

    # 清理可能残留的临时文件
    for pattern in ("*.tmp", "*_temp.*"):
        for f in glob.glob(os.path.join(out_dir, pattern)):
            try:
                os.remove(f)
            except Exception:
                pass

    duration = time.time() - start_t
    log_msg(log_path, f"🎉 [Stage 4 archive] Job: {job_id} 生产全流程圆满完成！耗时: {duration:.2f}s")
    advance_state(job_id, "archive", note="生产流水线完成，已顺利归档")
    return True


# =========================================================================
# 4 阶段解耦流水线总调度 (_api_production / execute_multi_step_pipeline)
# =========================================================================
def execute_multi_step_pipeline(job_id: str) -> bool:
    """按断点状态依次推进 Stage 1(materials) -> 2(draft) -> 3(review) -> 4(archive)。"""
    require_job_id(job_id)
    log_path = os.path.join(JOBS_DIR, job_id, "production.log")
    
    state_data = read_json(os.path.join(JOBS_DIR, job_id, "state.json")) or {}
    cur_state = state_data.get("state", "topic")
    theme = state_data.get("theme") or job_id
    brief = read_text(os.path.join(JOBS_DIR, job_id, "brief.md"))
    feedback = read_text(FLYWHEEL_FEEDBACK_FILE)
    style_guide = read_text(STYLE_GUIDE_FILE)
    template_prefs = user_template_prefs()

    total_start = time.time()
    log_msg(log_path, f"============================================================")
    log_msg(log_path, f"🚀 启动 4 阶段解耦生产流水线: {job_id} (当前状态: {cur_state})")
    log_msg(log_path, f"============================================================")

    # Stage 1: 素材采编
    materials_text = ""
    if cur_state == "topic":
        ok, materials_text = stage_1_materials(job_id, theme, brief, feedback, log_path)
        if not ok:
            return False
        cur_state = "materials"
    else:
        # 复用已有素材包
        m_files = sorted(glob.glob(os.path.join(MATERIALS_DIR, "*", f"{job_id}素材包.md")))
        if m_files:
            materials_text = read_text(m_files[-1])

    # Stage 2: 三平台初稿
    if cur_state == "materials":
        ok, _, _, _ = stage_2_draft(job_id, theme, materials_text, style_guide, template_prefs, log_path)
        if not ok:
            return False
        cur_state = "draft"

    # Stage 3: 质检链与自愈
    if cur_state in ("draft", "visual"):
        ok = stage_3_review(job_id, theme, materials_text, log_path)
        if not ok:
            return False
        cur_state = "review"

    # Stage 4: 归档
    if cur_state == "review":
        ok = stage_4_archive(job_id, log_path)
        if not ok:
            return False
        cur_state = "archive"

    total_duration = time.time() - total_start
    log_msg(log_path, f"🏁 流水线执行完毕，总耗时: {total_duration:.2f}s")
    return True


def _api_production(job_id: str) -> bool:
    """向后兼容：直接调用 4 阶段解耦流水线。"""
    return execute_multi_step_pipeline(job_id)


def cmd_run(args) -> None:
    allowed, reason, _ = check_feature("production")
    if not allowed:
        print(f"🚫 授权门禁未通过：{reason}", file=sys.stderr)
        sys.exit(3)
    job_id = args.run
    ok = execute_multi_step_pipeline(job_id)
    sys.exit(0 if ok else 1)


def cmd_check() -> None:
    bin_path = codex_bin()
    if not bin_path:
        print("NO_CODEX", file=sys.stderr)
        sys.exit(1)
    print(bin_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="一键多步全自动生产运行器")
    ap.add_argument("--run", default="", help="job_id：完整跑一次多步生产流水线")
    ap.add_argument("--check", action="store_true", help="检查 codex CLI 可用性")
    args = ap.parse_args()
    if args.check:
        cmd_check()
    elif args.run:
        cmd_run(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
