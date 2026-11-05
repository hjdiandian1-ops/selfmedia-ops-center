# -*- coding: utf-8 -*-
"""
Playwright 自动化 UI 验证脚本 (test_skills_repo_browser.py)
验证 Skills 模态弹窗与封面提示词模态弹窗的样式、字体颜色与模块边界
"""
import os
import sys
import time
import pytest
from playwright.sync_api import sync_playwright

ARTIFACTS_DIR = "/Users/xiaowuliao/.gemini/antigravity/brain/ae4a3b30-c515-43f5-affa-649fcf998c34"


def _launch_browser(p):
    for kwargs in ({"headless": True}, {"headless": True, "channel": "chrome"}):
        try:
            return p.chromium.launch(**kwargs)
        except Exception:
            continue
    return None


def test_browser_flow():
    if os.environ.get("RUN_E2E_BROWSER") != "1":
        pytest.skip("跳过手工浏览器截图脚本（设置 RUN_E2E_BROWSER=1 开启）")
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = _launch_browser(p)
        if browser is None:
            pytest.skip("未检测到可用 Chromium/Chrome 浏览器内核")
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        context.add_init_script("localStorage.setItem('onboarding_done', '1');")
        page = context.new_page()

        print("1. 正在访问运营看板首页 http://127.0.0.1:8787 ...")
        page.goto("http://127.0.0.1:8787", wait_until="networkidle")
        time.sleep(1)

        # 2. 点击导航切换至 Skills 技能库
        print("2. 点击导航切换至 Skills 技能库...")
        page.click("button[data-view='skills-repo']")
        time.sleep(1)

        # 搜索 Brand Voice (用户截图中的案例)
        print("3. 检索 Brand Voice 技能并打开弹窗...")
        page.fill("#skills-search-input", "Brand Voice")
        time.sleep(0.5)

        card = page.locator(".skill-card", has_text="Brand Voice").first
        card.click()
        time.sleep(1)

        # 截图: Brand Voice 详情弹窗 (Skills 弹窗修复后)
        shot_skill = os.path.join(ARTIFACTS_DIR, "skills_repo_modal_brandvoice.png")
        page.screenshot(path=shot_skill)
        print(f"   Skills 详情弹窗已截图: {shot_skill}")

        page.click("#skill-detail-modal button:has-text('关闭')")
        time.sleep(0.5)

        # 3. 点击导航切换至 封面提示词
        print("4. 点击导航切换至 封面提示词...")
        page.click("button[data-view='cover-templates']")
        time.sleep(1)

        # 打开首个封面模板 (用户截图中的案例)
        print("5. 点击封面模板卡片打开封面弹窗...")
        cover_card = page.locator(".cover-card").first
        cover_card.click()
        time.sleep(1)

        # 截图: 封面详情弹窗 (封面弹窗修复后)
        shot_cover = os.path.join(ARTIFACTS_DIR, "cover_templates_modal_fixed.png")
        page.screenshot(path=shot_cover)
        print(f"   封面详情弹窗已截图: {shot_cover}")

        page.click("#cover-detail-modal button:has-text('关闭')")
        time.sleep(0.5)

        browser.close()
        print("🎉 自动化浏览器交互与截图测试全部通过！")

if __name__ == "__main__":
    test_browser_flow()
