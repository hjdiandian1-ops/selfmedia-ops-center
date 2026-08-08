#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点雷达采集器（RSSHub + 谷歌趋势 + X 热点 → 选题素材流）
==========================================================
聚合三路热度源：
  1. 国内源：NAS RSSHub（微博/知乎/36氪/少数派/B站/掘金）
  2. 谷歌趋势：官方趋势 RSS（需代理访问海外网站）
  3. X 热点：复用 personal-website 的 x_scraper（NAS 上 twikit + clash 代理 + cookie），
     优先走 X_TRENDS_URL（若配置了 HTTP 端点），否则尝试 SSH docker exec 直取。

海外源默认打上「海外源·需人工复核」标记，且经过合规初筛（国内可发布性）。

用法：
    python3 scripts/fetch_hot_topics.py              # 采集并落盘 materials/YYYY-MM/YYYY-MM-DD_热点雷达.md
    python3 scripts/fetch_hot_topics.py --top 8      # 每个源取前 8 条（默认 10）
    python3 scripts/fetch_hot_topics.py --json       # 只打印 JSON，不落盘

环境变量：
    NAS_IP / RSSHUB_PORT         NAS 与 RSSHub 地址（默认 192.168.50.229 / 1200）
    SELFMEDIA_PROXY              海外源代理（复用 personal-website 的 X_SCRAPER_PROXY 模式）
    X_SCRAPER_PROXY / HTTP(S)_PROXY  代理备选链（未设 SELFMEDIA_PROXY 时使用）
    X_TRENDS_URL                 可选：X 趋势 HTTP 端点（返回 {"success":true,"trends":[...]}）
    X_TRENDS_ENABLED=1           显式启用 X 热点（默认尝试，失败自动跳过）

退出码：0 = 至少一个源成功；1 = 全部失败（此时采编应降级用 WebSearch 搜集热点）。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
except ImportError:
    NAS_IP = os.environ.get("NAS_IP", "192.168.50.229")
    NAS_SSH_PORT = int(os.environ.get("NAS_SSH_PORT", "233"))
    NAS_USER = os.environ.get("NAS_USER", "")
    NAS_PASS = os.environ.get("NAS_PASS", "")

RSSHUB_PORT = int(os.environ.get("RSSHUB_PORT", "1200"))
BASE = f"http://{NAS_IP}:{RSSHUB_PORT}"
GOOGLE_TRENDS_URL = os.environ.get(
    "GOOGLE_TRENDS_URL", "https://trends.google.com/trending/rss?geo=US")
GOOGLE_TRENDS_GEO = os.environ.get("GOOGLE_TRENDS_GEO", "US")
X_TRENDS_URL = os.environ.get("X_TRENDS_URL", "")
X_TRENDS_ENABLED = os.environ.get("X_TRENDS_ENABLED", "1") == "1"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
HT_NS = "{https://trends.google.com/trending/rss}"

# 国内 RSSHub 热榜路由（按需增删；不可用的源会自动跳过）
SOURCES = {
    "微博热搜": "/weibo/search/hot",
    "知乎热榜": "/zhihu/hotlist",
    "36氪快讯": "/36kr/newsflashes",
    "少数派热门": "/sspai/matrix",
    "B站热门": "/bilibili/popular/all",
    "掘金趋势": "/juejin/trending/all/daily",
}

OVERSEAS_SOURCES = ("谷歌趋势", "X热点")

# 合规初筛：命中关键词的条目直接剔除（海外源强制复核，机器只做保守初筛）
COMPLIANCE_BLOCK = [
    "选举", "竞选", "总统", "首相", "国会", "议会", "政变", "抗议", "示威", "游行",
    "战争", "冲突升级", "核武器", "导弹", "恐怖", "暗杀", "泄密", "制裁",
    "赌博", "博彩", "毒品", "色情", "裸", "违法", "诈骗", "翻墙",
    "election", "protest", "riot", "coup", "war", "nuclear", "missile",
    "terror", "assassination", "sanction", "porn", "drug", "gambling",
]


def resolve_proxy():
    """代理解析链：SELFMEDIA_PROXY > X_SCRAPER_PROXY > HTTPS/HTTP_PROXY > 本机默认 7897。
    与 personal-website 的 X_SCRAPER_PROXY 用法一致（本机实测 clash 混合端口 7897）。"""
    for key in ("SELFMEDIA_PROXY", "X_SCRAPER_PROXY", "HTTPS_PROXY", "https_proxy",
                "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return "http://127.0.0.1:7897"


PROXY_URL = resolve_proxy()


def fetch_http(url, proxy=None, timeout=20):
    """带代理的 HTTP GET，返回 bytes。"""
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({
            "http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={"User-Agent": "selfmedia-hot-radar/1.0"})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_source(name, route, top):
    """RSSHub 源（RSS 2.0 / Atom）。"""
    raw = fetch_http(f"{BASE}{route}", proxy=None, timeout=15)
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title:
            items.append({"title": re.sub(r"\s+", " ", title), "link": link})
    if not items:
        for it in root.iter(f"{ATOM_NS}entry"):
            title = (it.findtext(f"{ATOM_NS}title") or "").strip()
            link_el = it.find(f"{ATOM_NS}link")
            link = link_el.get("href", "") if link_el is not None else ""
            if title:
                items.append({"title": re.sub(r"\s+", " ", title), "link": link})
    return items[:top]


def fetch_google_trends(top):
    """谷歌趋势官方 RSS（海外源，走代理）。"""
    raw = fetch_http(GOOGLE_TRENDS_URL, proxy=PROXY_URL, timeout=20)
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        traffic = (it.findtext(f"{HT_NS}approx_traffic") or "").strip()
        if title:
            items.append({
                "title": re.sub(r"\s+", " ", title),
                "link": link,
                "traffic": traffic,
                "compliance": "海外源·需人工复核（谷歌趋势）",
            })
    return items[:top]


def fetch_x_trends_via_nas(top):
    """复用 NAS x_scraper 容器（personal-website 的 twikit + clash 代理 + cookie）取 X 热点。"""
    if not (NAS_USER and NAS_PASS):
        raise RuntimeError("缺少 NAS 凭据，无法取 X 热点")
    try:
        import paramiko
    except ImportError:
        raise RuntimeError("缺少 paramiko，无法取 X 热点")

    script = '''
import asyncio, json, os
from twikit import Client
async def main():
    c = Client("zh-CN", proxy=os.environ.get("HTTP_PROXY") or None)
    cf = os.environ.get("X_COOKIES_FILE") or "/app/cookies.json"
    if os.path.exists(cf):
        c.load_cookies(cf)
    tr = await c.get_trends("trending")
    items = getattr(tr, "trends", None) or tr or []
    out = []
    for t in list(items)[:20]:
        name = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
        url = getattr(t, "url", None) or (t.get("url") if isinstance(t, dict) else None)
        cnt = getattr(t, "tweet_count", None) or getattr(t, "tweetCount", None) or (t.get("tweet_count") if isinstance(t, dict) else None)
        if name:
            out.append({"name": name, "url": url, "tweet_count": cnt})
    print(json.dumps({"success": True, "trends": out}, ensure_ascii=False))
asyncio.run(main())
'''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=15)
    docker = "/volume1/@appstore/ContainerManager/usr/bin/docker"
    cmd = f"sudo -S {docker} exec -i x_scraper python3 -"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=25)
    stdin.write(NAS_PASS + "\n" + script + "\n")
    stdin.flush()
    stdin.close()
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    if not out.strip():
        raise RuntimeError(f"X 容器无输出（stderr: {err[:300]}）")
    data = json.loads(out)
    if not data.get("success"):
        raise RuntimeError(f"X 趋势接口返回失败: {str(data)[:120]}")
    return [{
        "title": re.sub(r"\s+", " ", str(t.get("name") or "")),
        "link": str(t.get("url") or ""),
        "tweet_count": t.get("tweet_count"),
        "compliance": "海外源·需人工复核（X热点）",
    } for t in data.get("trends", [])[:top] if t.get("name")]


def fetch_x_trends_http(top):
    """通过 X_TRENDS_URL HTTP 端点取 X 热点（返回 {"success":true,"trends":[...]}）。"""
    raw = fetch_http(X_TRENDS_URL, proxy=PROXY_URL, timeout=20)
    data = json.loads(raw.decode("utf-8"))
    if not data.get("success"):
        raise RuntimeError(f"X 趋势接口返回失败: {str(data)[:120]}")
    return [{
        "title": re.sub(r"\s+", " ", str(t.get("name") or "")),
        "link": str(t.get("url") or ""),
        "tweet_count": t.get("tweet_count"),
        "compliance": "海外源·需人工复核（X热点）",
    } for t in data.get("trends", [])[:top] if t.get("name")]


def fetch_x_trends(top):
    if not X_TRENDS_ENABLED:
        return []
    if X_TRENDS_URL:
        return fetch_x_trends_http(top)
    return fetch_x_trends_via_nas(top)


def compliance_pass(items):
    """合规初筛：返回 (通过列表, 被拦截标题列表)。"""
    ok, blocked = [], []
    for it in items:
        title = it.get("title", "")
        if any(kw in title for kw in COMPLIANCE_BLOCK):
            blocked.append(title)
            continue
        ok.append(it)
    return ok, blocked


def main():
    ap = argparse.ArgumentParser(description="热点雷达采集器（国内 RSSHub + 谷歌趋势 + X 热点）")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    results, failed, blocked = {}, [], []

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

    # 谷歌趋势（海外源，走代理）
    try:
        items = compliance_pass(fetch_google_trends(args.top))
        blocked += items[1]
        if items[0]:
            results["谷歌趋势"] = items[0]
            print(f"✅ 谷歌趋势: {len(items[0])} 条（代理 {PROXY_URL}）", file=sys.stderr)
        else:
            failed.append("谷歌趋势(空)")
    except Exception as e:
        failed.append("谷歌趋势")
        print(f"❌ 谷歌趋势: {e}", file=sys.stderr)

    # X 热点（复用 NAS x_scraper；失败自动跳过，不影响整体）
    try:
        items = compliance_pass(fetch_x_trends(args.top))
        blocked += items[1]
        if items[0]:
            results["X热点"] = items[0]
            print(f"✅ X热点: {len(items[0])} 条", file=sys.stderr)
        else:
            failed.append("X热点(空)")
    except Exception as e:
        failed.append("X热点")
        print(f"⚠️ X热点: {e}（已跳过，不影响其他源）", file=sys.stderr)

    if not results:
        print("\n🛑 所有热点源均失败。请检查：1) NAS/RSSHub 是否在线 2) 海外代理是否可用 3) X x_scraper 容器状态。", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"results": results, "blocked": blocked},
                         ensure_ascii=False, indent=2))
        return

    out_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "materials", month))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{today}_热点雷达.md")

    lines = [
        f"# 📡 热点雷达（{today}）",
        "",
        f"> 来源：国内 RSSHub（{BASE}）+ 谷歌趋势 + X热点 ｜ 成功 {len(results)} 源"
        + (f"，失败 {len(failed)} 源：{'、'.join(failed)}" if failed else ""),
        "> 用途：资深采编选题输入。标注 (source_type: 真实数据 | priority: 辅助)；经采编研判后入选素材包的条目再标 核心。",
        "> 合规：海外源（谷歌趋势/X热点）已做关键词初筛，入选选题前必须人工复核「国内可合规发布」。",
        "",
    ]
    if blocked:
        lines += ["> ⛔ 合规初筛拦截 " + str(len(blocked)) + " 条：" + "；".join(blocked[:8]) + ("…" if len(blocked) > 8 else ""), ""]
    for name, items in results.items():
        lines += [f"## {name}", ""]
        for i, it in enumerate(items, 1):
            link = f"（[链接]({it['link']})）" if it.get("link") else ""
            flag = f" ｜ ⚠️ {it['compliance']}" if it.get("compliance") else ""
            extra = f"（{it['traffic']}）" if it.get("traffic") else ""
            lines.append(f"{i}. {it['title']}{extra}{link}{flag}")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n📁 热点雷达已落盘：{out_path}（共 {sum(len(v) for v in results.values())} 条，合规拦截 {len(blocked)} 条）")


if __name__ == "__main__":
    main()
