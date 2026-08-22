#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原文正文抓取器 (Source Content Fetcher)
========================================
从热点雷达 / 榜单的原文链接抓取正文文本，作为生产素材的「真实 grounding」，
根治「仅凭标题推断、LLM 编造数字」的问题。

设计原则：
  - 纯标准库实现（urllib + 正则 + 并发），零第三方依赖；
  - 只抓公网 http/https（经 security_utils.safe_http_url 校验，禁内网/元数据地址）；
  - 单页超时、失败静默降级，绝不阻塞主流程；
  - 对外提供纯函数 extract_main_text()（可单测）与批量入口 gather_grounding()。

用法：
    python3 scripts/fetch_source_content.py --url "https://..." --max-chars 8000
    python3 scripts/fetch_source_content.py --radar materials/2026-08/2026-08-20_热点雷达.md --theme "AI客服" --limit 5
"""
import argparse
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security_utils import safe_http_url  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MAX_READ_BYTES = 200_000


def _clean_text(s):
    s = re.sub(r"(?is)<[^>]+>", " ", s or "")
    s = unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    return s.strip()


def extract_main_text(html, max_chars=12000):
    """从 HTML 提取正文（纯函数，便于单测）：优先 <article>/<main>，退化为全页文本。"""
    if not html:
        return ""
    html = re.sub(r"(?is)<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>", " ", html or "")
    container = html
    m = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
    if m:
        container = m.group(1)
    else:
        m = re.search(r"(?is)<main[^>]*>(.*?)</main>", html)
        if m:
            container = m.group(1)
    parts = re.findall(r"(?is)<(?:p|li|h[1-3]|blockquote)[^>]*>(.*?)</(?:p|li|h[1-3]|blockquote)>", container)
    if not parts:
        parts = [container]
    lines = []
    for p in parts:
        t = _clean_text(p)
        if len(t) > 1:
            lines.append(t)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def fetch_url_text(url, timeout=15, max_chars=12000):
    """抓取单个公网 URL 的正文文本；失败返回空串（静默降级）。"""
    if not url or not safe_http_url(url, resolve_dns=False):
        return ""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # 已由 safe_http_url 校验公网地址
            if getattr(resp, "getcode", lambda: 200)() != 200:
                return ""
            ctype = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read(MAX_READ_BYTES)
    except Exception:
        return ""
    try:
        text = raw.decode("utf-8", "ignore")
    except Exception:
        return ""
    if "text/html" in ctype or not ctype:
        return extract_main_text(text, max_chars)
    return text[:max_chars]


def parse_radar_links(radar_path):
    """解析热点雷达 md → [(title, link)]（无链接的条目跳过）。"""
    rows = []
    if not radar_path or not os.path.isfile(radar_path):
        return rows
    with open(radar_path, encoding="utf-8") as f:
        for ln in f:
            m = re.match(r"\s*\d+[\.、．]\s*(.+?)\s*（\[链接\]\((.*?)\)）", ln)
            if m:
                title = re.sub(r"\s*（发布于[^）]*）\s*$", "", m.group(1)).strip()
                rows.append((title, m.group(2).strip()))
    return rows


def _related(theme, rows, limit=5):
    """按主题关键词命中数对雷达条目排序；无命中则取前 limit 条兜底。"""
    kws = [w for w in re.split(r"[\s，,、/|：:（）()\-—]+", theme or "") if len(w) >= 2]
    scored = []
    for title, link in rows:
        hit = sum(1 for w in kws if w in title)
        scored.append((hit, title, link))
    scored.sort(key=lambda x: -x[0])
    top = [s for s in scored if s[0] > 0] or scored[:limit]
    return [(t, l) for _, t, l in top[:limit]]


def gather_grounding(theme="", link="", radar_path="", limit=5, timeout=12):
    """批量抓取正文并组织成 markdown（供 run_production Stage1 注入）。"""
    entries = []
    seen = set()
    if link and safe_http_url(link, resolve_dns=False):
        entries.append(("采纳来源", link))
        seen.add(link)
    if radar_path:
        for t, l in _related(theme, parse_radar_links(radar_path), limit):
            if l and l not in seen:
                entries.append((t[:60], l))
                seen.add(l)
    if not entries:
        return ""

    def _fetch(e):
        title, url = e
        return title, url, fetch_url_text(url, timeout=timeout)

    results = []
    with ThreadPoolExecutor(max_workers=min(6, len(entries))) as pool:
        futs = [pool.submit(_fetch, e) for e in entries]
        for f in as_completed(futs):
            title, url, text = f.result()
            if text and len(text) > 80:
                results.append((title, url, text))

    if not results:
        return ""
    blocks = ["## 真实抓取到的原文素材（必须基于这些写，禁止编造数字）", ""]
    for i, (title, url, text) in enumerate(results, 1):
        blocks.append(f"### 来源 {i}：{title}")
        blocks.append(f"- 链接：{url}")
        blocks.append("")
        blocks.append(text[:4000])
        blocks.append("")
    return "\n".join(blocks)


def main():
    ap = argparse.ArgumentParser(description="原文正文抓取器")
    ap.add_argument("--url", default="", help="抓取单个 URL")
    ap.add_argument("--radar", default="", help="热点雷达 md 路径（配合 --theme 批量抓取）")
    ap.add_argument("--theme", default="", help="主题关键词，用于从雷达中筛选相关条目")
    ap.add_argument("--link", default="", help="采纳时的原始链接（优先抓取）")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--max-chars", type=int, default=12000)
    args = ap.parse_args()

    if args.url:
        text = fetch_url_text(args.url, max_chars=args.max_chars)
        print(text if text else "（未抓到正文：可能是 JS 动态页或链接失效）")
        return 0
    md = gather_grounding(args.theme, args.link, args.radar, args.limit)
    print(md if md else "（未抓到可用正文）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
