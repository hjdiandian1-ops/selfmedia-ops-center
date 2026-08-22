# -*- coding: utf-8 -*-
"""
Deterministic HTML-to-MP4 B-Roll Rendering Engine (确定性 HTML 转 MP4 视频引擎)
===========================================================================
基于 Playwright 逐帧无损截屏 + FFmpeg 管道流式硬编码，输出 1080x1920 60/30fps 高清 B-roll MP4。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from jinja2 import Template
from ..radar.transcript import get_ffmpeg_binary


def render_broll_clip(
    scene_data: Dict[str, Any],
    duration_sec: float,
    output_mp4: str,
    fps: int = 24,
    width: int = 1080,
    height: int = 1920,
) -> str:
    """
    将单个场景 HTML 渲染为确定性无损 MP4 视频片段
    :param scene_data: 包含 headline, tag, bullets 的字典
    :param duration_sec: 该片段持续时长（秒）
    :param output_mp4: 输出 MP4 文件路径
    :param fps: 帧率（默认 24fps 兼顾平滑度与极速渲染）
    """
    from playwright.sync_api import sync_playwright

    ffmpeg = get_ffmpeg_binary()
    out = Path(output_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    template_path = Path(__file__).parent / "templates" / "broll_scene.html"
    with open(template_path, "r", encoding="utf-8") as f:
        tmpl = Template(f.read())

    html_content = tmpl.render(scene_data)
    total_frames = max(int(duration_sec * fps), 1)

    cmd = [
        ffmpeg, "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "19",
        str(out),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page.set_content(html_content, wait_until="networkidle")

        for frame_idx in range(total_frames):
            progress = frame_idx / max(total_frames - 1, 1)
            cur_sec = frame_idx / fps
            m, s = divmod(int(cur_sec), 60)
            time_str = f"{m:02d}:{s:02d}"
            
            page.evaluate(f"window.setTimelineProgress({progress}, '{time_str}')")
            png_bytes = page.screenshot(type="png")
            proc.stdin.write(png_bytes)

        browser.close()

    proc.stdin.close()
    proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg 编码失败: {err[-400:]}")

    return str(out)
