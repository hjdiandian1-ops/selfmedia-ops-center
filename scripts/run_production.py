#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键全自动生产运行器
====================
把采纳后的 Job 交给本机 codex CLI，按「自媒体运营工厂」工作流完成
素材 → 初稿 → 视觉 → 质检 → 归档，每完成一个阶段推进 job_state.py。

用法：
    python3 scripts/run_production.py --run <job_id>   # 前台跑（服务端 Popen 托管）
    python3 scripts/run_production.py --check          # 检查 codex CLI 可用性

服务端负责队列与生命周期；本脚本只负责一次 Job 的完整生产。
"""
import argparse
import os
import shutil
import subprocess  # nosec B404  # 固定命令列表 + 无 shell
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.path.join(ROOT, "jobs")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license.license_gate import check_feature  # noqa: E402
import llm_engine  # noqa: E402

# codex CLI 解析链：环境变量 > PATH > ChatGPT App 内置
CODEX_CANDIDATES = (
    os.environ.get("CODEX_BIN", ""),
    shutil.which("codex") or "",
    "/Applications/ChatGPT.app/Contents/Resources/codex",
)


def codex_bin():
    for c in CODEX_CANDIDATES:
        if c and os.path.isfile(c):
            return c
    return None


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def build_prompt(job_id):
    state = {}
    try:
        import json
        with open(os.path.join(JOBS_DIR, job_id, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        pass  # nosec B110  # state 读取失败时回退到 job_id，属预期兜底
    theme = state.get("theme") or job_id
    brief = read_text(os.path.join(JOBS_DIR, job_id, "brief.md"))
    feedback = read_text(os.path.join(ROOT, "data", "flywheel", "pipeline_feedback.md"))
    return "\n".join([
        "你是「自媒体运营工厂」的生产执行器。请把下面的 Job 从素材一路生产到归档，不要中途停下来问问题。",
        "",
        f"Job ID：{job_id}",
        f"主题：{theme}",
        "期望平台：小红书（图文卡片 + 文案）+ 公众号（深度长文 + 排版 HTML）+ 短视频分镜脚本（可选，主题适合时）。",
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


def _api_production(job_id, prompt, log_path):
    """API 模式生产（无需 Codex，只需 LLM_API_KEY）。
    单轮生成素材包 + 三平台初稿并落盘，推进状态机到 draft。
    """
    system = (
        "你是「自媒体运营工厂」的生产执行器。根据用户提供的主题与工作流要求，一次性产出完整初稿，"
        "严格按 JSON 结构返回：materials=素材包 Markdown（含核心事实/数据/来源标注，禁止编造）；"
        "xhs={\"title\":\"小红书标题≤20字\",\"body\":\"小红书正文\"}；"
        "gzh=公众号长文 Markdown；video=短视频 120s 分镜脚本 Markdown。"
        "内容要硬核、有具体数字、无 AI 腔（不用“不是…而是…”“首先其次最后”等模板）。"
    )
    try:
        out = llm_engine.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ], max_tokens=8000)
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\n===== API 生产失败: {e} =====\n")
        print(f"❌ API 生产失败: {e}", file=sys.stderr)
        return False
    if not isinstance(out, dict):
        return False
    from datetime import datetime
    month = datetime.now().strftime("%Y-%m")
    materials = str(out.get("materials") or f"# {job_id} 素材包\n\n（未生成，主题见 brief）")
    mat_path = os.path.join(ROOT, "materials", month, f"{job_id}素材包.md")
    os.makedirs(os.path.dirname(mat_path), exist_ok=True)
    write_text(mat_path, materials)
    xhs = out.get("xhs") or {}
    gzh = str(out.get("gzh") or "# 公众号初稿\n\n（未生成）")
    video = str(out.get("video") or "# 短视频分镜脚本\n\n（未生成）")
    xhs_md = (f"---\ntitle: {xhs.get('title', '')}\nplatform: 小红书\n---\n\n{xhs.get('body', '')}"
              if isinstance(xhs, dict) else str(xhs))
    for sub, content in (("小红书", xhs_md), ("公众号", gzh), ("短视频", video)):
        d = os.path.join(ROOT, "outputs", job_id, sub)
        os.makedirs(d, exist_ok=True)
        name = "文案.md" if sub != "短视频" else "120s黄金分镜脚本.md"
        write_text(os.path.join(d, name), content)
    # 推进状态机：materials → draft
    for st, note in (("materials", "API 模式素材包已落盘"), ("draft", "API 模式三平台初稿已生成")):
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"),  # nosec B603  # job_id 已通过白名单校验
                        "set", job_id, st, "--note", note],
                       cwd=ROOT, capture_output=True, text=True, timeout=30)
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n===== API 生产完成 {job_id} =====\n")
    print(f"✅ API 生产完成：{job_id}（素材包 + 三平台初稿）")
    print("   ⚠️ 初稿质量需人工复核，随后运行质检链：python3 scripts/run_daily_pipeline.py --qa outputs/<job_id>/")
    return True


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def cmd_run(args):
    allowed, reason, _ = check_feature("production")
    if not allowed:
        print(f"🚫 授权门禁未通过：{reason}", file=sys.stderr)
        sys.exit(3)
    job_id = args.run
    log_path = os.path.join(JOBS_DIR, job_id, "production.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    prompt = build_prompt(job_id)
    bin_path = codex_bin()
    if not bin_path:
        print("ℹ️ 未找到 codex CLI，尝试 API 模式（需要 LLM_API_KEY）", file=sys.stderr)
        if _api_production(job_id, prompt, log_path):
            sys.exit(0)
        print("❌ 无法生产：既没有 codex CLI，也没有配置 LLM_API_KEY", file=sys.stderr)
        sys.exit(2)

    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n===== 生产开始 {job_id} =====\n")
        proc = subprocess.Popen(  # nosec B603  # 固定 codex 命令 + 受控 job_id
            [bin_path, "exec", "--approve-for-me", "-"],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            proc.communicate(input=prompt.encode("utf-8"), timeout=60 * 60 * 6)
        except subprocess.TimeoutExpired:
            proc.kill()
            log.write("\n===== 生产超时（6h），已终止 =====\n")
            sys.exit(3)
        log.write(f"\n===== 生产结束 {job_id} exit={proc.returncode} =====\n")
    sys.exit(proc.returncode or 0)


def cmd_check():
    bin_path = codex_bin()
    if not bin_path:
        print("NO_CODEX", file=sys.stderr)
        sys.exit(1)
    print(bin_path)


def main():
    ap = argparse.ArgumentParser(description="一键全自动生产运行器")
    ap.add_argument("--run", default="", help="job_id：完整跑一次生产")
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
