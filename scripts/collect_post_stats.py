#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布数据回收器（Phase 3 · 数据闭环入口）
=========================================
发布 48h 后回收各平台数据，落盘 jobs/<job_id>/publish_log.json，
并按爆款阈值判定是否触发解剖反哺。

用法（手机端看数后回填）：
    python3 scripts/collect_post_stats.py <job_id> --platform 小红书 \
        --reads 5200 --likes 260 --collects 80 --comments 15 --url "笔记链接"

    # 仅查看某 Job 的回收记录
    python3 scripts/collect_post_stats.py <job_id> --show

爆款阈值（可用参数覆盖）：阅读 ≥ 5000 或 点赞 ≥ 200
说明：自动抓取为后续迭代（公众号 datacube 需开通权限、小红书无官方 API），当前以人工回填为准——
真实数据 > 自动但不可靠的抓取。
"""
import argparse
import json
import os
import sys
from datetime import datetime

JOBS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs"))


def log_path(job_id):
    return os.path.join(JOBS_DIR, job_id, "publish_log.json")


def load_log(job_id):
    p = log_path(job_id)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"job_id": job_id, "records": []}


def save_log(job_id, data):
    os.makedirs(os.path.dirname(log_path(job_id)), exist_ok=True)
    with open(log_path(job_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_hit(rec, reads_th, likes_th):
    return (rec.get("reads", 0) >= reads_th) or (rec.get("likes", 0) >= likes_th)


def engagement_rate(rec):
    reads = rec.get("reads", 0)
    if reads <= 0:
        return 0.0
    return (rec.get("likes", 0) + rec.get("collects", 0) + rec.get("comments", 0)) / reads


def main():
    ap = argparse.ArgumentParser(description="发布数据回收器")
    ap.add_argument("job_id")
    ap.add_argument("--platform", choices=["小红书", "公众号", "短视频"])
    ap.add_argument("--reads", type=int, default=0, help="阅读/播放量")
    ap.add_argument("--likes", type=int, default=0)
    ap.add_argument("--collects", type=int, default=0, help="收藏数")
    ap.add_argument("--comments", type=int, default=0)
    ap.add_argument("--url", default="", help="作品链接（可选）")
    ap.add_argument("--reads-threshold", type=int, default=5000)
    ap.add_argument("--likes-threshold", type=int, default=200)
    ap.add_argument("--show", action="store_true", help="只查看记录")
    args = ap.parse_args()

    data = load_log(args.job_id)

    if args.show:
        if not data["records"]:
            print(f"（{args.job_id} 暂无回收记录）")
            return
        print(f"📊 {args.job_id} 数据回收记录：")
        for r in data["records"]:
            hit = "🔥爆款" if r.get("hit") else "  "
            print(f"  {hit} [{r['platform']}] {r['collected_at']}  阅读 {r['reads']} / 赞 {r['likes']} / 藏 {r['collects']} / 评 {r['comments']}  互动率 {r.get('engagement', 0):.1%}")
        return

    if not args.platform:
        print("❌ 缺少 --platform（或加 --show 只查看）")
        sys.exit(1)

    rec = {
        "platform": args.platform,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reads": args.reads, "likes": args.likes,
        "collects": args.collects, "comments": args.comments,
        "url": args.url,
    }
    rec["engagement"] = round(engagement_rate(rec), 4)
    rec["hit"] = is_hit(rec, args.reads_threshold, args.likes_threshold)
    data["records"].append(rec)
    save_log(args.job_id, data)

    print(f"✅ 已记录 [{args.platform}] 阅读 {args.reads} / 赞 {args.likes} / 藏 {args.collects} / 评 {args.comments}（互动率 {rec['engagement']:.1%}）")
    print(f"   落盘：{log_path(args.job_id)}")

    if rec["hit"]:
        print(f"\n🔥 达到爆款阈值（阅读≥{args.reads_threshold} 或 赞≥{args.likes_threshold}）！")
        print("   建议立即执行解剖反哺：")
        print(f"   python3 scripts/init_hit_anatomy.py {args.job_id}")
    else:
        print(f"\n（未达爆款阈值：阅读≥{args.reads_threshold} 或 赞≥{args.likes_threshold}，继续观察）")

    # 若三平台都有记录，提示推进 recycle 状态
    plats = {r["platform"] for r in data["records"]}
    if len(plats) >= 1:
        print(f"\n提示：数据回收后可推进 Job 状态 → python3 scripts/job_state.py set {args.job_id} recycle")


if __name__ == "__main__":
    main()
