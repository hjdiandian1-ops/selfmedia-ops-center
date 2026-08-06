#!/usr/bin/env python3
import os
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-08-04_DeepSeek_V4_Flash_AgenticAI"
XHS_HTML = os.path.join(OUTPUT_DIR, "小红书/rednote_slides.html")

def render_xhs():
    print("🎨 正在使用 Swiss International 设计系统重新渲染小红书 1080×1440 高清卡片...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 6500}, device_scale_factor=1)
        page.goto(f"file://{XHS_HTML}")
        page.wait_for_selector(".poster.xhs")
        posters = page.query_selector_all(".poster.xhs")
        for i, poster in enumerate(posters):
            img_path = os.path.join(OUTPUT_DIR, f"小红书/xhs-0{i+1}.png")
            poster.screenshot(path=img_path)
            print(f"  ✨ [1080×1440 Swiss 级] 卡片 xhs-0{i+1}.png 导出成功: {img_path}")
        browser.close()

if __name__ == "__main__":
    render_xhs()
