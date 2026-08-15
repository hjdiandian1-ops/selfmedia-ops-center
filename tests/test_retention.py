# -*- coding: utf-8 -*-
"""数据保留清理引擎单测：候选/日志/快照/跟踪库/归档/大文件/导入文件。"""
import json
import os
import time
from datetime import datetime, timedelta

import retention as RT


def _w(root, rel, data):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return p


def _old(path, days=100):
    t = time.time() - days * 86400
    os.utime(path, (t, t))


def _now():
    return datetime.now()


def test_candidates_expiry(tmp_path):
    root = str(tmp_path)
    now = _now()
    store = {"candidates": [
        {"id": "c_old_pending", "status": "pending", "last_seen_at": (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")},
        {"id": "c_fresh_pending", "status": "pending", "last_seen_at": now.strftime("%Y-%m-%d %H:%M:%S")},
        {"id": "c_old_ignored", "status": "ignored", "last_seen_at": (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")},
        {"id": "c_tracked", "status": "tracked", "last_seen_at": (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")},
    ]}
    _w(root, "data/flywheel/viral_candidates.json", store)
    result = RT.scan(root, now=now)
    assert set(result["plan"]["candidates"]) == {"c_old_pending", "c_old_ignored"}
    applied = RT.apply_plan(result, root)
    assert applied["applied"]["candidates"] == 2
    kept = json.load(open(os.path.join(root, "data/flywheel/viral_candidates.json")))["candidates"]
    assert {c["id"] for c in kept} == {"c_fresh_pending", "c_tracked"}


def test_logs_and_platform_days_and_videos(tmp_path):
    root = str(tmp_path)
    now = _now()
    old_log = os.path.join(root, "data/flywheel/breakdowns", "v_old.log")
    fresh_log = os.path.join(root, "data/flywheel/breakdowns", "v_fresh.log")
    os.makedirs(os.path.dirname(old_log), exist_ok=True)
    open(old_log, "w").write("x")
    open(fresh_log, "w").write("x")
    _old(old_log)

    _w(root, "data/flywheel/platform_virals.json", {
        "days": {"2026-01-01": {}, "2026-08-01": {}, (now - timedelta(days=3)).strftime("%Y-%m-%d"): {}},
    })
    vv_path = os.path.join(root, "data/flywheel/viral_videos.json")
    _w(root, "data/flywheel/viral_videos.json", {"videos": [
        {"id": "v_stale", "status": "tracked", "updated_at": (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")},
        {"id": "v_analyzed", "status": "analyzed", "updated_at": (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")},
    ]})

    result = RT.scan(root, now=now)
    assert old_log in result["plan"]["logs"]
    assert fresh_log not in result["plan"]["logs"]
    assert "2026-01-01" in result["plan"]["platform_days"]
    assert "2026-08-01" not in result["plan"]["platform_days"]
    assert result["plan"]["stale_videos"] == ["v_stale"]

    RT.apply_plan(result, root)
    assert not os.path.exists(old_log)
    assert os.path.exists(fresh_log)
    pv = json.load(open(os.path.join(root, "data/flywheel/platform_virals.json")))
    assert "2026-01-01" not in pv["days"]
    vv = json.load(open(vv_path))["videos"]
    assert {v["id"] for v in vv} == {"v_analyzed"}


def test_job_archive_marker(tmp_path):
    root = str(tmp_path)
    now = _now()
    old = (now - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    fresh = now.strftime("%Y-%m-%d %H:%M:%S")
    for jid, ts in (("old_job", old), ("fresh_job", fresh)):
        _w(root, f"jobs/{jid}/state.json", {"job_id": jid, "state": "archive", "updated_at": ts})
    result = RT.scan(root, now=now)
    assert result["plan"]["jobs_to_archive"] == ["old_job"]
    RT.apply_plan(result, root)
    assert os.path.exists(os.path.join(root, "jobs/old_job/.archived"))
    assert not os.path.exists(os.path.join(root, "jobs/fresh_job/.archived"))


def test_media_cleanup_keeps_hit_jobs(tmp_path):
    root = str(tmp_path)
    now = _now()
    media1 = os.path.join(root, "outputs/no_hit_job", "img.png")
    media2 = os.path.join(root, "outputs/hit_job", "img.png")
    os.makedirs(os.path.dirname(media1), exist_ok=True)
    os.makedirs(os.path.dirname(media2), exist_ok=True)
    open(media1, "w").write("x")
    open(media2, "w").write("x")
    _old(media1)
    _old(media2)
    _w(root, "jobs/hit_job/publish_log.json", {"records": [{"hit": True}]})
    _w(root, "jobs/no_hit_job/publish_log.json", {"records": [{"hit": False}]})
    result = RT.scan(root, now=now)
    assert media1 in result["plan"]["media_files"]
    assert media2 not in result["plan"]["media_files"]
    RT.apply_plan(result, root)
    assert not os.path.exists(media1)
    assert os.path.exists(media2)


def test_dashboard_keep_last_12(tmp_path):
    root = str(tmp_path)
    dash = os.path.join(root, "data/stats/dashboard")
    os.makedirs(dash, exist_ok=True)
    paths = []
    for i in range(14):
        p = os.path.join(dash, f"dash_{i:02d}.json")
        open(p, "w").write("{}")
        t = time.time() - (14 - i) * 86400
        os.utime(p, (t, t))
        paths.append(p)
    result = RT.scan(root)
    assert len(result["plan"]["dashboard_files"]) == 2
    RT.apply_plan(result, root)
    assert len(os.listdir(dash)) == 12


def test_dry_run_does_not_delete(tmp_path):
    root = str(tmp_path)
    now = _now()
    p = _w(root, "data/flywheel/viral_candidates.json", {"candidates": [
        {"id": "c_old", "status": "pending", "last_seen_at": (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")},
    ]})
    RT.scan(root, now=now)
    store = json.load(open(p))
    assert len(store["candidates"]) == 1
