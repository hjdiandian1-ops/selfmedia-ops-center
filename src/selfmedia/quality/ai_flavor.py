# -*- coding: utf-8 -*-
"""
Anti-AI Flavor Checker (去AI味22条规则检测引擎)
==============================================
对生成内容进行严苛的 AI 味扫描，输出 AI 味评分、命中的禁用词与修改建议。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 22 条去 AI 味特征词库
AI_FLAVOR_PATTERNS = [
    (r"在这个.+的时代", "公文式宏大开场，缺乏具体生活/业务场景"),
    (r"总而言之|综上所述|总的来说", "总结套话，口播/社媒禁止使用公文总结词"),
    (r"值得一提的是|不得不提的是", "无信息增量填充词，直接说核心事实"),
    (r"显而易见|众所周知", "傲慢设问/理所当然，容易引发读者反感"),
    (r"不可否认|毋庸置疑", "绝对化武断说辞，缺乏客观事实支撑"),
    (r"为我们敲响了警钟|引发了深思", "陈旧说教话术，缺少真实情绪"),
    (r"如同一把双刃剑", "老套比喻，缺乏新意"),
    (r"让我们拭目以待", "空洞收尾，缺乏行动指引或互动钩子"),
    (r"赋能|闭环|抓手|底层逻辑|打法|心智", "过度互联网黑话堆砌（除非特定职场讽刺赛道）"),
    (r"首先.*其次.*再次.*最后", "僵硬的公文序号罗列，缺乏叙事起伏"),
    (r"你是否也曾经历过.+呢？", "模板化设问钩子，读起来极其刻意"),
    (r"不仅如此|与此同时", "僵硬的连接过渡词，可直接用口语短句替换"),
    (r"可以说|某种程度上", "模棱两可的废话填充"),
    (r"在当今快节奏的社会中", "极度泛滥的 AI 式开篇废话"),
    (r"让我们一起来看看吧", "低幼化营销号套话"),
    (r"希望对你有所帮助", "平庸无力收尾"),
    (r"毫无疑问|毫无悬念", "过度自信的空洞副词"),
    (r"深入浅出|言简意赅", "自我标榜的修饰词"),
    (r"带来翻天覆地的变化", "夸张空泛的描述"),
    (r"开启了新的篇章", "宏大叙事套话"),
    (r"在这一背景下", "机械式背景铺垫"),
    (r"可以说是一大亮点", "陈词滥调点评"),
]


def check_ai_flavor(text: str) -> Dict[str, Any]:
    """
    检查文本中的 AI 味程度
    :param text: 输入文本
    :return: 包含得分（0-100分，越低越好/100代表纯人味）、命中规则、修改建议的字典
    """
    if not text or not text.strip():
        return {"score": 100, "ai_flavor_ratio": 0.0, "violations": [], "passed": True}

    violations = []
    total_penalty = 0

    for pattern, advice in AI_FLAVOR_PATTERNS:
        matches = list(re.finditer(pattern, text))
        if matches:
            count = len(matches)
            penalty = count * 6
            total_penalty += penalty
            for m in matches:
                violations.append({
                    "matched_text": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "advice": advice,
                    "penalty": 6,
                })

    # 计算人味得分（满分 100，扣分制）
    score = max(100 - total_penalty, 0)
    passed = score >= 80

    return {
        "score": score,
        "penalty_total": total_penalty,
        "violations_count": len(violations),
        "violations": violations,
        "passed": passed,
        "verdict": "✅ 纯净人味（通过）" if passed else "❌ AI味浓重（需人工润色去套话）",
    }
