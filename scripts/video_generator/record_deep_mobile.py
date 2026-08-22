#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体运营中台 2.0 · 手机版 (9:16 竖屏 1080x1920) +30% 高燃极客版全流程录制与合成
========================================================================================
升级点：
  1. 语速提速 +30%（紧凑高燃，信息密度极高）
  2. BGM 采用「极客高燃电子卡点风（Cyber Phonk Beat）」重低音卡点律动（volume=0.15）
  3. 字幕升级为「爆款短视频标配」：纯净亮黄大字 + 黑色立体硬描边（无底框遮挡，清爽居中）
  4. 封面大标题重塑：《告别玩具Demo！我把自媒体做成了全自动工业流水线》
  5. 真实网页端全套交互：新手 3 分钟引导弹出 ➔ 点击关闭 ➔ 7 模块深度实操 ➔ 设置中心 7 项菜单逐一点击演示与现场换肤 ➔ 关闭
"""
import os
import time
import json
import subprocess
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(ROOT, "outputs", "video_assets", "deep_walkthrough")
RAW_RECORD_DIR = os.path.join(OUTPUT_DIR, "raw_mobile_record")
os.makedirs(RAW_RECORD_DIR, exist_ok=True)

BGM_FILE = os.path.join(ROOT, "outputs", "video_assets", "cyber_phonk_bgm.mp3")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def smooth_scroll(page, start_y, end_y, steps=20, delay=0.025):
    for i in range(steps + 1):
        y = start_y + (end_y - start_y) * (i / steps)
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(delay)


def record_mobile_walkthrough():
    meta_path = os.path.join(OUTPUT_DIR, "deep_scenes_meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
    scenes = meta_data["scenes"]
    durs = [s["duration"] for s in scenes]

    for f in os.listdir(RAW_RECORD_DIR):
        if f.endswith(".webm") or f.endswith(".mp4"):
            try:
                os.remove(os.path.join(RAW_RECORD_DIR, f))
            except Exception:
                pass

    print(f"🎬 启动 Playwright 1080x1920 竖屏录制环境 (总时长: {sum(durs):.1f}s)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--font-render-hinting=none", "--enable-font-antialiasing"]
        )
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            record_video_dir=RAW_RECORD_DIR,
            record_video_size={"width": 1080, "height": 1920},
            device_scale_factor=2,  # Retina 2x 高清
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8787", wait_until="networkidle")
        time.sleep(0.5)

        # 注入逼真高亮蓝色光标与波纹
        page.evaluate('''() => {
            const cursor = document.createElement("div");
            cursor.id = "mobile-cursor";
            cursor.innerHTML = `<svg width="40" height="40" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 6px 12px rgba(0,0,0,0.6));">
                <path d="M4 3L18 13L11.5 14L8.5 21L4 3Z" fill="#3B82F6" stroke="#FFFFFF" stroke-width="2.5" stroke-linejoin="round"/>
            </svg>`;
            cursor.style = "position:fixed;top:200px;left:200px;width:40px;height:40px;pointer-events:none;z-index:9999999;transition:left 0.22s cubic-bezier(0.25, 1, 0.5, 1), top 0.22s cubic-bezier(0.25, 1, 0.5, 1), transform 0.12s ease;";
            document.body.appendChild(cursor);

            window.__moveCursor = (x, y) => {
                cursor.style.left = (x - 2) + "px";
                cursor.style.top = (y - 2) + "px";
            };

            window.__clickCursor = () => {
                cursor.style.transform = "scale(0.8) rotate(-6deg)";
                const ripple = document.createElement("div");
                ripple.style = `position:fixed;left:${cursor.style.left};top:${cursor.style.top};width:60px;height:60px;border-radius:50%;border:4px solid #60A5FA;box-shadow:0 0 25px #3B82F6;pointer-events:none;z-index:9999998;transform:translate(-50%,-50%) scale(0.2);transition:all 0.4s ease-out;opacity:1;`;
                document.body.appendChild(ripple);
                setTimeout(() => {
                    ripple.style.transform = "translate(-50%,-50%) scale(2.2)";
                    ripple.style.opacity = "0";
                    cursor.style.transform = "scale(1)";
                }, 40);
                setTimeout(() => ripple.remove(), 450);
            };
        }''')

        def move_to(selector, wait_after=0.3):
            el = page.query_selector(selector)
            if el:
                box = el.bounding_box()
                if box:
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    page.evaluate(f"window.__moveCursor({cx}, {cy})")
                    time.sleep(wait_after)
                    return el
            return None

        def move_and_click(selector, wait_after=0.8):
            el = move_to(selector, wait_after=0.25)
            if el:
                page.evaluate("window.__clickCursor()")
                el.click()
                time.sleep(wait_after)

        print("\n🎬 开始执行 +30% 紧凑高能动作流...")

        # ----------------------------------------------------
        # 幕 0 (22.7s): Hook 痛点共鸣与工作台展示
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 0 幕 · Hook 痛点] 创作者痛点共鸣，展示工作台界面...")
        move_to("nav a[data-tab='dashboard']", wait_after=0.8)
        smooth_scroll(page, 0, 400, steps=20, delay=0.025)
        time.sleep(1.2)
        smooth_scroll(page, 400, 0, steps=18, delay=0.025)
        time.sleep(max(0.1, durs[0] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 1 (23.2s): 首次打开与新手指引弹窗 ➔ 点击关闭
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 1 幕 · 新手引导] 弹出 3 分钟快速开始引导，点击关闭...")
        page.evaluate("showOnboarding(true)")
        time.sleep(0.6)
        move_to("#onboard-modal .onboard-step:nth-child(1)", wait_after=1.0)
        move_to("#onboard-modal .onboard-step:nth-child(2)", wait_after=1.0)
        move_to("#onboard-modal .onboard-step:nth-child(3)", wait_after=1.0)
        move_to("#onboard-modal .onboard-step:nth-child(4)", wait_after=1.0)
        # 点击底部「我知道了，开始使用」按钮关闭弹窗
        move_and_click("#onboard-modal .modal-box > button.filled", wait_after=1.0)
        time.sleep(max(0.1, durs[1] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 2 (19.0s): 概览大盘全景掌控
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 2 幕 · 概览大盘] 浏览三端核心指标与薄弱点诊断雷达...")
        move_and_click("nav a[data-tab='dashboard']", wait_after=0.6)
        smooth_scroll(page, 0, 450, steps=20, delay=0.025)
        move_to("#dash-weak-points", wait_after=1.0)
        time.sleep(1.0)
        smooth_scroll(page, 450, 0, steps=15, delay=0.025)
        time.sleep(max(0.1, durs[2] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 3 (27.7s): 选题雷达、1.5s采集与双池打分
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 3 幕 · 选题雷达] 展开 8 大国内源榜单与日/周双池加权打分...")
        move_and_click("nav a[data-tab='topics']", wait_after=0.8)
        # 展开第一、二个热搜详情
        move_and_click("#radar-list details:first-child summary", wait_after=0.6)
        smooth_scroll(page, 0, 400, steps=18, delay=0.025)
        time.sleep(1.0)
        # 悬停在日选题高分行
        move_to("#suggest-daily tbody tr:first-child", wait_after=1.2)
        smooth_scroll(page, 400, 750, steps=18, delay=0.025)
        move_to("#suggest-weekly tbody tr:first-child", wait_after=1.2)
        time.sleep(max(0.1, durs[3] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 4 (26.4s): 采纳生产与 9 Agent 流水线
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 4 幕 · 采纳生产] 采纳选题，切入流水线看 9 Agent 协同...")
        move_to("#suggest-daily tbody tr:first-child button", wait_after=0.6)
        page.evaluate("window.__clickCursor()")
        time.sleep(0.4)
        move_and_click("nav a[data-tab='pipeline']", wait_after=0.8)
        smooth_scroll(page, 0, 400, steps=18, delay=0.025)
        time.sleep(1.5)
        move_to("#prod-flow-status", wait_after=1.2)
        time.sleep(max(0.1, durs[4] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 5 (29.0s): 成品验收与 22 条去 AI 味机器质检
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 5 幕 · 成品与质检] 22 条去 AI 味质检报告与公众号排版复制...")
        move_and_click("nav a[data-tab='finished']", wait_after=0.8)
        smooth_scroll(page, 0, 450, steps=20, delay=0.025)
        time.sleep(1.5)
        move_to("#finished-list .finished-card:first-child", wait_after=1.0)
        smooth_scroll(page, 450, 0, steps=18, delay=0.025)
        time.sleep(max(0.1, durs[5] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 6 (21.8s): 运营复盘：爆款跟踪与数据飞轮自进化
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 6 幕 · 爆款与飞轮] 查看对标爆款库与经验反哺升级...")
        move_and_click("nav a[data-tab='viral']", wait_after=0.8)
        smooth_scroll(page, 0, 300, steps=15, delay=0.025)
        time.sleep(0.8)
        move_and_click("nav a[data-tab='flywheel']", wait_after=0.8)
        smooth_scroll(page, 0, 350, steps=18, delay=0.025)
        time.sleep(1.0)
        move_to("#lessons-list", wait_after=0.8)
        time.sleep(max(0.1, durs[6] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 7 (37.9s): 设置中心全功能拆解：逐项点击与换肤 ➔ 关闭
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 7 幕 · 设置中心全拆解] 逐项点击设置菜单、实时换肤并返回...")
        move_and_click("#btn-open-settings", wait_after=0.8)
        # 1. 个人资料
        move_and_click("button[data-panel='profile']", wait_after=0.8)
        # 2. 外观主题
        move_and_click("button[data-panel='theme']", wait_after=0.8)
        page.evaluate("applyTheme('hermes')")
        time.sleep(1.5)
        page.evaluate("applyTheme('chanel')")
        time.sleep(1.5)
        page.evaluate("applyTheme('cyberpunk')")
        time.sleep(1.5)
        # 3. 文风设置
        move_and_click("button[data-panel='style']", wait_after=1.0)
        # 4. AI 引擎
        move_and_click("button[data-panel='llm']", wait_after=1.0)
        # 5. 网络与代理
        move_and_click("button[data-panel='proxy']", wait_after=1.0)
        # 6. 公众号
        move_and_click("button[data-panel='gzh']", wait_after=1.0)
        # 7. 数据管理
        move_and_click("button[data-panel='data']", wait_after=1.0)
        # 点击返回按钮关闭设置
        move_and_click("#settings-menu .set-back", wait_after=0.8)
        time.sleep(max(0.1, durs[7] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 8 (18.9s): 开源开箱即用与行动号召 (CTA)
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 8 幕 · 开源 CTA] 返回大盘全景并号召体验与 Star...")
        move_and_click("nav a[data-tab='dashboard']", wait_after=0.8)
        smooth_scroll(page, 0, 0, steps=12, delay=0.025)
        move_to(".stat-card:first-child", wait_after=1.0)
        time.sleep(max(0.1, durs[8] - (time.time() - t0)))

        page.close()
        context.close()
        browser.close()
        print("🎉 +30% 高燃版 9 幕深度全流程实操录制全部完成！")


def composite_master_video_with_phonk():
    """
    合成手机版 9:16 竖屏 MP4 视频：
      1. 纯净亮黄大字 + 黑色立体硬描边 ASS 字幕（无底框遮挡，清爽居中）
      2. 混入极客高燃 Cyber Phonk Beat BGM（人声 100% + BGM 15% 卡点混音）
    """
    webm_files = [f for f in os.listdir(RAW_RECORD_DIR) if f.endswith(".webm")]
    if not webm_files:
        raise RuntimeError("未找到录制的 webm 视频文件！")
    raw_video = os.path.join(RAW_RECORD_DIR, webm_files[0])
    full_audio = os.path.join(OUTPUT_DIR, "deep_full_voiceover.mp3")
    ass_file = "deep_subtitles.ass"
    master_video = os.path.join(ROOT, "outputs", "宣发视频_自媒体运营中台2.0_手机实操版.mp4")

    print(f"\n🎬 正在使用「纯净亮黄黑描边字幕 + Cyber Phonk BGM」合成最终高燃视频 -> {master_video}...")

    filter_complex = f"[0:v]subtitles={ass_file}[v_out]; [1:a]volume=1.0[voice]; [2:a]volume=0.15[bgm]; [voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[a_out]"

    cmd = [
        FFMPEG_EXE, "-y",
        "-i", raw_video,
        "-i", full_audio,
        "-i", BGM_FILE,
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "[a_out]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        master_video
    ]

    res = subprocess.run(cmd, cwd=OUTPUT_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFMPEG STDERR:", res.stderr[-800:])
        raise RuntimeError(f"FFmpeg 合成失败: {res.returncode}")

    print(f"🎉 最终高燃手机版实操宣发视频已成功生成：{master_video}")

    # 导出全新设计的高转化封面
    generate_high_converting_cover(master_video)


def generate_high_converting_cover(video_path):
    """
    生成高转化爆款封面：
    大标题：《告别玩具Demo！我把自媒体做成了全自动工业流水线》
    """
    cover_file = os.path.join(ROOT, "outputs", "手机实操宣发_高清封面.png")
    temp_frame = "/tmp/cover_base.png"
    
    # 截取选题雷达高光时刻
    subprocess.run([
        FFMPEG_EXE, "-y",
        "-ss", "00:01:00",
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        temp_frame
    ], check=True, stderr=subprocess.DEVNULL)
    
    # 使用 Python PIL 绘制高质感极客封面海报
    from PIL import Image, ImageDraw, ImageFont
    
    im = Image.open(temp_frame).convert("RGBA")
    w, h = im.size
    
    # 顶部添加深色暗角渐变，增强标题可读性
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    for y in range(500):
        alpha = int(220 * (1.0 - (y / 500.0) ** 1.5))
        draw.line([(0, y), (w, y)], fill=(10, 15, 30, alpha))
        
    im = Image.alpha_composite(im, overlay)
    draw = ImageDraw.Draw(im)
    
    font_path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    try:
        f_badge = ImageFont.truetype(font_path, 34)
        f_title = ImageFont.truetype(font_path, 60)
        f_sub = ImageFont.truetype(font_path, 36)
    except Exception:
        f_badge = f_title = f_sub = ImageFont.load_default()
        
    # 1. 顶部 Badge
    badge_text = "⚡ 自媒体运营工厂 2.0 · 全流程保姆级实操"
    badge_bg = (245, 158, 11, 230)  # Amber
    draw.rounded_rectangle([70, 70, 750, 130], radius=14, fill=badge_bg)
    draw.text((90, 80), badge_text, fill=(0, 0, 0, 255), font=f_badge)
    
    # 2. 核心吸睛大标题
    t_line1 = "告别玩具Demo！"
    t_line2 = "我把自媒体做成了全自动工业流水线"
    
    # 阴影与描边
    for dx, dy in [(-3,-3), (3,3), (-3,3), (3,-3), (0,4)]:
        draw.text((70 + dx, 160 + dy), t_line1, fill=(0, 0, 0, 240), font=f_title)
        draw.text((70 + dx, 240 + dy), t_line2, fill=(0, 0, 0, 240), font=f_title)
        
    draw.text((70, 160), t_line1, fill=(255, 220, 40, 255), font=f_title)
    draw.text((70, 240), t_line2, fill=(255, 255, 255, 255), font=f_title)
    
    # 3. 底部特性胶囊
    feats = ["1.5s全网雷达", "9-Agent协同", "22条去AI味", "微信一键排版", "8套主题实时换肤"]
    fx = 70
    for feat in feats:
        draw.rounded_rectangle([fx, 340, fx + 170, 390], radius=8, fill=(30, 41, 59, 210), outline=(59, 130, 246, 255), width=2)
        draw.text((fx + 12, 350), feat, fill=(240, 249, 255, 255), font=f_sub)
        fx += 185
        if fx > w - 180:
            break
            
    im.convert("RGB").save(cover_file, quality=95)
    print(f"🖼️ 高转化爆款视频封面已生成：{cover_file}")


def main():
    record_mobile_walkthrough()
    composite_master_video_with_phonk()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
