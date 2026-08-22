# -*- coding: utf-8 -*-
"""
Production Subpackage: 工业化内容生产与多平台改写
"""
from .engine import extract_material_facts, generate_xiaohongshu_post, generate_video_script

__all__ = [
    "extract_material_facts",
    "generate_xiaohongshu_post",
    "generate_video_script",
]
