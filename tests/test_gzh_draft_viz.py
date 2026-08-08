# -*- coding: utf-8 -*-
"""公众号推送图表图卡化：组件提取与替换（纯逻辑，不触网、不启浏览器）。"""
import os
import sys

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from gzh_draft_api import extract_viz_components, replace_viz_with_images  # noqa: E402


CONTENT = (
    '<p>开头</p>'
    '<section data-viz="table" style="a">A块</section>'
    '<p>中间</p>'
    '<section data-viz="bar" style="b">B块</section>'
    '<p>结尾</p>'
)


def test_extract_viz_components():
    blocks = extract_viz_components(CONTENT)
    assert len(blocks) == 2
    assert blocks[0].startswith('<section data-viz="table"')
    assert blocks[1].startswith('<section data-viz="bar"')
    assert "A块" in blocks[0]


def test_replace_viz_with_images():
    calls = []

    def uploader(blk, idx):
        calls.append((blk, idx))
        return f"https://img.example/{idx}.png"

    new, n = replace_viz_with_images(CONTENT, uploader)
    assert n == 2
    assert "<section" not in new
    assert '<img src="https://img.example/1.png"' in new
    assert '<img src="https://img.example/2.png"' in new
    assert "开头" in new and "结尾" in new
    assert len(calls) == 2


def test_replace_empty_content():
    new, n = replace_viz_with_images("<p>没有组件</p>", lambda blk, idx: "")
    assert n == 0
    assert new == "<p>没有组件</p>"
