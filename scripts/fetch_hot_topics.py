#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点雷达采集器（全网免鉴权直接源 + 智能容错 + 代理海外源 + 离线兜底）
========================================================================
特点：
  1. 默认开箱即用：内置国内全网直连公开源（微博、知乎、B站、百度、少数派、掘金、IT之家、V2EX 等），
     0 配置、秒级直连，不需要在本地自建 RSSHub 或配置 NAS；
  2. 极速异步并发：多源并行抓取（超时 6 秒），单源网络波动自动降级，绝不阻塞整体；
  3. 海外源显式解耦：谷歌趋势 / X 热点仅在配置代理（SELFMEDIA_PROXY / HTTP_PROXY）时抓取，
     未配置代理时自动跳过，绝不制造全局报错；
  4. 离线样本兜底：极端离线断网环境下自动加载内置样本池，确保 100% 不白屏、不报错。
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SAMPLE_RADAR_FILE = os.path.join(ROOT, "materials", "样例_热点雷达.md")

DEFAULT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 兼容常量与配置
X_TRENDS_ENABLED = os.environ.get("X_TRENDS_ENABLED", "1") == "1"
X_TRENDS_URL = os.environ.get("X_TRENDS_URL", "")
X_TRENDS_MODE = os.environ.get("X_TRENDS_MODE", "zh")
GOOGLE_TRENDS_URL = os.environ.get("GOOGLE_TRENDS_URL", "https://trends.google.com/trending/rss?geo=US")
HT_NS = "{https://trends.google.com/trending/rss}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
BASE = "http://127.0.0.1:1200"

# 合规初筛词表
COMPLIANCE_BLOCK = [
    "选举", "竞选", "总统", "首相", "国会", "议会", "政变", "抗议", "示威", "游行",
    "战争", "冲突升级", "核武器", "导弹", "恐怖", "暗杀", "泄密", "制裁",
    "赌博", "博彩", "毒品", "色情", "裸", "违法", "诈骗", "翻墙", "AV",
    "election", "protest", "riot", "coup", "war", "nuclear", "missile",
    "terror", "assassination", "sanction", "porn", "drug", "gambling",
]


def resolve_proxy():
    """代理解析链：SELFMEDIA_PROXY > X_SCRAPER_PROXY > HTTPS/HTTP_PROXY。未配置时返回空。"""
    for key in ("SELFMEDIA_PROXY", "X_SCRAPER_PROXY", "HTTPS_PROXY", "https_proxy",
                "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


PROXY_URL = resolve_proxy()


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = unescape(s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _clean_html_text(s):
    return unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def is_compliant(title: str, summary: str = "") -> bool:
    blob = (title + " " + summary).lower()
    return not any(w.lower() in blob for w in COMPLIANCE_BLOCK)


def compliance_pass(items):
    """合规初筛过滤：返回 (ok_items, blocked_titles)。"""
    ok, blocked = [], []
    for it in items:
        title = it.get("title", "") or it.get("name", "")
        summary = it.get("summary", "")
        if is_compliant(title, summary):
            ok.append(it)
        else:
            blocked.append(title)
    return ok, blocked


def fetch_http(url, proxy=None, timeout=6, ua=DEFAULT_UA, allow_private=True):
    """带代理的 HTTP GET 基础函数，返回 bytes。"""
    req_headers = {"User-Agent": ua or DEFAULT_UA, "Accept": "application/json, text/plain, */*"}
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=req_headers)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


# ============================================================
# 国内免鉴权官方直连源
# ============================================================

def fetch_weibo(top=10):
    url = "https://weibo.com/ajax/side/hotSearch"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    realtime = data.get("data", {}).get("realtime", [])
    items = []
    for r in realtime:
        word = clean_text(r.get("word", ""))
        num = r.get("num", 0)
        if word and not r.get("is_ad") and is_compliant(word):
            items.append({
                "title": word,
                "link": f"https://s.weibo.com/weibo?q={urllib.parse.quote(word)}",
                "heat": f"{num} 热度" if num else "热搜",
                "source": "微博热搜",
            })
        if len(items) >= top:
            break
    return items


def fetch_bilibili(top=10):
    url = "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    vlist = data.get("data", {}).get("list", [])
    items = []
    for v in vlist:
        title = clean_text(v.get("title", ""))
        bvid = v.get("bvid", "")
        desc = clean_text(v.get("desc", ""))
        stat = v.get("stat", {})
        view = stat.get("view", 0)
        if title and is_compliant(title, desc):
            items.append({
                "title": title,
                "link": f"https://www.bilibili.com/video/{bvid}" if bvid else "https://www.bilibili.com",
                "heat": f"{view} 播放" if view else "热门",
                "summary": desc[:100],
                "source": "B站热门",
            })
        if len(items) >= top:
            break
    return items


def fetch_baidu(top=10):
    url = "https://top.baidu.com/board?tab=realtime"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    html = raw.decode("utf-8", errors="ignore")
    matches = re.findall(r'<!--\s*s-data:\s*({.+?})\s*-->', html)
    items = []
    if matches:
        data = json.loads(matches[0])
        cards = data.get("data", {}).get("cards", [])
        for c in cards:
            for content in c.get("content", []):
                word = clean_text(content.get("word", ""))
                url = content.get("url", "")
                desc = clean_text(content.get("desc", ""))
                hot = content.get("hotScore", "")
                if word and is_compliant(word, desc):
                    items.append({
                        "title": word,
                        "link": url or "https://top.baidu.com",
                        "heat": f"{hot} 热搜" if hot else "热搜",
                        "summary": desc[:100],
                        "source": "百度热搜",
                    })
                if len(items) >= top:
                    break
            if len(items) >= top:
                break
    return items


def fetch_sspai(top=10):
    url = "https://sspai.com/feed"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    root = ET.fromstring(raw)  # nosec B314
    items = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        desc = clean_text(it.findtext("description") or "")
        if title and is_compliant(title, desc):
            items.append({
                "title": title,
                "link": link or "https://sspai.com",
                "summary": desc[:100],
                "source": "少数派热门",
            })
        if len(items) >= top:
            break
    return items


def fetch_juejin(top=10):
    url = "https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    dlist = data.get("data", [])
    items = []
    for d in dlist:
        info = d.get("content", {})
        title = clean_text(info.get("title", ""))
        cid = info.get("content_id", "")
        views = d.get("content_counter", {}).get("view_count", 0)
        if title and cid and is_compliant(title):
            items.append({
                "title": title,
                "link": f"https://juejin.cn/post/{cid}",
                "heat": f"{views} 阅读" if views else "热榜",
                "source": "掘金热榜",
            })
        if len(items) >= top:
            break
    return items


def fetch_ithome(top=10):
    url = "https://www.ithome.com/rss/"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    root = ET.fromstring(raw)  # nosec B314
    items = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        desc = clean_text(it.findtext("description") or "")
        if title and is_compliant(title, desc):
            items.append({
                "title": title,
                "link": link,
                "summary": desc[:100],
                "source": "IT之家",
            })
        if len(items) >= top:
            break
    return items


def fetch_v2ex(top=10):
    url = "https://www.v2ex.com/api/topics/hot.json"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    items = []
    if isinstance(data, list):
        for d in data:
            title = clean_text(d.get("title", ""))
            url_link = d.get("url", "")
            replies = d.get("replies", 0)
            if title and is_compliant(title):
                items.append({
                    "title": title,
                    "link": url_link,
                    "heat": f"{replies} 回复",
                    "source": "V2EX热议",
                })
            if len(items) >= top:
                break
    return items


def fetch_dailyhot_zhihu(top=10):
    url = "https://api.vvhan.com/api/hotlist?type=zhihuHot"
    raw = fetch_http(url, timeout=6, ua=DEFAULT_UA)
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    items = []
    for d in data.get("data", [])[:top]:
        title = clean_text(d.get("title", ""))
        link = d.get("url", "")
        hot = d.get("hot", "")
        if title and is_compliant(title):
            items.append({
                "title": title,
                "link": link or "https://www.zhihu.com",
                "heat": f"{hot} 热度" if hot else "热榜",
                "source": "知乎热榜",
            })
    return items


# ============================================================
# 兼容旧单测解析函数
# ============================================================

def fetch_source(name, route, top=10):
    routes = route if isinstance(route, list) else [route]
    last_err = None
    raw = None
    for r in routes:
        try:
            raw = fetch_http(f"{BASE}{r}", proxy=None, timeout=15)
            break
        except Exception as e:
            last_err = e
    if raw is None:
        raise last_err
    root = ET.fromstring(raw)  # nosec B314
    items = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        if title:
            items.append({"title": title, "link": link})
    return items[:top]


def fetch_google_trends(top=10):
    p = resolve_proxy() or PROXY_URL or "http://127.0.0.1:7897"
    raw = fetch_http(GOOGLE_TRENDS_URL, proxy=p, timeout=20)
    root = ET.fromstring(raw)  # nosec B314
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        traffic = (it.findtext(f"{HT_NS}approx_traffic") or "").strip()
        published_at = (it.findtext("pubDate") or "").strip()
        if title:
            items.append({
                "title": re.sub(r"\s+", " ", title),
                "link": link,
                "traffic": traffic,
                "published_at": published_at,
                "compliance": "海外源·需人工复核（谷歌趋势）",
                "source": "谷歌趋势",
                "is_overseas": True,
            })
    return items[:top]


def x_items_to_radar(raw_trends, top):
    label = ("海外源·需人工复核（X热点·中文热议）" if X_TRENDS_MODE == "zh"
             else "海外源·需人工复核（X热点·地区趋势）")
    return [{
        "title": re.sub(r"\s+", " ", str(t.get("name") or "")),
        "link": str(t.get("url") or ""),
        "tweet_count": t.get("tweet_count"),
        "published_at": str(t.get("created_at") or ""),
        "compliance": label,
    } for t in raw_trends[:top] if t.get("name")]


def fetch_x_trends_http(top=10):
    raw = fetch_http(X_TRENDS_URL or "http://127.0.0.1:8788/trends", proxy=PROXY_URL, timeout=20)
    data = json.loads(raw.decode("utf-8"))
    if not data.get("success"):
        raise RuntimeError(f"X 趋势接口返回失败: {str(data)[:120]}")
    return x_items_to_radar(data.get("trends", []), top)


def fetch_x_trends(top=10):
    if not X_TRENDS_ENABLED:
        return []
    if X_TRENDS_URL:
        return fetch_x_trends_http(top)
    return []


def fetch_tophub(top=10):
    url = "https://tophub.today/c/ai"
    raw = fetch_http(url, timeout=10)
    html = raw.decode("utf-8", errors="ignore")
    items = []
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>.*?<span\s+class="t">([^<]+)</span>', html, re.S):
        link = m.group(1).strip()
        title = clean_text(m.group(2))
        if title:
            items.append({"title": title, "link": link})
        if len(items) >= top:
            break
    return items


def fetch_tl1(top=10):
    url = "https://example.com/tl1/hours"
    raw = fetch_http(url, timeout=10)
    hours = json.loads(raw.decode("utf-8"))
    if not hours:
        raise RuntimeError("推楼1号暂无小时热点")
    hour_key = hours[0].get("hour_key", "") if isinstance(hours, list) else ""
    data = json.loads(fetch_http(
        f"https://tl1.com/api/hotspot?hour={hour_key}", proxy=None, timeout=20).decode("utf-8"))
    items = []
    for it in (data.get("items") or [])[:top]:
        title = (it.get("topic") or "").strip()
        if not title:
            continue
        items.append({
            "title": re.sub(r"\s+", " ", title),
            "link": it.get("url", ""),
            "traffic": str(it.get("score") or ""),
            "published_at": hour_key,
            "compliance": "海外源·需人工复核（推楼1号/X）",
        })
    return items


def fetch_hex2077(top=10):
    index_html = fetch_http("https://hex2077.dev/docs/", proxy=None, timeout=20).decode("utf-8", "ignore")
    m = re.search(r'href="(/docs/\d{4}-\d{2}/\d{4}-\d{2}-\d{2}/)"', index_html)
    if not m:
        raise RuntimeError("hex2077 索引页未找到日报链接")
    article_url = "https://hex2077.dev" + m.group(1)
    article = fetch_http(article_url, proxy=None, timeout=25).decode("utf-8", "ignore")

    section, items = "", []
    token_re = re.compile(
        r'<h[23][^>]*>(.*?)</h[23]>'
        r'|<p class="my-5[^>]*>(.*?)</p>', re.S)
    for tm in token_re.finditer(article):
        if tm.group(1) is not None:
            section = _clean_html_text(tm.group(1)).strip()
            continue
        para = tm.group(2)
        link_m = re.search(r'href="(https?://[^"]+)"[^>]*>([^<]{2,50})<', para)
        if not link_m or "hex2077.dev" in link_m.group(1):
            continue
        lead = ""
        strong_m = re.search(r"<strong[^>]*>(.*?)</strong>", para)
        if strong_m:
            lead = _clean_html_text(strong_m.group(1))
        title = (f"{lead}：" if lead else "") + _clean_html_text(link_m.group(2))
        link = link_m.group(1)
        compliance = ""
        if "x.com" in link or "twitter.com" in link:
            compliance = "海外源·需人工复核（X 链接）"
        items.append({
            "title": re.sub(r"\s+", " ", title)[:120],
            "link": link,
            "published_at": m.group(1).rstrip("/").split("/")[-1],
            "section": section,
            "compliance": compliance or "海外源·需人工复核",
        })
        if len(items) >= top:
            break
    return items


# ============================================================
# 采集调度与渲染
# ============================================================

ALL_SOURCE_FETCHERS = [
    ("微博热搜", fetch_weibo),
    ("知乎热榜", fetch_dailyhot_zhihu),
    ("B站热门", fetch_bilibili),
    ("百度热搜", fetch_baidu),
    ("少数派热门", fetch_sspai),
    ("掘金热榜", fetch_juejin),
    ("IT之家", fetch_ithome),
    ("V2EX热议", fetch_v2ex),
]


def fetch_all(top=10):
    proxy = resolve_proxy()
    results = {}
    statuses = {}

    def _worker(name, fn):
        try:
            items = fn(top)
            return name, items, True, None
        except Exception as e:
            return name, [], False, str(e)

    tasks = list(ALL_SOURCE_FETCHERS)
    if proxy:
        tasks.append(("谷歌趋势", fetch_google_trends))

    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as pool:
        futures = [pool.submit(_worker, name, fn) for name, fn in tasks]
        for f in as_completed(futures):
            name, items, ok, err = f.result()
            statuses[name] = {"ok": ok, "count": len(items), "error": err}
            if ok and items:
                results[name] = items

    # 离线保底：若因极端断网无任何源成功，加载内置样本
    if not results and os.path.exists(SAMPLE_RADAR_FILE):
        print("ℹ️ 处于离线环境或网络不可达，自动载入内置热点雷达样本...")
        with open(SAMPLE_RADAR_FILE, "r", encoding="utf-8") as sf:
            sample_content = sf.read()
        return {"ok": True, "offline": True, "content": sample_content, "statuses": statuses}

    return {"ok": bool(results), "offline": False, "results": results, "statuses": statuses}


def render_radar_markdown(fetch_result, top=10):
    if fetch_result.get("offline"):
        return fetch_result.get("content", "")

    results = fetch_result.get("results", {})
    statuses = fetch_result.get("statuses", {})
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    succ_names = [k for k, v in statuses.items() if v["ok"] and v["count"] > 0]
    fail_names = [k for k, v in statuses.items() if not v["ok"]]

    header = [
        f"# 热点雷达（{datetime.now().strftime('%Y-%m-%d')}）",
        f"> 采集时间：{stamp}",
        f"> 来源概况：成功 {len(succ_names)} 源（{'、'.join(succ_names)}）" +
        (f" ｜ 离线 {len(fail_names)} 源（{'、'.join(fail_names)}）" if fail_names else ""),
        f"> 筛选标准：各源 Top{top}，已剔除合规敏感词与广告条目",
        "",
        "---",
        "",
    ]

    body = []
    for source_name, items in sorted(results.items(), key=lambda x: len(x[1]), reverse=True):
        body.append(f"## {source_name}")
        body.append("")
        for i, item in enumerate(items, 1):
            title = item["title"]
            link = item.get("link", "")
            heat = item.get("heat", "")
            heat_str = f" `[{heat}]`" if heat else ""
            link_str = f"（[链接]({link})）" if link else ""
            summary = f"\n   > {item['summary']}" if item.get("summary") else ""
            body.append(f"{i}. {title}{heat_str} {link_str}{summary}")
        body.append("")

    return "\n".join(header + body)


def main():
    ap = argparse.ArgumentParser(description="自媒体热点雷达采集器")
    ap.add_argument("--top", type=int, default=10, help="每个源抓取条数")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    res = fetch_all(top=args.top)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    md = render_radar_markdown(res, top=args.top)

    month_dir = os.path.join(ROOT, "materials", datetime.now().strftime("%Y-%m"))
    os.makedirs(month_dir, exist_ok=True)
    out_file = os.path.join(month_dir, f"{datetime.now().strftime('%Y-%m-%d')}_热点雷达.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"✅ 热点雷达已落盘：{out_file}")
    print(f"📊 成功汇总 {len(res.get('results', {}))} 个信息源")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
