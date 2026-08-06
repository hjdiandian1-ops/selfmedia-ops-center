# -*- coding: utf-8 -*-
"""
小红书 n8n + Playwright 4图全自动渲染与发布脚本
路径：/Users/xiaowuliao/Projects/自媒体发布agent/auto_publish_xiaohongshu.py
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
COOKIES_PATH = os.path.join(PROJECT_DIR, "xiaohongshu_cookies.json")

def render_html_slides_to_images(html_file_path, output_dir):
    """ 第一步：使用 Playwright 将 4 个 HTML 卡片渲染并截图保存为 3:4 高清 PNG 图片 """
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 2000})
        page.goto(f"file://{html_file_path}")
        page.wait_for_selector(".slide-card")
        
        cards = page.query_selector_all(".slide-card")
        print(f"📷 正在自动截取 {len(cards)} 张 3:4 图文卡片...")
        
        for index, card in enumerate(cards):
            img_path = os.path.join(output_dir, f"card_{index+1:02d}.png")
            card.screenshot(path=img_path)
            image_paths.append(img_path)
            print(f"  ✓ 已生成卡片 {index+1}: {img_path}")
            
        browser.close()
    return image_paths

def publish_to_xiaohongshu(title, content_text, tags, image_paths):
    """ 第二步：登录小红书创作者服务平台，多图一次性上传并发布 """
    if not os.path.exists(COOKIES_PATH):
        print(f"❌ 未找到登录 Session 文件 {COOKIES_PATH}！请先运行初始化登录。")
        return False
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # 可改成 True 后台无头运行
        context = browser.new_context(storage_state=COOKIES_PATH)
        page = context.new_page()
        
        print("🌐 正在打开小红书创作者发布后台...")
        page.goto("https://creator.xiaohongshu.com/creator/post")
        page.wait_for_selector('input[type="file"]', timeout=30000)
        
        # 1. 一次性上传 4 张图片（第一张自动为封面，后续为图文卡）
        print(f"📤 正在上传 {len(image_paths)} 张图片（封面 + 正文卡片）...")
        page.set_input_files('input[type="file"]', image_paths)
        time.sleep(5) # 等待图片上传解析完成
        
        # 2. 填写标题
        print("✍️ 正在填写笔记标题...")
        page.fill('input[placeholder*="标题"]', title)
        
        # 3. 填写正文与标签
        print("✍️ 正在填写正文与标签...")
        full_text = content_text + "\n\n" + " ".join([f"#{t}" for t in tags])
        page.fill('div[contenteditable="true"]', full_text)
        
        time.sleep(2)
        # 4. 点击发布
        print("🚀 点击发布...")
        page.click('button:has-text("发布")')
        time.sleep(5)
        print("🎉 小红书多图文笔记全自动发布成功！")
        browser.close()
    return True

if __name__ == "__main__":
    # 示例调用
    html_path = os.path.join(PROJECT_DIR, "rednote_august_market_slides.html")
    img_dir = os.path.join(PROJECT_DIR, "output_images")
    
    # 1. 自动截取 4 张图
    images = render_html_slides_to_images(html_path, img_dir)
    
    # 2. 从参数或指定变量获取文案
    sample_title = "8月策略：绝望中孕育希望，市场底何时到来？"
    sample_content = "从上周二国家队带头反攻，市场经历了暴力反弹到持续缩量回落...\n完整宏观拆解与8月三大主线请看图文卡片！"
    sample_tags = ["A股", "股市复盘", "8月策略", "宏观经济", "理财干货"]
    
    # 3. 自动发布
    # publish_to_xiaohongshu(sample_title, sample_content, sample_tags, images)
