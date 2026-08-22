# -*- coding: utf-8 -*-
"""
Phase 3 QA Gate: 视觉排版与出图自动化测试套件
===========================================
"""

import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..")))

from src.selfmedia.visual.cover_checker import check_cover_spec
from src.selfmedia.visual.diagrams import generate_pipeline_diagram_html
from src.selfmedia.visual.renderer import (
    render_html_to_image,
    render_xhs_slide_deck,
    THEMES,
)


class TestVisualDesignAndSpecs:
    """视觉与封面规范测试"""

    def test_cover_spec_validation(self):
        good = check_cover_spec("【保姆级教程】自媒体全自动内容工厂🔥", items_count=3)
        assert good["passed"] is True

        too_long = check_cover_spec("这是一个非常非常非常非常非常非常非常非常非常非常长的没有亮点的标题", items_count=8)
        assert too_long["passed"] is False
        assert len(too_long["issues"]) >= 2

    def test_generate_pipeline_diagram(self):
        steps = [
            {"title": "公域情报抓取", "desc": "多源探测公众号低粉爆款与热搜", "icon": "📡"},
            {"title": "素材事实契约", "desc": "提取量化数据与关键冲突", "icon": "📝"},
            {"title": "去AI味门禁", "desc": "22条硬性规则彻底去套话", "icon": "🛡️"},
        ]
        html = generate_pipeline_diagram_html(steps, title="自媒体工业化生产链路")
        assert "<!DOCTYPE html>" in html
        assert "公域情报抓取" in html
        assert "STEP 01" in html


class TestHeadlessRenderer:
    """Playwright 无头渲染引擎测试"""

    def test_render_single_card(self, tmp_path):
        out_png = tmp_path / "test_card.png"
        sample_html = """<!DOCTYPE html>
        <html><body style="width:1080px;height:1440px;background:#0f172a;color:#fff;display:flex;align-items:center;justify-content:center;">
        <h1 style="font-size:60px;">Playwright 2x Retina Test</h1>
        </body></html>"""

        rendered = render_html_to_image(sample_html, str(out_png), width=1080, height=1440, device_scale=2)
        assert Path(rendered).exists()
        assert Path(rendered).stat().st_size > 1000

    def test_render_xhs_deck(self, tmp_path):
        deck_data = [
            {
                "headline": "自媒体内容工厂 <span>01</span>",
                "tag": "SOP全景",
                "items": [
                    {"icon": "📍", "content": "<strong>全域雷达：</strong>自动抓取低粉高赞文章"},
                    {"icon": "⚡", "content": "<strong>四重质检：</strong>Harsh Critic 80分把关"},
                ],
                "callout": "建议收藏实操 🔥",
            },
            {
                "headline": "为什么必须去 <span>AI味</span>",
                "tag": "核心痛点",
                "items": [
                    {"icon": "❌", "content": "传统AI文案：充满套话与宏大叙事"},
                    {"icon": "✅", "content": "工业化生产：只保留真实量化数据"},
                ],
                "callout": "点赞关注不迷路 🚀",
            }
        ]
        out_files = render_xhs_slide_deck(deck_data, output_dir=str(tmp_path), theme_name="dark-pro")
        assert len(out_files) == 2
        for f in out_files:
            assert Path(f).exists()
            assert Path(f).stat().st_size > 5000
