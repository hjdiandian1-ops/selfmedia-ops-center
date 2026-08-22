# -*- coding: utf-8 -*-
"""原文正文抓取器单测（纯函数，不触网）。"""
import os
import sys

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import fetch_source_content as FSC  # noqa: E402


def test_extract_main_text_prefers_article_and_strips_noise():
    html = (
        "<html><head><script>var x=1;</script><style>.a{color:red}</style></head>"
        "<body><nav>导航文字</nav><article>"
        "<h1>标题</h1><p>第一段真实内容。</p><p>第二段内容。</p>"
        "</article></body></html>"
    )
    text = FSC.extract_main_text(html)
    assert "第一段真实内容" in text
    assert "第二段内容" in text
    assert "var x=1" not in text
    assert "导航文字" not in text


def test_extract_main_text_handles_empty():
    assert FSC.extract_main_text("") == ""
    assert FSC.extract_main_text(None) == ""


def test_related_matches_keywords():
    rows = [
        ("AI客服国标出台", "https://a.com/1"),
        ("今天天气晴朗", "https://a.com/2"),
        ("AI客服乱象频发", "https://a.com/3"),
    ]
    rel = FSC._related("AI客服", rows, 5)
    assert len(rel) == 2
    assert all("AI客服" in t for t, _ in rel)


def test_fetch_url_text_rejects_non_public_urls():
    # 非 http/https 或内网地址直接拒绝，不触网
    assert FSC.fetch_url_text("") == ""
    assert FSC.fetch_url_text("file:///etc/passwd") == ""
    assert FSC.fetch_url_text("http://127.0.0.1:8787") == ""
