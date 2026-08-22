# -*- coding: utf-8 -*-
"""热点雷达新增源单测：谷歌趋势 RSS / X 热点 / 代理解析 / 合规初筛。"""
import json
import os
import sys
import urllib.error

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import fetch_hot_topics as FHT  # noqa: E402


GOOGLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item><title>strait of hormuz</title><ht:approx_traffic>500+</ht:approx_traffic><link>https://trends.google.com/a</link></item>
    <item><title>election fraud</title><ht:approx_traffic>100+</ht:approx_traffic><link>https://trends.google.com/b</link></item>
    <item><title>ai video tools</title><ht:approx_traffic>200K+</ht:approx_traffic><link>https://trends.google.com/c</link></item>
  </channel>
</rss>"""


def test_resolve_proxy_chain(monkeypatch):
    monkeypatch.delenv("SELFMEDIA_PROXY", raising=False)
    monkeypatch.delenv("X_SCRAPER_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7897")
    assert FHT.resolve_proxy() == "http://127.0.0.1:7897"

    monkeypatch.setenv("SELFMEDIA_PROXY", "http://127.0.0.1:7890")
    assert FHT.resolve_proxy() == "http://127.0.0.1:7890"


def test_compliance_pass():
    items = [
        {"title": "strait of hormuz"},
        {"title": "election fraud"},
        {"title": "AI 工具价格战"},
        {"title": "赌博网站"},
    ]
    ok, blocked = FHT.compliance_pass(items)
    assert [i["title"] for i in ok] == ["strait of hormuz", "AI 工具价格战"]
    assert set(blocked) == {"election fraud", "赌博网站"}


def test_fetch_source_route_fallback(monkeypatch):
    """RSSHub 单路由 503 时自动尝试备选路由。"""
    calls = []

    def fake_http(url, proxy=None, timeout=20, ua="", allow_private=False):
        calls.append(url)
        if url.endswith("/zhihu/hotlist"):
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", None, None)
        return "<rss><channel><item><title>test</title><link>http://x</link></item></channel></rss>".encode("utf-8")

    monkeypatch.setattr(FHT, "fetch_http", fake_http)
    items = FHT.fetch_source("知乎热榜", ["/zhihu/hotlist", "/zhihu/hot"], 5)
    assert calls == [FHT.BASE + "/zhihu/hotlist", FHT.BASE + "/zhihu/hot"]
    assert items and items[0]["title"] == "test"


def test_fetch_google_trends(monkeypatch):
    def fake_http(url, proxy=None, timeout=20):
        assert "trends.google.com" in url
        assert proxy
        return GOOGLE_RSS.encode("utf-8")

    monkeypatch.setattr(FHT, "fetch_http", fake_http)
    items = FHT.fetch_google_trends(10)
    assert len(items) == 3
    assert items[0]["title"] == "strait of hormuz"
    assert items[0]["traffic"] == "500+"
    assert "需人工复核" in items[0]["compliance"]


def test_fetch_x_trends_http(monkeypatch):
    payload = {"success": True, "trends": [
        {"name": "AI agents", "url": "https://x.com/hashtag/AIagents", "tweet_count": 12345},
        {"name": "election night", "url": "https://x.com/hashtag/x", "tweet_count": 999},
    ]}

    def fake_http(url, proxy=None, timeout=20):
        assert url == "http://x.local/trends"
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    monkeypatch.setattr(FHT, "fetch_http", fake_http)
    monkeypatch.setattr(FHT, "X_TRENDS_URL", "http://x.local/trends")
    items = FHT.fetch_x_trends_http(5)
    assert items[0]["title"] == "AI agents"
    assert items[0]["tweet_count"] == 12345
    assert "需人工复核" in items[0]["compliance"]


def test_fetch_x_trends_disabled(monkeypatch):
    monkeypatch.setattr(FHT, "X_TRENDS_ENABLED", False)
    assert FHT.fetch_x_trends(5) == []
