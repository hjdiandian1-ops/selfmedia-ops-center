# -*- coding: utf-8 -*-
"""平台独立看板：三平台聚合 / 健康度 / 雷达 / 诊断快照。"""
import json
import os
from datetime import datetime, timedelta

import dashboard_analysis as DA
import data_stats


def _write_job(root, job_id, platform, records=None, publishes=None):
    jdir = os.path.join(root, "jobs", job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "state.json"), "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id, "theme": f"主题-{job_id}", "state": "archive",
            "updated_at": _days_ago_str(0),
        }, f, ensure_ascii=False, indent=2)
    data = {
        "job_id": job_id,
        "records": records or [],
        "publish": publishes or [],
        "platforms": [platform],
    }
    with open(os.path.join(jdir, "publish_log.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _days_ago_str(days):
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def test_platforms_aggregation_and_health(tmp_path):
    root = str(tmp_path)
    _write_job(root, "job_gzh", "公众号", records=[
        {"platform": "公众号", "collected_at": _days_ago_str(1), "reads": 800,
         "likes": 30, "collects": 10, "comments": 5, "engagement": 0.056, "hit": False},
        {"platform": "公众号", "collected_at": _days_ago_str(2), "reads": 300,
         "likes": 2, "collects": 1, "comments": 0, "engagement": 0.01, "hit": False},
    ], publishes=[
        {"platform": "公众号", "status": "success", "mode": "manual",
         "at": _days_ago_str(1)},
    ])
    _write_job(root, "job_video", "短视频", records=[
        {"platform": "短视频", "collected_at": _days_ago_str(1), "reads": 5000,
         "likes": 300, "collects": 100, "comments": 60, "engagement": 0.092, "hit": True},
    ], publishes=[
        {"platform": "短视频", "status": "success", "mode": "manual",
         "at": _days_ago_str(1)},
    ])
    d = DA.build_dashboard(range_days=7, jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    # 旧字段兼容
    assert "tabs" in d and "weak_points" in d and "sources" in d
    # 新字段
    assert set(d["platforms"]) == {"小红书", "公众号", "短视频"}
    assert "overview" in d and "diagnostics" in d

    gzh = d["platforms"]["公众号"]
    assert gzh["totals"]["publish_count"] == 1
    assert gzh["totals"]["backfill_count"] == 2
    assert gzh["totals"]["total_reads"] == 1100
    assert gzh["health_score"] is not None and 0 <= gzh["health_score"] <= 100
    assert any(a["available"] for a in gzh["radar"]["axes"])

    video = d["platforms"]["短视频"]
    assert video["totals"]["hits"] == 1
    assert video["recent"][0]["quick"] == "爆款：延续该公式"

    assert d["overview"]["health_score"] is not None
    assert d["overview"]["focus"]
    assert len(d["overview"]["recent"]) <= 10


def test_platform_no_data_guidance(tmp_path):
    root = str(tmp_path)
    d = DA.build_dashboard(range_days=7, jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    assert d["platforms"]["公众号"]["health_score"] is None
    assert d["platforms"]["短视频"]["health_score"] is None
    assert any(w["id"] == "公众号_no_data" for w in d["platforms"]["公众号"]["weak_points"])
    assert any(w["id"] == "短视频_no_data" for w in d["platforms"]["短视频"]["weak_points"])


def test_diagnostics_snapshot_and_delta(tmp_path):
    root = str(tmp_path)
    jobs = os.path.join(root, "jobs")
    data = os.path.join(root, "data")
    _write_job(root, "job_gzh", "公众号", records=[
        {"platform": "公众号", "collected_at": _days_ago_str(1), "reads": 1000,
         "likes": 50, "collects": 10, "comments": 5, "engagement": 0.065, "hit": True},
    ], publishes=[{"platform": "公众号", "status": "success", "mode": "manual",
                   "at": _days_ago_str(1)}])
    d1 = DA.build_dashboard(range_days=7, jobs_dir=jobs,
                            outputs_dir=os.path.join(root, "outputs"), data_dir=data)
    assert d1["diagnostics"]["previous_at"] is None
    d2 = DA.build_dashboard(range_days=7, jobs_dir=jobs,
                            outputs_dir=os.path.join(root, "outputs"), data_dir=data)
    assert d2["diagnostics"]["previous_at"] == d1["diagnostics"]["generated_at"]
    assert "公众号" in d2["diagnostics"]["deltas"]
    path = os.path.join(data, "dashboard", "diagnostics.json")
    assert os.path.exists(path)


def test_radar_values_normalized(tmp_path):
    root = str(tmp_path)
    d = DA.build_dashboard(range_days=7, jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    for p in d["platforms"].values():
        for ax in p["radar"]["axes"]:
            if ax["value"] is not None:
                assert 0 <= ax["value"] <= 125


def test_period_mapping(tmp_path):
    root = str(tmp_path)
    d = DA.build_dashboard(period="week", jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    assert d["range_days"] == 90 and d["period"] == "week"


def test_platform_filter(tmp_path):
    root = str(tmp_path)
    _write_job(root, "job_gzh", "公众号", records=[
        {"platform": "公众号", "collected_at": _days_ago_str(1), "reads": 800,
         "likes": 20, "collects": 5, "comments": 2, "engagement": 0.034, "hit": False},
    ], publishes=[{"platform": "公众号", "status": "success", "mode": "manual",
                   "at": _days_ago_str(1)}])
    d = DA.build_dashboard(range_days=7, platforms=["公众号"],
                           jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    assert set(d["platforms"]) == {"公众号"}
    assert d["overview"]["health_score"] is not None


def test_stats_platform_filter(tmp_path):
    root = str(tmp_path)
    _write_job(root, "job_xhs", "小红书", records=[
        {"platform": "小红书", "collected_at": _days_ago_str(1), "reads": 2000,
         "likes": 100, "collects": 20, "comments": 10, "engagement": 0.065, "hit": True},
    ], publishes=[{"platform": "小红书", "status": "success", "mode": "manual",
                   "at": _days_ago_str(1)}])
    _write_job(root, "job_gzh", "公众号", records=[
        {"platform": "公众号", "collected_at": _days_ago_str(1), "reads": 9999,
         "likes": 500, "collects": 50, "comments": 20, "engagement": 0.057, "hit": True},
    ], publishes=[{"platform": "公众号", "status": "success", "mode": "manual",
                   "at": _days_ago_str(1)}])
    s = data_stats.build_summary(jobs_dir=os.path.join(root, "jobs"),
                                 outputs_dir=os.path.join(root, "outputs"),
                                 data_dir=os.path.join(root, "data"),
                                 platforms=["小红书"])
    assert {p["platform"] for p in s["by_platform"]} == {"小红书"}
    assert "followers_gained" in s["by_platform"][0]
    assert "followers_total" in s
    assert s["total_reads"] == 2000


def test_xhs_publish_uses_imported_export(tmp_path):
    root = str(tmp_path)
    _write_job(root, "job_xhs", "小红书", records=[], publishes=[
        {"platform": "小红书", "status": "success", "mode": "manual", "at": _days_ago_str(1)},
        {"platform": "小红书", "status": "success", "mode": "manual", "at": _days_ago_str(2)},
    ])
    dash = os.path.join(root, "data", "dashboard")
    os.makedirs(dash, exist_ok=True)
    today = datetime.now().date().isoformat()
    with open(os.path.join(dash, "publish.json"), "w", encoding="utf-8") as f:
        json.dump({
            "kind": "publish",
            "account": {"总发布": 20},
            "series": {"总发布趋势": [
                {"date": today, "value": 3},
                {"date": _days_ago_str(1)[:10], "value": 2},
            ]},
        }, f, ensure_ascii=False, indent=2)
    d = DA.build_dashboard(range_days=7, jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"),
                           data_dir=os.path.join(root, "data"))
    xhs = d["platforms"]["小红书"]
    assert xhs["totals"]["publish_count"] == 20
    assert sum(xhs["trend"]["publishes"]) == 5


def test_xhs_notes_feed_platform_stats(tmp_path):
    root = str(tmp_path)
    _write_job(root, "job_xhs", "小红书", records=[], publishes=[])
    data = os.path.join(root, "data")
    os.makedirs(data, exist_ok=True)
    now = datetime.now()
    with open(os.path.join(data, "xhs_notes.json"), "w", encoding="utf-8") as f:
        json.dump({"notes": {
            "n1": {
                "title": "笔记A", "first_published_at": now.strftime("%Y年%m月%d日%H时%M分%S秒"),
                "format": "图文", "reads": 1000, "likes": 50, "collects": 10,
                "comments": 5, "shares": 2, "followers_gained": 3,
                "exposure": 5000, "ctr": 20, "avg_watch_seconds": 8,
            },
        }}, f, ensure_ascii=False, indent=2)
    d = DA.build_dashboard(range_days=7, jobs_dir=os.path.join(root, "jobs"),
                           outputs_dir=os.path.join(root, "outputs"), data_dir=data)
    xhs = d["platforms"]["小红书"]
    assert xhs["totals"]["total_reads"] == 1000
    assert xhs["totals"]["followers"] == 3
    assert xhs["totals"]["engagement"] == 0.065
    assert sum(xhs["trend"]["reads"]) == 1000
    assert xhs["recent"][0]["title"] == "笔记A"
