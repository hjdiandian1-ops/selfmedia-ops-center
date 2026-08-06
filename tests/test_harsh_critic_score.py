# -*- coding: utf-8 -*-
"""Harsh Critic 评分器单测（覆盖可独立验证的纯函数 + B1 legacy 回归）。"""
import validate_materials_contract as VMC
import harsh_critic_score as HCS


def test_first_line_skips_blank_and_heading():
    text = "\n# 标题\n\n这是第一行正文\n"
    assert HCS.first_line(text) == "这是第一行正文"


def test_first_sentence():
    assert HCS.first_sentence("今天天气真好。明天会下雨吗？") == "今天天气真好。"


def test_draft_texts_strips_frontmatter(tmp_path):
    d = tmp_path / "小红书"
    d.mkdir()
    p = d / "文案.md"
    p.write_text("---\njob_id: x\n---\n正文内容有数字 30%。\n", encoding="utf-8")
    out = HCS.draft_texts({"小红书": [str(p)]})
    assert "job_id" not in out["小红书"]
    assert "30%" in out["小红书"]


def test_legacy_pack_parse_via_vm_no_crash():
    # B1 回归：harsh_critic 复用 VMC.parse_materials，legacy 包必须不崩
    legacy = "# Hook\n一个足够长的钩子句子\n\n数据：增长 25%。\n"
    items, complete = VMC.parse_materials(legacy)
    assert complete is False
