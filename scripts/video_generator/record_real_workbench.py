#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自媒体运营中台 2.0 · 真实网页端实操自动化录屏脚本
============================================================
使用 Playwright 在 1920x1080 高清分辨率下模拟真实用户操作：
  - 概览大盘与数据看板浏览
  - 1.5秒热点雷达折叠展开与日/周选题双池打分查看
  - 采纳生产与流水线 9-Agent 协同
  - 22条去AI味质检与合规报告查看
  - 8套高定质感主题（爱马仕/香奈儿/赛博朋克）实时换肤
  - 公众号红白系排版与小红书卡片成品库预览
"""
import os
import time
import json
import subprocess
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(ROOT, "outputs", "video_assets")
RAW_RECORD_DIR = os.path.join(ASSETS_DIR, "raw_records")
os.makedirs(RAW_RECORD_DIR, exist_ok=True)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def smooth_scroll(page, start_y, end_y, steps=25, delay=0.03):
    """平滑滚动页面"""
    for i in range(steps + 1):
        y = start_y + (end_y - start_y) * (i / steps)
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(delay)


def record_real_operations(scene_durations):
    """
    按照 7 幕配音的时长精准执行实操动作录制
    """
    for f in os.listdir(RAW_RECORD_DIR):
        if f.endswith(".webm") or f.endswith(".mp4"):
            try:
                os.remove(os.path.join(RAW_RECORD_DIR, f))
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--font-render-hinting=none", "--enable-font-antialiasing"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=RAW_RECORD_DIR,
            record_video_size={"width": 1920, "height": 1080},
            device_scale_factor=2,  # Retina 2x 超高清
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8787", wait_until="networkidle")
        time.sleep(1)

        # 注入逼真平滑光标与点击波纹动效
        page.evaluate('''() => {
            const cursor = document.createElement("div");
            cursor.id = "playwright-cursor";
            cursor.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));">
                <path d="M4 3L18 13L11.5 14L8.5 21L4 3Z" fill="#3B82F6" stroke="#FFFFFF" stroke-width="2" stroke-linejoin="round"/>
            </svg>`;
            cursor.style = "position:fixed;top:100px;left:100px;width:32px;height:32px;pointer-events:none;z-index:9999999;transition:left 0.25s cubic-bezier(0.25, 1, 0.5, 1), top 0.25s cubic-bezier(0.25, 1, 0.5, 1), transform 0.15s ease;";
            document.body.appendChild(cursor);

            window.__moveCursor = (x, y) => {
                cursor.style.left = (x - 2) + "px";
                cursor.style.top = (y - 2) + "px";
            };

            window.__clickCursor = () => {
                cursor.style.transform = "scale(0.85) rotate(-5deg)";
                const ripple = document.createElement("div");
                ripple.style = `position:fixed;left:${cursor.style.left};top:${cursor.style.top};width:40px;height:40px;border-radius:50%;border:3px solid #60A5FA;box-shadow:0 0 15px #3B82F6;pointer-events:none;z-index:9999998;transform:translate(-50%,-50%) scale(0.2);transition:all 0.4s ease-out;opacity:1;`;
                document.body.appendChild(ripple);
                setTimeout(() => {
                    ripple.style.transform = "translate(-50%,-50%) scale(2)";
                    ripple.style.opacity = "0";
                    cursor.style.transform = "scale(1)";
                }, 50);
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

        def move_and_click(selector, wait_after=1.0):
            el = move_to(selector, wait_after=0.4)
            if el:
                page.evaluate("window.__clickCursor()")
                el.click()
                time.sleep(wait_after)

        print("\n🎬 开始执行 7 幕真实网页实操录制...")

        # ----------------------------------------------------
        # 幕 1 (10.5s)：痛点共鸣与概览大盘全景
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 1 幕 · 概览大盘] 痛点共鸣与三平台数据总览...")
        move_to("nav a[data-tab='dashboard']", wait_after=0.6)
        time.sleep(1.0)
        smooth_scroll(page, 0, 350, steps=20, delay=0.04)
        time.sleep(1.5)
        move_to("#dash-weak-points", wait_after=0.8)
        smooth_scroll(page, 350, 0, steps=20, delay=0.04)
        time.sleep(max(0.1, scene_durations[0] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 2 (9.4s)：中台架构与 9 Agent 核心模块
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 2 幕 · 中台登场] 切换导航栏展示 7 大核心模块...")
        move_and_click("nav a[data-tab='pipeline']", wait_after=1.5)
        smooth_scroll(page, 0, 200, steps=15, delay=0.04)
        time.sleep(1.5)
        move_to(".pipeline-step:nth-child(2)", wait_after=0.8)
        time.sleep(max(0.1, scene_durations[1] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 3 (11.6s)：1.5秒全网热点雷达 + 双池评分
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 3 幕 · 热点雷达] 8 大源秒级采集与双池打分...")
        move_and_click("nav a[data-tab='topics']", wait_after=1.2)
        # 点击展开雷达源详情
        move_and_click("#radar-list details:first-child summary", wait_after=0.8)
        smooth_scroll(page, 0, 400, steps=20, delay=0.03)
        time.sleep(1.2)
        # 鼠标移动到日选题/周选题第一行高分
        move_to("#suggest-daily tbody tr:first-child", wait_after=1.0)
        time.sleep(1.0)
        move_to("#suggest-weekly tbody tr:first-child", wait_after=1.0)
        time.sleep(max(0.1, scene_durations[2] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 4 (11.3s)：一键采纳生产与 9 Agent 流水线
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 4 幕 · 流水线生产] 采纳选题与全自动生产流...")
        move_to("#suggest-daily tbody tr:first-child button", wait_after=0.8)
        page.evaluate("window.__clickCursor()")
        time.sleep(0.5)
        move_and_click("nav a[data-tab='pipeline']", wait_after=1.2)
        smooth_scroll(page, 0, 300, steps=18, delay=0.03)
        time.sleep(1.5)
        move_to("#prod-flow-status", wait_after=1.0)
        time.sleep(max(0.1, scene_durations[3] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 5 (11.7s)：4 道可计算质检与 22 条去 AI 味
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 5 幕 · 硬核质检] 22 条去 AI 味质检与合规审查...")
        move_and_click("nav a[data-tab='finished']", wait_after=1.0)
        # 滚动查看质检结果与报告
        smooth_scroll(page, 0, 350, steps=20, delay=0.03)
        time.sleep(1.5)
        move_to("#finished-list", wait_after=1.0)
        time.sleep(max(0.1, scene_durations[4] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 6 (10.4s)：8 套奢华质感换肤 + 成品库预览
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 6 幕 · 高定换肤] 打开设置实时切换爱马仕橙/香奈儿/赛博朋克...")
        move_and_click("#btn-open-settings", wait_after=0.8)
        page.evaluate("switchSettingsPanel('theme')")
        time.sleep(0.5)
        # 切换主题为爱马仕橙
        page.evaluate("applyTheme('hermes')")
        time.sleep(1.8)
        # 切换主题为香奈儿
        page.evaluate("applyTheme('chanel')")
        time.sleep(1.8)
        # 切换主题为赛博朋克
        page.evaluate("applyTheme('cyberpunk')")
        time.sleep(1.8)
        # 关闭弹窗
        page.evaluate("closeSettings()")
        time.sleep(0.5)
        # 切换到成品库
        move_and_click("nav a[data-tab='finished']", wait_after=1.0)
        time.sleep(max(0.1, scene_durations[5] - (time.time() - t0)))

        # ----------------------------------------------------
        # 幕 7 (9.9s)：开源开箱即用与行动号召 (CTA)
        # ----------------------------------------------------
        t0 = time.time()
        print("▶ [第 7 幕 · 开源号召] 概览大盘与授权透明展示...")
        move_and_click("nav a[data-tab='dashboard']", wait_after=1.0)
        smooth_scroll(page, 0, 0, steps=15, delay=0.03)
        move_to(".stat-card:first-child", wait_after=1.0)
        time.sleep(max(0.1, scene_durations[6] - (time.time() - t0)))

        page.close()
        context.close()
        browser.close()
        print("🎉 真实实操录制已顺利完成！")


def composite_master_screen_recording(meta_list):
    """
    将录制好的实操 webm 视频，与 7 幕连续配音轨和底部高质感字幕合成最终 MP4 宣发视频
    """
    webm_files = [f for f in os.listdir(RAW_RECORD_DIR) if f.endswith(".webm")]
    if not webm_files:
        raise RuntimeError("未找到录制的 webm 视频文件！")
    raw_video = os.path.join(RAW_RECORD_DIR, webm_files[0])

    # 1. 拼接 7 幕音频为单一连贯音轨
    full_audio = os.path.join(ASSETS_DIR, "full_voiceover.mp3")
    audio_concat_txt = os.path.join(ASSETS_DIR, "audio_concat.txt")
    with open(audio_concat_txt, "w", encoding="utf-8") as f:
        for m in meta_list:
            f.write(f"file '{m['mp3']}'\n")

    print("\n🎙️ 正在合并 7 幕完整语音轨...")
    subprocess.run([
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", audio_concat_txt,
        "-c", "copy",
        full_audio
    ], check=True, stderr=subprocess.DEVNULL)

    # 2. 生成连贯完整 SRT 字幕
    full_srt = os.path.join(ASSETS_DIR, "full_subtitles.srt")
    current_time_offset = 0.0
    srt_index = 1

    with open(full_srt, "w", encoding="utf-8") as out_f:
        for m in meta_list:
            dur = m["duration"]
            srt_path = m["srt"]
            if os.path.exists(srt_path):
                with open(srt_path, "r", encoding="utf-8") as in_f:
                    lines = in_f.readlines()
                # 调整时间戳偏移
                for line in lines:
                    if "-->" in line:
                        parts = line.strip().split(" --> ")
                        if len(parts) == 2:
                            t1 = parse_srt_time(parts[0]) + current_time_offset
                            t2 = parse_srt_time(parts[1]) + current_time_offset
                            out_f.write(f"{format_srt_time(t1)} --> {format_srt_time(t2)}\n")
                    elif line.strip().isdigit():
                        out_f.write(f"{srt_index}\n")
                        srt_index += 1
                    else:
                        out_f.write(line)
            current_time_offset += dur

    # 3. 最终音画字幕合成
    master_video = os.path.join(ROOT, "outputs", "宣发视频_自媒体运营中台2.0_实操录屏版.mp4")
    print(f"\n🎬 正在合成最终高清实操录屏宣发视频 -> {master_video}...")

    # 使用 ASS/SRT 滤镜或底部高对比度字幕盒子
    sub_filter = f"subtitles={full_srt}:force_style='Fontsize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=4,Outline=2,Shadow=1,MarginV=35,Bold=1'"

    cmd = [
        FFMPEG_EXE, "-y",
        "-i", raw_video,
        "-i", full_audio,
        "-vf", sub_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        master_video
    ]
    subprocess.run(cmd, check=True)
    print(f"🎉 最终实操录屏宣发视频已生成：{master_video}")

    # 导出封面
    cover_cmd = [
        FFMPEG_EXE, "-y",
        "-ss", "00:00:22",
        "-i", master_video,
        "-vframes", "1",
        "-q:v", "2",
        os.path.join(ROOT, "outputs", "实操录屏宣发_高清封面.png")
    ]
    subprocess.run(cover_cmd, check=True, stderr=subprocess.DEVNULL)
    print("🖼️ 视频封面已生成：outputs/实操录屏宣发_高清封面.png")


def parse_srt_time(s):
    s = s.replace(",", ".")
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def main():
    meta_path = os.path.join(ASSETS_DIR, "scenes_meta.json")
    if not os.path.exists(meta_path):
        print("❌ 未找到配音元数据，先执行 generate_voiceover.py")
        return 1

    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("scenes", [])
    durations = [s["duration"] for s in scenes]

    # 1. 录屏
    record_real_operations(durations)

    # 2. 合成
    composite_master_screen_recording(scenes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
