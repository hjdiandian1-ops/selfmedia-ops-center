# -*- coding: utf-8 -*-
"""去 AI 味机器初筛单测：句式壳/标点/语气/开头收尾/聚合计数/报告落盘。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import ai_flavor_check as AFC


def _write(tmp_path, plat, text):
    d = tmp_path / plat
    d.mkdir(parents=True, exist_ok=True)
    (d / "文案.md").write_text(text, encoding="utf-8")
    return str(tmp_path)


def _rules(report):
    return {h["rule"] for h in report["hits"]}


def test_clean_text_passed(tmp_path):
    _write(tmp_path, "小红书", "实测跑了三天，NAS 上 8G 显存就能跑通。具体数字和结论都在后面。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "PASSED"
    assert r["hits"] == []


def test_formula_progression_rejects(tmp_path):
    _write(tmp_path, "公众号", "首先我们要看它的架构，其次对比性能，最后给出结论。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "REJECTED"
    assert "formula_progression" in _rules(r)


def test_symmetry_closure_rejects(tmp_path):
    _write(tmp_path, "公众号", "这不是结束，而是新的开始。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "REJECTED"
    assert "symmetry_closure" in _rules(r)


def test_announcer_transition_rejects(tmp_path):
    _write(tmp_path, "公众号", "接下来，我们从三个方面来看这个问题。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "REJECTED"
    assert "announcer_transition" in _rules(r)


def test_belittle_reader_rejects(tmp_path):
    _write(tmp_path, "小红书", "如果你连这个都不知道，说明你落后了。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "REJECTED"
    assert "belittle_reader" in _rules(r)


def test_binary_shell_warn_then_reject(tmp_path):
    one = "这不是价格问题，而是价值问题。其他内容都正常。"
    r1 = AFC.run(_write(tmp_path / "a", "小红书", one))
    assert r1["verdict"] == "WARN"
    three = "不是 A 而是 B；不是 C 而是 D；不是 E 而是 F。"
    r2 = AFC.run(_write(tmp_path / "b", "公众号", three))
    assert r2["verdict"] == "REJECTED"
    assert any(h["rule"] == "binary_shell" and h["count"] == 3 for h in r2["hits"])


def test_essence_claim_warn_then_reject(tmp_path):
    one = "本质上，这个方案可行。"
    r1 = AFC.run(_write(tmp_path / "a", "小红书", one))
    assert r1["verdict"] == "WARN"
    assert "essence_claim" in _rules(r1)
    three = "本质上要稳；真正重要的是成本；核心在于落地；底层逻辑是数据。"
    r2 = AFC.run(_write(tmp_path / "b", "公众号", three))
    assert r2["verdict"] == "REJECTED"


def test_assistant_marker_aggregates_across_platforms(tmp_path):
    _write(tmp_path, "小红书", "值得注意的是，这个数字变了。")
    _write(tmp_path, "公众号", "不可否认的是，趋势已经形成。")
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "REJECTED"  # 跨平台合并计数 2 ≥ 2
    hit = next(h for h in r["hits"] if h["rule"] == "assistant_marker")
    assert hit["count"] == 2
    assert set(hit["platforms"]) == {"小红书", "公众号"}


def test_quotes_and_dash_warn(tmp_path):
    text = "这就是所谓的“AI同事”，还有“数字员工”“超级个体”，以及《终极答案》。——这真的对吗？——其实不用纠结。"
    r = AFC.run(_write(tmp_path, "公众号", text))
    assert r["verdict"] == "WARN"
    assert "prose_quotes" in _rules(r)
    assert "dash_rhetoric" in _rules(r)


def test_parallel_structure_warn(tmp_path):
    text = "\n".join([
        "能不能让流程更短一点。",
        "能不能让成本更低一点。",
        "能不能让门槛更低一点。",
        "能不能让结果更稳一点。",
    ])
    r = AFC.run(_write(tmp_path, "短视频", text))
    assert r["verdict"] == "WARN"
    hit = next(h for h in r["hits"] if h["rule"] == "parallel_structure")
    assert hit["count"] >= 4


def test_teacher_qa_warn_then_reject(tmp_path):
    one = "那么，这意味着什么？答案是显而易见的。"
    r1 = AFC.run(_write(tmp_path / "a", "小红书", one))
    assert r1["verdict"] == "WARN"
    three = "那么这意味着什么？答案是 A。所以这意味着什么？答案很简单。原因很简单，就是成本。"
    r2 = AFC.run(_write(tmp_path / "b", "公众号", three))
    assert r2["verdict"] == "REJECTED"
    assert "teacher_qa" in _rules(r2)


def test_rhetorical_opening_warn(tmp_path):
    text = "那这对创业者意味着什么？先看一组数据。"
    r = AFC.run(_write(tmp_path, "公众号", text))
    assert r["verdict"] == "WARN"
    assert "rhetorical_opening" in _rules(r)


def test_no_platform_texts_passed(tmp_path):
    r = AFC.run(str(tmp_path))
    assert r["verdict"] == "PASSED"
    assert r["summary"]["platforms"] == []


def test_report_json_written(tmp_path, monkeypatch):
    _write(tmp_path, "小红书", "本质上，这个方案可行。")
    out = tmp_path / "ai_flavor_report.json"
    monkeypatch.setattr(sys, "argv", [
        "ai_flavor_check.py", str(tmp_path), "--out", str(out),
    ])
    with pytest.raises(SystemExit) as exc:
        AFC.main()
    assert exc.value.code == 0  # WARN 不阻塞
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["verdict"] == "WARN"
    assert "rules_note" in saved


def test_report_rejected_exit_code(tmp_path, monkeypatch):
    _write(tmp_path, "公众号", "首先讲背景，其次讲方案，最后给结论。")
    out = tmp_path / "ai_flavor_report.json"
    monkeypatch.setattr(sys, "argv", [
        "ai_flavor_check.py", str(tmp_path), "--out", str(out),
    ])
    with pytest.raises(SystemExit) as exc:
        AFC.main()
    assert exc.value.code == 1
