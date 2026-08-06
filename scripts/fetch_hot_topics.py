#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点雷达采集器（RSSHub → 选题素材流）
======================================
从 NAS 上的 RSSHub 拉取多平台热榜，聚合落盘为当日热点雷达 md，
供「资深采编」选题使用。

用法：
    python3 scripts/fetch_hot_topics.py              # 采集并落盘 materials/YYYY-MM/YYYY-MM-DD_热点雷达.md
    python3 scripts/fetch_hot_topics.py --top 8      # 每个源取前 8 条（默认 10）
    python3 scripts/fetch_hot_topics.py --json       # 只打印 JSON，不落盘

环境变量：NAS_IP（默认 192.168.50.229）、RSSHUB_PORT（默认 1200）
退出码：0 = 至少一个源成功；1 = 全部失败（此时采编应降级用 WebSearch 搜集热点）
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from nas_config import NAS_IP
except ImportError:
    NAS_IP = os.environ.get("NAS_IP", "192.168.50.229")

RSSHUB_PORT = int(os.environ.get("RSSHUB_PORT", "1200"))
BASE = f"http://{NAS_IP}:{RSSHUB_PORT}"

# 热榜路由（按需增删；不可用的源会自动跳过）
SOURCES = {
    "微博热搜": "/weibo/search/hot",
    "知乎热榜": "/zhihu/hotlist",
    "36氪快讯": "/36kr/newsflashes",
    "少数派热门": "/sspai/matrix",
    "B站热门": "/bilibili/popular/all",
    "掘金趋势": "/juejin/trending/all/daily",
}

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch_source(name, route, top):
    url = f"{BASE}{route}"
    req = urllib.request.Request(url, headers={"User-Agent": "selfmedia-hot-radar/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    # RSS 2.0
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title:
            items.append({"title": re.sub(r"\s+", " ", title), "link": link})
    # Atom
    if not items:
        for it in root.iter(f"{ATOM_NS}entry"):
            title = (it.findtext(f"{ATOM_NS}title") or "").strip()
            link_el = it.find(f"{ATOM_NS}link")
            link = link_el.get("href", "") if link_el is not None else ""
            if title:
                items.append({"title": re.sub(r"\s+", " ", title), "link": link})
    return items[:top]


def main():
    ap = argparse.ArgumentParser(description="热点雷达采集器")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    results, failed = {}, []

    for name, route in SOURCES.items():
        try:
            items = fetch_source(name, route, args.top)
            if items:
                results[name] = items
                print(f"✅ {name}: {len(items)} 条", file=sys.stderr)
            else:
                failed.append(f"{name}(空)")
                print(f"⚠️ {name}: 返回为空", file=sys.stderr)
        except Exception as e:
            failed.append(name)
            print(f"❌ {name}: {e}", file=sys.stderr)

    if not results:
        print("\n🛑 所有热点源均失败。请检查：1) NAS 是否在线 2) RSSHub 容器是否运行（docker ps | grep rsshub）3) NAS_IP/RSSHUB_PORT 配置。", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    out_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "materials", month))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{today}_热点雷达.md")

    lines = [
        f"# 📡 热点雷达（{today}）",
        "",
        f"> 来源：NAS RSSHub（{BASE}）｜成功 {len(results)} 源" + (f"，失败 {len(failed)} 源：{'、'.join(failed)}" if failed else ""),
        "> 用途：资深采编选题输入。标注 (source_type: 真实数据 | priority: 辅助)；经采编研判后入选素材包的条目再标 核心。",
        "",
    ]
    for name, items in results.items():
        lines += [f"## {name}", ""]
        for i, it in enumerate(items, 1):
            link = f"（[链接]({it['link']})）" if it["link"] else ""
            lines.append(f"{i}. {it['title']}{link}")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n📁 热点雷达已落盘：{out_path}（共 {sum(len(v) for v in results.values())} 条）")


if __name__ == "__main__":
    main()
