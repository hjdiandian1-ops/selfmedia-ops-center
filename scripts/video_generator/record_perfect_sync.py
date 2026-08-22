#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
确定性 PTS 画音卡点录制引擎 (真正无遮挡 · 真实视图切换 · 毫秒卡点)
========================================================================
核心修复：
  1. 正确注入 localStorage.setItem('selfmedia_onboarded', '1') 彻底消除弹窗在全场景的错误遮挡；
  2. 首幕 (Scene 1) 真实展示 3 分钟新手引导并在念到台词时准时点击关闭；
  3. 使用正确的 switchView('topics' / 'pipeline' / 'outputs' / 'themes' / 'flywheel') 与 openSettings() 切换全套真实视图；
  4. 采用 FFmpeg setpts 数学时间基准强对齐，消除 WebM VFR 时间膨胀，保证 100% 音画同步！
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


def record_all_scenes_deterministic():
    meta_path = os.path.join(OUTPUT_DIR, "deep_scenes_meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
    scenes = meta_data["scenes"]

    print("🚀 启动真正无遮挡 · 确定性 PTS 画音卡点录制引擎...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--font-render-hinting=none",
                "--enable-font-antialiasing",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding"
            ]
        )

        for idx, scene in enumerate(scenes):
            sid = scene["id"]
            audio_path = scene["mp3"]
            target_dur = get_media_duration(audio_path)
            print(f"\n🎬 [幕 {idx} · {scene['title']}] 目标音频时长: {target_dur:.2f}s")

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

            # 关键：除第 1 幕展示指引外，其余全部默认已引导，彻底杜绝弹窗遮挡
            if idx != 1:
                context.add_init_script("localStorage.setItem('selfmedia_onboarded', '1');")
            else:
                context.add_init_script("localStorage.removeItem('selfmedia_onboarded');")

            page = context.new_page()
            page.goto("http://127.0.0.1:8787", wait_until="networkidle")
            time.sleep(0.4)

            # 注入高亮光标与 30fps 活跃渲染心跳
            page.evaluate('''() => {
                const cursor = document.createElement("div");
                cursor.id = "smart-cursor";
                cursor.innerHTML = `<svg width="42" height="42" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(0 6px 14px rgba(0,0,0,0.6));">
                    <path d="M4 3L18 13L11.5 14L8.5 21L4 3Z" fill="#3B82F6" stroke="#FFFFFF" stroke-width="2.5" stroke-linejoin="round"/>
                </svg>`;
                cursor.style = "position:fixed;top:200px;left:200px;width:42px;height:42px;pointer-events:none;z-index:9999999;transition:left 0.22s cubic-bezier(0.22, 1, 0.36, 1), top 0.22s cubic-bezier(0.22, 1, 0.36, 1), transform 0.12s ease;";
                document.body.appendChild(cursor);

                window.__moveCursor = (x, y) => {
                    cursor.style.left = (x - 2) + "px";
                    cursor.style.top = (y - 2) + "px";
                };

                window.__clickCursor = () => {
                    cursor.style.transform = "scale(0.82) rotate(-8deg)";
                    const ripple = document.createElement("div");
                    ripple.style = `position:fixed;left:${cursor.style.left};top:${cursor.style.top};width:65px;height:65px;border-radius:50%;border:4px solid #60A5FA;box-shadow:0 0 30px #3B82F6;pointer-events:none;z-index:9999998;transform:translate(-50%,-50%) scale(0.2);transition:all 0.4s ease-out;opacity:1;`;
                    document.body.appendChild(ripple);
                    setTimeout(() => {
                        ripple.style.transform = "translate(-50%,-50%) scale(2.3)";
                        ripple.style.opacity = "0";
                        cursor.style.transform = "scale(1)";
                    }, 40);
                    setTimeout(() => ripple.remove(), 450);
                };

                // 恒定渲染心跳
                const ticker = document.createElement("canvas");
                ticker.width = 2; ticker.height = 2;
                ticker.style = "position:fixed;top:0;left:0;opacity:0.01;pointer-events:none;z-index:9999999;";
                document.body.appendChild(ticker);
                const ctx = ticker.getContext("2d");
                let c = 0;
                function loop() {
                    c++;
                    ctx.fillStyle = c % 2 === 0 ? "#000" : "#fff";
                    ctx.fillRect(0, 0, 2, 2);
                    requestAnimationFrame(loop);
                }
                requestAnimationFrame(loop);
            }''')

            def move_to_pos(x, y, wait_after=0.2):
                page.evaluate(f"window.__moveCursor({x}, {y})")
                time.sleep(wait_after)

            def move_to_el(selector, wait_after=0.2):
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

            def click_el(selector, wait_after=0.5):
                el = move_to_el(selector, wait_after=0.2)
                if el:
                    page.evaluate("window.__clickCursor()")
                    el.click()
                    time.sleep(wait_after)

            def smooth_scroll(start_y, end_y, duration_sec=1.5):
                steps = int(duration_sec * 30)
                delay = duration_sec / max(1, steps)
                for i in range(steps + 1):
                    y = start_y + (end_y - start_y) * (i / steps)
                    page.evaluate(f"window.scrollTo(0, {y})")
                    time.sleep(delay)

            t0 = time.time()

            # ----------------------------------------------------
            # 真实动作分镜执行（音画卡点）
            # ----------------------------------------------------
            if idx == 0:  # Hook (22.70s) - 大盘全景
                page.evaluate("switchView('overview')")
                time.sleep(0.5)
                move_to_pos(400, 280, wait_after=0.5)
                smooth_scroll(0, 500, duration_sec=target_dur * 0.45)
                smooth_scroll(500, 0, duration_sec=target_dur * 0.35)
                move_to_pos(300, 200, wait_after=1.0)

            elif idx == 1:  # 新手指引 (23.16s) - 弹窗4步介绍与准时关闭
                page.evaluate("showOnboarding(true)")
                time.sleep(target_dur * 0.12)
                move_to_el("#onboard-modal .onboard-step:nth-child(1)", wait_after=target_dur * 0.14)
                move_to_el("#onboard-modal .onboard-step:nth-child(2)", wait_after=target_dur * 0.14)
                move_to_el("#onboard-modal .onboard-step:nth-child(3)", wait_after=target_dur * 0.14)
                move_to_el("#onboard-modal .onboard-step:nth-child(4)", wait_after=target_dur * 0.14)
                # 准时点击底部的“我知道了，开始使用”关闭弹窗！
                click_el("#onboard-modal .modal-box > button.filled", wait_after=0.8)

            elif idx == 2:  # 概览大盘 (18.96s) - 诊断雷达
                page.evaluate("switchView('overview')")
                time.sleep(0.5)
                smooth_scroll(0, 480, duration_sec=target_dur * 0.4)
                move_to_pos(540, 600, wait_after=target_dur * 0.3)
                smooth_scroll(480, 0, duration_sec=target_dur * 0.2)

            elif idx == 3:  # 选题雷达 (27.74s) - 8大源与日/周双池
                # 0s: 点击切换到「选题」
                move_to_el('button.nav-item[data-view="topics"]', wait_after=0.2)
                page.evaluate("window.__clickCursor(); switchView('topics');")
                time.sleep(0.6)
                # 20%: 展开热搜详情
                move_to_el("#btn-refresh-topics", wait_after=0.4)
                page.evaluate("window.__clickCursor()")
                time.sleep(0.5)
                smooth_scroll(0, 400, duration_sec=target_dur * 0.25)
                # 50%: 滚动至日选题
                move_to_pos(540, 500, wait_after=target_dur * 0.2)
                smooth_scroll(400, 750, duration_sec=target_dur * 0.2)
                # 80%: 悬停在 95 分高分选题行
                move_to_pos(540, 680, wait_after=1.5)

            elif idx == 4:  # 采纳生产 (26.42s) - 9-Agent 流水线
                # 0s: 采纳
                page.evaluate("switchView('topics')")
                time.sleep(0.4)
                move_to_pos(900, 420, wait_after=0.3)
                page.evaluate("window.__clickCursor()")
                time.sleep(0.4)
                # 20%: 切入流水线
                move_to_el('button.nav-item[data-view="pipeline"]', wait_after=0.2)
                page.evaluate("window.__clickCursor(); switchView('pipeline');")
                time.sleep(0.6)
                smooth_scroll(0, 450, duration_sec=target_dur * 0.4)
                move_to_pos(540, 500, wait_after=target_dur * 0.25)

            elif idx == 5:  # 成品验收 (28.97s) - 22条去AI味与公众号排版
                # 0s: 切换到成品库
                move_to_el('button.nav-item[data-view="outputs"]', wait_after=0.2)
                page.evaluate("window.__clickCursor(); switchView('outputs');")
                time.sleep(0.6)
                # 20%: 滚动查看质检报告
                smooth_scroll(0, 450, duration_sec=target_dur * 0.35)
                move_to_pos(750, 400, wait_after=target_dur * 0.2)
                # 65%: 点击公众号预览并一键复制
                smooth_scroll(450, 0, duration_sec=target_dur * 0.15)
                move_to_pos(350, 480, wait_after=0.5)
                page.evaluate("window.__clickCursor()")
                time.sleep(0.4)
                move_to_pos(320, 520, wait_after=0.6)
                page.evaluate("window.__clickCursor()")

            elif idx == 6:  # 运营复盘 (21.77s) - 爆款拆解与飞轮反哺
                # 0s: 爆款跟踪
                move_to_el('button.nav-item[data-view="themes"]', wait_after=0.2)
                page.evaluate("window.__clickCursor(); switchView('themes');")
                time.sleep(0.5)
                smooth_scroll(0, 350, duration_sec=target_dur * 0.25)
                # 35%: 数据飞轮
                move_to_el('button.nav-item[data-view="flywheel"]', wait_after=0.2)
                page.evaluate("window.__clickCursor(); switchView('flywheel');")
                time.sleep(0.5)
                smooth_scroll(0, 350, duration_sec=target_dur * 0.3)
                move_to_pos(540, 450, wait_after=1.2)

            elif idx == 7:  # 设置中心全拆解 (37.85s) - 7大子菜单与实时换肤
                page.evaluate("switchView('overview')")
                time.sleep(0.3)
                # 0s: 打开设置
                page.evaluate("openSettings()")
                time.sleep(0.5)
                # 10%: 个人资料
                move_to_pos(250, 380, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 18%: 外观主题
                move_to_pos(250, 420, wait_after=0.4)
                page.evaluate("window.__clickCursor()")
                # 25%: 爱马仕橙
                page.evaluate("applyTheme('hermes')")
                time.sleep(target_dur * 0.07)
                # 32%: 香奈儿
                page.evaluate("applyTheme('chanel')")
                time.sleep(target_dur * 0.07)
                # 39%: 赛博朋克
                page.evaluate("applyTheme('cyberpunk')")
                time.sleep(target_dur * 0.07)
                # 47%: 文风设置
                move_to_pos(250, 460, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 56%: AI 引擎
                move_to_pos(250, 500, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 66%: 网络与代理
                move_to_pos(250, 540, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 76%: 公众号
                move_to_pos(250, 580, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 84%: 数据管理
                move_to_pos(250, 620, wait_after=target_dur * 0.08)
                page.evaluate("window.__clickCursor()")
                # 92%: 准时点击返回关闭设置！
                page.evaluate("closeSettings()")
                time.sleep(0.6)

            elif idx == 8:  # 开源 CTA (18.91s)
                page.evaluate("switchView('overview')")
                time.sleep(0.4)
                smooth_scroll(0, 0, duration_sec=target_dur * 0.3)
                move_to_pos(540, 300, wait_after=1.5)

            elapsed = time.time() - t0
            remain = target_dur - elapsed
            if remain > 0:
                time.sleep(remain)

            page.close()
            context.close()

            # 找到本幕原始 WebM
            webms = [f for f in os.listdir(scene_raw_dir) if f.endswith(".webm")]
            if not webms:
                raise RuntimeError(f"幕 {idx} 未录制出视频文件！")
            raw_scene_video = os.path.join(scene_raw_dir, webms[0])
            synced_scene_mp4 = os.path.join(SCENES_DIR, f"{sid}_synced.mp4")

            raw_v_dur = get_media_duration(raw_scene_video)
            if raw_v_dur <= 0:
                raw_v_dur = target_dur

            print(f"   ⏱️ 原始视频时长: {raw_v_dur:.2f}s ➔ 目标音频时长: {target_dur:.2f}s")
            pts_ratio = target_dur / raw_v_dur

            # PTS 数学时间基准强对齐
            align_cmd = [
                FFMPEG_EXE, "-y",
                "-i", raw_scene_video,
                "-i", audio_path,
                "-filter_complex", f"[0:v]setpts={pts_ratio:.6f}*PTS[v_out]",
                "-map", "[v_out]",
                "-map", "1:a",
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
            print(f"✅ 幕 {idx} 真实视图无遮挡 + PTS 强对齐完成：{synced_scene_mp4}")

        browser.close()
        print("\n🎉 全部 9 幕真实视图无遮挡画音同步视频已录制完成！")


def stitch_final_master_video():
    """
    无缝拼接 9 幕同步视频，混入 Phonk BGM，烧录精准 ASS 亮黄字幕！
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

    print(f"\n🎬 正在压制最终成品视频（真实全流程视图 + Phonk BGM + ASS 亮黄字幕）-> {master_video}...")

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

    print(f"🎉 最终真正无遮挡实操宣发视频已成功生成：{master_video}")

    # 更新封面
    update_cover_script = "/Users/xiaowuliao/.gemini/antigravity/brain/8581a3ab-63fe-4d42-872f-6524272b0bee/scratch/update_cover.py"
    if os.path.exists(update_cover_script):
        subprocess.run(["python3", update_cover_script], check=True)


def main():
    record_all_scenes_deterministic()
    stitch_final_master_video()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
