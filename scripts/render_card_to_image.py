import sys
import os
import asyncio
from playwright.async_api import async_playwright

async def render_card(input_html, output_png):
    input_path = os.path.abspath(input_html)
    output_path = os.path.abspath(output_png)

    if not os.path.exists(input_path):
        print(f"❌ 错误: 输入 HTML 文件不存在: {input_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"🚀 启动 Playwright 渲染卡片: {input_path}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 540, "height": 720},
            device_scale_factor=2
        )
        page = await context.new_page()
        file_url = f"file://{input_path}"
        await page.goto(file_url, wait_until="networkidle")

        await page.screenshot(path=output_path, full_page=True, type="png")
        await browser.close()
        print(f"✅ 成功渲染高清晰度图片: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 scripts/render_card_to_image.py <input_html> <output_png>")
        sys.exit(1)
    
    asyncio.run(render_card(sys.argv[1], sys.argv[2]))
