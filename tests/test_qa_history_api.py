"""
质检通过率趋势可视化与历史汇总测试 (QA History & Trend Visualization Tests)
==========================================================================
"""
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
WEBAPP = os.path.join(ROOT, "webapp")

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, WEBAPP)

import core  # noqa: E402
from server import app  # noqa: E402


def test_qa_history_empty(tmp_path, monkeypatch):
    """测试无 outputs 输出目录时的空态返回。"""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(core, "OUTPUTS_DIR", str(out_dir))

    client = TestClient(app)
    resp = client.get("/api/qa/history")
    assert resp.status_code == 200
    data = resp.json()

    assert data["items"] == []
    assert data["trends"]["total_inspections"] == 0
    assert data["trends"]["overall_pass_rate"] == 0.0
    assert data["top_issues"] == []


def test_qa_history_populated(tmp_path, monkeypatch):
    """测试多任务质检报告聚合、趋势指标与高频违规项统计。"""
    jobs_dir = tmp_path / "jobs"
    out_dir = tmp_path / "outputs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(core, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(core, "OUTPUTS_DIR", str(out_dir))

    # 1. 任务 1: 全部通过，Harsh 92 分
    j1 = "2026-08-10_AI短剧出海"
    (jobs_dir / j1).mkdir(parents=True, exist_ok=True)
    (jobs_dir / j1 / "state.json").write_text(json.dumps({"theme": "AI短剧出海", "state": "archive"}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j1).mkdir(parents=True, exist_ok=True)
    (out_dir / j1 / "validate_report.json").write_text(json.dumps({"verdict": "PASSED"}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j1 / "harsh_report.json").write_text(json.dumps({"verdict": "PASSED", "score": 92}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j1 / "ai_flavor_report.json").write_text(json.dumps({"verdict": "PASSED", "total_hits": 0}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j1 / "compliance_report.json").write_text(json.dumps({"verdict": "PASSED"}, ensure_ascii=False), encoding="utf-8")

    # 2. 任务 2: Harsh 82 分但通过
    j2 = "2026-08-11_AI写作变现实战"
    (jobs_dir / j2).mkdir(parents=True, exist_ok=True)
    (jobs_dir / j2 / "state.json").write_text(json.dumps({"theme": "AI写作变现", "state": "publish"}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j2).mkdir(parents=True, exist_ok=True)
    (out_dir / j2 / "validate_report.json").write_text(json.dumps({"verdict": "PASSED"}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j2 / "harsh_report.json").write_text(json.dumps({"verdict": "PASSED", "score": 82}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j2 / "ai_flavor_report.json").write_text(json.dumps({"verdict": "PASSED", "total_hits": 1}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j2 / "compliance_report.json").write_text(json.dumps({"verdict": "PASSED"}, ensure_ascii=False), encoding="utf-8")

    # 3. 任务 3: 契约失败 (未通过)
    j3 = "2026-08-12_自媒体自动化实战"
    (jobs_dir / j3).mkdir(parents=True, exist_ok=True)
    (jobs_dir / j3 / "state.json").write_text(json.dumps({"theme": "自媒体自动化", "state": "review"}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j3).mkdir(parents=True, exist_ok=True)
    (out_dir / j3 / "validate_report.json").write_text(json.dumps({
        "verdict": "REJECTED",
        "results": [{"level": "FAIL", "code": "C13-follow-cta"}]
    }, ensure_ascii=False), encoding="utf-8")
    (out_dir / j3 / "harsh_report.json").write_text(json.dumps({"verdict": "PASSED", "score": 78}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j3 / "ai_flavor_report.json").write_text(json.dumps({"verdict": "REJECTED", "total_hits": 4, "rules": [{"rule": "ai_opening"}]}, ensure_ascii=False), encoding="utf-8")
    (out_dir / j3 / "compliance_report.json").write_text(json.dumps({"verdict": "PASSED"}, ensure_ascii=False), encoding="utf-8")

    client = TestClient(app)
    resp = client.get("/api/qa/history")
    assert resp.status_code == 200
    data = resp.json()

    items = data["items"]
    assert len(items) == 3

    # 验证第一条 (j1) 全部通过
    it1 = next(x for x in items if x["job_id"] == j1)
    assert it1["overall"] is True
    assert it1["harsh_score"] == 92

    # 验证第三条 (j3) 综合未通过
    it3 = next(x for x in items if x["job_id"] == j3)
    assert it3["overall"] is False
    assert it3["contract_pass"] is False
    assert it3["ai_pass"] is False

    # 验证汇总趋势指标
    trends = data["trends"]
    assert trends["total_inspections"] == 3
    # 2/3 通过 = 66.7%
    assert 66.0 <= trends["overall_pass_rate"] <= 67.0

    # 验证高频失分项
    top_issues = data["top_issues"]
    rules = [iss["rule"] for iss in top_issues]
    assert "C13-follow-cta" in rules
    assert "ai_opening" in rules

    # 验证里程碑徽章
    milestones = data["milestones"]
    ms_titles = [m["title"] for m in milestones]
    assert "质检闭环" in ms_titles
    assert "品质巅峰" in ms_titles
