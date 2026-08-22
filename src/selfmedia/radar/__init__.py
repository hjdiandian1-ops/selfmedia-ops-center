# -*- coding: utf-8 -*-
"""
Radar Subpackage: 爆款情报、赛道探测与多源音视频转录
"""
from .gzh_trends import fetch_gzh_explosive_articles
from .xhs_search import search_cross_platform, search_xhs_notes, fetch_bilibili_hot, fetch_douyin_hot
from .transcript import process_url_transcript, detect_platform

__all__ = [
    "fetch_gzh_explosive_articles",
    "search_cross_platform",
    "search_xhs_notes",
    "fetch_bilibili_hot",
    "fetch_douyin_hot",
    "process_url_transcript",
    "detect_platform",
]
