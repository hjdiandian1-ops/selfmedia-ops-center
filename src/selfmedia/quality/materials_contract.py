# -*- coding: utf-8 -*-
"""
Materials Contract Validator (素材事实契约校验器)
==============================================
确保创作有据可依，杜绝大模型无事实幻觉与虚构数据。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def validate_materials_contract(material_doc: str) -> Dict[str, Any]:
    """
    校验《素材事实清单》是否符合严谨创作契约
    必须包含：
      1. 核心事实陈述 (Core Facts)
      2. 数据与量化依据 (Quantitative Data)
      3. 来源/参考背书 (Source Reference)
      4. 受众痛点/认知冲突 (Pain Point / Conflict)
    """
    if not material_doc or len(material_doc.strip()) < 50:
        return {
            "passed": False,
            "score": 0,
            "reasons": ["素材内容过短，未达到最小事实密度要求（最少50字）"],
        }

    reasons = []
    score = 100

    # 1. 检查数据锚点（包含数字/百分比/量词）
    has_numbers = bool(re.search(r"\d+(?:\.\d+)?(?:%|w|W|万|亿|k|K|元|美元|倍|人|条|篇|秒|分钟|天|年)?", material_doc))
    if not has_numbers:
        score -= 30
        reasons.append("缺少明确的数据量化锚点（数字/百分比/倍数等）")

    # 2. 检查来源标注（链接/作者/论文/机构/平台等）
    has_source = bool(re.search(r"来源|出处|链接|http|arXiv|作者|机构|报告|根据|据|参考", material_doc, re.IGNORECASE))
    if not has_source:
        score -= 25
        reasons.append("缺少事实来源或出处背书标注")

    # 3. 检查受众痛点或核心冲突
    has_conflict = bool(re.search(r"问题|痛点|难点|坑|避坑|真相|误区|为什么|挑战|突破|区别|对比", material_doc))
    if not has_conflict:
        score -= 20
        reasons.append("缺少受众痛点、认知误区或核心冲突点")

    # 4. 检查字数与信息密度
    words_count = len(material_doc.strip())
    if words_count < 150:
        score -= 15
        reasons.append(f"素材体量偏单薄（当前 {words_count} 字，建议 ≥ 150 字）")

    passed = score >= 70
    return {
        "passed": passed,
        "score": max(score, 0),
        "reasons": reasons,
        "words_count": words_count,
        "verdict": "✅ 素材契约达标" if passed else "❌ 素材契约不合格（需补充量化数据与来源）",
    }
