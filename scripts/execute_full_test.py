#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS 宿主机（192.168.50.229:5800）与飞书多维表格端到端图文发布测试脚本
"""

import os
import sys
import json
import time
import base64
import urllib.request
import urllib.parse
import paramiko
from playwright.sync_api import sync_playwright

# NAS 配置
NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
NAS_SHARED_DIR = "/volume1/docker/n8n/shared_files"
PUBLISHER_URL = f"http://{NAS_IP}:5800/publish"

# 飞书多维表格配置
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output_test_flow")

def step1_generate_visual_card():
    """步骤 1: 生成 3:4 高审美测试视觉卡片"""
    print("\n🎨 [步骤 1/4] 正在渲染 3:4 高审美测试视觉卡片...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_card_path = os.path.join(OUTPUT_DIR, "test_card.html")
    
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
      <div class="tag">⚡️ NAS 自动化链路测试</div>
      <div class="title">全自动图文发布测试：NAS 宿主机 + 飞书多维表格联动</div>
      <div class="badge-container">
        <div class="badge">🖥️ NAS (192.168.50.229:5800)</div>
        <div class="badge">📊 飞书多维表格同步</div>
      </div>
      <div class="desc">
        测试包含 Playwright 无头浏览器渲染、SFTP 共享文件池传输、微服务发布调起与飞书 Base 状态实时追踪。<br><br>
        测试时间：{current_time_str}
      </div>
    </div>
    <div class="footer">
      <span>@小吴聊自媒体 Agent</span>
      <span>3:4 杂志风卡片</span>
    </div>
  </div>
</body>
</html>
"""
    with open(html_card_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    img_path = os.path.join(OUTPUT_DIR, "nas_test_card.png")
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

def step2_upload_to_nas(local_img_path):
    """步骤 2: 将本地测试配图上传至 NAS 共享目录"""
    print("\n📤 [步骤 2/4] 正在通过 SFTP 传输配图至 NAS 共享文件池...")
    filename = f"publish_test_{int(time.time())}.png"
    nas_remote_path = f"{NAS_SHARED_DIR}/{filename}"
    container_path = f"/data/shared/{filename}"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=30)

    try:
        with open(local_img_path, "rb") as f:
            b64_data = base64.b64encode(f.read())

        exec_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'base64 -d > {nas_remote_path} && chmod 777 {nas_remote_path}'"
        stdin, stdout, stderr = ssh.exec_command(exec_cmd)
        stdin.write(b64_data.decode('ascii') + "\n")
        stdin.flush()
        stdin.close()
        stdout.read()
        print(f"✅ 配图同步至 NAS 成功: {container_path}")
        return container_path
    finally:
        ssh.close()

def step3_call_nas_publisher(container_img_path, title, content, tags):
    """步骤 3: 请求 NAS 宿主机发布服务 (192.168.50.229:5800)"""
    print(f"\n🚀 [步骤 3/4] 正在请求 NAS 宿主机发布微服务 ({PUBLISHER_URL})...")
    payload = {
        "title": title,
        "content": content,
        "images": [container_img_path],
        "tags": tags,
        "cookies_json_path": "/data/shared/xhs_cookies.json"
    }

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Antigravity-Agent-Test/1.0"
    }

    req = urllib.request.Request(PUBLISHER_URL, data=data_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_body = response.read().decode("utf-8")
            print(f"🎉 NAS 发布微服务响应 [HTTP {response.status}]:")
            print(res_body)
            return True, res_body
    except Exception as e:
        print(f"❌ NAS 发布微服务响应异常: {e}")
        return False, str(e)

def step4_update_feishu_bitable(title, publish_status, log_msg):
    """步骤 4: 写入飞书多维表格记录"""
    print(f"\n📊 [步骤 4/4] 正在同步状态至飞书多维表格《【小吴聊】爆款选题雷达库》...")
    
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
        "主题或链接": PUBLISHER_URL,
        "文案风格": "极客操盘手风格",
        "配图风格": "3:4 视觉科技卡片",
        "发布状态": publish_status,
        "发布时间": current_time_str,
        "错误日志": log_msg
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
    print("🚀 NAS 宿主机发布服务 (192.168.50.229:5800) + 飞书多维表格端到端测试")
    print("=" * 60)

    title = "【发布测试】NAS 宿主机 + 飞书多维表格 AI 自媒体全自动闭环"
    content = (
        "🚀【无人值守发布测试】\n"
        "这是一条来自于 NAS 宿主机（192.168.50.229:5800）发布微服务与飞书多维表格的实战测试。\n\n"
        "💡 系统能力验证：\n"
        "1️⃣ 飞书多维表格实时记录与状态更新\n"
        "2️⃣ 3:4 视觉高审美卡片自动生成与 Playwright 渲染\n"
        "3️⃣ SFTP 自动同步至 NAS 宿主机共享文件池\n"
        "4️⃣ NAS 无头 Chromium 自动登录与一键挂载提交\n\n"
        "--- \n"
        f"测试时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
    )
    tags = ["发布测试", "NAS自动化", "AI自媒体", "飞书多维表格"]

    # 步骤 1: 生成本地 3:4 卡片
    local_img = step1_generate_visual_card()

    # 步骤 2: SFTP 同步到 NAS
    container_img = step2_upload_to_nas(local_img)

    # 步骤 3: 调起 NAS 5800 发布服务
    success, res_msg = step4_res = step3_call_nas_publisher(container_img, title, content, tags)

    # 步骤 4: 写入飞书多维表格
    pub_status = "✅ 已成功提交发布" if success else "❌ 发布过程异常"
    step4_update_feishu_bitable(title, pub_status, res_msg)

    print("\n" + "=" * 60)
    if success:
        print("✨ 【测试成功】已成功完成 NAS 宿主机发布服务调起与飞书多维表格状态同步！")
    else:
        print("💥 【测试完成（含异常）】请查阅上述详细日志。")
    print("=" * 60)

if __name__ == "__main__":
    main()
