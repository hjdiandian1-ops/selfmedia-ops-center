# -*- coding: utf-8 -*-
"""Harsh Critic 评分器单测（覆盖可独立验证的纯函数 + B1 legacy 回归）。"""
import os
import subprocess
import sys

import validate_materials_contract as VMC
import harsh_critic_score as HCS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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


def test_hook_can_reach_full_10_points():
    text = (
        "# 任何标题\n\n"
        "实测 3 个月：NAS token 成本砍了 90%，秘密是缓存命中。\n\n"
        "正文继续 90%。"
    )
    dims, pts = HCS.machine_hook_breakdown(text)
    assert pts == 10
    assert len(dims) == 6


def _write_job(tmp_path, platforms_text, pack_text):
    out = tmp_path / "2026-08-07_评分Job"
    for plat, text in platforms_text.items():
        d = out / plat
        d.mkdir(parents=True, exist_ok=True)
        (d / "文案.md").write_text(text, encoding="utf-8")
    pack = out / "素材包.md"
    pack.write_text(pack_text, encoding="utf-8")
    return out, pack


def test_harsh_rejects_real_data_without_url(tmp_path):
    out, pack = _write_job(
        tmp_path,
        {
            "小红书": "# 标题\n\n正文 30%。\n\n评论区聊聊👇",
            "公众号": "# 标题\n\n正文 30%。",
        },
        "真实数据｜核心：某公司增长 30%（source_type: 真实数据 | priority: 核心）",
    )
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "harsh_critic_score.py"),
         str(out), "--materials", str(pack)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "REJECTED" in r.stdout
    assert "C8-url-required" in r.stdout
