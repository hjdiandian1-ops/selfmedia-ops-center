#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宣发视频全自动多轨合成器 (Video & Audio Compositor)
============================================================
将 7 幕视觉帧、Azure 云希配音、字幕与时间轴合成 1080x1920 竖屏 MP4 成品视频。
"""
import os
import sys
import json
import subprocess
import time
import imageio_ffmpeg
from render_scenes import render_scene_frame, WIDTH, HEIGHT, FPS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(ROOT, "outputs", "video_assets")
OUTPUT_VIDEO = os.path.join(ROOT, "outputs", "宣发视频_自媒体运营中台2.0.mp4")
COVER_IMAGE = os.path.join(ROOT, "outputs", "宣发视频_封面.png")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def render_scene_video(scene_idx, scene_meta):
    """
    为单幕渲染 30fps 视频并与对应 mp3 配音合并为 scene_xx.mp4
    """
    sid = scene_meta["id"]
    duration = scene_meta["duration"]
    mp3_file = scene_meta["mp3"]
    out_mp4 = os.path.join(ASSETS_DIR, f"{sid}.mp4")
    
    total_frames = int(duration * FPS) + 1
    print(f"\n🎬 正在渲染 [{sid}] 视频帧 (共 {total_frames} 帧 · {duration:.2f}s)...")
    
    # 启动 ffmpeg 进程，通过 stdin 管道接收 raw rgb24 视频帧并合并音频
    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",  # 从 stdin 读取图像帧
        "-i", mp3_file,  # 输入对应配音音频
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_mp4
    ]
    
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    
    t0 = time.time()
    for frame_idx in range(total_frames):
        t = frame_idx / FPS
        frame_img = render_scene_frame(scene_idx, t, duration, scene_meta)
        proc.stdin.write(frame_img.tobytes())
        
        if frame_idx % 60 == 0 or frame_idx == total_frames - 1:
            pct = (frame_idx + 1) / total_frames * 100
            print(f"   ⏳ 渲染进度: {pct:.1f}% ({frame_idx+1}/{total_frames})", end="\r")
            
    proc.stdin.close()
    proc.wait()
    cost = time.time() - t0
    print(f"\n✅ [{sid}.mp4] 合成完成 (耗时: {cost:.1f}s)")
    return out_mp4


def concat_all_scenes(meta_list):
    """
    无缝拼接 7 幕视频为最终 master MP4
    """
    print("\n🎞️ 正在无缝拼接 7 幕视频为最终成品...")
    concat_list_file = os.path.join(ASSETS_DIR, "concat_list.txt")
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for m in meta_list:
            mp4_path = os.path.join(ASSETS_DIR, f"{m['id']}.mp4")
            f.write(f"file '{mp4_path}'\n")
            
    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_file,
        "-c", "copy",
        OUTPUT_VIDEO
    ]
    subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
    print(f"🎉 最终成品宣发视频已生成：{OUTPUT_VIDEO}")
    
    # 导出封面图 (使用第 2 幕的高光帧)
    cover = render_scene_frame(1, 2.5, 9.0, meta_list[1])
    cover.save(COVER_IMAGE)
    print(f"🖼️ 宣发视频封面已导出：{COVER_IMAGE}")


def main():
    meta_path = os.path.join(ASSETS_DIR, "scenes_meta.json")
    if not os.path.exists(meta_path):
        print(f"❌ 未找到配音元数据文件: {meta_path}，请先运行 generate_voiceover.py")
        return 1
        
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    scenes = data.get("scenes", [])
    t_start = time.time()
    
    for idx, scene_meta in enumerate(scenes):
        render_scene_video(idx, scene_meta)
        
    concat_all_scenes(scenes)
    
    total_cost = time.time() - t_start
    print(f"\n✨ 全部合成工作已完成！总耗时: {total_cost:.1f} 秒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
