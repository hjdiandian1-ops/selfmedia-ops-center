#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爆款解剖骨架生成器（Phase 3 · 范文库反哺）
===========================================
从 jobs/<job_id>/publish_log.json 与 outputs/<job_id>/ 的成稿 frontmatter
自动预填元数据，生成 skills/范文库/<job_id>.md 解剖骨架。
解剖分析部分由 LLM（资深校对排版/总编）逐段填写。

用法：
    python3 scripts/init_hit_anatomy.py <job_id>
    python3 scripts/init_hit_anatomy.py <job_id> --platform 小红书   # 只解剖指定平台
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.path.join(ROOT, "jobs")
LIB_DIR = os.path.join(ROOT, "skills", "范文库")


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    data = {}
    for line in m.group(1).splitlines():
        km = re.match(r"(\w+)\s*:\s*(.*)", line.strip())
        if km:
            data[km.group(1)] = km.group(2).strip()
    return data


def first_title(text):
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("# ") and not ln.startswith("##"):
            return ln[2:].strip()
    return "（未识别）"


def main():
    ap = argparse.ArgumentParser(description="爆款解剖骨架生成器")
    ap.add_argument("job_id")
    ap.add_argument("--platform", choices=["小红书", "公众号", "短视频"])
    args = ap.parse_args()

    # 1. 发布数据
    log_file = os.path.join(JOBS_DIR, args.job_id, "publish_log.json")
    records = []
    if os.path.exists(log_file):
        records = read_json(log_file).get("records", [])
    hits = [r for r in records if r.get("hit")]
    if not hits:
        print("⚠️ 该 Job 暂无达爆款阈值的平台记录（hit=true）。")
        print("   若确认要解剖（如手动判定高质量），请先在 publish_log.json 将对应记录 hit 置为 true。")
        sys.exit(1)

    # 2. 成稿元数据
    out_dir = os.path.join(ROOT, "outputs", args.job_id)
    drafts = {}
    for md in glob.glob(os.path.join(out_dir, "*", "*.md")):
        plat = os.path.basename(os.path.dirname(md))
        if args.platform and plat != args.platform:
            continue
        with open(md, "r", encoding="utf-8") as f:
            text = f.read()
        drafts[plat] = {"path": md, "fm": parse_frontmatter(text), "title": first_title(text)}

    if not drafts:
        print(f"❌ 未找到成稿：{out_dir}")
        sys.exit(1)

    # 3. 生成骨架
    os.makedirs(LIB_DIR, exist_ok=True)
    out_path = os.path.join(LIB_DIR, f"{args.job_id}.md")
    if os.path.exists(out_path):
        print(f"⚠️ 解剖文件已存在：{out_path}（如需重建请先删除）")
        sys.exit(1)

    lines = [
        f"# 🔥 爆款解剖：《{next(iter(drafts.values()))['title']}》",
        "",
        f"> 入库时间：{datetime.now().strftime('%Y-%m-%d')} ｜ Job：`{args.job_id}`",
        "> 状态：⏳ 骨架已生成，待 LLM 完成解剖分析（见文末待填区）",
        "",
        "---",
        "",
        "## 一、 元数据（自动预填）",
        "",
        "### 数据表现（publish_log）",
        "| 平台 | 阅读 | 赞 | 藏 | 评 | 互动率 | 采集时间 |",
        "|---|---|---|---|---|---|---|"]
    for r in hits:
        lines.append(f"| {r['platform']} | {r['reads']} | {r['likes']} | {r['collects']} | {r['comments']} | {r.get('engagement', 0):.1%} | {r['collected_at']} |")
    lines += ["", "### 成稿契约（frontmatter）",
              "| 平台 | 标题公式 | 消费素材 | 成稿路径 |",
              "|---|---|---|---|"]
    for plat, d in drafts.items():
        rel = os.path.relpath(d["path"], ROOT)
        lines.append(f"| {plat} | {d['fm'].get('hook_formula', '—')} | {d['fm'].get('consumed_materials', '—')} | `{rel}` |")

    lines += [
        "",
        "---",
        "",
        "## 二、 标题解剖（待填）",
        "> 命中哪个公式/心理触发器？数字、冲突、身份代入分别起了什么作用？",
        "",
        "## 三、 Hook 解剖（待填）",
        "> 开篇用了素材包哪条素材？制造了什么悬念？可信度如何建立？",
        "",
        "## 四、 结构解剖（待填）",
        "> 段落级标注：每段的功能（钩子/数据/转折/金句/CTA），为什么这样排布？",
        "",
        "## 五、 可复制规则（待填，1-3 条）",
        "> 可迁移到下一篇的写作规则。经用户确认后回写 personal-style-guide.md。",
        "",
        "1. ",
        "",
        "---",
        "",
        "*本文件由 init_hit_anatomy.py 生成骨架，解剖分析由资深校对排版完成。*",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ 解剖骨架已生成：{out_path}")
    print("   下一步：由资深校对排版逐段完成解剖，提炼的可复制规则经用户确认后回写 style-guide。")


if __name__ == "__main__":
    main()
