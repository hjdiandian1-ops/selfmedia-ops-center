# -*- coding: utf-8 -*-
"""
Phase 4 QA Gate: 短视频物理渲染与成片测试套件
===========================================
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..")))

from src.selfmedia.radar.transcript import get_ffmpeg_binary
from src.selfmedia.video.audio_mixer import mix_voice_and_bgm
from src.selfmedia.video.broll_engine import render_broll_clip
from src.selfmedia.video.composer import compose_final_video


@pytest.fixture
def dummy_audio_files(tmp_path):
    ffmpeg = get_ffmpeg_binary()
    voice = tmp_path / "voice.wav"
    bgm = tmp_path / "bgm.wav"

    # 生成 3 秒测试音频
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
        str(voice)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        str(bgm)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    return voice, bgm


class TestVideoPipeline:
    """视频成片流水线测试"""

    def test_audio_sidechain_ducking(self, tmp_path, dummy_audio_files):
        voice, bgm = dummy_audio_files
        out_mixed = tmp_path / "mixed.mp3"

        res = mix_voice_and_bgm(str(voice), str(bgm), str(out_mixed))
        assert Path(res).exists()
        assert Path(res).stat().st_size > 1000

    def test_render_broll_clip(self, tmp_path):
        scene = {
            "headline": "打造全自动 <span>内容工厂</span>",
            "tag": "实操拆解",
            "bullets": [
                {"icon": "⚡", "text": "<strong>公域雷达：</strong>全网探测低粉爆款"},
                {"icon": "🛡️", "text": "<strong>四重质检：</strong>Harsh Critic 80分"},
            ]
        }
        out_broll = tmp_path / "broll_test.mp4"
        # 渲染 1 秒极速片段测试
        res = render_broll_clip(scene, duration_sec=1.0, output_mp4=str(out_broll), fps=15)
        assert Path(res).exists()
        assert Path(res).stat().st_size > 5000

    def test_compose_final_video(self, tmp_path, dummy_audio_files):
        voice, bgm = dummy_audio_files
        mixed_audio = tmp_path / "audio.mp3"
        mix_voice_and_bgm(str(voice), str(bgm), str(mixed_audio))

        scene = {"headline": "成片合成测试", "bullets": [{"icon": "🎬", "text": "测试成片"}]}
        broll_mp4 = tmp_path / "broll.mp4"
        render_broll_clip(scene, duration_sec=1.5, output_mp4=str(broll_mp4), fps=15)

        final_mp4 = tmp_path / "final.mp4"
        composed = compose_final_video(str(broll_mp4), str(mixed_audio), str(final_mp4))
        assert Path(composed).exists()
        assert Path(composed).stat().st_size > 5000
