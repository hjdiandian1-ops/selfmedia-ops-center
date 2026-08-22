# -*- coding: utf-8 -*-
"""
Phase 5 QA Gate: 全流程端到端 (E2E) 工业化生产闭环回归测试
=========================================================
涵盖：情报探测 ➔ 事实萃取 ➔ 四重质检 ➔ 3:4高清单出图 ➔ 视频成片合成
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..")))

from src.selfmedia.radar import fetch_gzh_explosive_articles
from src.selfmedia.production import extract_material_facts, generate_xiaohongshu_post, generate_video_script
from src.selfmedia.quality import validate_materials_contract, check_ai_flavor, check_compliance, evaluate_harsh_critic
from src.selfmedia.visual import render_xhs_slide_deck
from src.selfmedia.video import render_broll_clip, mix_voice_and_bgm, compose_final_video
from src.selfmedia.radar.transcript import get_ffmpeg_binary


class TestEndToEndLifecycle:
    """全流程闭环回归测试"""

    def test_complete_production_and_render_flow(self, tmp_path):
        # 1. 模拟情报探测输入
        raw_radar_data = """在 2026 年最新一期的 AI 独立开发者调研中，实测全自动自媒体内容工厂提效 300%。
通过将公域低粉爆款雷达与去AI味 22 条规则相结合，500 名博主实现了零人工硬憋文案的工业化闭环。
数据出处：自媒体运营工厂实测基准报告。"""

        # 2. 事实清单萃取
        fact_res = extract_material_facts(raw_radar_data, topic="全自动内容工厂")
        assert fact_res["ok"] is True
        fact_doc = fact_res["fact_doc"]

        # 3. 事实契约门禁校验
        contract = validate_materials_contract(fact_doc)
        assert contract["passed"] is True

        # 4. 内容生产 (小红书图文 + 短视频台本)
        xhs_post = generate_xiaohongshu_post(fact_doc)
        assert xhs_post["qa"]["all_passed"] is True

        video_script = generate_video_script(fact_doc)
        assert video_script["qa"]["all_passed"] is True

        # 5. 视觉渲染 (渲染 2 张 3:4 组图)
        deck_data = [
            {
                "headline": "自媒体内容工厂 <span>SOP</span>",
                "tag": "实操拆解",
                "items": [{"icon": "⚡", "content": "<strong>公域雷达：</strong>自动抓取低粉黑马爆款"}],
            },
            {
                "headline": "22条去 <span>AI味</span> 门禁",
                "tag": "质量把关",
                "items": [{"icon": "🛡️", "content": "<strong>Harsh Critic：</strong>挑剔读者80分红线"}],
            },
        ]
        img_dir = tmp_path / "images"
        rendered_images = render_xhs_slide_deck(deck_data, output_dir=str(img_dir), theme_name="dark-pro")
        assert len(rendered_images) == 2
        for img in rendered_images:
            assert Path(img).exists()
            assert Path(img).stat().st_size > 5000

        # 6. 短视频成片渲染 (B-roll + 混音 + MP4 合成)
        ffmpeg = get_ffmpeg_binary()
        voice_wav = tmp_path / "voice.wav"
        bgm_wav = tmp_path / "bgm.wav"
        subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=2", str(voice_wav)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=3", str(bgm_wav)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        mixed_audio = tmp_path / "mixed.mp3"
        mix_voice_and_bgm(str(voice_wav), str(bgm_wav), str(mixed_audio))

        scene = {"headline": "E2E 全链路成片", "bullets": [{"icon": "🚀", "text": "全自动生产测试"}]}
        broll_mp4 = tmp_path / "broll.mp4"
        render_broll_clip(scene, duration_sec=1.0, output_mp4=str(broll_mp4), fps=15)

        final_mp4 = tmp_path / "final_complete.mp4"
        composed = compose_final_video(str(broll_mp4), str(mixed_audio), str(final_mp4))

        assert Path(composed).exists()
        assert Path(composed).stat().st_size > 5000
        print("\n🎉 全流程端到端 E2E 测试 100% 跑通！")
