#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书发布素材包生成器（人工发布模式 · 风控合规）
==================================================
把 outputs/<job_id>/小红书/ 下的成品整理成“小红书发布素材包”文件夹，
内容：图片 + 文案.md + 发布说明.md（标题/正文/标签/手动上传步骤/风控提醒）。

小红书账号存在风控要求，禁止任何自动化工具写入/发布；
本脚本只做本地文件整理，不打开浏览器、不触碰创作者后台。

用法：
    python3 scripts/prepare_xhs_material.py <job_id>

输出：
    outputs/<job_id>/小红书发布素材包/
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", os.path.join(ROOT, "outputs"))
JOBS_DIR = os.environ.get("JOBS_DIR", os.path.join(ROOT, "jobs"))
PACK_DIR_NAME = "小红书发布素材包"


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


def extract_note_body(md):
    """提取“## 📝 笔记正文”后的可复制正文（去掉数据来源与标签行）。"""
    body = md.split("## 📝 笔记正文：", 1)[1] if "## 📝 笔记正文：" in md else md
    lines = []
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("数据来源") or s.startswith("#"):
            break
        lines.append(ln)
    return "\n".join(lines).strip()


def extract_tags(md):
    tags = [t for t in re.findall(r"#[\w\u4e00-\u9fa5]+", md)
            if not re.fullmatch(r"#\d+", t)]
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def pick_title(job_id, state, log, outputs_dir=OUTPUTS_DIR, jobs_dir=JOBS_DIR):
    if log.get("title"):
        return log["title"]
    md = read_text(os.path.join(outputs_dir, job_id, "小红书", "文案.md"))
    m = re.search(r"选项 1[（(]?[^）)]*[）)]?\s*[:：]\s*\*\*(.+?)\*\*", md)
    if m:
        return m.group(1).strip()
    return state.get("theme") or job_id


def prepare(job_id, outputs_dir=OUTPUTS_DIR, jobs_dir=JOBS_DIR):
    """生成小红书发布素材包，返回目标目录。缺产出时抛 ValueError。"""
    src = os.path.join(outputs_dir, job_id, "小红书")
    if not os.path.isdir(src):
        raise ValueError(f"未找到小红书产出目录：{src}")

    images = sorted(
        p for p in glob.glob(os.path.join(src, "*.png"))
        + glob.glob(os.path.join(src, "*.jpg"))
        + glob.glob(os.path.join(src, "*.jpeg"))
        + glob.glob(os.path.join(src, "*.webp")))
    if not images:
        raise ValueError(f"小红书目录下没有图片（{src}）")

    state = read_json(os.path.join(jobs_dir, job_id, "state.json")) or {}
    log = read_json(os.path.join(jobs_dir, job_id, "publish_log.json")) or {}
    md_path = os.path.join(src, "文案.md")
    md = read_text(md_path)
    title = pick_title(job_id, state, log, outputs_dir, jobs_dir)
    body = extract_note_body(md)
    tags = extract_tags(md)

    dest = os.path.join(outputs_dir, job_id, PACK_DIR_NAME)
    os.makedirs(dest, exist_ok=True)
    # 幂等覆盖：先清掉旧素材包里的说明文件与拷贝，再重新生成
    for old in glob.glob(os.path.join(dest, "*")):
        try:
            os.remove(old)
        except OSError:
            pass

    for img in images:
        shutil.copy2(img, os.path.join(dest, os.path.basename(img)))
    if os.path.exists(md_path):
        shutil.copy2(md_path, os.path.join(dest, "文案.md"))

    guide = "\n".join([
        "# 📕 小红书发布素材包（人工发布）",
        "",
        "> 本素材包用于人工上传，禁止使用任何自动化工具写入或发布。",
        "",
        "## 一、标题（直接复制）",
        title,
        "",
        "## 二、正文（直接复制）",
        body,
        "",
        "## 三、标签",
        " ".join(tags) if tags else "（文案中未发现标签，请自行补充 5-8 个）",
        "",
        "## 四、手动发布步骤",
        "### 手机端（推荐）",
        "1. 打开小红书 App → 底部「+」→ 选择「上传图文」；",
        "2. 从本素材包选择图片，按顺序上传（建议 4-7 张 3:4 卡片）；",
        "3. 粘贴标题与正文，补充话题标签；",
        "4. 检查封面与预览 → 点击「发布」。",
        "",
        "### 网页端",
        "1. 登录创作者中心 → 「内容发布」→「上传图文」；",
        "2. 上传图片、粘贴标题/正文/标签；",
        "3. 预览确认后手动点击「发布」。",
        "",
        "## 五、风控提醒",
        "- 平台已提示禁止自动化工具写入：请全程手动完成上传与发布；",
        "- 发布后回到运营中心「数据」页回填阅读/赞/藏/评，或先点「标记已手动发布」。",
        "",
    ])
    with open(os.path.join(dest, "发布说明.md"), "w", encoding="utf-8") as f:
        f.write(guide)

    return dest, {"images": len(images), "title": title, "tags": tags}


def main():
    ap = argparse.ArgumentParser(description="小红书发布素材包生成器")
    ap.add_argument("job_id", help="任务 ID（YYYY-MM-DD_主题名）")
    args = ap.parse_args()

    job_id = args.job_id.strip()
    try:
        dest, info = prepare(job_id)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"✅ 小红书发布素材包已生成：{dest}")
    print(f"   图片 {info['images']} 张 ｜ 文案.md ｜ 发布说明.md")
    print(f"   标题：{info['title']}")
    print(f"   标签：{' '.join(info['tags']) if info['tags'] else '（未识别）'}")


if __name__ == "__main__":
    main()
