# -*- coding: utf-8 -*-
"""
High-Resolution Visual Renderer (高审美无损截图渲染器)
====================================================
基于 Playwright 驱动无头 Chromium，实现 2x Retina 级超清像素渲染（3:4 组图 / 公众号配图 / 逻辑图解）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Template

THEMES = {
    "dark-pro": {
        "theme_bg": "#0b0f19",
        "theme_card": "#182234",
        "theme_text": "#f8fafc",
        "theme_text_sub": "#94a3b8",
        "theme_accent": "#38bdf8",
        "theme_border": "#334155",
        "theme_badge": "#0284c7",
    },
    "minimalist-cream": {
        "theme_bg": "#faf7f2",
        "theme_card": "#ffffff",
        "theme_text": "#1e293b",
        "theme_text_sub": "#64748b",
        "theme_accent": "#ea580c",
        "theme_border": "#e2e8f0",
        "theme_badge": "#c2410c",
    },
    "cyber-neon": {
        "theme_bg": "#09090b",
        "theme_card": "#18181b",
        "theme_text": "#fafafa",
        "theme_text_sub": "#a1a1aa",
        "theme_accent": "#a855f7",
        "theme_border": "#3f3f46",
        "theme_badge": "#9333ea",
    },
    "lux-caramel": {
        "theme_bg": "#211510",
        "theme_card": "#332219",
        "theme_text": "#fef3c7",
        "theme_text_sub": "#d97706",
        "theme_accent": "#f59e0b",
        "theme_border": "#78350f",
        "theme_badge": "#b45309",
    }
}


def render_html_to_image(
    html_content: str,
    output_path: str,
    width: int = 1080,
    height: int = 1440,
    device_scale: int = 2,
) -> str:
    """
    使用 Playwright 将 HTML 渲染为 2x Retina 高清 PNG 图片
    """
    from playwright.sync_api import sync_playwright

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=device_scale,
        )
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(path=str(out), type="png")
        browser.close()

    return str(out)


def render_xhs_slide_deck(
    slides: List[Dict[str, Any]],
    output_dir: str = "./outputs/images/xhs",
    theme_name: str = "dark-pro",
    author: str = "自媒体运营工厂",
) -> List[str]:
    """
    批量渲染小红书 3:4 组图
    """
    template_path = Path(__file__).parent / "templates" / "xhs_card.html"
    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = Template(f.read())

    theme = THEMES.get(theme_name, THEMES["dark-pro"])
    out_paths = []
    total = len(slides)

    for idx, slide in enumerate(slides, 1):
        ctx = {
            **theme,
            "title": slide.get("headline", f"第{idx}页"),
            "tag": slide.get("tag", "核心干货"),
            "page_index": f"{idx:02d}",
            "total_pages": f"{total:02d}",
            "headline": slide.get("headline", ""),
            "items": slide.get("items", []),
            "author": author,
            "callout": slide.get("callout", "点赞收藏不迷路 🚀"),
        }
        rendered_html = tmpl.render(ctx)
        img_file = os.path.join(output_dir, f"slide_{idx:02d}.png")
        render_html_to_image(rendered_html, img_file, width=1080, height=1440, device_scale=2)
        out_paths.append(img_file)

    return out_paths
