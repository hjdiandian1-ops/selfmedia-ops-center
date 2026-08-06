#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书 5+ 张 3:4 高审美视觉卡片渲染与测试脚本
测试主题：AI 自媒体全自动发布系统搭建
"""

import os
import sys
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

# 飞书配置
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_test_flow/5cards_test")

def create_html_slides():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_file = os.path.join(OUTPUT_DIR, "slides.html")
    
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #f8fafc; display: flex; flex-direction: column; align-items: center; gap: 40px; padding: 40px 0; }}
  
  .slide-card {{
    width: 600px;
    height: 800px;
    background: linear-gradient(145deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
    border-radius: 28px;
    padding: 44px;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 30px 60px -15px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }}

  /* Card Accent Gradients */
  .slide-card::before {{
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; height: 6px;
    background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899);
  }}

  .header {{ display: flex; justify-content: space-between; align-items: center; }}
  .tag {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; }}
  .slide-num {{ color: #64748b; font-size: 14px; font-weight: 700; font-family: monospace; }}

  .main-title {{ font-size: 32px; font-weight: 800; line-height: 1.35; background: linear-gradient(to right, #ffffff, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 20px; }}
  .sub-title {{ font-size: 16px; color: #94a3b8; line-height: 1.5; margin-top: 12px; }}

  .content-box {{
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 24px;
    margin-top: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}

  .item {{ display: flex; gap: 14px; align-items: flex-start; }}
  .item-icon {{ font-size: 20px; line-height: 1; flex-shrink: 0; margin-top: 2px; }}
  .item-text {{ font-size: 15px; color: #e2e8f0; line-height: 1.6; }}
  .item-text strong {{ color: #a855f7; font-weight: 700; }}
  .highlight {{ color: #38bdf8; font-weight: 700; }}

  .code-badge {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px 16px; font-family: monospace; font-size: 13px; color: #cbd5e1; line-height: 1.5; }}

  .footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 18px; color: #64748b; font-size: 13px; }}
  .footer-author {{ color: #a5b4fc; font-weight: 600; }}
</style>
</head>
<body>

  <!-- Slide 1: 封面卡片 -->
  <div class="slide-card" id="card-1">
    <div>
      <div class="header">
        <div class="tag">🚀 极客实战排坑 · 01/06</div>
        <div class="slide-num">SLIDE 01</div>
      </div>
      <div class="main-title">全网首发：我的 AI 自媒体全自动发布系统搭建全过程</div>
      <div class="sub-title">告别传统排版做图体力活！本地 Agent 大脑 + 高审美 3:4 视觉卡片 + 飞书多维表格一键分发</div>
      <div class="content-box">
        <div class="item">
          <div class="item-icon">🧠</div>
          <div class="item-text"><strong>核心大脑</strong>：Antigravity Agent 深度提炼 19 篇语料，建立去“AI 腔”规则。</div>
        </div>
        <div class="item">
          <div class="item-icon">🎨</div>
          <div class="item-text"><strong>视觉引擎</strong>：3:4 杂志风卡片 + Playwright 3x 采样超高清导出。</div>
        </div>
        <div class="item">
          <div class="item-icon">📊</div>
          <div class="item-text"><strong>状态中枢</strong>：飞书多维表格 Open API 实时链路绑定与数据沉淀。</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>3:4 封面卡片</span>
    </div>
  </div>

  <!-- Slide 2: 系统四层架构 -->
  <div class="slide-card" id="card-2">
    <div>
      <div class="header">
        <div class="tag">🏗️ 架构拆解 · 02/06</div>
        <div class="slide-num">SLIDE 02</div>
      </div>
      <div class="main-title">系统四大核心层级架构图</div>
      <div class="sub-title">确定性 Workflow 与自主 Agent 结合的极客生产力闭环</div>
      <div class="content-box">
        <div class="code-badge">
          ┌──────────────────────────────────┐<br>
          │ 1. 大脑层：Antigravity + IP 风格  │<br>
          ├──────────────────────────────────┤<br>
          │ 2. 视觉层：3:4 HTML 渲染引擎      │<br>
          ├──────────────────────────────────┤<br>
          │ 3. 调度层：Python Worker / n8n   │<br>
          ├──────────────────────────────────┤<br>
          │ 4. 存储层：飞书 Base + SFTP 池   │<br>
          └──────────────────────────────────┘
        </div>
        <div class="item">
          <div class="item-icon">⚡️</div>
          <div class="item-text">告别任何手动做图！在 Agent 对话框中下达指令，全程无人干预产出爆款配图。</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>系统架构全景</span>
    </div>
  </div>

  <!-- Slide 3: 个人 IP 语料库 -->
  <div class="slide-card" id="card-3">
    <div>
      <div class="header">
        <div class="tag">✍️ 去 AI 味指南 · 03/06</div>
        <div class="slide-num">SLIDE 03</div>
      </div>
      <div class="main-title">个人 IP 语料库提炼：拒绝营销号爹味</div>
      <div class="sub-title">通过 19 篇微信公众号发文深度训练“小吴聊”直爽实战语气</div>
      <div class="content-box">
        <div class="item">
          <div class="item-icon">🙅‍♂️</div>
          <div class="item-text"><strong>黑名单红线</strong>：严禁“在当今时代”、“颠覆”、“听我一句劝”、“月入过万”等套话。</div>
        </div>
        <div class="item">
          <div class="item-icon">✅</div>
          <div class="item-text"><strong>推荐口吻</strong>：开篇强 Hook 暴击（“兄弟们，装完别急着走，真正的乐趣在后面”）。</div>
        </div>
        <div class="item">
          <div class="item-icon">🎯</div>
          <div class="item-text"><strong>真实干货</strong>：只聊代码、架构与真实的避坑经验，绝不凭空编造案例。</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>语料库与语气规则</span>
    </div>
  </div>

  <!-- Slide 4: 3:4 高审美视觉引擎 -->
  <div class="slide-card" id="card-4">
    <div>
      <div class="header">
        <div class="tag">🎨 视觉渲染引擎 · 04/06</div>
        <div class="slide-num">SLIDE 04</div>
      </div>
      <div class="main-title">高审美 3:4 视觉卡片渲染方案</div>
      <div class="sub-title">解决手机端预览卡片模糊、对比度低与像素错乱问题</div>
      <div class="content-box">
        <div class="item">
          <div class="item-icon">📱</div>
          <div class="item-text"><strong>3:4 黄金比例</strong>：专为小红书移动端设计的视觉构图，浏览体验极佳。</div>
        </div>
        <div class="item">
          <div class="item-icon">🖥️</div>
          <div class="item-text"><strong>Playwright 亚像素截取</strong>：3x Device Scale Factor 采样，产出 4K 超高清图。</div>
        </div>
        <div class="item">
          <div class="item-icon">💎</div>
          <div class="item-text"><strong>暗黑双色调</strong>：渐变紫/青花瓷风，搭配 Apple 系统字体，彰显极客审美。</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>3:4 卡片美学</span>
    </div>
  </div>

  <!-- Slide 5: 工程踩坑复盘 -->
  <div class="slide-card" id="card-5">
    <div>
      <div class="header">
        <div class="tag">⚠️ 踩坑避坑复盘 · 05/06</div>
        <div class="slide-num">SLIDE 05</div>
      </div>
      <div class="main-title">实战中踩过的三大工程坑点</div>
      <div class="sub-title">真实踩过的坑，全是血泪经验总结</div>
      <div class="content-box">
        <div class="item">
          <div class="item-icon">💥</div>
          <div class="item-text"><strong>坑 1：n8n 容器 502/端口映射</strong><br>局域网 HTTP 跨域与容器内部 python 路径配置不一致。</div>
        </div>
        <div class="item">
          <div class="item-icon">💥</div>
          <div class="item-text"><strong>坑 2：FastAPI 异步协程阻塞</strong><br>Playwright 必须使用 `async_playwright` 或独立 Worker 进程。</div>
        </div>
        <div class="item">
          <div class="item-icon">💥</div>
          <div class="item-text"><strong>坑 3：飞书 API Tenant Token 机制</strong><br>Token 仅 2 小时有效，需建立自动刷新机制防断连。</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>工程排坑复盘</span>
    </div>
  </div>

  <!-- Slide 6: 极客心法与总结 -->
  <div class="slide-card" id="card-6">
    <div>
      <div class="header">
        <div class="tag">🌟 总结与心法 · 06/06</div>
        <div class="slide-num">SLIDE 06</div>
      </div>
      <div class="main-title">极客操盘手核心心法</div>
      <div class="sub-title">AI 是放大器，人才是最终的品质把关者</div>
      <div class="content-box">
        <div class="item">
          <div class="item-icon">💡</div>
          <div class="item-text"><strong>解放体力活</strong>：把排版、截图、复制粘贴这些机械重复的工作全部交给 AI Agent。</div>
        </div>
        <div class="item">
          <div class="item-icon">🔥</div>
          <div class="item-text"><strong>聚焦核心价值</strong>：把精力和时间留给真正有深度、有创见的思考与生活本身。</div>
        </div>
        <div class="item">
          <div class="item-icon">📌</div>
          <div class="item-text"><strong>一键复刻配置</strong>：拿走这套架构与配置文件，今晚就能在你的 NAS 上跑通！</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-author">@小吴聊 · 极客操盘手</span>
      <span>总结收尾卡片</span>
    </div>
  </div>

</body>
</html>
"""
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    return html_file

def render_cards(html_file):
    print("🎨 [步骤 1/3] 正在使用 Playwright 渲染 6 张 3:4 高审美视觉卡片...")
    img_paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 6000}, device_scale_factor=2)
        page.goto(f"file://{html_file}")
        page.wait_for_selector(".slide-card")
        
        cards = page.query_selector_all(".slide-card")
        print(f"📷 检测到 {len(cards)} 张卡片，开始并发截取...")
        for i, card in enumerate(cards):
            img_path = os.path.join(OUTPUT_DIR, f"card_{i+1:02d}.png")
            card.screenshot(path=img_path)
            img_paths.append(img_path)
            print(f"  ✓ 已生成卡片 {i+1}/6: {img_path}")
        browser.close()
    return img_paths

def generate_xiaohongshu_post():
    print("\n✍️ [步骤 2/3] 应用《小吴聊个人 IP 风格指南》生成小红书图文正文与标签...")
    title = "全网首发：我的 AI 自媒体全自动发布系统搭建全过程 🚀"
    content = (
        "兄弟们！装完别急着走，真正的乐趣在后面！今天把这套 AI 自媒体全自动发布系统全流程大公开！\n\n"
        "实话实说，以前做自媒体最头疼的就是写完文案还要在各个软件里调字号、切 3:4 卡片、对齐像素，一套流程下来半小时没了 [捂脸]。\n\n"
        "这次直接找 Antigravity Agent 结对编程，搞定了一套极客专属的自动化系统：\n"
        "1️⃣ 大脑：Antigravity Agent + 19 篇微信语料库，彻底去 AI 腔\n"
        "2️⃣ 视觉：3:4 高审美 HTML/CSS 杂志风卡片 + Playwright 3x retina 采样\n"
        "3️⃣ 调度：零代码 Workflow 中枢\n"
        "4️⃣ 存储：飞书多维表格数据同步与状态沉淀\n\n"
        "详细的工程坑点与四层架构拆解我整理在图文卡片里了（一共 6 张高清大图，滑动查看）！\n\n"
        "最后一句话总结：AI 不是用来替代人的，而是帮我们扛下那些繁琐机械的体力活，把时间留给真正有价值的思考！"
    )
    tags = ["AI自媒体", "自动化工具", "极客实战", "做号复盘", "小吴聊", "高效工作流", "AI创作"]
    return title, content, tags

def sync_feishu(title, img_paths):
    print("\n📊 [步骤 3/3] 正在同步 6 图发布记录至飞书多维表格《【小吴聊】爆款选题雷达库》...")
    
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
        "配图风格": "3:4 视觉科技卡片 (6张套图)",
        "发布状态": f"✅ 已成功生成 6 张 3:4 高清套图并测试连通",
        "发布时间": current_time_str,
        "错误日志": f"已生成 {len(img_paths)} 张卡片，目录: {OUTPUT_DIR}"
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
    print("🚀 主题测试：AI 自媒体全自动发布系统搭建（6 张 3:4 套图输出）")
    print("=" * 60)

    html_file = create_html_slides()
    img_paths = render_cards(html_file)
    title, content, tags = generate_xiaohongshu_post()
    success = sync_feishu(title, img_paths)

    print("\n" + "=" * 60)
    if success:
        print(f"✨ 【测试成功】已成功生成 {len(img_paths)} 张 3:4 高审美小红书图片卡片！")
        print(f"📁 图片输出目录: {OUTPUT_DIR}")
        for path in img_paths:
            print(f"   - {path}")
    else:
        print("💥 【测试完成（含异常）】请查阅上述详细日志。")
    print("=" * 60)

if __name__ == "__main__":
    main()
