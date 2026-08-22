# -*- coding: utf-8 -*-
"""
Harsh Critic 80-Point Gatekeeper (严苛读者视角 80分红线评审器)
============================================================
从挑剔读者的视角评估成文的吸引力与完读率，低于 80 分坚决打回重修。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def evaluate_harsh_critic(title: str, content: str, platform: str = "小红书") -> Dict[str, Any]:
    """
    四维严苛评分（每项满分 25 分，总分 100 分，80分及格红线）：
      1. 首屏/前3秒抓人度 (Hook Strength)
      2. 信息增量与干货密度 (Value Density)
      3. 叙事结构与认知起伏 (Structure & Flow)
      4. 行动启发与互动转化 (Engagement & Action)
    """
    if not content or len(content.strip()) < 30:
        return {
            "total_score": 20,
            "passed": False,
            "dimensions": {},
            "critique": "内容过于单薄，无法进行有效评审",
        }

    # 1. 钩子打分 (0-25)
    hook_score = 15
    title_and_intro = (title + " " + content[:150])
    if re.search(r"为什么|怎么做|竟然|避坑|千万别|实测|手把手|彻底搞懂|保姆级|3分钟|真相|对比", title_and_intro):
        hook_score += 6
    if re.search(r"\d+|[？！!]", title_and_intro):
        hook_score += 4
    hook_score = min(hook_score, 25)

    # 2. 信息增量打分 (0-25)
    value_score = 14
    # 数据、代码、步骤、案例词
    data_points = len(re.findall(r"\d+(?:\.\d+)?(?:%|w|万|倍|元|k)?", content))
    if data_points >= 3:
        value_score += 5
    if re.search(r"步骤|第一步|核心原理|源码|工具|方法|实操|配置|公式", content):
        value_score += 6
    value_score = min(value_score, 25)

    # 3. 结构与排版打分 (0-25)
    struct_score = 15
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        struct_score += 5
    if re.search(r"[\#\-•✦📍📌👉💡🔥]", content):
        struct_score += 5
    struct_score = min(struct_score, 25)

    # 4. 行动与互动打分 (0-25)
    action_score = 14
    if re.search(r"建议|去试试|在评论区|收藏|关注|你觉得|快去|附完整|自取", content[-200:]):
        action_score += 8
    else:
        action_score += 3
    action_score = min(action_score, 25)

    total_score = hook_score + value_score + struct_score + action_score
    passed = total_score >= 80

    critique = []
    if hook_score < 20:
        critique.append("前3秒/首屏缺乏冲突感，建议加入认知反差或量化痛点")
    if value_score < 20:
        critique.append("干货密度偏低，建议增加具体数据点或实操避坑细节")
    if struct_score < 20:
        critique.append("排版段落过长，缺乏小标题或视觉锚点引导")
    if action_score < 20:
        critique.append("文末缺乏明确的行动指引或评论区互动钩子")

    return {
        "total_score": total_score,
        "passed": passed,
        "pass_line": 80,
        "dimensions": {
            "hook": hook_score,
            "value_density": value_score,
            "structure": struct_score,
            "engagement": action_score,
        },
        "critiques": critique if critique else ["内容各维度表现优异，符合爆款质感"],
        "verdict": "✅ Harsh Critic 评审通过（≥80分）" if passed else f"❌ 未达80分红线（当前得分: {total_score}），需按评审意见修改",
    }
