# -*- coding: utf-8 -*-
"""
Quality & Compliance Gatekeepers (四重质检门禁套件)
=================================================
1. 素材事实契约 (Materials Contract)
2. Harsh Critic 80分红线 (Harsh Critic)
3. 22条去AI味硬性规则 (Anti-AI Flavor)
4. 广告法与三平台合规审核 (Compliance Review)
"""
from .materials_contract import validate_materials_contract
from .harsh_critic import evaluate_harsh_critic
from .ai_flavor import check_ai_flavor
from .compliance import check_compliance

__all__ = [
    "validate_materials_contract",
    "evaluate_harsh_critic",
    "check_ai_flavor",
    "check_compliance",
]
