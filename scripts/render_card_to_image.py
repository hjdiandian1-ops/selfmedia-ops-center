import sys
import os
import asyncio
import argparse
from playwright.async_api import async_playwright

async def render_card(input_html, output_png, width=540, height=720, scale=2):
    input_path = os.path.abspath(input_html)
    output_path = os.path.abspath(output_png)

    if not os.path.exists(input_path):
        print(f"❌ 错误: 输入 HTML 文件不存在: {input_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"🚀 启动 Playwright 渲染卡片: {input_path}（{width}x{height} @{scale}x）")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=scale,
        )
        page = await context.new_page()
        file_url = f"file://{input_path}"
        await page.goto(file_url, wait_until="networkidle")

        await page.screenshot(path=output_path, full_page=True, type="png")
        await browser.close()
        print(f"✅ 成功渲染高清晰度图片: {output_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="HTML 卡片渲染为 PNG（默认 540x720 @2x = 1080x1440）")
    ap.add_argument("input_html")
    ap.add_argument("output_png")
    ap.add_argument("--width", type=int, default=540, help="视口宽度（像素，默认 540）")
    ap.add_argument("--height", type=int, default=720, help="视口高度（像素，默认 720）")
    ap.add_argument("--scale", type=int, default=2, help="缩放系数（默认 2，输出 = 视口×scale）")
    args = ap.parse_args()

    asyncio.run(render_card(args.input_html, args.output_png, args.width, args.height, args.scale))
