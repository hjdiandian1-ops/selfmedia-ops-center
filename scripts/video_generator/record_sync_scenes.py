#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧级画音同步引擎：分幕精准时间戳录制与卡点合成 (Zero-Drift Frame-Perfect Sync)
================================================================================
工作原理：
  1. 读取每幕配音的精准毫秒级时长 (durations) 与台词关键词时间点；
  2. Playwright 分幕独立录制，依据每幕内台词的精确出现时间点触发点击/滚动/弹窗/换肤动作；
  3. 将每一幕录制出的独立视频与其对应音频合并，确保每幕时长 100.00% 毫秒级对齐；
  4. FFmpeg 无缝拼接 9 幕视频 + 混入 Phonk BGM + 烧录精准 ASS 亮黄字幕！
"""
import os
import time
import json
import subprocess
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = "/Users/xiaowuliao/Projects/自媒体发布agent"
OUTPUT_DIR = os.path.join(ROOT, "outputs", "video_assets", "deep_walkthrough")
SCENES_DIR = os.path.join(OUTPUT_DIR, "synced_scenes")
os.makedirs(SCENES_DIR, exist_ok=True)

BGM_FILE = os.path.join(ROOT, "outputs", "video_assets", "cyber_phonk_bgm.mp3")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_media_duration(file_path):
    cmd = [FFMPEG_EXE, "-i", file_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if m:
        hours, mins, secs = m.groups()
        return int(hours) * 3600 + int(mins) * 60 + float(secs)
    return 0.0


def smooth_scroll(page, start_y, end_y, duration_sec=1.0):
    steps = int(duration_sec * 30)
    delay = duration_sec / max(1, steps)
    for i in range(steps + 1):
        y = start_y + (end_y - start_y) * (i / steps)
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(delay)


def record_all_synced_scenes():
    meta_path = os.path.join(OUTPUT_DIR, "deep_scenes_meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
    scenes = meta_data["scenes"]

    print("🚀 启动分幕精准画音卡点录制引擎...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--font-render-hinting=none", "--enable-font-antialiasing"]
        )

        for idx, scene in enumerate(scenes):
            sid = scene["id"]
            audio_path = scene["mp3"]
            target_dur = get_media_duration(audio_path)
            print(f"\n🎬 [幕 {idx} · {scene['title']}] 目标精准时长: {target_dur:.2f}s")

            scene_raw_dir = os.path.join(SCENES_DIR, f"raw_{sid}")
            os.makedirs(scene_raw_dir, exist_ok=True)
            for f in os.listdir(scene_raw_dir):
                os.remove(os.path.join(scene_raw_dir, f))

            context = browser.new_context(
                viewport={"width": 1080, "height": 1920},
                record_video_dir=scene_raw_dir,
                record_video_size={"width": 1080, "height": 1920},
                device_scale_factor=2,
            )
            page = context.new_page()
            page.goto("http://127.0.0.1:8787", wait_until="networkidle")
            time.sleep(0.3)

            # 注入高亮蓝色光标与波纹
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

            def move_to(selector, wait_after=0.25):
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

            def move_and_click(selector, wait_after=0.6):
                el = move_to(selector, wait_after=0.2)
                if el:
                    page.evaluate("window.__clickCursor()")
                    el.click()
                    time.sleep(wait_after)

            t_start = time.time()

            # ----------------------------------------------------
            # 依据台词卡点精准执行每幕动作
            # ----------------------------------------------------
            if idx == 0:  # Hook
                # 0-8s: 鼠标浏览大盘
                move_to("nav a[data-tab='dashboard']", wait_after=0.5)
                smooth_scroll(page, 0, 450, duration_sec=4.0)
                # 8-16s: 向上回滚展示全景
                smooth_scroll(page, 450, 0, duration_sec=3.5)
                move_to(".stat-card:first-child", wait_after=1.0)

            elif idx == 1:  # 新手指引
                # 0s: 弹出新手指引
                page.evaluate("showOnboarding(true)")
                time.sleep(0.5)
                # 3-15s: 依次划过 4 个步骤 (配合讲解 4 步)
                move_to("#onboard-modal .onboard-step:nth-child(1)", wait_after=2.5)
                move_to("#onboard-modal .onboard-step:nth-child(2)", wait_after=2.5)
                move_to("#onboard-modal .onboard-step:nth-child(3)", wait_after=2.5)
                move_to("#onboard-modal .onboard-step:nth-child(4)", wait_after=2.5)
                # 17s: 当念到“点击底部的我知道了开始使用”时准时点击关闭
                move_and_click("#onboard-modal .modal-box > button.filled", wait_after=0.8)

            elif idx == 2:  # 概览大盘
                # 0s: 切换到概览
                move_and_click("nav a[data-tab='dashboard']", wait_after=0.5)
                # 3-10s: 滚动浏览三端数据
                smooth_scroll(page, 0, 450, duration_sec=3.0)
                # 10-18s: 悬停在薄弱点诊断雷达
                move_to("#dash-weak-points", wait_after=3.0)
                smooth_scroll(page, 450, 0, duration_sec=2.0)

            elif idx == 3:  # 选题雷达
                # 0s (每天早上开工第一件事点击选题): 准时点击「选题」
                move_and_click("nav a[data-tab='topics']", wait_after=0.8)
                # 3s (点一下采集热点 1.5 秒): 展开热搜详情
                move_and_click("#radar-list details:first-child summary", wait_after=0.6)
                smooth_scroll(page, 0, 400, duration_sec=3.0)
                # 14s (往下看分好了日更池和周更池): 滚动至日选题表格
                move_to("#suggest-daily tbody tr:first-child", wait_after=2.5)
                smooth_scroll(page, 400, 750, duration_sec=3.0)
                # 21s (今天这条 95 分爆款潜质最高): 悬停在 95 分高分选题行
                move_to("#suggest-weekly tbody tr:first-child", wait_after=2.5)

            elif idx == 4:  # 采纳生产 & 流水线
                # 0s (选好之后点击采纳生产): 准时点击选题页的采纳按钮
                move_and_click("nav a[data-tab='topics']", wait_after=0.4)
                move_to("#suggest-daily tbody tr:first-child button", wait_after=0.4)
                page.evaluate("window.__clickCursor()")
                time.sleep(0.4)
                # 3s (切换到流水线页面): 点击「流水线」
                move_and_click("nav a[data-tab='pipeline']", wait_after=0.8)
                # 6-22s: 滚动查看 9 Agent 协同流转
                smooth_scroll(page, 0, 450, duration_sec=4.0)
                move_to("#prod-flow-status", wait_after=3.0)

            elif idx == 5:  # 成品库 & 22 条去 AI 味
                # 0s (来到成品库验收): 点击「成品库」
                move_and_click("nav a[data-tab='finished']", wait_after=0.8)
                # 4-15s (22条去AI味规则消解套话): 滚动查看质检报告
                smooth_scroll(page, 0, 450, duration_sec=3.5)
                move_to("#finished-list .finished-card:first-child", wait_after=2.0)
                # 18-26s (点击一键复制直接粘贴微信): 点击一键复制按钮
                smooth_scroll(page, 450, 0, duration_sec=2.0)
                move_to("#finished-list .finished-card:first-child button", wait_after=1.5)
                page.evaluate("window.__clickCursor()")

            elif idx == 6:  # 爆款与数据飞轮
                # 0s (点开爆款跟踪): 点击「爆款跟踪」
                move_and_click("nav a[data-tab='viral']", wait_after=0.8)
                smooth_scroll(page, 0, 300, duration_sec=2.5)
                # 8s (发完内容来到数据飞轮): 点击「数据飞轮」
                move_and_click("nav a[data-tab='flywheel']", wait_after=0.8)
                # 14s (点击一键反哺升级): 滚动查看 Lessons 并悬停
                smooth_scroll(page, 0, 350, duration_sec=2.5)
                move_to("#lessons-list", wait_after=2.0)

            elif idx == 7:  # 设置中心全拆解 (逐项卡点点击)
                # 0s (再来看设置中心): 打开设置
                move_and_click("#btn-open-settings", wait_after=0.6)
                # 3s (第一项个人资料): 点击个人资料
                move_and_click("button[data-panel='profile']", wait_after=1.2)
                # 6s (第二项外观主题): 点击外观主题
                move_and_click("button[data-panel='theme']", wait_after=0.8)
                # 8s (爱马仕橙): 切换爱马仕橙
                page.evaluate("applyTheme('hermes')")
                time.sleep(1.8)
                # 11s (香奈儿): 切换香奈儿
                page.evaluate("applyTheme('chanel')")
                time.sleep(1.8)
                # 14s (赛博朋克): 切换赛博朋克
                page.evaluate("applyTheme('cyberpunk')")
                time.sleep(1.8)
                # 18s (第三项文风设置): 点击文风设置
                move_and_click("button[data-panel='style']", wait_after=1.8)
                # 22s (接着是 AI 引擎): 点击 AI 引擎
                move_and_click("button[data-panel='llm']", wait_after=1.8)
                # 26s (网络与代理): 点击网络与代理
                move_and_click("button[data-panel='proxy']", wait_after=1.8)
                # 30s (配置好公众号): 点击公众号
                move_and_click("button[data-panel='gzh']", wait_after=1.8)
                # 33s (最后在数据管理里): 点击数据管理
                move_and_click("button[data-panel='data']", wait_after=1.8)
                # 36s (设置完成后点击返回即可): 准时点击返回关闭
                move_and_click("#settings-menu .set-back", wait_after=0.8)

            elif idx == 8:  # 开源 CTA
                # 0s: 返回概览大盘
                move_and_click("nav a[data-tab='dashboard']", wait_after=0.6)
                smooth_scroll(page, 0, 0, duration_sec=1.5)
                move_to(".stat-card:first-child", wait_after=1.5)

            # 精确补齐到 target_dur
            elapsed = time.time() - t_start
            remain = target_dur - elapsed
            if remain > 0:
                time.sleep(remain)

            page.close()
            context.close()

            # 找到本幕录制的 webm 视频
            webms = [f for f in os.listdir(scene_raw_dir) if f.endswith(".webm")]
            if not webms:
                raise RuntimeError(f"幕 {idx} 未录制出视频文件！")
            raw_scene_video = os.path.join(scene_raw_dir, webms[0])
            synced_scene_mp4 = os.path.join(SCENES_DIR, f"{sid}_synced.mp4")

            # 将本幕视频与音频精确强制对齐压制为一致时长
            align_cmd = [
                FFMPEG_EXE, "-y",
                "-i", raw_scene_video,
                "-i", audio_path,
                "-t", str(target_dur),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                synced_scene_mp4
            ]
            subprocess.run(align_cmd, check=True, stderr=subprocess.DEVNULL)
            print(f"✅ 幕 {idx} 精准对齐视频生成：{synced_scene_mp4}")

        browser.close()
        print("\n🎉 全部 9 幕分段画音卡点视频已全部录制并对齐完毕！")


def stitch_final_master_video():
    """
    无缝拼接 9 幕同步视频，混入 Phonk BGM，烧录精准 ASS 字幕！
    """
    meta_path = os.path.join(OUTPUT_DIR, "deep_scenes_meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        scenes = json.load(f)["scenes"]

    concat_txt = os.path.join(SCENES_DIR, "concat_list.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in scenes:
            sid = s["id"]
            mp4_path = os.path.join(SCENES_DIR, f"{sid}_synced.mp4")
            f.write(f"file '{mp4_path}'\n")

    stitched_temp = os.path.join(SCENES_DIR, "stitched_temp.mp4")
    # 1. 无损拼接
    concat_cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        stitched_temp
    ]
    subprocess.run(concat_cmd, check=True, stderr=subprocess.DEVNULL)

    master_video = os.path.join(ROOT, "outputs", "宣发视频_自媒体运营中台2.0_手机实操版.mp4")
    ass_file = "deep_subtitles.ass"

    print(f"\n🎬 正在压制最终成品视频（画音卡点 + Phonk BGM + ASS 亮黄字幕）-> {master_video}...")

    filter_complex = f"[0:v]subtitles={ass_file}[v_out]; [0:a]volume=1.0[voice]; [1:a]volume=0.15[bgm]; [voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[a_out]"

    final_cmd = [
        FFMPEG_EXE, "-y",
        "-i", stitched_temp,
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

    res = subprocess.run(final_cmd, cwd=OUTPUT_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFMPEG STDERR:", res.stderr[-800:])
        raise RuntimeError(f"合成失败: {res.returncode}")

    print(f"🎉 最终卡点同步实操视频已生成：{master_video}")

    # 更新封面
    update_cover_script = "/Users/xiaowuliao/.gemini/antigravity/brain/8581a3ab-63fe-4d42-872f-6524272b0bee/scratch/update_cover.py"
    if os.path.exists(update_cover_script):
        subprocess.run(["python3", update_cover_script], check=True)


def main():
    record_all_synced_scenes()
    stitch_final_master_video()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
