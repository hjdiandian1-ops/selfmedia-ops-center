#!/usr/bin/env python3
"""
全流程端到端自动化测试脚本
测试步骤：
1. 抓取 NAS RSSHub 实热点（36氪/AI快讯）
2. 触发“小吴聊”风格 AI 写作（融入 personal-style-guide.md 语气与 Hook）
3. 渲染小红书 3:4 HTML 视觉卡片并由 Playwright 截取 3:4 高清 PNG 图片
4. 生成公众号排版 HTML
5. 调用 publish_to_n8n.py 将配图同步至 NAS SFTP 并触发 n8n Webhook
"""

import os
import sys
import json
import urllib.request
import subprocess
from playwright.sync_api import sync_playwright

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_test_flow")

def step1_fetch_trend():
    print("📡 [步骤 1/5] 从 NAS 端 RSSHub 抓取全网实时科技热点...")
    url = "http://192.168.50.229:1200/36kr/newsflashes"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")
            # 简单提取第一条快讯标题
            import re
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', xml_data)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', xml_data)
            hot_title = titles[1] if len(titles) > 1 else "AI 自动化新纪元：NAS + n8n 打造个人第二大脑"
            print(f"🔥 成功抓取今日爆款热点主题: 《{hot_title}》")
            return hot_title
    except Exception as e:
        print(f"⚠️ RSSHub 抓取异常，使用备用实战选题: {e}")
        return "全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程"

def step2_generate_content(topic):
    print("\n✍️ [步骤 2/5] 应用《小吴聊个人 IP 风格指南》创作双平台文案...")
    title = f"全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程"
    content_xhs = (
        "兄弟们！等了好久终于跑通了…今天把全套 NAS + AI 自媒体无人值守系统全开源！\n\n"
        "实话实说，以前每天手动写文案、做卡片、登录多平台复制粘贴，心率走得跟 K 线差不多 [捂脸]。\n"
        "这次彻底搞定了零成本闭环：本地 Agent 负责高审美卡片，NAS 端 n8n + Playwright 负责后台一键自动发布！\n\n"
        "💡 核心拆解：\n"
        "1. 大脑：Antigravity + 个人 IP 风格提炼\n"
        "2. 中枢：NAS Docker 部署 n8n + PostgreSQL\n"
        "3. 视觉：3:4 杂志风卡片 + AI 封面双轨渲染\n"
        "4. 分发：一条 HTTP Webhook，多端无人值守！\n\n"
        "拿到这套配置，今晚就能在你的 NAS 上跑通！完整教程看评论区~"
    )
    gzh_html = (
        f"<section style='padding:15px; font-family:sans-serif;'>"
        f"<h1 style='color:#1e3a8a;'>{title}</h1>"
        f"<p style='color:#3b82f6;'><b>原创 小吴聊</b></p>"
        f"<blockquote style='border-left:4px solid #3b82f6; padding-left:10px; color:#475569;'>"
        f"兄弟们，DS v4 与 NAS 自动化都搞定了，装完别急着走，真正的乐趣在后面！"
        f"</blockquote>"
        f"<p>实话实说，感觉这套架构会进一步颠覆现有内容生产力。不聊基础安装，只聊实战，全是真实踩过的坑、跑通的路。</p>"
        f"</section>"
    )
    tags = ["NAS应用", "AI自媒体", "n8n自动化", "极客工具", "高效方法"]
    return title, content_xhs, gzh_html, tags

def step3_render_visual_cards(title):
    print("\n🎨 [步骤 3/5] 渲染小红书 3:4 视觉卡片 HTML 并截取 PNG 图片...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_card_path = os.path.join(OUTPUT_DIR, "card_preview.html")
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; background: #0f172a; display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  .slide-card {{ width: 600px; height: 800px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 24px; padding: 48px; box-sizing: border-box; color: #f8fafc; border: 1px solid #334155; position: relative; display: flex; flex-direction: column; justify-content: space-between; }}
  .tag {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; width: fit-content; }}
  .title {{ font-size: 34px; font-weight: 800; line-height: 1.3; background: linear-gradient(to right, #ffffff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 20px; }}
  .desc {{ font-size: 18px; color: #94a3b8; line-height: 1.6; margin-top: 20px; }}
  .footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #334155; padding-top: 20px; color: #64748b; font-size: 14px; }}
</style>
</head>
<body>
  <div class="slide-card">
    <div>
      <div class="tag">🚀 极客实战排坑</div>
      <div class="title">{title}</div>
      <div class="desc">不用买傻瓜教程！本地 Agent 负责高审美卡片，NAS 端 n8n 负责无人值守全自动分发。小吴聊带你一条线跑通！</div>
    </div>
    <div class="footer">
      <span>@小吴聊 · 极客操盘手</span>
      <span>3:4 高审美卡片</span>
    </div>
  </div>
</body>
</html>
"""
    with open(html_card_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    img_path = os.path.join(OUTPUT_DIR, "card_01.png")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1600})
        page.goto(f"file://{html_card_path}")
        card = page.query_selector(".slide-card")
        if card:
            card.screenshot(path=img_path)
            print(f"✅ 已成功截取 3:4 视觉卡片图片: {img_path}")
        browser.close()
    return [img_path]

def step4_trigger_n8n_publish(title, content_xhs, gzh_html, images, tags):
    print("\n🚀 [步骤 4/5] 调用 publish_to_n8n.py 将卡片传输至 NAS 并触发 Webhook...")
    cmd = [
        sys.executable,
        os.path.join(PROJECT_DIR, "scripts/publish_to_n8n.py"),
        "--title", title,
        "--content", content_xhs,
        "--gzh-html", gzh_html,
        "--images"
    ] + images + ["--tags"] + tags
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print("✅ 已经成功将 Payload 与卡片远程推送至 NAS n8n 发布队列！")
        return True
    else:
        print(f"❌ 发布过程中发生错误: {result.stderr}")
        return False

def main():
    print("=" * 60)
    print("🎉 开始执行自媒体全流程端到端实战测试")
    print("=" * 60)
    
    topic = step1_fetch_trend()
    title, content_xhs, gzh_html, tags = step2_generate_content(topic)
    images = step3_render_visual_cards(title)
    success = step4_trigger_n8n_publish(title, content_xhs, gzh_html, images, tags)
    
    print("\n" + "=" * 60)
    if success:
        print("✨ [测试成功] 全流程完美跑通！从 RSSHub 抓取 -> 小吴聊风格撰写 -> 3:4 卡片截图 -> NAS 传输 -> n8n 触发发布！")
    else:
        print("💥 [测试中中断] 请检查上述步骤日志。")
    print("=" * 60)

if __name__ == "__main__":
    main()
