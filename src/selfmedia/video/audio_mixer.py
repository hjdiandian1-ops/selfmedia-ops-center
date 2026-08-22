# -*- coding: utf-8 -*-
"""
Audio Sidechain Ducking Mixer (音频侧链避让混音引擎)
==================================================
当旁白/口播人声响起时，背景音乐 (BGM) 自动平滑衰减 -18dB，人声结束时优雅回升。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional
from ..radar.transcript import get_ffmpeg_binary


def mix_voice_and_bgm(
    voice_path: str,
    bgm_path: Optional[str],
    output_path: str,
    bgm_volume: float = 0.18,
    duck_threshold: float = 0.08,
    duck_ratio: float = 8.0,
) -> str:
    """
    使用 FFmpeg 侧链压缩滤镜将人声与背景音乐智能混音
    :param voice_path: 口播人声音频文件 (MP3/WAV/AAC)
    :param bgm_path: 背景音乐文件 (MP3/WAV) - 若为空则直接转码输出人声
    :param output_path: 混音输出文件路径
    :param bgm_volume: BGM 基础音量比例 (0.0 - 1.0)
    :return: 输出音频文件路径
    """
    ffmpeg = get_ffmpeg_binary()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not bgm_path or not Path(bgm_path).exists():
        # 无 BGM 时直接规范化人声导出
        cmd = [
            ffmpeg, "-y", "-i", voice_path,
            "-ac", "2", "-ar", "44100", "-b:a", "192k",
            str(out)
        ]
    else:
        # 侧链压缩避让滤镜
        # [0:a] 人声, [1:a] BGM (先调基础音量)
        filter_complex = (
            f"[1:a]volume={bgm_volume}[bg];"
            f"[bg][0:a]sidechaincompress=threshold={duck_threshold}:ratio={duck_ratio}:attack=150:release=500[ducked_bg];"
            f"[0:a][ducked_bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd = [
            ffmpeg, "-y",
            "-i", voice_path,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-ac", "2", "-ar", "44100", "-b:a", "192k",
            str(out)
        ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg 混音失败: {res.stderr[-500:]}")

    return str(out)
