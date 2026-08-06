# -*- coding: utf-8 -*-
"""素材契约校验器纯逻辑单测。仅依赖标准库，不触网、不连 NAS。"""
import os

import validate_materials_contract as VMC

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEGACY_PACK = os.path.join(ROOT, "materials", "2026-08", "2026-08-04_Agent副业创收素材包.md")


def test_normalize_strips_punctuation_and_spaces():
    assert VMC.normalize("  AI 时代，来了！") == "AI时代来了"


def test_parse_frontmatter_basic():
    text = "---\njob_id: 2026-08-04_X\ntheme: 测试\nconsumed_materials: M1 M2\n---\n正文"
    fm = VMC.parse_frontmatter(text)
    assert fm is not None
    assert fm["job_id"] == "2026-08-04_X"
    assert fm["consumed_materials"] == ["M1", "M2"]


def test_parse_frontmatter_none_when_missing():
    assert VMC.parse_frontmatter("没有 frontmatter 的正文") is None


SCHEMA_PACK = """\
# 素材包
- **M1｜快手数据**：2026 年第一季度快手磁力引擎大会披露，AI 漫剧产量 12.2 万部、占比 95%。（source_type: 真实数据 | priority: 核心）
- **A1｜完播率生死线**：制作精良的 AI 短剧完播率可达 60%。（source_type: 真实数据 | priority: 辅助）
"""


def test_parse_materials_schema_mode():
    items, complete = VMC.parse_materials(SCHEMA_PACK)
    assert complete is True
    assert len(items) == 2
    assert all("kw" in it for it in items)
    assert items[0]["id"] == "M1"
    assert items[0]["source_type"] == "真实数据"


LEGACY_SAMPLE = """\
# Hook
这是一句足够长的钩子标题，用来触发 legacy hook 分支

## 数据
某报告显示用户增长了 30%。
"""


def test_parse_materials_legacy_no_crash_and_has_kw():
    # 关键回归：legacy 分支此前 mid 未初始化会抛 UnboundLocalError（B1）
    items, complete = VMC.parse_materials(LEGACY_SAMPLE)
    assert complete is False
    assert len(items) >= 1
    assert all("kw" in it for it in items), "legacy item 必须含 kw 键"
    assert all(it["id"].startswith("M") for it in items)


def test_parse_materials_real_legacy_pack_no_crash():
    # 用真实老素材包做回归：其 source_type 计数为 0，必走 legacy 分支
    import pytest
    if not os.path.exists(LEGACY_PACK):
        pytest.skip("真实 legacy 素材包不存在，跳过")
    text = VMC.read_text(LEGACY_PACK)
    items, complete = VMC.parse_materials(text)
    assert complete is False
    for it in items:
        assert "kw" in it
