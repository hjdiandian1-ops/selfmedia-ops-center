#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright 自动化截图脚本
=========================
在本地工作台运行状态下，自动截取 8 张高质量高清界面截图并保存至 docs/screenshots/
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")
BASE_URL = os.environ.get("SELFMEDIA_BASE_URL", "http://127.0.0.1:8787")


def capture_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"🚀 开始通过 Playwright 捕获工作台真实截图：{BASE_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. 截取 00-onboarding-demo.png (1280x720, 2x scale)
        ctx00 = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page00 = ctx00.new_page()
        page00.goto(BASE_URL, wait_until="networkidle")
        page00.evaluate("localStorage.clear()")
        page00.reload(wait_until="networkidle")
        page00.evaluate("showOnboardingWizard(true)")
        time.sleep(1)
        path00 = os.path.join(OUT_DIR, "00-onboarding-demo.png")
        page00.screenshot(path=path00)
        print(f"  ✅ [00/07] 00-onboarding-demo.png 已捕获 ({path00})")
        ctx00.close()

        # 2. 截取 01~06 (1920x1080, 2x scale)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("skipOnboardingWizard()")
        time.sleep(1)

        shots = [
            ("01-dashboard-overview.png", "overview", None),
            ("02-topics-radar.png", "topics", None),
            ("03-viral-breakdown.png", "themes", None),
            ("04-production-pipeline.png", "pipeline", None),
            ("05-outputs-preview.png", "outputs", None),
            ("06-qa-trends.png", "data", "switchDataTab('qa')"),
        ]

        for fname, view_name, extra_js in shots:
            page.evaluate(f"switchView('{view_name}')")
            time.sleep(1)
            if extra_js:
                page.evaluate(extra_js)
                time.sleep(1)
            fpath = os.path.join(OUT_DIR, fname)
            page.screenshot(path=fpath)
            print(f"  ✅ 截图已保存：{fname}")

        # 3. 截取 07-theme-showcase.png (1920x720)
        ctx07 = browser.new_context(viewport={"width": 1920, "height": 720}, device_scale_factor=2)
        page07 = ctx07.new_page()
        page07.goto(BASE_URL, wait_until="networkidle")
        page07.evaluate("skipOnboardingWizard()")
        page07.evaluate("document.documentElement.dataset.theme = 'lv-monogram'")
        page07.evaluate("switchView('overview')")
        time.sleep(1)
        path07 = os.path.join(OUT_DIR, "07-theme-showcase.png")
        page07.screenshot(path=path07)
        print(f"  ✅ [07/07] 07-theme-showcase.png 已捕获 ({path07})")
        ctx07.close()

        ctx.close()
        browser.close()

    print("🎉 8 张工作台真实高清截图已全部完成更新！")


if __name__ == "__main__":
    capture_all()
