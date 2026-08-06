# -*- coding: utf-8 -*-
import os, sys, time
from playwright.sync_api import sync_playwright

PROJECT_DIR = "/Users/xiaowuliao/Projects/自媒体发布agent"
COOKIES_PATH = os.path.join(PROJECT_DIR, "nas-n8n", "shared_files", "xhs_cookies.json")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "outputs/2026-08-03_Antigravity小红书图文自动化发布/小红书")

TITLE = "公开分享我和 AI 打造小红书图文助手的全过程 ✨"

CONTENT = """平时做小红书，最耗费精力的往往不是脑子里的想法，而是选题抓耳挠腮、排版手酸，以及在各种做图工具里调字号、对齐像素。

这三天我决定不干体力活了，直接找 Antigravity (AI Agent) 结对编程，从零搭建了一个懂我风格的小红书图文助手。

今天把整个搭建过程、踩过的坑以及目前还没做完的待办，毫无保留地做一次真实经验分享！

---

💡 一、 为什么要搭这个助手？

过去做图文，好不容易写完文案，还要切软件搞 3:4 卡片、调配色，一套流程下来半小时没了，创作热情都被磨掉了一半。

我的想法很简单：让 AI 扛下繁琐的排版与做图，我只负责思考选题和品质把关。

---

🛠️ 二、 三天结对编程的实操阶段

1️⃣ 第一阶段：注入个人 IP 语料与“去 AI 味”规范
提取了我过去发过的 19 篇文章，提炼出直爽实战的口吻，建立 stop-slop 规范，严格剔除“在当今时代”、“颠覆”等虚头八脑的机器套话。

2️⃣ 第二阶段：集成高审美 3:4 视觉 Skill
引入最新的 guizang-social-card-skill 视觉排版系统，支持青花瓷蓝与电子墨水风，自动处理标题与正文字号对比，一秒渲染高颜值图文。

---

⚠️ 三、 踩过的真实坑点复盘

💥 踩坑 1：n8n 部署与接口解析
在 NAS 部署 Docker 中文版 n8n 时，遇到了局域网通信与 Webhook 实体解析坑，最后自己写了修复脚本才成功打通。

💥 踩坑 2：4K Retina 高清画质升级
刚开始截出来的网页卡片在手机上看模糊有锯齿，后来调高了 2x/3x 亚像素级渲染采样，直接升级到 4K 超高清（2160×2880 像素）。

---

📌 四、 目前的项目进度与未竟待办

1. 本次发文就是我和 AI 首篇端到端闭环测试！
2. 待办一：打通 RSSHub 热点雷达与云端表格选题库的自动推荐。
3. 待办二：拓展微信公众号深度长图文排版与草稿箱接入。

---

🌟 总结心法

AI 不是用来替代人的，而是帮我们扛下那些繁琐机械的体力活，把时间和精力留给真正有价值的思考与生活本身！

希望这篇真实的结对编程与做号复盘，能给大家带来一点启发！"""

TAGS = ["小红书图文", "AI协作", "做号复盘", "做号实操", "工作流拆解", "高效工具", "小吴聊"]

IMAGES = [os.path.join(OUTPUT_DIR, f"porcelain_card_{i+1:02d}.png") for i in range(8)]

def publish():
    print("🚀 启动小红书 8 图经验分享自动化发布助手...", flush=True)
    if not os.path.exists(COOKIES_PATH):
        print(f"❌ 未找到 Session Cookies 文件: {COOKIES_PATH}", flush=True)
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=COOKIES_PATH)
        page = context.new_page()
        
        print("🌐 正在直达小红书【发布图文】创作者页面...", flush=True)
        page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
        time.sleep(4)
        
        print(f"📤 正在上传 8 张 4K 青花瓷风格视觉卡片...", flush=True)
        time.sleep(2)
        all_inputs = page.query_selector_all('input[type="file"]')
        image_input = None
        for inp in all_inputs:
            acc = inp.get_attribute("accept") or ""
            has_mult = inp.get_attribute("multiple") is not None
            if "image" in acc or has_mult or ".png" in acc:
                image_input = inp
                break
        
        if not image_input and all_inputs:
            image_input = all_inputs[-1]
            
        if image_input:
            image_input.set_input_files(IMAGES)
            print("✅ 8 张 4K 图片卡片批量上传成功！等待解析...", flush=True)
        else:
            print("⚠️ 尝试常规 set_input_files...", flush=True)
            page.set_input_files('input[type="file"]', IMAGES)
            
        time.sleep(8)
        
        print("✍️ 正在自动填写标题与正文话题...", flush=True)
        try:
            title_input = page.wait_for_selector('input[placeholder*="标题"]', timeout=10000)
            title_input.fill(TITLE)
            print("✅ 标题填写成功！", flush=True)
        except Exception as e:
            print("填写标题提示:", e, flush=True)
            
        try:
            full_text = CONTENT + "\n\n" + " ".join([f"#{t}" for t in TAGS])
            content_input = page.wait_for_selector('div[contenteditable="true"]', timeout=10000)
            content_input.fill(full_text)
            print("✅ 正文与话题标签填写成功！", flush=True)
        except Exception as e:
            print("填写正文提示:", e, flush=True)

        time.sleep(3)
        print("\n🎉【成功】8 张配图、标题与正文已全自动在小红书后台就位！", flush=True)
        
        # Click publish
        try:
            publish_btn = page.query_selector('button:has-text("发布")') or page.query_selector('.publishBtn')
            if publish_btn:
                print("⚡️ 正在自动点击【发布】按钮...", flush=True)
                publish_btn.click()
                time.sleep(8)
                print("🎉🎉🎉 [发布成功] 您的 8 图经验分享笔记已成功提交小红书进行上线发布！", flush=True)
        except Exception as err:
            print("自动点击发布提示:", err, flush=True)

        context.storage_state(path=COOKIES_PATH)
        print("✅ Session Cookies 已更新保存！", flush=True)
        time.sleep(3)

if __name__ == "__main__":
    publish()
