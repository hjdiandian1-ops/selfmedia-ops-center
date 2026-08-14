# -*- coding: utf-8 -*-
"""内容合规审核器单测：广告法/医疗金融/导流/标题党/AI标识/外挂词库。"""
import json
import os

import compliance_check as CC


def _write(tmp_path, plat, name, text):
    d = tmp_path / plat
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _run(tmp_path):
    return CC.run(str(tmp_path))


def test_ad_absolute_rejects(tmp_path):
    _write(tmp_path, "小红书", "文案.md", "这是全网第一的AI工具，最好用，绝对领先。")
    r = _run(tmp_path)
    assert r["verdict"] == "REJECTED"
    highs = [c for c in r["checks"] if c["severity"] == "high"]
    assert any(c["rule"] == "ad_absolute" for c in highs)


def test_medical_claim_rejects(tmp_path):
    _write(tmp_path, "公众号", "文案.md", "这款茶饮能根治高血压，三天见效。")
    r = _run(tmp_path)
    assert r["verdict"] == "REJECTED"
    assert any(c["rule"] == "medical" for c in r["checks"])


def test_contact_leak_platform_severity(tmp_path):
    xhs_dir = tmp_path / "xhs"
    _write(xhs_dir, "小红书", "文案.md", "想领资料加微信 abc12345，私信领取。")
    r1 = _run(xhs_dir)
    assert r1["verdict"] == "REJECTED"
    assert any(c["rule"] == "contact_leak" and c["severity"] == "high" for c in r1["checks"])

    gzh_dir = tmp_path / "gzh"
    _write(gzh_dir, "公众号", "文案.md", "想领资料加微信 abc12345。")
    r2 = _run(gzh_dir)
    assert any(c["rule"] == "contact_leak" and c["severity"] == "medium" for c in r2["checks"])
    assert r2["verdict"] == "WARN"


def test_ai_notice_warn_and_ok(tmp_path):
    dy_dir = tmp_path / "dy"
    _write(dy_dir, "短视频", "文案.md", "这个技巧真的绝了。")
    r1 = _run(dy_dir)
    assert r1["verdict"] == "PASSED"  # 只有 warn 建议
    assert any(c["rule"] == "ai_notice" for c in r1["checks"])
    assert all(c["platform"] == "抖音" for c in r1["checks"])

    dy2 = tmp_path / "dy2"
    _write(dy2, "抖音", "文案.md", "本文由AI生成，以上内容为AI创作。")
    r2 = _run(dy2)
    assert not any(c["rule"] == "ai_notice" for c in r2["checks"])


def test_clickbait_warn(tmp_path):
    _write(tmp_path, "公众号", "文案.md", "震惊！不转不是中国人，速看。")
    r = _run(tmp_path)
    assert r["verdict"] == "WARN"
    assert any(c["rule"] == "clickbait" for c in r["checks"])


def test_external_wordlist(tmp_path, monkeypatch):
    words_dir = tmp_path / "words"
    words_dir.mkdir()
    (words_dir / "gzh.txt").write_text("# 公众号词库\n请立即删除\n", encoding="utf-8")
    monkeypatch.setattr(CC, "WORDS_DIR", str(words_dir))
    _write(tmp_path, "公众号", "文案.md", "这篇文章请立即删除，否则违规。")
    r = _run(tmp_path)
    assert any(c["rule"] == "platform_wordlist" and c["keyword"] == "请立即删除" for c in r["checks"])


def test_report_json_written(tmp_path):
    _write(tmp_path, "小红书", "文案.md", "普通内容，没有违规。")
    r = _run(tmp_path)
    p = tmp_path / "compliance_report.json"
    assert p.exists()
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved["verdict"] == r["verdict"]
    assert "rules_note" in saved


def test_builtin_and_external_dedup(tmp_path, monkeypatch):
    words_dir = tmp_path / "words"
    words_dir.mkdir()
    (words_dir / "ad.txt").write_text("排名第一\n", encoding="utf-8")
    monkeypatch.setattr(CC, "WORDS_DIR", str(words_dir))
    _write(tmp_path, "公众号", "文案.md", "这款产品排名第一。")
    r = _run(tmp_path)
    hits = [c for c in r["checks"] if c["rule"] == "ad_absolute" and c["keyword"] == "排名第一"]
    assert len(hits) == 1
