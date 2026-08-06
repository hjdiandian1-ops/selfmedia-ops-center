#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号（mp.weixin.qq.com）首次扫码登录并保存 Session 脚本
=========================================================
公众号草稿箱链路需要 NAS 端存在 /data/shared/gzh_cookies.json，
本脚本在本地登录后把 Session 保存到 nas-n8n/shared_files/gzh_cookies.json，
该目录与 NAS 容器挂载路径对应。

用法（建议使用项目受管 Python）：
    /Users/xiaowuliao/.workbuddy/binaries/python/envs/default/bin/python \
        scripts/init_gzh_login.py
"""
import os
import time

from playwright.sync_api import sync_playwright

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES_PATH = os.path.join(PROJECT_DIR, "nas-n8n", "shared_files", "gzh_cookies.json")


def init_login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://mp.weixin.qq.com/")
        print("👉 请在弹出的浏览器中扫码登录公众号后台...")
        print(f"   登录成功后，Session 将保存至 {COOKIES_PATH}")

        ok = False
        for _ in range(240):  # 最多等待 12 分钟
            has_token = "token=" in page.url
            if not has_token:
                try:
                    has_token = bool(page.evaluate("window.token || ''"))
                except Exception:
                    pass
            if has_token:
                time.sleep(2)
                ok = True
                break
            time.sleep(3)
        if not ok:
            browser.close()
            raise SystemExit("❌ 登录超时（10 分钟未完成扫码）")

        os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
        context.storage_state(path=COOKIES_PATH)
        print(f"✅ 登录成功！Session 已保存至: {COOKIES_PATH}")
        print("   下一步：把该文件同步到 NAS /volume1/docker/n8n/shared_files/gzh_cookies.json")
        browser.close()


if __name__ == "__main__":
    init_login()
