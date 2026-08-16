#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爆款 AI 拆解运行器
==================
调 codex CLI 按 skills/viral-breakdown-skill/SKILL.md 拆解一条爆款，
把结果 JSON 落盘 data/flywheel/breakdowns/<id>.json 并回写 viral_videos.json。

用法：
    python3 scripts/run_viral_analysis.py --id v_xxx --title "标题" [--content "正文/逐字稿"] [--link URL] [--platform 小红书]
"""
import argparse
import json
import os
import subprocess  # nosec B404  # 固定命令列表 + 无 shell
import sys
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VIRAL_FILE = os.path.join(ROOT, "data", "flywheel", "viral_videos.json")
BREAKDOWN_DIR = os.path.join(ROOT, "data", "flywheel", "breakdowns")
SKILL_FILE = os.path.join(ROOT, "skills", "viral-breakdown-skill", "SKILL.md")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_production import codex_bin  # noqa: E402
from license.license_gate import check_feature  # noqa: E402
import llm_engine  # noqa: E402


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def build_prompt(vid, title, content, link, platform):
    skill = read_text(SKILL_FILE)
    return "\n".join([
        "请严格按下面的 Skill 拆解一条爆款内容。",
        "",
        skill,
        "",
        "## 本次拆解对象",
        f"- viral_id：{vid}",
        f"- 平台：{platform or '未知'}",
        f"- 标题：{title}",
        f"- 链接：{link or '无'}",
        f"- 原文/逐字稿：\n{content or '（未提供，请基于标题拆解并注明）'}",
        "",
        "拆解完成后把 JSON 与 Markdown 写到指定路径，然后输出一段 ≤200 字可复用创作指令。",
    ])


def update_record(vid, patch):
    data = read_text(VIRAL_FILE)
    if not data:
        return False
    store = json.loads(data)
    changed = False
    for v in store.get("videos", []):
        if v.get("id") == vid:
            v.update(patch)
            v["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            changed = True
            break
    if changed:
        store["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_json(VIRAL_FILE, store)
    return changed


def _finalize(vid):
    """读取拆解产物 JSON+MD 并回写记录。成功返回 True。"""
    json_path = os.path.join(BREAKDOWN_DIR, f"{vid}.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                bd = json.load(f)
            notes = read_text(os.path.join(BREAKDOWN_DIR, f"{vid}.md"))
            evidence = bd.get("evidence_level", "")
            notes_head = f"依据级别：{evidence}\n\n" if evidence else ""
            update_record(vid, {
                "status": "analyzed",
                "hook": bd.get("hook", ""),
                "structure": bd.get("structure", ""),
                "why_viral": bd.get("why_viral", ""),
                "formula": bd.get("formula", ""),
                "evidence_level": evidence,
                "notes": notes_head + (bd.get("summary") or "") + ("\n\n拆解报告：" + notes[:500] if notes else ""),
            })
            print(f"✅ 拆解完成：{json_path}")
            return True
        except Exception as e:
            update_record(vid, {"status": "tracked", "notes": f"AI 拆解输出解析失败: {e}"})
            print(f"❌ 拆解输出解析失败: {e}", file=sys.stderr)
            return False
    update_record(vid, {"status": "tracked", "notes": "AI 拆解未产出 JSON 文件，请查看日志"})
    print("❌ 未找到拆解 JSON 输出", file=sys.stderr)
    return False


def _api_breakdown(vid, title, content, link, platform):
    """API 模式拆解（无需 Codex）：生成 JSON + Markdown 落盘。"""
    system = (
        "你是爆款内容拆解分析师。严格按给定 JSON 结构输出，字段含义："
        "hook=前3秒钩子；structure=内容结构；why_viral=为什么火（依据平台推荐逻辑）；"
        "formula=可复用公式标签；evidence_level=title_only（仅标题）或 content（有正文）；"
        "summary=≤200字可复用创作指令。没有原文时禁止编造数据，必须标注推断置信度。"
    )
    user = (
        f"平台：{platform or '未知'}\n标题：{title}\n"
        f"链接：{link or '无'}\n原文/逐字稿：{content or '（未提供）'}\n\n"
        "输出 JSON：{\"hook\":\"\",\"structure\":\"\",\"why_viral\":\"\","
        "\"formula\":\"\",\"evidence_level\":\"\",\"summary\":\"\"}"
    )
    try:
        bd = llm_engine.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    except Exception as e:
        update_record(vid, {"status": "tracked", "notes": f"AI 拆解 API 失败: {e}"})
        print(f"❌ AI 拆解 API 失败: {e}", file=sys.stderr)
        return False
    if not isinstance(bd, dict):
        update_record(vid, {"status": "tracked", "notes": "AI 拆解 API 返回格式异常"})
        return False
    os.makedirs(BREAKDOWN_DIR, exist_ok=True)
    write_json(os.path.join(BREAKDOWN_DIR, f"{vid}.json"), bd)
    md = (f"# 拆解报告：{title}\n\n"
          f"- 平台：{platform or '未知'}\n- 依据级别：{bd.get('evidence_level', 'title_only')}\n\n"
          f"## 前3秒钩子\n{bd.get('hook', '')}\n\n## 结构\n{bd.get('structure', '')}\n\n"
          f"## 为什么火\n{bd.get('why_viral', '')}\n\n## 公式\n{bd.get('formula', '')}\n\n"
          f"## 可复用指令\n{bd.get('summary', '')}\n")
    with open(os.path.join(BREAKDOWN_DIR, f"{vid}.md"), "w", encoding="utf-8") as f:
        f.write(md)
    return True


def main():
    ap = argparse.ArgumentParser(description="爆款 AI 拆解运行器")
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--content", default="")
    ap.add_argument("--link", default="")
    ap.add_argument("--platform", default="小红书")
    args = ap.parse_args()

    allowed, reason, _ = check_feature("viral_breakdown", consume=True)
    if not allowed:
        update_record(args.id, {"status": "tracked", "notes": f"AI 拆解被授权门禁拦截：{reason}"})
        print(f"LICENSE_DENIED: {reason}", file=sys.stderr)
        sys.exit(3)

    bin_path = codex_bin()
    if not bin_path:
        print("ℹ️ 未找到 codex CLI，尝试 API 模式（需要 LLM_API_KEY）", file=sys.stderr)
        if _api_breakdown(args.id, args.title, args.content, args.link, args.platform):
            if _finalize(args.id):
                sys.exit(0)
        sys.exit(2)

    os.makedirs(BREAKDOWN_DIR, exist_ok=True)
    log_path = os.path.join(BREAKDOWN_DIR, f"{args.id}.log")
    prompt = build_prompt(args.id, args.title, args.content, args.link, args.platform)

    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n===== 拆解开始 {args.id} =====\n")
        proc = subprocess.Popen(  # nosec B603  # 固定 codex 命令 + 受控 viral_id
            [bin_path, "exec", "--approve-for-me", "-"],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            proc.communicate(input=prompt.encode("utf-8"), timeout=60 * 60 * 2)
        except subprocess.TimeoutExpired:
            proc.kill()
            update_record(args.id, {"status": "tracked", "notes": "AI 拆解超时（2h），已终止"})
            log.write("\n===== 拆解超时 =====\n")
            sys.exit(3)

    if _finalize(args.id):
        sys.exit(0)
    sys.exit(5)


if __name__ == "__main__":
    main()
