# -*- coding: utf-8 -*-
"""运营中心看板后端单测：/api/stats 聚合 与 /api/stats/backfill 校验。"""
import json
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

WEBAPP_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"))
if WEBAPP_DIR not in sys.path:
    sys.path.insert(0, WEBAPP_DIR)

import server  # noqa: E402


def _write_job(job_id, state="archive", log=None, scores=None):
    jdir = os.path.join(server.JOBS_DIR, job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "state.json"), "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id, "theme": f"主题-{job_id}", "state": state,
            "reject_count": 0, "scores": scores or {"review": 95},
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }, f, ensure_ascii=False)
    if log is not None:
        with open(os.path.join(jdir, "publish_log.json"), "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)


@pytest.fixture()
def isolated_dirs(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    jobs_dir.mkdir()
    outputs_dir.mkdir()
    monkeypatch.setattr(server, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(server, "OUTPUTS_DIR", str(outputs_dir))
    return jobs_dir, outputs_dir


def test_stats_empty(isolated_dirs):
    d = server.api_stats()
    assert d["jobs_total"] == 0
    assert d["pending_recycle"] == 0
    assert d["hits"] == 0
    assert d["recent"] == []
    assert len(d["trend"]) == 7


def test_themes_endpoint():
    d = server.api_themes()
    assert d["count"] == 6
    assert len(d["themes"]) == 6
    for t in d["themes"]:
        for key in ("id", "name", "emoji", "slogan", "audience",
                    "hooks", "samples", "traffic", "formulas"):
            assert key in t, f"主题缺少字段: {key}"
        assert len(t["samples"]) >= 2


def test_stats_aggregation(isolated_dirs):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    _write_job("2026-08-01_A", state="recycle", log={
        "job_id": "2026-08-01_A", "records": [
            {"platform": "小红书", "collected_at": yesterday, "reads": 5000, "likes": 300,
             "collects": 50, "comments": 10, "engagement": 0.072, "hit": True},
            {"platform": "公众号", "collected_at": three_days_ago, "reads": 1200, "likes": 30,
             "collects": 5, "comments": 2, "engagement": 0.0308, "hit": False},
        ],
    })
    _write_job("2026-08-02_B", state="archive", log={
        "job_id": "2026-08-02_B", "published_at": yesterday, "publish": [{"platform": "公众号"}], "records": [],
    })

    d = server.api_stats()
    assert d["jobs_total"] == 2
    assert d["published_jobs"] == 2
    assert d["hits"] == 1
    assert d["total_reads"] == 6200
    assert d["total_likes"] == 330
    assert d["total_collects"] == 55
    assert d["total_comments"] == 12
    assert d["avg_engagement"] == round(397 / 6200, 4)
    assert len(d["recent"]) == 2
    assert d["recent"][0]["job_id"] == "2026-08-01_A"
    assert d["recent"][0]["platform"] == "小红书"


def test_stats_pending_recycle(isolated_dirs):
    old = (datetime.now() - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
    _write_job("2026-07-30_待回收", state="archive", log={
        "job_id": "2026-07-30_待回收", "published_at": old, "publish": [], "records": [],
    })
    d = server.api_stats()
    assert d["pending_recycle"] == 1


def _call_backfill(payload):
    return server.api_stats_backfill(server.StatsBackfill(**payload))


def test_backfill_validation(isolated_dirs):
    _write_job("2026-08-03_校验")
    base = {"job_id": "2026-08-03_校验", "platform": "小红书",
            "reads": 100, "likes": 10, "collects": 2, "comments": 1}
    with pytest.raises(HTTPException) as e:
        _call_backfill({**base, "platform": "微博"})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_backfill({**base, "reads": -1})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_backfill({**base, "job_id": "  "})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_backfill({**base, "job_id": "不存在"})
    assert e.value.status_code == 404


def test_backfill_success(isolated_dirs, monkeypatch):
    _write_job("2026-08-04_回填")
    captured = {}

    def fake_run(args, timeout=60):
        captured["args"] = args
        captured["timeout"] = timeout
        return {"ok": True, "exit": 0, "stdout": "✅ 已记录", "stderr": ""}

    monkeypatch.setattr(server, "run_script", fake_run)
    r = _call_backfill({
        "job_id": "2026-08-04_回填", "platform": "小红书",
        "reads": 5200, "likes": 260, "collects": 80, "comments": 15, "url": "https://xhs.example/note",
    })
    assert r["ok"] is True
    assert captured["args"][0] == "collect_post_stats.py"
    assert "2026-08-04_回填" in captured["args"]
    assert "--platform" in captured["args"]
    assert "--reads" in captured["args"]
    assert "5200" in captured["args"]
    assert captured["timeout"] == 30


def test_manual_publish_validation(isolated_dirs):
    _write_job("2026-08-05_手动发布")
    base = {"job_id": "2026-08-05_手动发布", "platform": "小红书"}
    with pytest.raises(HTTPException) as e:
        _call_manual_publish({**base, "platform": "微博"})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_manual_publish({**base, "note": "x" * 201})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_manual_publish({**base, "title": "t" * 121})
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _call_manual_publish({**base, "job_id": "不存在"})
    assert e.value.status_code == 404


def _call_manual_publish(payload):
    return server.api_publish_manual(server.ManualPublishRequest(**payload))


def test_manual_publish_success(isolated_dirs, monkeypatch):
    _write_job("2026-08-05_手动发布")
    captured = {}

    def fake_run(args, timeout=60):
        captured["args"] = args
        captured["timeout"] = timeout
        return {"ok": True, "exit": 0, "stdout": "✅ 已记录手动发布", "stderr": ""}

    monkeypatch.setattr(server, "run_script", fake_run)
    r = _call_manual_publish({
        "job_id": "2026-08-05_手动发布", "platform": "小红书", "note": "手机端已发"})
    assert r["ok"] is True
    assert captured["args"][0] == "record_manual_publish.py"
    assert captured["args"][1] == "2026-08-05_手动发布"
    assert "--platform" in captured["args"]
    assert captured["timeout"] == 30


def test_xhs_material_endpoint(isolated_dirs, monkeypatch):
    with pytest.raises(HTTPException) as e:
        server.api_xhs_material(server.XhsMaterialRequest(job_id="不存在"))
    assert e.value.status_code == 404

    _write_job("2026-08-05_素材包")
    os.makedirs(os.path.join(server.OUTPUTS_DIR, "2026-08-05_素材包"), exist_ok=True)
    captured = {}

    def fake_run(args, timeout=60):
        captured["args"] = args
        return {"ok": True, "exit": 0, "stdout": "✅ 小红书发布素材包已生成", "stderr": ""}

    monkeypatch.setattr(server, "run_script", fake_run)
    r = server.api_xhs_material(server.XhsMaterialRequest(job_id="2026-08-05_素材包"))
    assert r["ok"] is True
    assert r["folder"].endswith("小红书发布素材包")
    assert captured["args"] == ["prepare_xhs_material.py", "2026-08-05_素材包"]
