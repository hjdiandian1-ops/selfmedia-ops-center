#!/usr/bin/env python3
import paramiko
import base64
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS

fixed_code = """import os
import asyncio
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from playwright.async_api import async_playwright

app = FastAPI()

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
        raise HTTPException(status_code=400, detail=f"Cookies 文件不存在: {payload.cookies_json_path}")
    
    valid_images = []
    for img_path in payload.images:
        if os.path.exists(img_path):
            valid_images.append(os.path.abspath(img_path))
        else:
            print(f"图片路径不存在: {img_path}")
            
    if not valid_images:
        raise HTTPException(status_code=400, detail="没有有效的图片文件")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                storage_state=payload.cookies_json_path
            )
            page = await context.new_page()
            print("🌐 打开小红书发布页面...")
            await page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
            await page.wait_for_timeout(4000)

            print(f"📤 准备上传 {len(valid_images)} 张图片...")
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
            
            if target_input:
                await target_input.set_input_files(valid_images)
            else:
                await inputs.last.set_input_files(valid_images)

            await page.wait_for_timeout(6000)

            print("✍️ 填写标题和正文...")
            title_input = page.locator("input[placeholder*='标题']")
            if await title_input.count() > 0:
                await title_input.first.fill(payload.title)

            full_content = payload.content
            if payload.tags:
                full_content += "\\n\\n" + " ".join([f"#{t}" for t in payload.tags])

            content_editor = page.locator("div[contenteditable='true']")
            if await content_editor.count() > 0:
                await content_editor.first.fill(full_content)

            await page.wait_for_timeout(3000)

            print("🚀 点击发布...")
            publish_btn = page.locator("button:has-text('发布'), .publishBtn")
            if await publish_btn.count() > 0:
                await publish_btn.first.click()
                await page.wait_for_timeout(8000)

            await browser.close()
            return {"status": "success", "message": "小红书笔记发布成功！", "title": payload.title}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

def main():
    b64_data = base64.b64encode(fixed_code.encode("utf-8"))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

    exec_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'base64 -d > /volume1/docker/n8n/shared_files/main.py'"
    stdin, stdout, stderr = ssh.exec_command(exec_cmd)
    stdin.write(b64_data.decode('ascii') + "\n")
    stdin.flush()
    stdin.close()
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("Write out:", out)
    print("Write err:", err)

    cmd_restart = f"echo {NAS_PASS} | sudo -S env PATH=$PATH:/usr/local/bin:/usr/bin:/volume1/@appstore/Docker/usr/bin docker restart xhs_publisher"
    stdin, stdout, stderr = ssh.exec_command(cmd_restart)
    out_r = stdout.read().decode()
    err_r = stderr.read().decode()
    print("Restart out:", out_r)
    print("Restart err:", err_r)

    ssh.close()

if __name__ == "__main__":
    main()
