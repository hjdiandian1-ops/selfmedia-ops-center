# -*- coding: utf-8 -*-
"""素材契约校验器纯逻辑单测。仅依赖标准库，不触网、不连 NAS。"""
import os
import subprocess
import sys

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


def test_parse_frontmatter_supports_a_ids():
    fm = VMC.parse_frontmatter("---\nconsumed_materials: [A2, A3, M1]\n---\n正文")
    assert fm["consumed_materials"] == ["A2", "A3", "M1"]


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


def _write_job(tmp_path, platforms_text, pack_text):
    out = tmp_path / "2026-08-07_测试Job"
    for plat, text in platforms_text.items():
        d = out / plat
        d.mkdir(parents=True, exist_ok=True)
        (d / "文案.md").write_text(text, encoding="utf-8")
    pack = out / "素材包.md"
    pack.write_text(pack_text, encoding="utf-8")
    return out, pack


def _run_validator(out, pack):
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "validate_materials_contract.py"),
         str(out), "--materials", str(pack)],
        capture_output=True, text=True,
    )
    return r


def test_validator_rejects_real_data_without_url(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {
            "小红书": "# 标题\n\n正文 30%。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n评论区聊聊👇",
        },
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心）",
    )
    r = _run_validator(out, pack)
    assert r.returncode == 1
    assert "C8-url-required" in r.stdout


def test_validator_rejects_url_placeholder(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {"小红书": "# 标题\n\n正文 30%。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n评论区聊聊👇"},
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心）链接待补",
    )
    r = _run_validator(out, pack)
    assert "C8-url-placeholder" in r.stdout


def test_validator_rejects_xhs_without_tags(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {
            "小红书": "# 标题\n\n正文 30%，具体数字两个：50 倍和 1 元。\n\n评论区聊聊👇",
            "公众号": "# 标题\n\n正文 30%。\n\n## 参考来源\n- 来源：https://example.com/x",
        },
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator(out, pack)
    assert "C9-xhs-tags" in r.stdout


def test_validator_rejects_gzh_duplicate_paragraph(tmp_path):
    dup = "API 价格进入上行周期，企业注意力会从哪个模型最强转向单位调用成本最低。"
    out, pack = _write_job(
        tmp_path,
        {
            "小红书": "# 标题\n\n正文 30%。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n评论区聊聊👇",
            "公众号": f"# 标题\n\n{dup}\n\n其他内容。\n\n{dup}\n\n## 参考来源\n- 来源：https://example.com/x",
        },
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator(out, pack)
    assert "C9-gzh-dup" in r.stdout


def test_platform_completeness_missing_dir(tmp_path):
    issues = VMC.platform_completeness(str(tmp_path))
    assert any(code == "C10-dir-missing" for _, code, _ in issues)
    assert any(code == "C10-score-report" for _, code, _ in issues)


def test_c11_gzh_viz_count_fails(tmp_path):
    d = tmp_path / "公众号"
    d.mkdir(parents=True)
    (d / "gzh_x.html").write_text('<section data-viz="table"></section>', encoding="utf-8")
    issues = VMC.gzh_data_viz_issues(str(tmp_path))
    assert any(code == "C11-viz-count" for _, code, _ in issues)


def test_c11_gzh_viz_placeholder_fails(tmp_path):
    d = tmp_path / "公众号"
    d.mkdir(parents=True)
    (d / "gzh_x.html").write_text(
        '<section data-viz="table"></section><section data-viz="bar"></section>'
        "[[IMG:outputs/x/chart.png]]",
        encoding="utf-8",
    )
    issues = VMC.gzh_data_viz_issues(str(tmp_path))
    assert any(code == "C11-img-placeholder" for _, code, _ in issues)


def test_c11_gzh_viz_two_components_pass(tmp_path):
    d = tmp_path / "公众号"
    d.mkdir(parents=True)
    (d / "gzh_x.html").write_text(
        '<section data-viz="table"></section><section data-viz="bar"></section>',
        encoding="utf-8",
    )
    assert VMC.gzh_data_viz_issues(str(tmp_path)) == []


def test_c12_xhs_viz_missing_fails(tmp_path):
    d = tmp_path / "小红书"
    d.mkdir(parents=True)
    (d / "rednote_x_slides.html").write_text("<div>纯文字，无可视化</div>", encoding="utf-8")
    issues = VMC.xhs_data_viz_issues(str(tmp_path))
    assert any(code == "C12-viz-missing" for _, code, _ in issues)


def test_c12_xhs_viz_marker_pass(tmp_path):
    d = tmp_path / "小红书"
    d.mkdir(parents=True)
    (d / "rednote_x_slides.html").write_text(
        '<div class="h-bar-chart"></div>', encoding="utf-8")
    assert VMC.xhs_data_viz_issues(str(tmp_path)) == []


def _run_validator_args(out, pack, extra):
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "validate_materials_contract.py"),
         str(out), "--materials", str(pack), *extra],
        capture_output=True, text=True,
    )


def _xhs_draft(body, series=""):
    fm = [
        "---",
        "job_id: 2026-08-08_测试",
        "platform: 小红书",
        "consumed_materials: [M1]",
        "hook_formula: dbs-xhs-title #1",
    ]
    if series:
        fm.append(f"series: {series}")
    fm.append("---")
    return "\n".join(fm) + "\n" + body


def test_c13_rejects_missing_follow_cta(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {"小红书": _xhs_draft(
            "# 标题\n\n正文 30% 和 1 元。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n评论区聊聊👇"
        )},
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator_args(out, pack, ["--outputs-root", str(tmp_path)])
    assert "C13-xhs-follow-cta" in r.stdout


def test_c13_rejects_follow_without_next_hook(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {"小红书": _xhs_draft(
            "# 标题\n\n正文 30% 和 1 元。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n觉得有用记得点赞关注！"
        )},
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator_args(out, pack, ["--outputs-root", str(tmp_path)])
    assert "C13-xhs-next-hook" in r.stdout


def test_c13_follow_cta_pass(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {"小红书": _xhs_draft(
            "# 标题\n\n正文 30% 和 1 元。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n关注我，下期拆这条流水线的成本账。"
        )},
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator_args(out, pack, ["--outputs-root", str(tmp_path)])
    assert "C13-xhs-follow-cta" not in r.stdout
    assert "C13-xhs-next-hook" not in r.stdout


def test_c13_series_format_fail(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {"小红书": _xhs_draft(
            "# 标题\n\n正文 30% 和 1 元。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n关注我，下期拆账本。",
            series="内容工厂3",
        )},
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
    )
    r = _run_validator_args(out, pack, ["--outputs-root", str(tmp_path)])
    assert "C13-series-format" in r.stdout


def test_c13_series_collection_required_at_3(tmp_path):
    outputs_root = tmp_path / "outputs"
    # 已有同系列第 1、2 篇（不含合集引导）
    for i, body in enumerate([
        "关注我，下期继续拆。正文 30% 和 1 元。#标签1 #标签2 #标签3 #标签4 #标签5",
        "关注我，下期继续拆。正文 30% 和 1 元。#标签1 #标签2 #标签3 #标签4 #标签5",
    ], start=1):
        d = outputs_root / f"2026-08-0{i}_旧" / "小红书"
        d.mkdir(parents=True)
        (d / "文案.md").write_text(_xhs_draft(body, series=f"AI内容工厂|第{i}篇"),
                                   encoding="utf-8")
    # 当前第 3 篇仍未引导合集 → FAIL
    cur = outputs_root / "2026-08-08_当前" / "小红书"
    cur.mkdir(parents=True)
    (cur / "文案.md").write_text(_xhs_draft(
        "# 标题\n\n正文 30% 和 1 元。\n\n#标签1 #标签2 #标签3 #标签4 #标签5\n\n关注我，下期继续拆。",
        series="AI内容工厂|第3篇",
    ), encoding="utf-8")
    pack = outputs_root / "2026-08-08_当前" / "素材包.md"
    pack.write_text(
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心 | source: https://example.com/x）",
        encoding="utf-8",
    )
    r = _run_validator_args(str(cur.parent), pack, ["--outputs-root", str(outputs_root)])
    assert "C13-series-collection" in r.stdout
