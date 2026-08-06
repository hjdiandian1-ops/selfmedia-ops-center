import paramiko, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

new_main_py = """import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from playwright.async_api import async_playwright

app = FastAPI(title="Xiaohongshu Publishing Service for n8n")

class PublishPayload(BaseModel):
    title: str
    content: str
    images: List[str]
    tags: Optional[List[str]] = []
    cookies_json_path: Optional[str] = "/data/shared/xhs_cookies.json"

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Xiaohongshu Publisher API"}

@app.post("/publish")
async def publish_note(payload: PublishPayload):
    if not os.path.exists(payload.cookies_json_path):
        raise HTTPException(status_code=400, detail=f"Cookies 文件不存在: {payload.cookies_json_path}。请先通过扫码脚本保存登录状态。")
    
    valid_images = []
    for img_path in payload.images:
        if os.path.exists(img_path):
            valid_images.append(os.path.abspath(img_path))
        else:
            print(f"警告: 图片文件不存在 - {img_path}")
            
    if not valid_images:
        raise HTTPException(status_code=400, detail="没有有效的待上传图片文件")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                storage_state=payload.cookies_json_path
            )
            page = await context.new_page()

            # 1. 打开小红书创作服务平台
            await page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
            await page.wait_for_timeout(3000)

            # 2. 自动点击切换到【发布图文/上传图文】模式
            try:
                tabs = page.locator("text='上传图文', text='发布图文', div:has-text('图文')")
                if await tabs.count() > 0:
                    await tabs.first.click()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"切换图文 Tab 提示: {e}")

            # 3. 定位带有 multiple 或 accept 包含 image 的 input
            inputs = page.locator("input[type='file']")
            input_count = await inputs.count()
            target_input = None
            for i in range(input_count):
                inp = inputs.nth(i)
                accept = await inp.get_attribute("accept") or ""
                is_multi = await inp.get_attribute("multiple") is not None
                if "image" in accept or is_multi or ".png" in accept:
                    target_input = inp
                    break
            
            if not target_input and input_count > 0:
                target_input = inputs.last

            if target_input:
                await target_input.set_input_files(valid_images)
            else:
                await page.locator("input[type='file']").last.set_input_files(valid_images)

            await page.wait_for_timeout(6000)

            # 4. 填写标题
            title_input = page.locator("input[placeholder*='填写标题'], input[placeholder*='标题']")
            if await title_input.count() > 0:
                await title_input.first.fill(payload.title)

            # 5. 填写正文（追加标签）
            full_content = payload.content
            if payload.tags:
                full_content += "\\n\\n" + " ".join([f"#{t}" for t in payload.tags])

            content_editor = page.locator(".post-content #post-textarea, .editor-container [contenteditable='true'], div[contenteditable='true']")
            if await content_editor.count() > 0:
                await content_editor.first.fill(full_content)

            await page.wait_for_timeout(3000)

            # 6. 点击发布按钮
            publish_btn = page.locator("button:has-text('发布'), .publishBtn")
            if await publish_btn.count() > 0:
                await publish_btn.first.click()
                await page.wait_for_timeout(8000)

            await browser.close()
            return {"status": "success", "message": "🎉 小红书笔记图文发布已成功通过 NAS 微服务提交上线！", "title": payload.title}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动化发布异常: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

b64_code = base64.b64encode(new_main_py.encode("utf-8")).decode("utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# Write to container /app/main.py
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_code} | base64 -d > /volume1/docker/n8n/shared_files/main.py && {DOCKER_BIN} cp /volume1/docker/n8n/shared_files/main.py xhs_publisher:/app/main.py'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

# Restart xhs_publisher container
print("🔄 重启 xhs_publisher 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart xhs_publisher"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
