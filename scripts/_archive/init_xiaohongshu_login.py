# -*- coding: utf-8 -*-
"""
小红书创作者服务平台 - 首次扫码登录并保存 Session 脚本
运行方法：python3 init_xiaohongshu_login.py
"""

import os
from playwright.sync_api import sync_playwright

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
COOKIES_PATH = os.path.join(PROJECT_DIR, "nas-n8n", "shared_files", "xhs_cookies.json")

def init_login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://creator.xiaohongshu.com/creator/post")
        print("👉 请在弹出的 Chrome 窗口中扫码登录小红书创作者服务平台...")
        print("   登录成功后，脚本将自动保存 Session 至 nas-n8n/shared_files/xhs_cookies.json。")
        
        # 等待登录成功后出现头像/发布按钮
        page.wait_for_selector('input[type="file"]', timeout=180000)
        context.storage_state(path=COOKIES_PATH)
        print(f"✅ 登录成功！Session 已成功保存至: {COOKIES_PATH}")
        browser.close()

if __name__ == "__main__":
    init_login()
