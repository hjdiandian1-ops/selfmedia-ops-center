#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书发布 · 本地有头半自动模式（人工终审）
============================================
自动完成：登录（复用 NAS 同步的 Cookie）→ 点“上传图文”→ 上传图片 →
填标题/正文/标签 → 保留浏览器窗口，由用户亲自点击右下角【发布】。

用法：
    /Users/xiaowuliao/.workbuddy/binaries/python/envs/default/bin/python \
        scripts/xhs_manual_publish.py \
        --title "标题" --content-file outputs/<job>/小红书/文案.md \
        --images outputs/<job>/小红书/xhs-01.png outputs/<job>/小红书/xhs-02.png \
        --tags AI 一人公司
"""
import argparse
import os
import sys
import time

from playwright.sync_api import sync_playwright

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES_PATH = os.path.join(PROJECT_DIR, "nas-n8n", "shared_files", "xhs_cookies.json")

DEFAULT_TITLE = "一个人拍短剧，72 小时流水 50 万美元"
DEFAULT_IMAGES = [
    os.path.join(PROJECT_DIR, "outputs/2026-08-06_AI短剧出海一人公司/小红书/xhs-01.png"),
    os.path.join(PROJECT_DIR, "outputs/2026-08-06_AI短剧出海一人公司/小红书/xhs-02.png"),
    os.path.join(PROJECT_DIR, "outputs/2026-08-06_AI短剧出海一人公司/小红书/xhs-03.png"),
    os.path.join(PROJECT_DIR, "outputs/2026-08-06_AI短剧出海一人公司/小红书/xhs-04.png"),
]
DEFAULT_MD = os.path.join(PROJECT_DIR, "outputs/2026-08-06_AI短剧出海一人公司/小红书/文案.md")
DEFAULT_TAGS = ["AI短剧", "出海", "一人公司", "AI工具", "副业", "内容创业"]


def build_content(md):
    text = open(md, encoding="utf-8").read()
    body = text.split("## 📝 笔记正文：", 1)[1]
    lines = []
    for ln in body.splitlines():
        if ln.strip().startswith("数据来源") or ln.strip().startswith("#"):
            break
        lines.append(ln)
    return "\n".join(lines).strip()


def run(title, content_file, images, tags):
    if not os.path.exists(COOKIES_PATH):
        print(f"❌ 未找到 Cookie：{COOKIES_PATH}，请先运行 scripts/init_xiaohongshu_login.py 扫码登录。")
        return
    content = build_content(content_file)
    content += "\n\n" + " ".join(f"#{t}" for t in tags)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=COOKIES_PATH)
        page = context.new_page()

        print("🌐 打开小红书创作者发布页 ...")
        page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
        page.wait_for_timeout(5000)
        if "login" in page.url.lower():
            print("❌ 登录态失效，请先运行 scripts/init_xiaohongshu_login.py 重新扫码。")
            browser.close()
            return

        print("🖱 点击【上传图文】...")
        page.evaluate("""() => {
            const els = [...document.querySelectorAll('*')].filter(e =>
                e.children.length === 0 &&
                (e.textContent || '').trim() === '上传图文');
            if (els.length) els[0].click();
        }""")
        page.wait_for_timeout(6000)

        print("🖼 上传 4 张图片 ...")
        inputs = page.query_selector_all('input[type="file"]')
        multi = [i for i in inputs if i.get_attribute("multiple") is not None]
        target = multi[0] if multi else (inputs[-1] if inputs else None)
        if target:
            target.set_input_files(images)
        page.wait_for_timeout(6000)

        print("✍️ 填写标题 ...")
        try:
            page.wait_for_selector('input[placeholder*="标题"]', timeout=15000).fill(title)
        except Exception as e:
            print("标题填写提示:", e)

        print("📝 填写正文与标签 ...")
        try:
            page.wait_for_selector('div[contenteditable="true"]', timeout=15000).fill(content)
        except Exception as e:
            print("正文填写提示:", e)

        page.wait_for_timeout(3000)
        print("")
        print("✅ 内容已全部填好！请在弹出的浏览器窗口中检查：")
        print("   1) 4 张图片、标题、正文、标签是否完整")
        print("   2) 点击右下角红色【发布】按钮完成发布")
        print("⏳ 浏览器将保持打开 10 分钟；发布完成后可直接关闭窗口。")
        time.sleep(600)
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="小红书半自动发布（人工终审）")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--content-file", default=DEFAULT_MD)
    ap.add_argument("--images", nargs="*", default=DEFAULT_IMAGES)
    ap.add_argument("--tags", nargs="*", default=DEFAULT_TAGS)
    args = ap.parse_args()
    run(args.title, args.content_file, args.images, args.tags)
