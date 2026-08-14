#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动发布记录器（小红书人工发布模式 · 数据闭环）
================================================
小红书改为人手发布后，发布动作不再由自动化脚本写入；
本脚本在人工发布完成后，向 jobs/<job_id>/publish_log.json 追加一条
`mode: manual` 的发布记录，保证 48h 回收检查与数据统计正常工作。

用法：
    python3 scripts/record_manual_publish.py <job_id> --platform 小红书 [--title "标题"] [--note "已手机端发布"]
"""
import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.environ.get("JOBS_DIR", os.path.join(ROOT, "jobs"))
PLATFORMS = ("小红书", "公众号", "短视频")


def load_log(job_id, jobs_dir=JOBS_DIR):
    p = os.path.join(jobs_dir, job_id, "publish_log.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"job_id": job_id, "records": [], "publish": []}


def save_log(job_id, data, jobs_dir=JOBS_DIR):
    p = os.path.join(jobs_dir, job_id, "publish_log.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def record(job_id, platform, title="", note="", jobs_dir=JOBS_DIR):
    """追加一条 mode=manual 的发布记录，返回 publish_log.json 路径。"""
    if not os.path.isdir(os.path.join(jobs_dir, job_id)):
        raise ValueError(f"任务不存在：{job_id}")
    if platform not in PLATFORMS:
        raise ValueError(f"平台不合法：{platform}")
    data = load_log(job_id, jobs_dir)
    data.setdefault("publish", [])
    data.setdefault("records", [])
    data.setdefault("platforms", [])
    if title:
        data["title"] = title
    if not data.get("title"):
        data["title"] = job_id
    data["published_at"] = data.get("published_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if platform not in data["platforms"]:
        data["platforms"].append(platform)
        data["platforms"] = sorted(data["platforms"])

    entry = {
        "platform": platform,
        "status": "success",
        "mode": "manual",
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if note:
        entry["note"] = note
    data["publish"].append(entry)

    p = save_log(job_id, data, jobs_dir)
    return p


def main():
    ap = argparse.ArgumentParser(description="手动发布记录器")
    ap.add_argument("job_id")
    ap.add_argument("--platform", required=True, choices=PLATFORMS)
    ap.add_argument("--title", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    try:
        p = record(args.job_id.strip(), args.platform, args.title, args.note)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"✅ 已记录手动发布：[{args.platform}] {args.job_id}")
    print(f"   落盘：{p}")
    data = load_log(args.job_id.strip())
    print(f"   发布动作总数：{len(data['publish'])} 次 ｜ 数据回填：{len(data['records'])} 条")


if __name__ == "__main__":
    main()
