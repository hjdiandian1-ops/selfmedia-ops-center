#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卡组逐张渲染器（美术总监工具）
================================
把 guizang-social-card-skill 产出的卡组 HTML 中每个 <section class="poster">
逐张渲染为独立 PNG（2x 高清），文件名取 poster 的 id。
内置「底部留白硬门」：3:4 卡片内容区底部距页脚锚点 ≤120px（规格见 workflows/产出标准.md 2.2），
超阈值会输出逐卡告警并以退出码 1 拒绝交付。

用法（需系统 python3 + playwright + 已缓存 chromium）：
    /usr/bin/python3 scripts/render_deck_to_images.py <卡组HTML> <输出目录>
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright


async def render(deck_html, out_dir):
    deck_path = os.path.abspath(deck_html)
    if not os.path.exists(deck_path):
        print(f"❌ 卡组 HTML 不存在: {deck_path}")
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(device_scale_factor=2)
        await page.goto(f"file://{deck_path}", wait_until="networkidle")
        # 等待 Web 字体与图标就绪
        await page.evaluate("document.fonts && document.fonts.ready")
        await page.wait_for_timeout(800)

        posters = page.locator("section.poster")
        count = await posters.count()
        if count == 0:
            print("❌ 未找到任何 section.poster")
            sys.exit(1)

        made = []
        whitespace_fails = []
        for i in range(count):
            el = posters.nth(i)
            pid = await el.get_attribute("id") or f"card_{i+1:02d}"
            out = os.path.join(out_dir, f"{pid}.png")
            await el.scroll_into_view_if_needed()
            await page.wait_for_timeout(200)
            await el.screenshot(path=out, type="png")
            made.append(out)
            print(f"✅ {pid}.png")
            # ---- 底部留白硬门（数据飞轮 · 规格统一） ----
            ws = await el.evaluate("""el => {
              const h = el.getBoundingClientRect().height;
              const kids = [...el.children];
              const body = kids.find(k => k.classList && k.classList.contains('body'));
              const flow = body ? [...body.children]
                                : kids.filter(k => getComputedStyle(k).position !== 'absolute');
              const abs = kids.filter(k => getComputedStyle(k).position === 'absolute');
              const top0 = el.getBoundingClientRect().top;
              const flowMax = flow.length
                ? Math.max(...flow.map(k => k.getBoundingClientRect().bottom - top0))
                : 0;
              const anchor = abs.length
                ? Math.min(...abs.map(k => k.getBoundingClientRect().top - top0))
                : h - 80;
              return {flowMax: Math.round(flowMax), anchor: Math.round(anchor), gap: Math.round(anchor - flowMax)};
            }""")
            if ws["gap"] > 120:
                whitespace_fails.append(pid)
                print(f"   ❌ 底部留白 {ws['gap']}px 超过阈值 120px（内容至 {ws['flowMax']}px / 页脚起点 {ws['anchor']}px）")
            else:
                print(f"   ✅ 底部留白 {ws['gap']}px（阈值 ≤120px）")

        await browser.close()
        print(f"\n🎉 共渲染 {len(made)} 张卡片 → {out_dir}")
        if whitespace_fails:
            print(f"❌ 底部留白不合格：{whitespace_fails}（规格见 workflows/产出标准.md 2.2，请调整布局后重渲）")
            sys.exit(1)
        print("✅ 底部留白全部达标（≤120px），可交付")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: render_deck_to_images.py <卡组HTML> <输出目录>")
        sys.exit(1)
    asyncio.run(render(sys.argv[1], sys.argv[2]))
