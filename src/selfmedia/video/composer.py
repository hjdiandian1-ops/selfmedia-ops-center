# -*- coding: utf-8 -*-
"""
Final Video Composer (成品短视频音视频成片合成器)
==============================================
合并 B-roll 画面、动态混音音轨与 ASS/SRT 字幕，一键合成可发布的最终成片 MP4。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional
from ..radar.transcript import get_ffmpeg_binary


def compose_final_video(
    video_path: str,
    audio_path: str,
    output_mp4: str,
    srt_path: Optional[str] = None,
) -> str:
    """
    合成最终 MP4 视频
    :param video_path: B-roll 视频源
    :param audio_path: 已混音的音频源
    :param output_mp4: 成品导出路径
    :param srt_path: 可选字幕文件路径
    """
    ffmpeg = get_ffmpeg_binary()
    out = Path(output_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg 成片合成失败: {res.stderr[-400:]}")

    return str(out)
