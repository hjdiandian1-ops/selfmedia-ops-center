#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据飞轮 → Agent SOP 自动升级器
===============================
读取经验库（lessons.json）与爆款公式（viral_videos.json），
按 apply_to 映射到对应 Agent SOP 文档，自动写入「经验补丁」章节并追加 changelog。

用法：
    python3 scripts/upgrade_agent_docs.py            # 升级 agents/ 全部 SOP
    python3 scripts/upgrade_agent_docs.py --json     # 只打印摘要
"""
import argparse
import glob
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_AGENTS_DIR = os.path.join(ROOT, "agents")
FLYWHEEL_DIR = os.path.join(ROOT, "data", "flywheel")

# apply_to 关键词 → Agent SOP 文件
ROLE_MAP = [
    ("小红书", "xhs-editor-小红书主编.md"),
    ("标题", "xhs-editor-小红书主编.md"),
    ("正文", "xhs-editor-小红书主编.md"),
    ("封面", "visual-director-美术总监.md"),
    ("视觉", "visual-director-美术总监.md"),
    ("卡片", "visual-director-美术总监.md"),
    ("公众号", "gzh-editor-公众号主编.md"),
    ("长文", "gzh-editor-公众号主编.md"),
    ("视频", "video-director-短视频导演.md"),
    ("脚本", "video-director-短视频导演.md"),
    ("分镜", "video-director-短视频导演.md"),
    ("口播", "video-director-短视频导演.md"),
    ("选题", "researcher-资深采编.md"),
    ("热点", "researcher-资深采编.md"),
    ("素材", "researcher-资深采编.md"),
    ("采编", "researcher-资深采编.md"),
    ("质检", "reviewer-资深校对排版.md"),
    ("校验", "reviewer-资深校对排版.md"),
    ("校对", "reviewer-资深校对排版.md"),
    ("发布", "distro-归档发布员.md"),
    ("回收", "distro-归档发布员.md"),
    ("归档", "distro-归档发布员.md"),
    ("节奏", "orchestrator-总编.md"),
    ("总编", "orchestrator-总编.md"),
]


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def role_files_for(apply_to):
    hits = []
    for kw, f in ROLE_MAP:
        if kw in (apply_to or ""):
            if f not in hits:
                hits.append(f)
    return hits


def bump_version(text):
    m = re.search(r"- version:\s*(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        return "1.0.1", text.replace("version:", "- version: 1.0.1", 1) if "- version:" in text else text
    maj, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    new_v = f"{maj}.{minor}.{patch + 1}"
    return new_v, re.sub(r"- version:\s*\d+\.\d+\.\d+", f"- version: {new_v}", text, count=1)


def apply_patch_to_doc(text, lessons_for_file, formulas, now):
    """替换/插入「经验补丁」章节 + 追加 changelog。"""
    new_v, text = bump_version(text)
    text = re.sub(r"- updated_at:\s*\S+", f"- updated_at: {now[:10]}", text, count=1)

    lesson_lines = "".join(
        f"- [经验] {l['title']}：{l['conclusion']}"
        f"（证据：{l.get('evidence') or '—'}；适用：{l.get('apply_to') or '—'}）\n"
        for l in lessons_for_file) or "- 暂无匹配经验\n"
    formula_lines = ""
    if formulas:
        formula_lines = "- 爆款公式参考：" + "、".join(
            f"{f}×{n}" for f, n in formulas.most_common(6)) + "\n"

    patch_section = (
        "## 🧬 经验补丁（数据飞轮自动升级）\n"
        f"> 更新时间：{now} ｜ 版本：{new_v}\n"
        + lesson_lines
        + formula_lines
    )

    # 替换旧补丁区
    if "## 🧬 经验补丁" in text:
        text = re.sub(
            r"## 🧬 经验补丁（数据飞轮自动升级）.*?(?=\n## |\Z)",
            patch_section.rstrip("\n") + "\n",
            text, count=1, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + patch_section.rstrip("\n") + "\n"

    # changelog 追加
    titles = "、".join(l["title"] for l in lessons_for_file[:3]) or "无新经验"
    entry = f"- {now[:10]} v{new_v} 数据飞轮自动升级：应用 {len(lessons_for_file)} 条经验（{titles}）"
    if "## Changelog" in text:
        text = re.sub(
            r"(## Changelog\n)",
            r"\1" + entry + "\n",
            text, count=1)
    else:
        text = text.rstrip() + "\n\n## Changelog\n" + entry + "\n"
    return text


def _patch_unchanged(text, lessons_for_file, formulas):
    """补丁区已有内容与本次完全相同 → 无需升级。"""
    m = re.search(r"## 🧬 经验补丁（数据飞轮自动升级）(.*?)(?=\n## |\Z)", text, re.S)
    if not m:
        return False
    existing = {l.strip() for l in m.group(1).splitlines() if l.strip().startswith("- [经验]")}
    expected = {
        f"- [经验] {l['title']}：{l['conclusion']}"
        f"（证据：{l.get('evidence') or '—'}；适用：{l.get('apply_to') or '—'}）"
        for l in lessons_for_file
    }
    has_formula = "爆款公式参考" in m.group(1)
    return existing == expected and bool(formulas) == has_formula


def upgrade_agents(agents_dir=DEFAULT_AGENTS_DIR, flywheel_dir=FLYWHEEL_DIR):
    lessons_path = os.path.join(flywheel_dir, "lessons.json")
    store = read_json(lessons_path) or {"lessons": []}
    lessons = store.get("lessons", [])
    meta_changed = False
    for l in lessons:
        if not l.get("id"):
            l["id"] = f"l_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
            meta_changed = True
    if meta_changed:
        write_json(lessons_path, store)
    videos = (read_json(os.path.join(flywheel_dir, "viral_videos.json")) or {}).get("videos", [])
    pending_ids = {l.get("id") for l in lessons if l.get("id") and not l.get("applied")}
    formulas = Counter()
    for v in videos:
        if v.get("status") in ("analyzed", "applied"):
            for f in re.split(r"[、,，/]", v.get("formula") or ""):
                f = f.strip()
                if f:
                    formulas[f] += 1

    results = []
    applied_ids = set()
    for path in sorted(glob.glob(os.path.join(agents_dir, "*.md"))):
        fname = os.path.basename(path)
        lessons_for_file = []
        for l in lessons:
            if fname in role_files_for(l.get("apply_to", "")):
                lessons_for_file.append(l)
        if not lessons_for_file and fname != "orchestrator-总编.md":
            # 未匹配的经验只进总编兜底
            pass
        text = read_text(path)
        if not text:
            continue
        has_section = "## 🧬 经验补丁" in text
        if has_section and _patch_unchanged(text, lessons_for_file, formulas):
            # 补丁区已包含这些经验（此前已写入）→ 视为已应用，标记状态并跳过升级
            applied_ids.update(l["id"] for l in lessons_for_file if l.get("id") in pending_ids)
            continue  # 无新经验/公式，不重复升版本
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_text = apply_patch_to_doc(text, lessons_for_file, formulas, now)
        write_text(path, new_text)
        applied_ids.update(l["id"] for l in lessons_for_file if l.get("id") in pending_ids)
        results.append({
            "file": fname,
            "version": re.search(r"- version:\s*(\S+)", new_text).group(1),
            "patches": len(lessons_for_file),
            "formulas": len(formulas),
        })

    # 本次已写入 SOP 的经验标记为「已应用」，让 KPI 与真实状态一致
    if applied_ids:
        store = read_json(lessons_path) or {"lessons": []}
        changed = False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for l in store.get("lessons", []):
            if l.get("id") in applied_ids and not l.get("applied"):
                l["applied"] = True
                l["updated_at"] = now_str
                changed = True
        if changed:
            store["updated_at"] = now_str
            write_json(lessons_path, store)

    return {"ok": True, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agents": results, "applied_lessons": len(applied_ids)}


def main():
    ap = argparse.ArgumentParser(description="数据飞轮 → Agent SOP 自动升级器")
    ap.add_argument("--agents-dir", default=DEFAULT_AGENTS_DIR)
    ap.add_argument("--flywheel-dir", default=FLYWHEEL_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = upgrade_agents(args.agents_dir, args.flywheel_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for a in result["agents"]:
            print(f"✅ {a['file']} → v{a['version']}（经验 {a['patches']} 条 / 公式 {a['formulas']} 个）")


if __name__ == "__main__":
    main()
