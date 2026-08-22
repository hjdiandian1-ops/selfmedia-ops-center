# -*- coding: utf-8 -*-
"""
Phase 1 QA Gate: selfmedia-radar 自动化质检测试套件
=================================================
验证：
  1. 公众号低粉爆款抓取接口与数据评分计算
  2. 小红书/B站多平台社媒热点搜索
  3. 链接平台识别与 Markdown/SRT 逐字稿生成
"""

import os
import sys
from pathlib import Path
import pytest

# 加入项目根目录
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..")))

from src.selfmedia.radar.gzh_trends import (
    fetch_gzh_explosive_articles,
    calculate_data_score,
    _parse_count,
)
from src.selfmedia.radar.xhs_search import (
    search_cross_platform,
    fetch_bilibili_hot,
    fetch_douyin_hot,
)
from src.selfmedia.radar.transcript import (
    detect_platform,
    Segment,
    export_transcript_markdown,
    export_srt_subtitles,
    process_url_transcript,
)


class TestGzhTrendsRadar:
    """公众号爆款雷达质检"""

    def test_parse_count_formats(self):
        assert _parse_count("1.5w") == 15000
        assert _parse_count("10W+") == 100000
        assert _parse_count("12,345") == 12345
        assert _parse_count(888) == 888
        assert _parse_count(None) == 0

    def test_calculate_data_score(self):
        item = {"fans": "2000", "clicksCount": "50000", "likeCount": "500", "shareCount": "200", "commentCount": "100"}
        score = calculate_data_score(item, "lowPowderExplosiveArticle")
        assert score > 0
        assert isinstance(score, float)

    def test_fetch_gzh_explosive_articles(self):
        result = fetch_gzh_explosive_articles("AI", max_items=5)
        assert result["ok"] is True
        assert "items" in result
        assert len(result["items"]) <= 5
        if result["items"]:
            first = result["items"][0]
            assert "title" in first
            assert "account_name" in first
            assert "url" in first
            assert "category" in first
            assert "data_score" in first


class TestCrossPlatformSearch:
    """跨平台搜索雷达质检"""

    def test_fetch_bilibili_hot(self):
        items = fetch_bilibili_hot(limit=3)
        assert isinstance(items, list)
        assert len(items) <= 3
        if items:
            assert items[0]["platform"] == "B站"
            assert "title" in items[0]
            assert "url" in items[0]

    def test_fetch_douyin_hot(self):
        items = fetch_douyin_hot(limit=5)
        assert isinstance(items, list)
        if items:
            assert items[0]["platform"] == "抖音"

    def test_search_cross_platform(self):
        res = search_cross_platform("科技", limit_per_platform=3)
        assert "results" in res
        assert "小红书" in res["results"]
        assert "B站" in res["results"]


class TestTranscriptExtractor:
    """音视频转录与字幕生成质检"""

    def test_detect_platform(self):
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
        assert detect_platform("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"
        assert detect_platform("https://www.xiaoyuzhoufm.com/episode/60b8d5a1e") == "xiaoyuzhou"
        assert detect_platform("https://www.douyin.com/video/1234567") == "douyin"
        assert detect_platform("https://www.xiaohongshu.com/explore/654321") == "xiaohongshu"
        assert detect_platform("https://example.com/audio.mp3") == "generic"

    def test_export_markdown_and_srt(self):
        segments = [
            Segment(0.0, 15.5, "大家好，今天我们来聊聊如何用 AI 打造全自动自媒体内容工厂。"),
            Segment(15.5, 45.0, "第一步是搞定公域真实爆款情报输入，而不是每天手动硬刷。"),
        ]
        md = export_transcript_markdown("测试逐字稿", "https://test.com", "B站", segments)
        srt = export_srt_subtitles(segments)

        assert "# 测试逐字稿" in md
        assert "[00:00:00]" in md
        assert "全自动自媒体内容工厂" in md

        assert "1\n00:00:00,000 --> 00:00:15,500" in srt
        assert "2\n00:00:15,500 --> 00:00:45,000" in srt

    def test_process_url_transcript_mock(self, tmp_path):
        res = process_url_transcript("https://www.bilibili.com/video/BV1kS8H6VERt", output_dir=str(tmp_path))
        assert res["ok"] is True
        assert res["platform"] == "bilibili"
        assert Path(res["md_path"]).exists()
