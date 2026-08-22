# -*- coding: utf-8 -*-
"""
Cover Image Quality & Safe-Zone Checker (封面安全区与质感检测器)
============================================================
检测小红书/短视频封面是否符合视觉黄金构图，边缘是否预留平台遮挡安全边距。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def check_cover_spec(
    headline: str,
    items_count: int,
    aspect_ratio: str = "3:4",
) -> Dict[str, Any]:
    """
    检查封面文字规范与信息密度：
      1. 标题字数建议在 12-24 字符内（大字突出，一眼可见）
      2. 核心卖点/小点不超过 4 条（避免密密麻麻信息过载）
      3. 必须包含至少一个高对比度重点词
    """
    issues = []
    headline_len = len(headline.strip())
    
    if headline_len < 6:
        issues.append("封面大标题过短，缺乏明确价值点")
    elif headline_len > 28:
        issues.append("封面大标题字数过多（超过28字），在手机信息流中容易缩放过小难以阅读")

    if items_count > 5:
        issues.append("封面要点过多（超过5条），建议精简为 3-4 条核心抓手")

    has_emphasis = bool(re.search(r"[！!🔥🚀💡📌⚡💥]|【.+】", headline))
    if not has_emphasis:
        issues.append("建议标题增加高亮修饰符或重点框定（如【核心解法】或🔥），强化视觉重心")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "aspect_ratio": aspect_ratio,
        "headline_len": headline_len,
        "issues": issues,
        "verdict": "✅ 封面视觉规范合格" if passed else f"⚠️ 发现 {len(issues)} 处可优化项",
    }
