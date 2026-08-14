#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爆款候选采集器
==============
从新增信息源（推楼1号小时热点 / 今日热榜AI / hex2077 AI 日报）与最近热点雷达
提取高热度内容，作为「待拆解」候选写入 data/flywheel/viral_candidates.json。

用法：
    python3 scripts/collect_viral_candidates.py            # 采集并落盘
    python3 scripts/collect_viral_candidates.py --json     # 只打印摘要
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_FILE = os.path.join(ROOT, "data", "flywheel", "viral_candidates.json")
VIRAL_FILE = os.path.join(ROOT, "data", "flywheel", "viral_videos.json")
MATERIALS_DIR = os.path.join(ROOT, "materials")
HEAT_TRACK_THRESHOLD = 8.0  # 热度数值 ≥ 8（推楼 8-10 / 谷歌趋势 200+ / 今日热榜 万级）自动转入跟踪库

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_hot_topics as fht  # noqa: E402


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


def _norm(s):
    return re.sub(r"[\s#*_\-—·•]+", "", str(s or "")).lower()[:60]


def _cand_id(title):
    return "c_" + hashlib.md5(_norm(title).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def _load_store(path):
    return read_json(path) or {"candidates": [], "updated_at": ""}


def _upsert(store, title, link, source, heat):
    if not title:
        return 0
    cid = _cand_id(title)
    existing = {c["id"]: c for c in store["candidates"]}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if cid in existing:
        old = existing[cid]
        if link and not old.get("link"):
            old["link"] = link
        if heat and (not old.get("heat") or str(old.get("heat", "")) < str(heat)):
            old["heat"] = heat
        old["last_seen_at"] = now
        return 0
    store["candidates"].insert(0, {
        "id": cid, "title": title, "link": link or "", "source": source,
        "heat": heat or "", "status": "pending", "discovered_at": now,
        "last_seen_at": now, "note": "",
    })
    return 1


def _heat_num(heat):
    """把热度标注解析成数值：9 / 500+ / 100.2万热度 → 9 / 500 / 1002000。"""
    if not heat:
        return None
    m = re.match(r"\s*([\d.]+)\s*(万)?", str(heat).replace(",", ""))
    if not m:
        return None
    value = float(m.group(1))
    return value * 10000 if m.group(2) else value


def _platform(source):
    if re.search(r"推楼|X热点|twitter", source or ""):
        return "X"
    if "B站" in (source or ""):
        return "B站"
    if "小红书" in (source or ""):
        return "小红书"
    if "抖音" in (source or ""):
        return "抖音"
    if "视频号" in (source or ""):
        return "视频号"
    return "其他"


def _auto_track(store):
    """高热候选自动转入跟踪库（viral_videos.json），无需手工填写。"""
    videos_store = read_json(VIRAL_FILE) or {"videos": []}
    videos = videos_store.setdefault("videos", [])
    known = {_norm(v.get("title", "")) for v in videos}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    promoted = 0
    for c in store.get("candidates", []):
        if c.get("status") != "pending":
            continue
        heat = _heat_num(c.get("heat"))
        if heat is None or heat < HEAT_TRACK_THRESHOLD:
            continue
        key = _norm(c.get("title"))
        if key not in known:
            videos.insert(0, {
                "id": "v_" + hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:12],
                "platform": _platform(c.get("source", "")),
                "title": c.get("title", ""), "author": "", "url": c.get("link", ""),
                "published_at": "", "reads": 0, "likes": 0, "collects": 0,
                "comments": 0, "theme": "", "hook": "", "structure": "",
                "why_viral": "", "formula": "", "status": "tracked",
                "notes": f"自动采集（来源 {c.get('source','')}，热度 {c.get('heat','')}）",
                "created_at": now, "updated_at": now,
            })
            known.add(key)
            promoted += 1
        c["status"] = "tracked"
    if promoted:
        videos_store["updated_at"] = now
        write_json(VIRAL_FILE, videos_store)
    return promoted


def collect_radar(store, limit=10):
    hits = sorted(os.path.join(MATERIALS_DIR, d) for d in os.listdir(MATERIALS_DIR)
                  if os.path.isdir(os.path.join(MATERIALS_DIR, d)))
    radar = None
    for d in reversed(hits):
        for f in reversed(sorted(os.listdir(d))):
            if f.endswith("_热点雷达.md"):
                radar = os.path.join(d, f)
                break
        if radar:
            break
    if not radar:
        return 0
    source, added = "", 0
    for ln in open(radar, encoding="utf-8"):
        if ln.startswith("## "):
            source = ln[3:].strip()
            continue
        m = re.match(r"\s*\d+[\.、．]\s*(.*?)\s*（\[链接\]\((.*?)\)）(.*)$", ln)
        if m and source:
            added += _upsert(store, m.group(1).strip(), m.group(2) or "", "热点雷达·" + source, "")
        elif not m:
            m2 = re.match(r"\s*\d+[\.、．]\s*(.+?)\s*$", ln)
            if m2 and source:
                added += _upsert(store, m2.group(1).strip(), "", "热点雷达·" + source, "")
    return added


def collect_online(store, limit=10):
    added = 0
    try:
        for it in fht.fetch_tl1(limit):
            added += _upsert(store, it["title"], it.get("link", ""),
                             "推楼1号小时热点", it.get("traffic", ""))
    except Exception as e:
        print(f"⚠️ 推楼1号候选采集失败: {e}", file=sys.stderr)
    try:
        for it in fht.fetch_tophub(limit):
            added += _upsert(store, it["title"], it.get("link", ""),
                             "今日热榜AI", it.get("traffic", ""))
    except Exception as e:
        print(f"⚠️ 今日热榜候选采集失败: {e}", file=sys.stderr)
    try:
        for it in fht.fetch_hex2077(limit):
            added += _upsert(store, it["title"], it.get("link", ""),
                             "hex2077 AI日报", "")
    except Exception as e:
        print(f"⚠️ hex2077 候选采集失败: {e}", file=sys.stderr)
    return added


def main():
    ap = argparse.ArgumentParser(description="爆款候选采集器")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    store = _load_store(args.file)
    added = collect_radar(store, args.limit)
    added += collect_online(store, args.limit)
    auto_tracked = _auto_track(store)
    store["candidates"] = store["candidates"][:100]
    store["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_json(args.file, store)

    pending = sum(1 for c in store["candidates"] if c.get("status") == "pending")
    summary = {
        "ok": True, "added": added, "auto_tracked": auto_tracked,
        "total": len(store["candidates"]),
        "pending": pending, "updated_at": store["updated_at"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"✅ 爆款候选已更新：新增 {added} ｜ 自动跟踪 {auto_tracked} ｜ 累计 {summary['total']}（待拆解 {pending}）")


if __name__ == "__main__":
    main()
