#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三平台爆款 Top5 批量拆解器
==========================
读取 data/flywheel/platform_virals.json 当日榜单，每平台按排名取前 5，
串行调用 run_viral_analysis.py（codex CLI）自动拆解；单条失败不阻塞其余，
条间默认间隔 10 秒限流；进度实时写入 data/flywheel/breakdown_batch.json。

用法：
    python3 scripts/run_viral_breakdown_daily.py            # 拆解今日 Top5×3
    python3 scripts/run_viral_breakdown_daily.py --dry-run  # 只打印将拆解队列
    python3 scripts/run_viral_breakdown_daily.py --json --per-platform 5
"""
import argparse
import json
import os
import subprocess  # nosec B404  # 固定命令列表 + 无 shell
import sys
import time
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PLATFORM_VIRALS_FILE = os.path.join(ROOT, "data", "flywheel", "platform_virals.json")
VIRAL_FILE = os.path.join(ROOT, "data", "flywheel", "viral_videos.json")
STATUS_FILE = os.path.join(ROOT, "data", "flywheel", "breakdown_batch.json")
RUN_VIRAL_ANALYSIS = os.path.join(ROOT, "scripts", "run_viral_analysis.py")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_production import codex_bin  # noqa: E402


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


def update_record(vid, patch):
    data = read_json(VIRAL_FILE)
    if not data:
        return
    for v in data.get("videos", []):
        if v.get("id") == vid:
            v.update(patch)
            v["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_json(VIRAL_FILE, data)


def select_queue(store, date=None, per_platform=5, limit=15):
    """从当日榜单选待拆解队列：[{platform, viral_id, title, link}]。"""
    date = date or datetime.now().strftime("%Y-%m-%d")
    day = (store.get("days") or {}).get(date, {})
    videos = (read_json(VIRAL_FILE) or {}).get("videos", [])
    by_id = {v["id"]: v for v in videos}
    queue = []
    for platform in ("小红书", "抖音", "公众号"):
        items = (day.get(platform) or [])[:per_platform]
        for it in items:
            vid = it.get("viral_id")
            rec = by_id.get(vid) or {}
            if rec.get("status") in ("analyzing", "analyzed", "applied"):
                continue
            queue.append({
                "platform": platform,
                "viral_id": vid,
                "title": it.get("title") or rec.get("title", ""),
                "link": it.get("link") or rec.get("url", ""),
            })
            if len(queue) >= limit:
                return queue
    return queue


def run_batch(queue, status_file=STATUS_FILE, sleep_fn=time.sleep, sleep_secs=10,
              run_one=None, now_fn=datetime.now):
    """串行执行拆解队列；run_one 可注入（单测用）。"""
    status = {
        "running": True,
        "date": now_fn().strftime("%Y-%m-%d"),
        "total": len(queue),
        "done": 0,
        "failed": 0,
        "skipped": 0,
        "current": None,
        "started_at": now_fn().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": "",
        "finished_at": "",
    }
    write_json(status_file, status)
    try:
        for idx, item in enumerate(queue):
            status["current"] = {
                "viral_id": item["viral_id"],
                "platform": item["platform"],
                "title": item["title"][:60],
            }
            status["updated_at"] = now_fn().strftime("%Y-%m-%d %H:%M:%S")
            write_json(status_file, status)
            update_record(item["viral_id"], {"status": "analyzing", "notes": f"批量自动拆解（{item['platform']} Top5）"})
            try:
                ok = bool(run_one(item))
                status["done" if ok else "failed"] += 1
            except Exception:
                status["failed"] += 1
                update_record(item["viral_id"], {"status": "tracked", "notes": "批量拆解启动失败"})
            status["current"] = None
            status["updated_at"] = now_fn().strftime("%Y-%m-%d %H:%M:%S")
            write_json(status_file, status)
            if idx < len(queue) - 1:
                sleep_fn(sleep_secs)
        return status
    finally:
        status["running"] = False
        status["finished_at"] = now_fn().strftime("%Y-%m-%d %H:%M:%S")
        status["updated_at"] = status["finished_at"]
        write_json(status_file, status)


def main():
    ap = argparse.ArgumentParser(description="三平台爆款 Top5 批量拆解器")
    ap.add_argument("--file", default=PLATFORM_VIRALS_FILE)
    ap.add_argument("--status-file", default=STATUS_FILE)
    ap.add_argument("--date", default="")
    ap.add_argument("--per-platform", type=int, default=5)
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--sleep", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    store = read_json(args.file)
    if not store:
        print("NO_STORE", file=sys.stderr)
        sys.exit(2)
    queue = select_queue(store, args.date or None, args.per_platform, args.limit)
    if not queue:
        result = {"ok": True, "queue": [], "message": "今日榜单无待拆解项"}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("✅ 今日榜单无待拆解项（均已拆解或在拆解中）")
        return
    if args.dry_run:
        result = {"ok": True, "dry_run": True, "queue": queue}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"待拆解 {len(queue)} 条：")
            for it in queue:
                print(f"  - [{it['platform']}] {it['title'][:50]}（{it['viral_id']}）")
        return

    bin_path = codex_bin()
    if not bin_path:
        result = {"ok": False, "error": "找不到 codex CLI，无法自动拆解"}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(result["error"], file=sys.stderr)
        sys.exit(2)

    def run_one(item):
        return subprocess.run(  # nosec B603  # 固定脚本参数，viral_id 来自内部榜单
            [sys.executable, RUN_VIRAL_ANALYSIS,
             "--id", item["viral_id"],
             "--title", item["title"],
             "--link", item.get("link", ""),
             "--platform", item["platform"]],
            cwd=ROOT, capture_output=True, text=True, timeout=60 * 60 * 3,
        ).returncode == 0

    status = run_batch(queue, args.status_file, sleep_fn=time.sleep,
                       sleep_secs=args.sleep, run_one=run_one)
    result = {"ok": True, **status, "queue": queue}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"批量拆解完成：成功 {status['done']} ｜ 失败 {status['failed']} ｜ 共 {status['total']}")


if __name__ == "__main__":
    main()
