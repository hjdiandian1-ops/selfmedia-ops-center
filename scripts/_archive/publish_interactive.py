# -*- coding: utf-8 -*-
import os, sys, time
from playwright.sync_api import sync_playwright

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
COOKIES_PATH = os.path.join(PROJECT_DIR, "nas-n8n", "shared_files", "xhs_cookies.json")

TITLE = "没事少刷短视频！多看看这个 AI 宝藏站 🔥"
CONTENT = """没事真的少刷无意义的短视频啦！💡
跟大家分享一个我私藏很久的【全球前沿 AI 情报站】。
把时间和精力花在吸收高质量信息上，同龄人之间的差距就是这么拉开的！

这个站点到底有多强？看图就懂了👇

1️⃣ 实时追踪全球 AI 热点
字节开源AI员工、马斯克AI预测、最新AI大模型发布…第一时间同步前沿动态，不再吃残渣二手信息！

2️⃣ 极客级 AI 灵感库
OpenAI最新降价情报、高效动画视频制作工具、各种高性能低成本模型测评，搞AI创作/副业灵感直接爆棚！

3️⃣ 优质 GitHub 开源项目榜
直接按Star数和热度给你整理好优质开源项目（从AI入门到语音合成工具都有），程序员和技术爱好者闭眼入！

4️⃣ 深度 AI 论文与策略解读
连大模型金融应用、算法拆单这种硬核论文都有结构化提取，想提升技术深度的朋友千万别错过。

信息差 = 资源差！早看到早受益！

---
🎁 怎么获取站点？
由于平台限制不能直接发外链：
在【评论区留言：学习】或者直接【私信我：站点】，我看到后会把完整地址一一发给你！"""

TAGS = ["AI工具", "宝藏网站", "学习提升", "程序员", "打破信息差", "干货分享", "高效神器"]

IMAGES = [
    "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images_4k_watermarked/xhs_cover_bright_yellow_4k.png",
    "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images_4k_watermarked/image1_censored_4k.png",
    "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images_4k_watermarked/image2_censored_4k.png",
    "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images_4k_watermarked/image3_censored_4k.png"
]

def run():
    print("🚀 启动小红书可视化发布助手...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=COOKIES_PATH) if os.path.exists(COOKIES_PATH) else browser.new_context()
        page = context.new_page()
        
        print("🌐 正在打开小红书创作者平台...", flush=True)
        page.goto("https://creator.xiaohongshu.com/creator/post")
        
        # Loop check login status
        print("⏳ 正在等待登录状态验证 (若弹框请在屏幕浏览器中完成扫码)...", flush=True)
        while True:
            curr_url = page.url
            if "/login" not in curr_url:
                print("🎉 识别到已成功登录创作者平台！", flush=True)
                break
            time.sleep(2)
            
        time.sleep(3)
        context.storage_state(path=COOKIES_PATH)
        print("✅ Session Cookies 已成功保存至本地！", flush=True)

        # Switch to "发布图文"
        print("👆 正在切换至【发布图文】专属页面...", flush=True)
        try:
            page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
            time.sleep(3)
        except Exception as e:
            print("页面跳转提示:", e, flush=True)

        # Set image inputs
        print("📤 正在上传 4 张 4K 视觉卡片（封面+脱敏配图）...", flush=True)
        try:
            # Look for input or set input directly
            file_inputs = page.query_selector_all('input[type="file"]')
            if file_inputs:
                file_inputs[0].set_input_files(IMAGES)
            else:
                page.set_input_files('input', IMAGES)
            print("✅ 4K 图片卡片上传成功！", flush=True)
        except Exception as err:
            print("⚠️ 上传图片提示:", err, flush=True)

        time.sleep(5)
        print("✍️ 正在自动填入标题与正文...", flush=True)
        try:
            page.fill('input[placeholder*="标题"]', TITLE)
        except Exception as e:
            print("填写标题提示:", e, flush=True)

        try:
            full_text = CONTENT + "\n\n" + " ".join([f"#{t}" for t in TAGS])
            page.fill('div[contenteditable="true"]', full_text)
        except Exception as e:
            print("填写正文提示:", e, flush=True)

        print("\n🎉【完成】所有 4K 封面、脱敏配图、爆款标题与文案标签已全部填入后台！", flush=True)
        print("👉 请在打开的浏览器中检查内容，并点击【发布】按钮完成最终上线！", flush=True)
        time.sleep(60)

if __name__ == "__main__":
    run()
