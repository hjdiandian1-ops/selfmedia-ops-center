#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三平台爆款榜单采集器
====================
每日抓取小红书 / 抖音 / 微信公众号的真实爆款信号，各平台 Top10：
  - 小红书：官方搜索热榜接口（edith.xiaohongshu.com，固定 xy 头）
  - 抖音：官方热搜榜接口（iesdouyin.com web api）
  - 微信公众号：今日热榜首页「微信 · 24h热文榜」（mp.weixin.qq.com 原文链接）

落盘 data/flywheel/platform_virals.json（按日期×平台），同时按标题去重
upsert 到 data/flywheel/viral_videos.json 复用既有拆解/状态机。
单源失败互不影响；小红书/抖音失败时回退 RanksLive 镜像接口。

用法：
    python3 scripts/collect_platform_virals.py            # 采集今日三平台榜单
    python3 scripts/collect_platform_virals.py --json     # 只打印 JSON 摘要
    python3 scripts/collect_platform_virals.py --date 2026-08-14
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security_utils import safe_http_url  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_FILE = os.path.join(ROOT, "data", "flywheel", "platform_virals.json")
VIRAL_FILE = os.path.join(ROOT, "data", "flywheel", "viral_videos.json")

DEFAULT_LIMIT = 10

# 小红书官方搜索热榜（固定 xy 头，2026-08 实测可用）
XHS_URL = "https://edith.xiaohongshu.com/api/sns/v1/search/hot_list"
XHS_HEADERS = {
    "xy-direction": "22",
    "accept-language": "zh-Hans-CN;q=1",
    "shield": "XYAAAAAQAAAAEAAABTAAAAUzUWEe4xG1IYD9/c+qCLOlKGmTtFa+lG434Oe+FTRagxxoaz6rUWSZ3+juJYz8RZqct+oNMyZQxLEBaBEL+H3i0RhOBVGrauzVSARchIWFYwbwkV",
    "xy-platform-info": "platform=iOS&version=8.7&build=8070515&deviceId=C323D3A5-6A27-4CE6-AA0E-51C9D4C26A24&bundle=com.xingin.discover",
    "xy-common-params": "app_id=ECFAAF02&build=8070515&channel=AppStore&deviceId=C323D3A5-6A27-4CE6-AA0E-51C9D4C26A24&device_fingerprint=20230920120211bd7b71a80778509cf4211099ea911000010d2f20f6050264&device_fingerprint1=20230920120211bd7b71a80778509cf4211099ea911000010d2f20f6050264&device_model=phone&fid=1695182528-0-0-63b29d709954a1bb8c8733eb2fb58f29&gid=7dc4f3d168c355f1a886c54a898c6ef21fe7b9a847359afc77fc24ad&identifier_flag=0&lang=zh-Hans&launch_id=716882697&platform=iOS&project_id=ECFAAF&sid=session.1695189743787849952190&t=1695190591&teenager=0&tz=Asia/Shanghai&uis=light&version=8.7",
    "referer": "https://app.xhs.cn/",
}

# 抖音官方热搜榜（web api，2026-08 实测可用）
DOUYIN_URL = ("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"
              "?reflow_source=reflow_page&web_id=7488166462781392438"
              "&device_id=7488166462781392438"
              "&user_cip=2a0f:7803:fae1:1::524&_zy_number=12")

# RanksLive 在线镜像（官方接口失败时的兜底，2026-08 实测可用）
RANKS_MIRROR = {
    "小红书": "https://ranks-live-api.vercel.app/xiaohongshu/hot",
    "抖音": "https://ranks-live-api.vercel.app/douyin/hot",
}

# 今日热榜首页（SSR 全量榜单，888KB 含微信24h热文榜）
TOPHUB_HOME = "https://tophub.today/"
TOPHUB_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
             "AppleWebKit/537.36 Chrome/126 Safari/537.36")


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


def _clean_html_text(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _fmt_heat(value):
    """热度统一成 w 单位：11331229 → 1133.1w，10.0万 → 10.0w，920.8w 原样。"""
    s = str(value or "").strip().replace(",", "")
    if not s:
        return ""
    m = re.match(r"^([\d.]+)\s*(万|w|W)$", s)
    if m:
        num = float(m.group(1))
        return f"{num:.1f}w"
    try:
        num = float(s)
    except ValueError:
        return s
    if abs(num) >= 10000:
        return f"{num / 10000:.1f}w"
    return str(int(num)) if num == int(num) else f"{num:.1f}"


def _http_get(url, headers=None, timeout=25):
    if not safe_http_url(url):
        raise ValueError(f"URL 不满足安全策略（仅公网 http/https）: {url[:120]}")
    req = urllib.request.Request(url, headers={
        "User-Agent": TOPHUB_UA,
        **({"Accept": "application/json,text/plain,*/*"} if headers is None else {}),
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected  # 已由 safe_http_url 校验公网地址
        return resp.read().decode("utf-8", "ignore")


def _norm_title(s):
    return re.sub(r"[\s#*_\-—·•]+", "", str(s or "")).lower()[:60]


def _video_id(platform, title):
    key = _norm_title(f"{platform}:{title}")
    return "v_" + hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


# ---------- 各平台原始抓取 ----------

def fetch_xhs(limit=DEFAULT_LIMIT):
    """小红书搜索热榜：items[] → {title, heat, tag, link, rank}。"""
    raw = _http_get(XHS_URL, headers=XHS_HEADERS)
    data = json.loads(raw)
    items = (data.get("data") or {}).get("items") or []
    out = []
    for i, it in enumerate(items[:limit], start=1):
        title = (it.get("title") or "").strip()
        if not title:
            continue
        kw = urllib.parse.quote(title)
        out.append({
            "title": title,
            "heat": _fmt_heat(it.get("score")),
            "tag": str(it.get("word_type") or ""),
            "link": f"https://www.xiaohongshu.com/search_result?keyword={kw}&source=web_explore_feed",
            "rank": i,
        })
    if not out:
        raise RuntimeError("小红书热榜接口返回空列表")
    return out


def fetch_douyin(limit=DEFAULT_LIMIT):
    """抖音热搜榜：word_list[] → {title, heat, tag, link, rank}。"""
    raw = _http_get(DOUYIN_URL)
    data = json.loads(raw)
    word_list = (data.get("word_list") or []) or ((data.get("data") or {}).get("word_list") or [])
    out = []
    for i, it in enumerate(word_list[:limit], start=1):
        word = (it.get("word") or "").strip()
        if not word:
            continue
        label_map = {1: "新", 3: "热", 5: "首发", 8: "独家"}
        out.append({
            "title": word,
            "heat": _fmt_heat(it.get("hot_value")),
            "tag": label_map.get(it.get("label"), ""),
            "link": "https://www.douyin.com/root/search/" + urllib.parse.quote(word),
            "rank": i,
        })
    if not out:
        raise RuntimeError("抖音热榜接口返回空列表")
    return out


def fetch_wechat(limit=DEFAULT_LIMIT):
    """微信公众号 24h 热文榜：解析今日热榜首页「微信 · 24h热文榜」板块。"""
    html = _http_get(TOPHUB_HOME)
    chunks = re.split(r'<div class="cc-cd" id="node-', html)
    board = None
    for chunk in chunks:
        if "mp.weixin.qq.com/s?" in chunk and "24h热文榜" in chunk:
            board = chunk
            break
    if board is None:
        raise RuntimeError("今日热榜首页未找到微信24h热文榜板块")
    item_re = re.compile(
        r'<a href="(https://mp\.weixin\.qq\.com/s\?[^"]+)"[^>]*>\s*'
        r'<div class="cc-cd-cb-ll">\s*'
        r'<span class="s[^"]*">(\d+)</span>\s*'
        r'<span class="t">(.*?)</span>\s*'
        r'<span class="e">(.*?)</span>',
        re.S)
    out = []
    for m in item_re.finditer(board):
        title = _clean_html_text(m.group(3))
        if not title:
            continue
        out.append({
            "title": title,
            "heat": _fmt_heat(_clean_html_text(m.group(4))),
            "tag": "10w+热文",
            "link": m.group(1),
            "rank": int(m.group(2)),
        })
        if len(out) >= limit:
            break
    if not out:
        raise RuntimeError("微信24h热文榜解析失败（页面结构可能变化）")
    return out


def fetch_ranks_mirror(platform, limit=DEFAULT_LIMIT):
    """RanksLive 镜像兜底：{code:200, data:{items:[{title,view,url}]}}。"""
    url = RANKS_MIRROR.get(platform)
    if not url:
        raise RuntimeError(f"无 {platform} 镜像源")
    raw = _http_get(url)
    data = json.loads(raw)
    items = ((data.get("data") or {}).get("items") or [])
    out = []
    for i, it in enumerate(items[:limit], start=1):
        title = (it.get("title") or "").strip()
        if not title:
            continue
        out.append({
            "title": title,
            "heat": _fmt_heat(it.get("view")),
            "tag": "镜像",
            "link": it.get("url") or "",
            "rank": i,
        })
    if not out:
        raise RuntimeError(f"{platform} 镜像返回空列表")
    return out


PLATFORM_FETCHERS = {
    "小红书": lambda limit: fetch_xhs(limit),
    "抖音": lambda limit: fetch_douyin(limit),
    "公众号": lambda limit: fetch_wechat(limit),
}


# ---------- 落盘 ----------

def _load_store(path):
    return read_json(path) or {"days": {}, "source_status": {}, "updated_at": ""}


def _upsert_video(videos_store, platform, item, now):
    """按「平台+标题」去重 upsert 到 viral_videos.json，返回 (added, updated)。"""
    videos = videos_store.setdefault("videos", [])
    vid = _video_id(platform, item["title"])
    for v in videos:
        if v.get("id") == vid:
            v["url"] = item.get("link") or v.get("url", "")
            v["heat"] = item.get("heat") or v.get("heat", "")
            v["tag"] = item.get("tag") or v.get("tag", "")
            v["updated_at"] = now
            return vid, 0, 1
    videos.insert(0, {
        "id": vid,
        "platform": platform,
        "title": item["title"],
        "author": "",
        "url": item.get("link", ""),
        "published_at": "",
        "reads": 0,
        "likes": 0,
        "collects": 0,
        "comments": 0,
        "theme": "",
        "hook": "",
        "structure": "",
        "why_viral": "",
        "formula": "",
        "status": "tracked",
        "heat": item.get("heat", ""),
        "tag": item.get("tag", ""),
        "notes": f"平台榜单自动采集（{platform}，热度 {item.get('heat', '—')}，第 {item.get('rank', '?')} 名）",
        "created_at": now,
        "updated_at": now,
    })
    return vid, 1, 0


def collect(store_path=DEFAULT_FILE, viral_path=VIRAL_FILE, date=None, limit=DEFAULT_LIMIT):
    """执行三平台采集并落盘，返回摘要 dict（不触网时可被单测复用逻辑拆解）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = date or datetime.now().strftime("%Y-%m-%d")
    store = _load_store(store_path)
    day = store.setdefault("days", {}).setdefault(date, {})
    source_status = store.setdefault("source_status", {})
    videos_store = read_json(viral_path) or {"videos": []}
    summary = {"ok": True, "date": date, "platforms": {}, "added": 0, "updated": 0}

    for platform, fetch in PLATFORM_FETCHERS.items():
        prev = source_status.get(platform, {})
        try:
            try:
                items = fetch(limit)
                used_mirror = False
            except Exception as e:
                if platform in RANKS_MIRROR:
                    items = fetch_ranks_mirror(platform, limit)
                    used_mirror = True
                else:
                    raise
            day[platform] = []
            for it in items:
                vid, added, updated = _upsert_video(videos_store, platform, it, now)
                day[platform].append({
                    "viral_id": vid,
                    "title": it["title"],
                    "rank": it.get("rank", 0),
                    "heat": it.get("heat", ""),
                    "tag": it.get("tag", ""),
                    "link": it.get("link", ""),
                })
                summary["added"] += added
                summary["updated"] += updated
            source_status[platform] = {
                "ok": True,
                "items": len(day[platform]),
                "updated_at": now,
                "error": "",
                "mirror": used_mirror,
            }
            summary["platforms"][platform] = {"ok": True, "items": len(items), "mirror": used_mirror}
        except Exception as e:
            source_status[platform] = {
                "ok": False,
                "items": len(day.get(platform, [])),
                "updated_at": prev.get("updated_at", ""),
                "error": str(e)[:200],
                "mirror": False,
            }
            summary["platforms"][platform] = {
                "ok": False, "items": len(day.get(platform, [])),
                "error": str(e)[:200],
            }

    store["updated_at"] = now
    write_json(store_path, store)
    if summary["added"] or summary["updated"]:
        videos_store["updated_at"] = now
        write_json(viral_path, videos_store)
    summary["source_status"] = source_status
    return summary


def main():
    ap = argparse.ArgumentParser(description="三平台爆款榜单采集器")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--viral-file", default=VIRAL_FILE)
    ap.add_argument("--date", default="")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    summary = collect(args.file, args.viral_file, args.date or None, args.limit)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        parts = []
        for platform, st in summary["platforms"].items():
            parts.append(f"{platform} {'✅' if st['ok'] else '❌'}×{st.get('items', 0)}")
        print(f"三平台榜单采集：{' / '.join(parts)} ｜ 新增 {summary['added']} 更新 {summary['updated']}")


if __name__ == "__main__":
    main()
