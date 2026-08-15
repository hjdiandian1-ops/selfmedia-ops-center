#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据保留与清理引擎
==================
按模块执行「保留 / 归档 / 清理」策略，默认只出 dry-run 报告，--apply 才真删。

策略（常量可调）：
  - 待拆解候选：>7 天未使用删除；已忽略候选 >30 天删除
  - 过程日志（拆解 .log / production.log）：只保留最近 7 天
  - 平台榜单快照（platform_virals.json 的日期桶）：只保留最近 90 天
  - 爆款跟踪库：tracked 且 90 天未更新、且无拆解报告 → 删除；已拆解/已应用永久保留
  - 任务：updated_at 超过 30 天 → 写入 .archived 标记（不删文件，前端默认隐藏）
  - 产出大文件（图片/视频）：任务超 90 天且未出过爆款 → 删除（文案/HTML 保留）
  - 数据导入文件（data/stats/dashboard）：只保留最近 12 份

用法：
    python3 scripts/retention.py                  # dry-run：报告各模块体积与将清理清单
    python3 scripts/retention.py --apply          # 真正执行清理与归档标记
    python3 scripts/retention.py --json           # JSON 报告
"""
import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 保留策略（集中常量）
CANDIDATE_PENDING_TTL_DAYS = 7
CANDIDATE_IGNORED_TTL_DAYS = 30
LOG_TTL_DAYS = 7
PLATFORM_DAYS_KEEP = 90
VIRAL_STALE_DAYS = 90
JOB_ARCHIVE_DAYS = 30
OUTPUT_MEDIA_TTL_DAYS = 90
DASHBOARD_KEEP = 12

MEDIA_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".mp3", ".wav")


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


def _age_days(ts, now):
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return (now - datetime.strptime(ts, fmt)).days
        except ValueError:
            continue
    return None


def _file_age_days(path, now):
    return (now - datetime.fromtimestamp(os.path.getmtime(path))).days


def _dir_size(path):
    total = 0
    for r, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return total


def scan(root=ROOT, now=None):
    """扫描各模块，返回清理计划与体积报告（不执行任何删除）。"""
    now = now or datetime.now()
    plan = {
        "candidates": [],      # 候选 id
        "logs": [],            # 文件路径
        "platform_days": [],   # 日期桶
        "stale_videos": [],    # viral_videos.json 记录 id
        "jobs_to_archive": [], # job_id
        "media_files": [],     # 产出大文件路径
        "dashboard_files": [], # 导入文件路径
    }
    sizes = {}

    # 1. 待拆解候选
    cand_path = os.path.join(root, "data", "flywheel", "viral_candidates.json")
    cand_store = read_json(cand_path)
    if cand_store:
        keep = []
        for c in cand_store.get("candidates", []):
            days = _age_days(c.get("last_seen_at") or c.get("discovered_at"), now)
            status = c.get("status")
            ttl = CANDIDATE_PENDING_TTL_DAYS if status == "pending" else (
                CANDIDATE_IGNORED_TTL_DAYS if status == "ignored" else None)
            if days is not None and ttl is not None and days > ttl:
                plan["candidates"].append(c.get("id", ""))
            else:
                keep.append(c)
        if plan["candidates"]:
            sizes["candidates"] = len(plan["candidates"])

    # 2. 过程日志
    log_globs = [
        os.path.join(root, "data", "flywheel", "breakdowns", "*.log"),
        os.path.join(root, "jobs", "*", "production.log"),
    ]
    for pat in log_globs:
        for p in glob.glob(pat):
            try:
                if _file_age_days(p, now) > LOG_TTL_DAYS:
                    plan["logs"].append(p)
            except OSError:
                pass
    if plan["logs"]:
        sizes["logs"] = sum(os.path.getsize(p) for p in plan["logs"] if os.path.exists(p))

    # 3. 平台榜单快照
    pv_path = os.path.join(root, "data", "flywheel", "platform_virals.json")
    pv_store = read_json(pv_path)
    if pv_store:
        cut = (now - timedelta(days=PLATFORM_DAYS_KEEP)).strftime("%Y-%m-%d")
        for day in sorted(pv_store.get("days", {}).keys()):
            if day < cut:
                plan["platform_days"].append(day)
        if plan["platform_days"]:
            sizes["platform_days"] = len(plan["platform_days"])

    # 4. 爆款跟踪库（tracked 且长期未更新、无报告）
    vv_path = os.path.join(root, "data", "flywheel", "viral_videos.json")
    vv_store = read_json(vv_path)
    breakdown_dir = os.path.join(root, "data", "flywheel", "breakdowns")
    if vv_store:
        keep = []
        for v in vv_store.get("videos", []):
            stale = False
            if v.get("status") == "tracked":
                days = _age_days(v.get("updated_at"), now)
                has_report = os.path.exists(os.path.join(breakdown_dir, v.get("id", "") + ".json"))
                if days is not None and days > VIRAL_STALE_DAYS and not has_report:
                    plan["stale_videos"].append(v.get("id", ""))
                    stale = True
            if not stale:
                keep.append(v)
        if plan["stale_videos"]:
            sizes["stale_videos"] = len(plan["stale_videos"])

    # 5. 任务归档标记
    jobs_dir = os.path.join(root, "jobs")
    if os.path.isdir(jobs_dir):
        for d in sorted(os.listdir(jobs_dir)):
            sf = os.path.join(jobs_dir, d, "state.json")
            st = read_json(sf)
            if not st:
                continue
            marker = os.path.join(jobs_dir, d, ".archived")
            if os.path.exists(marker):
                continue
            days = _age_days(st.get("updated_at"), now)
            if days is not None and days > JOB_ARCHIVE_DAYS:
                plan["jobs_to_archive"].append(d)
        if plan["jobs_to_archive"]:
            sizes["jobs_to_archive"] = len(plan["jobs_to_archive"])

    # 6. 产出大文件
    outputs_dir = os.path.join(root, "outputs")
    if os.path.isdir(outputs_dir):
        for job_id in sorted(os.listdir(outputs_dir)):
            jdir = os.path.join(outputs_dir, job_id)
            if not os.path.isdir(jdir):
                continue
            lg = read_json(os.path.join(root, "jobs", job_id, "publish_log.json")) or {}
            has_hit = any(rec.get("hit") for rec in lg.get("records", []))
            if has_hit:
                continue  # 出过爆款的任务永久保留图片
            for r, _, fs in os.walk(jdir):
                for f in fs:
                    if not f.lower().endswith(MEDIA_EXTS):
                        continue
                    p = os.path.join(r, f)
                    try:
                        if _file_age_days(p, now) > OUTPUT_MEDIA_TTL_DAYS:
                            plan["media_files"].append(p)
                    except OSError:
                        pass
        if plan["media_files"]:
            sizes["media_files"] = sum(os.path.getsize(p) for p in plan["media_files"] if os.path.exists(p))

    # 7. 数据导入文件（保留最近 N 份）
    dash_dir = os.path.join(root, "data", "stats", "dashboard")
    if os.path.isdir(dash_dir):
        files = sorted(glob.glob(os.path.join(dash_dir, "*.json")), key=os.path.getmtime)
        for p in files[:-DASHBOARD_KEEP]:
            plan["dashboard_files"].append(p)
        if plan["dashboard_files"]:
            sizes["dashboard_files"] = len(plan["dashboard_files"])

    total_now = 0
    for d in ("outputs", "data/flywheel", "data/stats"):
        p = os.path.join(root, d)
        if os.path.isdir(p):
            total_now += _dir_size(p)
    reclaim = sum(sizes.get(k, 0) if isinstance(sizes.get(k), (int, float))
                  else len(sizes.get(k, [])) for k in sizes)
    return {
        "plan": plan,
        "sizes": sizes,
        "space": {
            "scanned_mb": round(total_now / 1e6, 2),
            "reclaimable_mb": round(reclaim / 1e6, 2),
        },
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def apply_plan(result, root=ROOT):
    """执行清理计划（候选/日志/快照/视频/大文件/导入文件删除 + 任务归档标记）。"""
    plan = result["plan"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cand_path = os.path.join(root, "data", "flywheel", "viral_candidates.json")
    cand_store = read_json(cand_path)
    if cand_store and plan["candidates"]:
        ids = set(plan["candidates"])
        cand_store["candidates"] = [c for c in cand_store.get("candidates", []) if c.get("id") not in ids]
        cand_store["updated_at"] = now
        write_json(cand_path, cand_store)

    for p in plan["logs"]:
        try:
            os.remove(p)
        except OSError:
            pass

    pv_path = os.path.join(root, "data", "flywheel", "platform_virals.json")
    pv_store = read_json(pv_path)
    if pv_store and plan["platform_days"]:
        days = set(plan["platform_days"])
        pv_store["days"] = {k: v for k, v in pv_store.get("days", {}).items() if k not in days}
        pv_store["updated_at"] = now
        write_json(pv_path, pv_store)

    vv_path = os.path.join(root, "data", "flywheel", "viral_videos.json")
    vv_store = read_json(vv_path)
    if vv_store and plan["stale_videos"]:
        ids = set(plan["stale_videos"])
        vv_store["videos"] = [v for v in vv_store.get("videos", []) if v.get("id") not in ids]
        vv_store["updated_at"] = now
        write_json(vv_path, vv_store)

    jobs_dir = os.path.join(root, "jobs")
    for job_id in plan["jobs_to_archive"]:
        marker = os.path.join(jobs_dir, job_id, ".archived")
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        if not os.path.exists(marker):
            with open(marker, "w", encoding="utf-8") as f:
                f.write(f"archived by retention at {now}\n")

    for p in plan["media_files"]:
        try:
            os.remove(p)
        except OSError:
            pass

    for p in plan["dashboard_files"]:
        try:
            os.remove(p)
        except OSError:
            pass

    return {"ok": True, "applied": {k: len(v) for k, v in plan.items()}, "updated_at": now}


def _fmt_size(n):
    return f"{n/1e6:.2f}MB" if n >= 1e6 else f"{n/1e3:.1f}KB"


def main():
    ap = argparse.ArgumentParser(description="数据保留与清理引擎")
    ap.add_argument("--apply", action="store_true", help="真正执行清理；默认仅 dry-run")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = scan()
    if args.apply:
        applied = apply_plan(result)
        result["applied"] = applied
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"📊 空间扫描：当前 {result['space']['scanned_mb']}MB，可释放 {result['space']['reclaimable_mb']}MB")
    labels = {
        "candidates": "待拆解候选(>7天未用)",
        "logs": "过程日志(>7天)",
        "platform_days": "平台榜单快照(>90天)",
        "stale_videos": "爆款跟踪(90天未更新且未拆解)",
        "jobs_to_archive": "任务标记归档(>30天)",
        "media_files": "产出大文件(>90天且未出爆款)",
        "dashboard_files": "数据导入文件(超出最近12份)",
    }
    for key, label in labels.items():
        items = result["plan"].get(key, [])
        if items:
            print(f"  - {label}：{len(items)} 项")
    if not any(result["plan"].values()):
        print("✅ 无过期数据，无需清理")
    if not args.apply:
        print("\n（dry-run：以上仅为报告，未删除任何文件；确认后运行 --apply）")


if __name__ == "__main__":
    main()
