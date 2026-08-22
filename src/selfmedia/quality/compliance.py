# -*- coding: utf-8 -*-
"""
Compliance & Sensitive Word Reviewer (合规与广告法敏感词审核器)
============================================================
涵盖政治敏感、极限用语（第一/最/独家等广告法红线）、导流违规词。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# 广告法极限词与高危违规词库（排除正常序数词如“第一步/第一阶段”）
COMPLIANCE_PATTERNS = [
    (r"最(好|佳|强|高|低|快|牛|完美|顶级|领先|先进|便宜|大)(?!于|多|少)", "新广告法极限词违规（最xx）"),
    (r"全国第一|行业第一|全网第一|行业首个|全网唯一|独家首发|唯一正版", "绝对化宣传用语，需有国家级权威资质证书支撑"),
    (r"100%|包过|稳赚|必火|保本|零风险", "绝对化保证/收益承诺，严重违规"),
    (r"加v|私信我|看主页简介|进群|领资料|扫码", "平台明目张胆导流违规，易被限流或禁言"),
    (r"翻墙|科学上网|VPN|梯子|代充", "网络安全与监管红线"),
    (r"内幕|暴利|割韭菜|黑灰产|躺赚", "金融与运营违规词"),
]


def check_compliance(text: str) -> Dict[str, Any]:
    """
    检查文本合规性
    """
    if not text:
        return {"passed": True, "violations": []}

    violations = []
    for pattern, reason in COMPLIANCE_PATTERNS:
        for m in re.finditer(pattern, text):
            violations.append({
                "matched": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "reason": reason,
            })

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations_count": len(violations),
        "violations": violations,
        "verdict": "✅ 合规检查通过" if passed else f"❌ 发现 {len(violations)} 处合规风险（需修正极限词或导流话术）",
    }
