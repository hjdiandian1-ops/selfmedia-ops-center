# -*- coding: utf-8 -*-
"""
WeChat Official Accounts Explosive Articles Radar (微信公众号爆款雷达)
====================================================================
支持多榜单探测：低粉高阅读榜（黑马爆款）、10w+阅读榜、原创靠前榜、数据增长榜
"""

from __future__ import annotations

import gzip
import html
import json
import re
import socket
import ssl
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse


def _safe_url(url: Optional[str]) -> str:
    if not url:
        return ""
    url = str(url).strip()
    if len(url) > 4096:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    return url


def _parse_count(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    s = str(val).replace("+", "").replace(",", "").strip().lower()
    if "w" in s:
        s = s.replace("w", "")
        try:
            return int(float(s) * 10000)
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def _decode_chunked(data: bytes) -> bytes:
    chunks = []
    idx = 0
    while idx < len(data):
        line_end = data.find(b"\r\n", idx)
        if line_end == -1:
            break
        chunk_size_line = data[idx:line_end]
        try:
            chunk_size = int(chunk_size_line, 16)
        except Exception:
            break
        if chunk_size == 0:
            break
        chunk_start = line_end + 2
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(data):
            break
        chunks.append(data[chunk_start:chunk_end])
        idx = chunk_end + 2
    return b"".join(chunks)


def _fetch_no_sni(base_url: str, params: dict, timeout: int = 20) -> tuple[int, str]:
    if "://" in base_url:
        base_url = base_url.split("://", 1)[1]
    host, path = base_url.split("/", 1)
    if params:
        q = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in params.items())
        path = f"{path}?{q}"

    sock = socket.create_connection((host, 443), timeout=timeout)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    ssl_sock = context.wrap_socket(sock, server_hostname=None)

    req = (
        f"GET /{path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)\r\n"
        f"Accept: application/json, text/plain, */*\r\n"
        f"Accept-Encoding: gzip, deflate\r\n"
        f"Connection: close\r\n\r\n"
    )
    ssl_sock.send(req.encode())

    res = b""
    while True:
        try:
            chunk = ssl_sock.recv(8192)
            if not chunk:
                break
            res += chunk
        except Exception:
            break
    ssl_sock.close()

    header_end = res.find(b"\r\n\r\n")
    if header_end == -1:
        return 500, ""
    headers_str = res[:header_end].decode("utf-8", errors="ignore")
    body = res[header_end + 4 :]

    status_code = 200
    first_line = headers_str.splitlines()[0] if headers_str else ""
    parts = first_line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        status_code = int(parts[1])

    if "transfer-encoding: chunked" in headers_str.lower():
        body = _decode_chunked(body)
    if "content-encoding: gzip" in headers_str.lower():
        try:
            body = gzip.decompress(body)
        except Exception:
            pass

    return status_code, body.decode("utf-8", errors="ignore")


def calculate_data_score(item: dict, cat_key: str) -> float:
    fans = _parse_count(item.get("fans", 0))
    likes = _parse_count(item.get("likeCount", 0))
    reads = _parse_count(item.get("clicksCount", 0))
    shares = _parse_count(item.get("shareCount", 0))
    comments = _parse_count(item.get("commentCount", 0))
    
    total_interact = likes + comments + shares
    if cat_key == "lowPowderExplosiveArticle":
        # 低粉爆款重点看阅读/粉丝倍数
        fan_base = max(fans, 100)
        score = (reads / fan_base) * 20.0 + (total_interact / 100.0)
    elif cat_key == "ten_w_reading":
        score = 80.0 + min(total_interact / 500.0, 20.0)
    else:
        score = min((reads / 1000.0) * 5.0 + (total_interact / 50.0) * 5.0, 100.0)
    return round(score, 2)


def fetch_gzh_explosive_articles(
    keyword: str,
    start_date: Optional[str] = None,
    max_items: int = 10,
) -> Dict[str, Any]:
    """
    抓取微信公众号爆款文章
    :param keyword: 搜索关键词或赛道标签（空字符串表示全站热门）
    :param start_date: 开始日期 YYYY-MM-DD
    :param max_items: 最多返回条数
    :return: 包含 items 列表及元数据的结构化字典
    """
    base_url = "https://onetotenvip.com/skill/cozeSkill/getWxCozeSkillData"
    params = {"keyword": keyword, "source": "SelfMedia-Radar-Skill"}
    if start_date:
        params["startDate"] = start_date

    status, body = _fetch_no_sni(base_url, params)
    if status >= 400 or not body:
        return {"ok": False, "error": f"HTTP {status}", "keyword": keyword, "items": []}

    try:
        data = json.loads(body)
    except Exception as e:
        return {"ok": False, "error": f"JSON解析失败: {e}", "keyword": keyword, "items": []}

    payload = data.get("data", {})
    categories = [
        ("lowPowderExplosiveArticle", "低粉爆款"),
        ("tenWReadingArticle", "10w+爆款"),
        ("originalRankArticle", "原创飙升"),
        ("oneWReadingArticle", "数据增长"),
    ]

    all_items = []
    seen_urls = set()

    for cat_key, cat_name in categories:
        raw_list = payload.get(cat_key, []) or []
        for raw in raw_list:
            url = _safe_url(raw.get("oriUrl") or raw.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            score = calculate_data_score(raw, cat_key)
            title = (raw.get("title") or raw.get("summary") or "无标题").strip()
            summary = (raw.get("summary") or "").strip()
            account_name = raw.get("userName") or raw.get("accountId") or "未知公众号"
            
            all_items.append({
                "category": cat_name,
                "title": title,
                "summary": summary,
                "account_name": account_name,
                "account_id": raw.get("accountId", ""),
                "fans": _parse_count(raw.get("fans", 0)),
                "reads": _parse_count(raw.get("clicksCount", 0)),
                "likes": _parse_count(raw.get("likeCount", 0)),
                "comments": _parse_count(raw.get("commentCount", 0)),
                "shares": _parse_count(raw.get("shareCount", 0)),
                "watch_count": _parse_count(raw.get("watchCount", 0)),
                "public_time": raw.get("publicTime", ""),
                "url": url,
                "data_score": score,
            })

    # 按综合爆款分数降序排序
    all_items.sort(key=lambda x: x["data_score"], reverse=True)
    filtered = all_items[:max_items]

    return {
        "ok": True,
        "keyword": keyword,
        "total_scanned": len(all_items),
        "count": len(filtered),
        "items": filtered,
    }


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "AI编程"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(f"📡 正在探测公众号爆款（关键词: {kw}, 上限: {limit}）...")
    result = fetch_gzh_explosive_articles(kw, max_items=limit)
    print(f"✅ 找到 {result['count']} 篇爆款文章：")
    for i, item in enumerate(result["items"], 1):
        print(f"  [{i}] 【{item['category']}】{item['title']}")
        print(f"      公众号: {item['account_name']} (粉丝: {item['fans']}) | 阅读: {item['reads']} | 点赞: {item['likes']} | 分数: {item['data_score']}")
        print(f"      链接: {item['url']}")
