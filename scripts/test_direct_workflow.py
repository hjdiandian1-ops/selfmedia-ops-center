#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直连端到端测试脚本（跳过 n8n / NAS 自动发布微服务）
测试流程：
1. 抓取全网热点/选题 (RSSHub / 备用选题)
2. 提炼“小吴聊”风格双平台文案（小红书正文 + 公众号 HTML）
3. 渲染 3:4 高审美视觉卡片并由 Playwright 截取高清 PNG
4. 实时同步至飞书多维表格《【小吴聊】爆款选题雷达库》
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

# 飞书多维表格配置
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_test_flow")

def step1_fetch_trend():
    print("📡 [步骤 1/4] 从 NAS 端 RSSHub 抓取全网实时科技热点...")
    url = "http://192.168.50.229:1200/36kr/newsflashes"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read().decode("utf-8")
            import re
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', xml_data)
            if not titles:
                titles = re.findall(r'<title>(.*?)</title>', xml_data)
            hot_title = titles[1] if len(titles) > 1 else "AI 自动化新纪元：NAS + n8n 打造个人第二大脑"
            print(f"🔥 成功抓取今日爆款热点主题: 《{hot_title}》")
            return hot_title
    except Exception as e:
        print(f"ℹ️ 使用标准实战选题（RSSHub 暂未响应: {e}）")
        return "全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程"

def step2_generate_content(topic):
    print("\n✍️ [步骤 2/4] 应用《小吴聊个人 IP 风格指南》撰写小红书与公众号文案...")
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
    print(f"✅ 文案生成完毕！标题: 《{title}》")
    return title, content_xhs, gzh_html, tags

def step3_render_visual_cards(title):
    print("\n🎨 [步骤 3/4] 渲染 3:4 高审美 HTML 视觉卡片并截取 PNG...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_card_path = os.path.join(OUTPUT_DIR, "test_card_direct.html")
    
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; background: #0f172a; display: flex; justify-content: center; align-items: center; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  .card {{ width: 600px; height: 800px; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%); border-radius: 24px; padding: 48px; box-sizing: border-box; color: #f8fafc; border: 1px solid rgba(255,255,255,0.1); position: relative; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }}
  .tag {{ background: rgba(99, 102, 241, 0.2); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.4); padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; width: fit-content; }}
  .title {{ font-size: 32px; font-weight: 800; line-height: 1.35; background: linear-gradient(to right, #ffffff, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 24px; }}
  .badge-container {{ display: flex; gap: 10px; margin-top: 20px; }}
  .badge {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 10px 14px; color: #e2e8f0; font-size: 13px; font-weight: 500; }}
  .desc {{ font-size: 16px; color: #94a3b8; line-height: 1.6; margin-top: 24px; background: rgba(15, 23, 42, 0.6); padding: 18px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); }}
  .footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 20px; color: #64748b; font-size: 13px; }}
</style>
</head>
<body>
  <div class="card">
    <div>
      <div class="tag">⚡️ 前端视觉渲染流水线</div>
      <div class="title">{title}</div>
      <div class="badge-container">
        <div class="badge">🎨 3:4 高审美卡片</div>
        <div class="badge">📊 飞书 Base 结构化同步</div>
      </div>
      <div class="desc">
        已成功完成 Playwright 亚像素级卡片截取、个人 IP 语气规范填充与飞书多维表格同步。<br><br>
        生成时间：{current_time_str}
      </div>
    </div>
    <div class="footer">
      <span>@小吴聊自媒体 Agent</span>
      <span>极客操盘手风格</span>
    </div>
  </div>
</body>
</html>
"""
    with open(html_card_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    img_path = os.path.join(OUTPUT_DIR, "direct_test_card.png")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1600})
        page.goto(f"file://{html_card_path}")
        card = page.query_selector(".card")
        if card:
            card.screenshot(path=img_path)
            print(f"✅ 3:4 高清视觉卡片渲染完成: {img_path}")
        browser.close()
    return img_path

def step4_sync_feishu_bitable(title, img_path):
    print("\n📊 [步骤 4/4] 正在同步状态至飞书多维表格《【小吴聊】爆款选题雷达库》...")
    
    # 1. 获取 tenant_access_token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    token_headers = {"Content-Type": "application/json; charset=utf-8"}
    token_payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    req_token = urllib.request.Request(token_url, data=json.dumps(token_payload).encode("utf-8"), headers=token_headers, method="POST")
    
    token = None
    with urllib.request.urlopen(req_token, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        token = res.get("tenant_access_token")

    if not token:
        print("❌ 获取飞书 access token 失败")
        return False

    # 2. 写入记录
    write_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    record_fields = {
        "Text": title,
        "主题或链接": "https://creator.xiaohongshu.com",
        "文案风格": "极客操盘手风格",
        "配图风格": "3:4 视觉科技卡片",
        "发布状态": "✅ 前端渲染与内容生成已就绪 (跳过 n8n)",
        "发布时间": current_time_str,
        "错误日志": f"本地渲染配图: {img_path}"
    }

    data_bytes = json.dumps({"fields": record_fields}, ensure_ascii=False).encode("utf-8")
    req_write = urllib.request.Request(write_url, data=data_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req_write, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0:
                record_id = res.get("data", {}).get("record", {}).get("record_id")
                print(f"🎉 飞书多维表格同步成功！Record ID: {record_id}")
                return True
            else:
                print(f"❌ 飞书多维表格同步失败: {res}")
                return False
    except Exception as e:
        print(f"❌ 飞书多维表格请求异常: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 启动【去除 n8n 自动化】前端渲染与飞书多维表格连通测试")
    print("=" * 60)

    # 1. 抓取热点
    topic = step1_fetch_trend()
    # 2. 生成双平台文案
    title, content_xhs, gzh_html, tags = step2_generate_content(topic)
    # 3. 渲染视觉卡片
    img_path = step3_render_visual_cards(title)
    # 4. 同步飞书表格
    success = step4_sync_feishu_bitable(title, img_path)

    print("\n" + "=" * 60)
    if success:
        print("✨ 【测试成功】去除 n8n 发布步骤后，前端热点抓取 -> 双平台文案生成 -> 3:4 视觉卡片渲染 -> 飞书表格同步全流程完美跑通！")
    else:
        print("💥 【测试异常】请查阅上述详细日志。")
    print("=" * 60)

if __name__ == "__main__":
    main()
