import asyncio
from playwright.async_api import async_playwright

async def fetch_share():
    url = "https://codebuddy.work/agents/share/mfuK9631ZYR9-mm6vXqJik8jlIXR2RUeNqJb9MZ2XWNV0KI0GDKZOQj0T9fD-HfP?platform=workbuddy"
    print(f"🚀 正在用 Playwright 渲染抓取 WorkBuddy 页面: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000) # 等待 SPA 数据完全装载
        text = await page.inner_text("body")
        print("\n================== 抓取到的 Kimi K3 评价全文 ==================\n")
        print(text)
        print("\n=============================================================\n")
        with open("/tmp/kimi_eval.txt", "w", encoding="utf-8") as f:
            f.write(text)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_share())
