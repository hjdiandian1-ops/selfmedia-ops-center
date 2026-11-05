# -*- coding: utf-8 -*-
"""海外高可用热点采集器与多源聚合模块单测。
涵盖 Hacker News Firebase API、GitHub Trending、Product Hunt RSS、Reddit AI 以及多源并行聚合逻辑。
"""
import json
import os
import sys
import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from selfmedia.radar import overseas_sources as OS


MOCK_HN_ITEM = {
    "id": 10001,
    "title": "Show HN: Open Source Agentic AI Workflow",
    "url": "https://github.com/example/agentic-ai",
    "score": 342,
    "descendants": 89,
    "by": "geekdev",
    "type": "story",
    "time": 1726900000,
}

MOCK_GH_HTML = """
<!DOCTYPE html>
<html>
<body>
  <article class="Box-row">
    <h2 class="h3 lh-condensed">
      <a href="/anthropics/anthropic-cookbook">
        anthropics / <span>anthropic-cookbook</span>
      </a>
    </h2>
    <p class="col-9 color-fg-muted my-1 pr-4">A collection of notebooks and recipes for Claude API.</p>
    <div class="f6 color-fg-muted mt-2">
      <span class="d-inline-block ml-0 mr-3">
        <span class="repo-language-color"></span>
        <span itemprop="programmingLanguage">Python</span>
      </span>
      <a href="/anthropics/anthropic-cookbook/stargazers" class="Link--muted d-inline-block mr-3">8,450</a>
      <span class="d-inline-block float-sm-right">612 stars today</span>
    </div>
  </article>
</body>
</html>
"""

MOCK_PH_RSS = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Product Hunt – Today's Best New Products</title>
  <entry>
    <title>Cursor Composer</title>
    <link href="https://www.producthunt.com/posts/cursor-composer" />
    <content>AI code editor that predicts your next moves and builds entire features.</content>
  </entry>
</feed>
"""

MOCK_REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>LocalLLaMA: Open Source LLMs and Local AI</title>
  <entry>
    <title>Qwen 2.5 72B Instruct quantized benchmarks are out</title>
    <link href="https://www.reddit.com/r/LocalLLaMA/comments/xyz123/qwen_25_benchmarks/" />
    <content type="html">&lt;p&gt;Performance on RTX 4090 with EXL2 4.0bpw runs at 45 t/s.&lt;/p&gt;</content>
  </entry>
</feed>
"""


def test_fetch_hacker_news_mocked(monkeypatch, tmp_path):
    """验证 Hacker News Firebase API 解析与分数/评论数提取。"""
    cache_file = tmp_path / "hn_cache.json"
    monkeypatch.setattr(OS, "HN_CACHE_FILE", str(cache_file))

    def fake_http_get(url, timeout=8, proxy=None, headers=None):
        if "topstories.json" in url:
            return json.dumps([10001]).encode("utf-8")
        elif "item/10001.json" in url:
            return json.dumps(MOCK_HN_ITEM).encode("utf-8")
        return b"{}"

    monkeypatch.setattr(OS, "_http_get", fake_http_get)

    items = OS.fetch_hacker_news(top=5)
    assert len(items) == 1
    it = items[0]
    assert it["title"] == "Show HN: Open Source Agentic AI Workflow"
    assert it["link"] == "https://github.com/example/agentic-ai"
    assert "342 分" in it["heat"]
    assert "89 评" in it["heat"]
    assert "🟧 HN" in it["badge"]
    assert os.path.exists(cache_file)


def test_fetch_github_trending_mocked(monkeypatch, tmp_path):
    """验证 GitHub Trending HTML 解析、star 提取与语言识别。"""
    cache_file = tmp_path / "gh_cache.json"
    monkeypatch.setattr(OS, "GITHUB_CACHE_FILE", str(cache_file))

    def fake_http_get(url, timeout=8, proxy=None, headers=None):
        return MOCK_GH_HTML.encode("utf-8")

    monkeypatch.setattr(OS, "_http_get", fake_http_get)

    items = OS.fetch_github_trending(top=5)
    assert len(items) == 1
    it = items[0]
    assert "anthropic-cookbook" in it["title"]
    assert "anthropic-cookbook" in it["link"]
    assert "+612 Stars" in it["heat"]
    assert "Python" in it["summary"]
    assert "🐙" in it["badge"]
    assert os.path.exists(cache_file)


def test_fetch_product_hunt_mocked(monkeypatch, tmp_path):
    """验证 Product Hunt Atom RSS 解析。"""
    cache_file = tmp_path / "ph_cache.json"
    monkeypatch.setattr(OS, "PRODUCTHUNT_CACHE_FILE", str(cache_file))

    def fake_http_get(url, timeout=8, proxy=None, headers=None):
        return MOCK_PH_RSS.encode("utf-8")

    monkeypatch.setattr(OS, "_http_get", fake_http_get)

    items = OS.fetch_product_hunt(top=5)
    assert len(items) == 1
    it = items[0]
    assert "Cursor Composer" in it["title"]
    assert "producthunt.com" in it["link"]
    assert it["source"] == "ProductHunt"
    assert os.path.exists(cache_file)


def test_fetch_reddit_ai_mocked(monkeypatch, tmp_path):
    """验证 Reddit RSS 解析与 429 缓存降级机制。"""
    cache_file = tmp_path / "rd_cache.json"
    monkeypatch.setattr(OS, "REDDIT_CACHE_FILE", str(cache_file))

    def fake_http_get(url, timeout=8, proxy=None, headers=None):
        return MOCK_REDDIT_RSS.encode("utf-8")

    monkeypatch.setattr(OS, "_http_get", fake_http_get)

    items = OS.fetch_reddit_ai(top=5)
    assert len(items) == 1
    it = items[0]
    assert "Qwen 2.5 72B" in it["title"]
    assert "reddit.com/r/LocalLLaMA" in it["link"]
    assert it["badge"] == "🤖 Reddit AI"

    # 测试网络异常时自动降级到刚才写入的缓存
    def fake_http_fail(url, timeout=8, proxy=None, headers=None):
        raise RuntimeError("HTTP 429 Too Many Requests")

    monkeypatch.setattr(OS, "_http_get", fake_http_fail)
    cached_items = OS.fetch_reddit_ai(top=5)
    assert len(cached_items) == 1
    assert "Qwen 2.5 72B" in cached_items[0]["title"]


def test_fetch_all_overseas_categorized(monkeypatch):
    """验证多源并行聚合返回 4 大分区。"""
    monkeypatch.setattr(OS, "fetch_x_kol_and_trends", lambda top=10: [{"title": "X热点测试", "link": "https://x.com"}])
    monkeypatch.setattr(OS, "fetch_google_trends", lambda top=10: [{"title": "Google趋势测试", "link": "https://google.com"}])
    monkeypatch.setattr(OS, "fetch_hacker_news", lambda top=8: [{"title": "HN测试", "link": "https://news.ycombinator.com"}])
    monkeypatch.setattr(OS, "fetch_github_trending", lambda top=8: [{"title": "GH测试", "link": "https://github.com"}])
    monkeypatch.setattr(OS, "fetch_product_hunt", lambda top=8: [{"title": "PH测试", "link": "https://producthunt.com"}])
    monkeypatch.setattr(OS, "fetch_reddit_ai", lambda top=8: [{"title": "RD测试", "link": "https://reddit.com"}])

    res = OS.fetch_all_overseas_categorized()
    assert "x_trends" in res
    assert "google_trends" in res
    assert "geek_dev" in res
    assert "product_community" in res

    assert len(res["x_trends"]) == 1
    assert len(res["google_trends"]) == 1
    assert len(res["geek_dev"]) == 2  # HN + GH
    assert len(res["product_community"]) == 2  # PH + RD
