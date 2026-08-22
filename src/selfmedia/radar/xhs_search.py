# -*- coding: utf-8 -*-
"""
Cross-Platform Social Search & Viral Radar (跨平台社媒与小红书搜索雷达)
====================================================================
支持：
  1. 小红书（关键词搜索、官方搜索热榜、Guaikei API 适配）
  2. Bilibili（全站热门、垂类榜单）
  3. 抖音（官方热搜榜与飙升榜）
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 小红书搜索热榜
XHS_HOT_URL = "https://edith.xiaohongshu.com/api/sns/v1/search/hot_list"
XHS_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "xy-direction": "22",
    "accept-language": "zh-Hans-CN;q=1",
    "shield": "XYAAAAAQAAAAEAAABTAAAAUzUWEe4xG1IYD9/c+qCLOlKGmTtFa+lG434Oe+FTRagxxoaz6rUWSZ3+juJYz8RZqct+oNMyZQxLEBaBEL+H3i0RhOBVGrauzVSARchIWFYwbwkV",
    "referer": "https://app.xhs.cn/",
}

# 抖音热榜
DOUYIN_HOT_URL = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"

# B站全站榜单
BILI_HOT_URL = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"


def _request_json(url: str, headers: Optional[dict] = None, timeout: int = 15) -> Optional[dict]:
    req_headers = {"User-Agent": DEFAULT_UA}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            return json.loads(content)
    except Exception:
        return None


def fetch_xhs_hot(limit: int = 10) -> List[Dict[str, Any]]:
    """抓取小红书热搜词与爆款话题"""
    data = _request_json(XHS_HOT_URL, headers=XHS_HEADERS)
    items = []
    if data and "data" in data:
        raw_list = data["data"].get("items", []) or []
        for raw in raw_list:
            word = raw.get("title") or raw.get("word") or ""
            if not word:
                continue
            view_num = raw.get("view_num") or raw.get("score") or 0
            items.append({
                "platform": "小红书",
                "title": word,
                "author": "小红书热门",
                "url": f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(word)}",
                "reads": int(view_num) if str(view_num).isdigit() else 0,
                "likes": 0,
                "category": "热搜话题",
            })
            if len(items) >= limit:
                break
    return items


def search_xhs_notes(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    搜索小红书笔记（若配置 GUAIKEI_API_TOKEN 则调用云端抓取，否则返回构建的结构化搜索项）
    """
    token = os.environ.get("GUAIKEI_API_TOKEN", "").strip()
    if token:
        try:
            # Guaikei API 适配
            api_url = f"https://www.guaikei.com/api/xiaohongshu/note-search/keyword?token={token}&_={int(time.time()*1000)}"
            body = json.dumps({"keyword": keyword, "type": "normal", "sort": "general", "time": "all", "limit": limit}).encode("utf-8")
            req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json", "User-Agent": DEFAULT_UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                results = []
                for item in res.get("data", []) or []:
                    nid = item.get("id") or item.get("note_id")
                    xsec = item.get("xsec_token", "")
                    url = f"https://www.xiaohongshu.com/explore/{nid}?xsec_token={xsec}" if nid else ""
                    results.append({
                        "platform": "小红书",
                        "title": item.get("title") or item.get("display_title") or "小红书笔记",
                        "author": item.get("user", {}).get("nickname") or "小红书博主",
                        "url": url,
                        "likes": int(item.get("liked_count", 0)),
                        "collects": int(item.get("collected_count", 0)),
                        "comments": int(item.get("comment_count", 0)),
                        "category": "笔记检索",
                    })
                if results:
                    return results[:limit]
        except Exception:
            pass

    # 本地只读搜索构建
    return [{
        "platform": "小红书",
        "title": f"【小红书热门】{keyword} 核心讨论与高赞经验",
        "author": "小红书推荐",
        "url": f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(keyword)}",
        "likes": 0,
        "category": "搜索引导",
    }]


def fetch_bilibili_hot(keyword: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """抓取 Bilibili 热门或按关键词过滤视频"""
    data = _request_json(BILI_HOT_URL)
    items = []
    if data and "data" in data:
        raw_list = data["data"].get("list", []) or []
        for raw in raw_list:
            title = raw.get("title", "")
            desc = raw.get("desc", "")
            if keyword and (keyword.lower() not in title.lower() and keyword.lower() not in desc.lower()):
                continue
            
            bvid = raw.get("bvid", "")
            owner = raw.get("owner", {}).get("name", "B站UP主")
            stat = raw.get("stat", {})
            items.append({
                "platform": "B站",
                "title": title,
                "author": owner,
                "url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
                "reads": stat.get("view", 0),
                "likes": stat.get("like", 0),
                "collects": stat.get("favorite", 0),
                "comments": stat.get("reply", 0),
                "cover_url": raw.get("pic", ""),
                "summary": desc[:150],
                "category": raw.get("tname", "综合热门"),
            })
            if len(items) >= limit:
                break
    return items


def fetch_douyin_hot(limit: int = 10) -> List[Dict[str, Any]]:
    """抓取抖音官方实时热搜词"""
    data = _request_json(DOUYIN_HOT_URL)
    items = []
    if data and "word_list" in data:
        for raw in data["word_list"][:limit]:
            word = raw.get("word", "")
            if not word:
                continue
            hot_value = raw.get("hot_value", 0)
            items.append({
                "platform": "抖音",
                "title": word,
                "author": "抖音热点",
                "url": f"https://www.douyin.com/search/{urllib.parse.quote(word)}",
                "reads": int(hot_value) if str(hot_value).isdigit() else 0,
                "likes": 0,
                "category": "热搜榜单",
            })
    return items


def search_cross_platform(keyword: str, limit_per_platform: int = 5) -> Dict[str, Any]:
    """跨平台统一搜索聚合"""
    xhs = search_xhs_notes(keyword, limit=limit_per_platform)
    bili = fetch_bilibili_hot(keyword=keyword, limit=limit_per_platform)
    if not bili:
        bili = fetch_bilibili_hot(limit=limit_per_platform)

    return {
        "keyword": keyword,
        "results": {
            "小红书": xhs,
            "B站": bili,
        }
    }


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "AI"
    print(f"🔍 正在多平台搜索: {kw}...")
    res = search_cross_platform(kw)
    for p, items in res["results"].items():
        print(f"\n📌 【{p}】找到 {len(items)} 条内容：")
        for it in items:
            print(f"  - {it['title']} ({it.get('author', '')}) -> {it.get('url', '')}")
