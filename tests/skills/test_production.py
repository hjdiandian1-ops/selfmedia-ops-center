# -*- coding: utf-8 -*-
"""
Phase 2 QA Gate: 工业化生产与四重质检测试套件
===========================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "../..")))

from src.selfmedia.quality.materials_contract import validate_materials_contract
from src.selfmedia.quality.ai_flavor import check_ai_flavor
from src.selfmedia.quality.compliance import check_compliance
from src.selfmedia.quality.harsh_critic import evaluate_harsh_critic
from src.selfmedia.production.engine import (
    extract_material_facts,
    generate_xiaohongshu_post,
    generate_video_script,
)


class TestQualityGatekeepers:
    """四重质检门禁测试"""

    def test_materials_contract_valid(self):
        sample = """# 《AI工具评测》素材清单
根据 2026 年最新实测数据显示，我们对 500 名独立创作者进行了调研。
核心提升效率 300% 以上，解决了传统生产中写不出爆款的致命痛点。
出处来源：独立开发社区公开报告。"""
        res = validate_materials_contract(sample)
        assert res["passed"] is True
        assert res["score"] >= 70

    def test_materials_contract_invalid(self):
        res = validate_materials_contract("今天天气很好，我们来随便聊聊。")
        assert res["passed"] is False

    def test_ai_flavor_detection(self):
        bad_text = "总而言之，在这个快节奏的时代中，显而易见，这如同一把双刃剑，让我们拭目以待吧。"
        res = check_ai_flavor(bad_text)
        assert res["passed"] is False
        assert len(res["violations"]) >= 4

        good_text = "直接说结论：上周我测试了 10 个开发工具，挑出 3 个真正能帮普通人赚钱的。"
        res_good = check_ai_flavor(good_text)
        assert res_good["passed"] is True

    def test_compliance_detection(self):
        bad_ad = "全网第一最好的工具，100%稳赚零风险，赶紧加v进群领资料！"
        res = check_compliance(bad_ad)
        assert res["passed"] is False
        assert len(res["violations"]) >= 3

        clean_text = "这是一个经过开源社区实测的高效自媒体运营工具。"
        res_clean = check_compliance(clean_text)
        assert res_clean["passed"] is True

    def test_harsh_critic_scoring(self):
        title = "手把手教你如何避开自媒体运营的3大坑！实测提效300%"
        content = """为什么你每天花3个小时憋文案却还是0播放？
核心原因有三个步骤没有做对：
📌 第一步：事实清单先行，锁定核心数据；
📌 第二步：22条去AI味硬性过滤；
📌 第三步：确定性卡片渲染。
建议大家马上去试试，觉得有用在评论区收藏自取！"""
        res = evaluate_harsh_critic(title, content)
        assert res["total_score"] >= 80
        assert res["passed"] is True


class TestProductionEngine:
    """生产引擎与产物生成测试"""

    def test_extract_material_facts(self):
        raw = "我们团队实测了 100 篇小红书爆款，发现点赞过万的笔记中有 85% 在前3秒出现了量化痛点。"
        res = extract_material_facts(raw, topic="小红书前3秒钩子拆解")
        assert res["ok"] is True
        assert "素材事实清单" in res["fact_doc"]

    def test_generate_xiaohongshu_post(self):
        res = generate_xiaohongshu_post("素材内容...")
        assert res["platform"] == "小红书"
        assert res["qa"]["all_passed"] is True

    def test_generate_video_script(self):
        res = generate_video_script("素材内容...")
        assert res["platform"] == "短视频"
        assert res["qa"]["all_passed"] is True
