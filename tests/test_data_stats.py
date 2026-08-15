# -*- coding: utf-8 -*-
"""自有数据统计引擎单测：事件流 / 聚合 / 平台对比 / 主题 / 内容特征 / 待回收。"""
import json
import os
import sys
from datetime import datetime, timedelta

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import data_stats  # noqa: E402


def _write_state(jobs_dir, job_id, state="archive", theme="测试主题",
                 created_at=None, scores=None):
    jdir = os.path.join(str(jobs_dir), job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "state.json"), "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id,
            "theme": theme,
            "state": state,
            "created_at": created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reject_count": 0,
            "scores": scores or {"review": 95},
        }, f, ensure_ascii=False)


def _write_log(jobs_dir, job_id, publish=None, records=None,
               published_at=None, title=None):
    jdir = os.path.join(str(jobs_dir), job_id)
    os.makedirs(jdir, exist_ok=True)
    data = {
        "job_id": job_id,
        "publish": publish or [],
        "records": records or [],
        "title": title or job_id,
    }
    if published_at:
        data["published_at"] = published_at
    with open(os.path.join(jdir, "publish_log.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_outputs(outputs_dir, job_id, viz_count=2, card_count=4):
    gzh = os.path.join(str(outputs_dir), job_id, "公众号")
    os.makedirs(gzh, exist_ok=True)
    html = "正文" + '<section data-viz="bar"></section>' * viz_count
    with open(os.path.join(gzh, "gzh_test.html"), "w", encoding="utf-8") as f:
        f.write(html)
    xhs = os.path.join(str(outputs_dir), job_id, "小红书")
    os.makedirs(xhs, exist_ok=True)
    for i in range(card_count):
        with open(os.path.join(xhs, f"xhs-0{i + 1}.png"), "wb") as f:
            f.write(b"")
    with open(os.path.join(xhs, "slides.html"), "w", encoding="utf-8") as f:
        f.write('<div class="h-bar-chart"></div>')


def _dirs(tmp_path):
    jobs = tmp_path / "jobs"
    outputs = tmp_path / "outputs"
    data = tmp_path / "data"
    jobs.mkdir()
    outputs.mkdir()
    data.mkdir()
    return str(jobs), str(outputs), str(data)


def test_empty_summary(tmp_path):
    jobs, outputs, data = _dirs(tmp_path)
    s = data_stats.build_summary(jobs, outputs, data_dir=data)
    assert s["jobs_total"] == 0
    assert s["publish_events"] == 0
    assert s["backfill_records"] == 0
    assert s["hits"] == 0
    assert s["xhs_followers_gained"] == 0
    assert s["xhs_follower_rate"] == 0.0
    assert "by_follower_rate" in s["best"]
    assert "format" in s["content_insights"]
    assert s["recent"] == []
    assert len(s["trend"]) == 7
    assert [p["platform"] for p in s["by_platform"]] == ["小红书", "公众号", "短视频"]


def test_aggregation_with_platform_theme_and_features(tmp_path):
    jobs, outputs, data = _dirs(tmp_path)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    _write_state(jobs, "2026-08-01_数字标题", state="recycle", theme="AI 前沿")
    _write_outputs(outputs, "2026-08-01_数字标题", viz_count=3, card_count=4)
    _write_log(
        jobs, "2026-08-01_数字标题",
        publish=[
            {"platform": "公众号", "status": "success", "at": yesterday, "mode": "draft_api"},
            {"platform": "小红书", "status": "success", "at": yesterday},
        ],
        records=[
            {"platform": "小红书", "collected_at": yesterday, "reads": 5000, "likes": 300,
             "collects": 50, "comments": 10, "engagement": 0.072, "hit": True,
             "followers_gained": 2, "format": "图文", "ctr": 24.3},
            {"platform": "公众号", "collected_at": three_days_ago, "reads": 1200, "likes": 30,
             "collects": 5, "comments": 2, "engagement": 0.0308, "hit": False},
        ],
        published_at=yesterday,
        title="DeepSeek V4 数字实测",
    )

    _write_state(jobs, "2026-08-02_无回填", state="archive", theme="成本账本")
    _write_log(jobs, "2026-08-02_无回填",
               publish=[{"platform": "公众号", "status": "success", "at": yesterday}],
               published_at=yesterday,
               title="30 块钱的账")

    s = data_stats.build_summary(jobs, outputs, data_dir=data)
    assert s["jobs_total"] == 2
    assert s["published_jobs"] == 2
    assert s["publish_events"] == 3
    assert s["backfill_records"] == 2
    assert s["hits"] == 1
    assert s["total_reads"] == 6200
    assert s["total_likes"] == 330
    assert s["total_collects"] == 55
    assert s["total_comments"] == 12
    assert s["avg_engagement"] == round(397 / 6200, 4)
    assert s["xhs_followers_gained"] == 2
    assert s["xhs_follower_rate"] == round(2 / 5000, 6)
    assert s["recent"][0]["job_id"] == "2026-08-01_数字标题"
    assert s["recent"][0]["platform"] == "小红书"

    gzh = next(p for p in s["by_platform"] if p["platform"] == "公众号")
    xhs = next(p for p in s["by_platform"] if p["platform"] == "小红书")
    assert gzh["publish_events"] == 2
    assert gzh["backfills"] == 1
    assert xhs["publish_events"] == 1
    assert xhs["hits"] == 1

    themes = {t["theme"]: t for t in s["by_theme"]}
    assert themes["AI 前沿"]["posts"] == 1
    assert themes["AI 前沿"]["reads"] == 6200
    assert themes["成本账本"]["publish_events"] == 1

    assert s["best"]["by_reads"][0]["job_id"] == "2026-08-01_数字标题"
    assert s["content_insights"]["title_number"][0]["bucket"] == "标题含数字"
    assert s["content_insights"]["gzh_viz"][0]["bucket"] == "≥2 个图表"
    assert s["content_insights"]["gzh_viz"][0]["n"] == 2
    assert s["content_insights"]["xhs_cards"][0]["bucket"] == "≥4 张卡片"

    assert s["data_status"]["auto_tracked"] == 3
    assert s["data_status"]["manual_backfill"] == 2
    assert s["data_status"]["untracked_posts"] == 1
    assert s["data_status"]["untracked_list"][0]["job_id"] == "2026-08-02_无回填"


def test_pending_recycle_and_missing_features(tmp_path):
    jobs, outputs, data = _dirs(tmp_path)
    old = (datetime.now() - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
    _write_state(jobs, "2026-07-30_待回收", state="archive", theme="工具实测")
    _write_log(jobs, "2026-07-30_待回收",
               publish=[{"platform": "公众号", "status": "success", "at": old}],
               published_at=old)

    s = data_stats.build_summary(jobs, outputs, data_dir=data)
    assert s["pending_recycle"] == 1
    assert s["data_status"]["untracked_posts"] == 1
    assert s["content_insights"]["title_number"] == []
    # 无 outputs 时内容特征不应抛错
    assert s["by_theme"][0]["theme"] == "工具实测"


def test_report_and_summary_files(tmp_path):
    jobs, outputs, data = _dirs(tmp_path)
    root = tmp_path / "root"
    s = data_stats.build_summary(jobs, outputs, data_dir=data)
    p1 = data_stats.save_summary(str(root), summary=s)
    p2 = data_stats.write_report(str(root), summary=s)
    assert os.path.exists(p1)
    assert os.path.exists(p2)
    with open(p1, "r", encoding="utf-8") as f:
        assert json.load(f)["jobs_total"] == 0
    with open(p2, "r", encoding="utf-8") as f:
        assert "自有数据统计报告" in f.read()
