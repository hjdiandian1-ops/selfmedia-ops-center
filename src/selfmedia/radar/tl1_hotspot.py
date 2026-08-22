# -*- coding: utf-8 -*-
"""
TL1 Hotspot Radar (推楼1号 X中文区数据雷达)
=========================================
对接 https://tl1.com/ 实时获取 X.com 中文区小时热点、突发热帖与 AI 灵感脉搏。
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List


def fetch_tl1_hotspots(max_items: int = 15, timeout: int = 15) -> Dict[str, Any]:
    """
    抓取推楼1号 (https://tl1.com/) 小时热点与 AI 灵感脉搏
    :param max_items: 最大返回条数
    :param timeout: 超时时间（秒）
    :return: 包含 items, count, hour 的字典
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://tl1.com/",
    }

    items = []
    bj_tz = timezone(timedelta(hours=8))
    now_bj = datetime.now(bj_tz)

    # 1. 尝试抓取当前小时及前 1 小时的小时热点榜
    for offset_h in (0, 1, 2):
        target_hour = (now_bj - timedelta(hours=offset_h)).strftime("%Y%m%d%H")
        url = f"https://tl1.com/api/hotspot?hour={target_hour}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hot_items = data.get("items") or []
                if hot_items:
                    for it in hot_items:
                        topic = (it.get("topic") or "").strip()
                        summary = (it.get("summary") or "").strip()
                        url_link = it.get("url") or f"https://x.com/i/status/{it.get('tweetId')}" if it.get("tweetId") else "https://tl1.com/"
                        items.append({
                            "title": topic,
                            "summary": summary,
                            "why_viral": it.get("reason", ""),
                            "url": url_link,
                            "author": it.get("source", "X用户"),
                            "heat": str(it.get("score") or "9"),
                            "score": float(it.get("score") or 9.0),
                            "hour": target_hour,
                            "source": "推楼1号小时热点",
                            "compliance": "海外源·需人工复核（推楼1号/X）",
                        })
                    break
        except Exception:
            continue

    # 2. 补充抓取灵感脉搏与实时热帖 (/api/home/summary)
    try:
        req = urllib.request.Request("https://tl1.com/api/home/summary", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            home_data = json.loads(resp.read().decode("utf-8"))
            
            # AI 灵感脉搏
            idea_items = (home_data.get("idea") or {}).get("items") or []
            for idea in idea_items:
                title = (idea.get("t") or "").strip()
                if not title or any(x["title"] == title for x in items):
                    continue
                items.append({
                    "title": title,
                    "summary": (idea.get("m") or "").strip(),
                    "why_viral": (idea.get("n") or "").strip(),
                    "url": idea.get("u") or "https://tl1.com/",
                    "author": idea.get("r") or "@X",
                    "heat": str(idea.get("s") or "10"),
                    "score": float(idea.get("s") or 10.0),
                    "hour": now_bj.strftime("%Y%m%d%H"),
                    "source": "推楼1号AI脉搏",
                    "compliance": "海外源·需人工复核（推楼1号/X）",
                })

            # 实时突发热帖
            trending_items = (home_data.get("trending") or {}).get("items") or []
            for tr in trending_items:
                content = (tr.get("content") or "").strip().replace("\n", " ")
                title = content[:60] + ("..." if len(content) > 60 else "")
                author = tr.get("authorHandle") or "X"
                tweet_id = tr.get("tweetId") or ""
                url_link = f"https://x.com/{author}/status/{tweet_id}" if tweet_id else "https://tl1.com/"
                if not title or any(x["title"] == title for x in items):
                    continue
                items.append({
                    "title": title,
                    "summary": content,
                    "why_viral": f"每分钟曝光增速: {tr.get('viewsPerMin', 0)} / 阅读: {tr.get('currentStats', {}).get('viewCount', 0)}",
                    "url": url_link,
                    "author": f"@{author} ({tr.get('displayName', '')})",
                    "heat": f"{tr.get('viewsPerMin', 0):.0f}速",
                    "score": 8.5,
                    "hour": now_bj.strftime("%Y%m%d%H"),
                    "source": "推楼1号实时热帖",
                    "compliance": "海外源·需人工复核（推楼1号/X）",
                })
    except Exception:
        pass

    # 截取前 max_items 条
    selected = items[:max_items]
    return {
        "ok": len(selected) > 0,
        "source": "推楼1号 (tl1.com)",
        "count": len(selected),
        "items": selected,
    }
