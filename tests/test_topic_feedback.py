"""
选题评分模型数据反馈回路测试 (Topic Feedback & Weight Calibration Tests)
========================================================================
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

import suggest_topics  # noqa: E402
import topic_feedback as tf  # noqa: E402
from server import app  # noqa: E402


def test_collect_feedback_empty_and_populated(tmp_path, monkeypatch):
    """测试反馈数据收集：空目录与有效任务样本。"""
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tf, "JOBS_DIR", str(jobs_dir))

    # 1. 空目录
    empty_samples = tf.collect_feedback(str(jobs_dir))
    assert empty_samples == []

    # 2. 构造 2 个已回填任务样本
    job1_dir = jobs_dir / "2026-08-10_AI短剧出海"
    job1_dir.mkdir(parents=True, exist_ok=True)
    (job1_dir / "state.json").write_text(json.dumps({
        "job_id": "2026-08-10_AI短剧出海", "theme": "AI短剧出海一人公司", "state": "recycle"
    }, ensure_ascii=False), encoding="utf-8")
    (job1_dir / "publish_log.json").write_text(json.dumps({
        "records": [
            {"platform": "小红书", "reads": 5000, "likes": 300, "collects": 200, "comments": 50, "shares": 30, "hit": True},
            {"platform": "公众号", "reads": 2000, "likes": 100, "collects": 80, "comments": 20, "shares": 15, "hit": False},
        ]
    }, ensure_ascii=False), encoding="utf-8")

    samples = tf.collect_feedback(str(jobs_dir))
    assert len(samples) == 1
    s1 = samples[0]
    assert s1["job_id"] == "2026-08-10_AI短剧出海"
    assert s1["performance"]["reads"] == 7000
    assert s1["performance"]["likes"] == 400
    assert s1["performance"]["is_hit"] is True
    assert s1["performance"]["engagement"] > 1000
    assert "quality" in s1["features"]


def test_calibrate_weights_insufficient_samples(tmp_path, monkeypatch):
    """测试样本不足 10 条时不触发调参，维持默认权重。"""
    topics_dir = tmp_path / "data" / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    calib_file = topics_dir / "weight_calibration.json"
    monkeypatch.setattr(tf, "TOPICS_DIR", str(topics_dir))
    monkeypatch.setattr(tf, "CALIBRATION_FILE", str(calib_file))

    few_samples = [
        {
            "job_id": f"job_{i}",
            "theme": f"测试主题 {i}",
            "state": "recycle",
            "features": {"freshness": 5.0, "heat": 8.0, "quality": 10.0, "ip": 2.0, "raw_score": 20.0},
            "performance": {"reads": 100, "likes": 10, "collects": 5, "comments": 1, "shares": 1, "is_hit": False, "engagement": 50.0},
        }
        for i in range(5)
    ]

    res = tf.calibrate_weights(few_samples, save=True)
    assert res["calibrated"] is False
    assert res["sample_count"] == 5
    assert "样本不足" in res["message"]
    assert res["weights"] == tf.DEFAULT_WEIGHTS
    assert calib_file.exists()


def test_calibrate_weights_sufficient_samples_and_bounds(tmp_path, monkeypatch):
    """测试样本 ≥ 10 条时触发线性相关性校准，且权重调整幅度受控在 ±30% 以内。"""
    topics_dir = tmp_path / "data" / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    calib_file = topics_dir / "weight_calibration.json"
    monkeypatch.setattr(tf, "TOPICS_DIR", str(topics_dir))
    monkeypatch.setattr(tf, "CALIBRATION_FILE", str(calib_file))

    # 构建 12 条梯度样本：质量分与互动量呈强正相关
    rich_samples = []
    for i in range(1, 13):
        rich_samples.append({
            "job_id": f"job_{i:02d}",
            "theme": f"AI商业实战系列 {i}",
            "state": "recycle",
            "features": {
                "freshness": float(4.0 + (i % 3)),
                "heat": float(6.0 + (i % 4)),
                "quality": float(5.0 + i * 1.5),
                "ip": 3.0,
                "raw_score": float(15.0 + i * 2.0),
            },
            "performance": {
                "reads": i * 1000,
                "likes": i * 100,
                "collects": i * 80,
                "comments": i * 20,
                "shares": i * 10,
                "is_hit": i >= 10,
                "engagement": float(i * 500.0),
            },
        })

    res = tf.calibrate_weights(rich_samples, save=True)
    assert res["calibrated"] is True
    assert res["sample_count"] == 12
    assert res["correlations"]["quality"] > 0.5  # 质量分与互动显著正相关

    daily_w = res["weights"]["daily"]
    weekly_w = res["weights"]["weekly"]

    # 验证权重调整上限严格限制在 ±30% 以内
    base_d = tf.DEFAULT_WEIGHTS["daily"]
    base_w = tf.DEFAULT_WEIGHTS["weekly"]

    assert base_d["fresh_w"] * 0.70 <= daily_w["fresh_w"] <= base_d["fresh_w"] * 1.30
    assert base_d["heat_w"] * 0.70 <= daily_w["heat_w"] <= base_d["heat_w"] * 1.30
    assert base_d["quality_w"] * 0.70 <= daily_w["quality_w"] <= base_d["quality_w"] * 1.30

    assert base_w["quality_w"] * 0.70 <= weekly_w["quality_w"] <= base_w["quality_w"] * 1.30
    assert base_w["heat_w"] * 0.70 <= weekly_w["heat_w"] <= base_w["heat_w"] * 1.30
    assert base_w["fresh_w"] * 0.70 <= weekly_w["fresh_w"] <= base_w["fresh_w"] * 1.30


def test_generate_report(tmp_path, monkeypatch):
    """测试生成复盘 Markdown 报告与结构化指标。"""
    topics_dir = tmp_path / "data" / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    report_file = topics_dir / "选题复盘报告.md"
    monkeypatch.setattr(tf, "TOPICS_DIR", str(topics_dir))
    monkeypatch.setattr(tf, "REPORT_FILE", str(report_file))

    samples = [
        {
            "job_id": f"job_{i}",
            "theme": f"选题 {i}",
            "state": "recycle",
            "features": {"freshness": 5.0, "heat": 8.0, "quality": 12.0, "ip": 2.0, "raw_score": float(20 + i)},
            "performance": {"reads": i * 500, "likes": i * 50, "collects": i * 30, "comments": 5, "shares": 5, "is_hit": False, "engagement": float(i * 200)},
        }
        for i in range(1, 15)
    ]

    rep = tf.generate_report(samples)
    assert "markdown" in rep
    assert "# 📊 选题评分模型反馈回路与表现复盘报告" in rep["markdown"]
    assert "评分权重对比表" in rep["markdown"]
    assert report_file.exists()


def test_suggest_topics_loads_calibrated_weights(tmp_path, monkeypatch):
    """测试 suggest_topics 动态加载 weight_calibration.json 中的校准权重。"""
    calib_file = tmp_path / "weight_calibration.json"
    custom_weights = {
        "daily": {"fresh_w": 1.45, "heat_w": 1.10, "quality_w": 0.50},
        "weekly": {"quality_w": 1.50, "heat_w": 0.40, "fresh_w": 0.25},
    }
    calib_file.write_text(json.dumps({"weights": custom_weights}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(suggest_topics, "CALIBRATION_FILE", str(calib_file))

    loaded = suggest_topics.load_calibrated_weights()
    assert loaded["daily"]["fresh_w"] == 1.45
    assert loaded["weekly"]["quality_w"] == 1.50

    # 运行打分
    item = {
        "title": "AI 自动化生产",
        "dims": {"impact": 4.0, "search": 3.0, "durable": 2.0, "unique": 1.0, "ip": 3.0},
        "fresh": {"score": 5.0, "hours": 12.0},
        "heat_score": 8.0,
    }
    scored = suggest_topics.finalize_score(item)
    # daily_score = 5.0 * 1.45 + 8.0 * 1.10 + 10.0 * 0.50 = 7.25 + 8.80 + 5.0 = 21.05 -> 21.1
    assert scored["daily_score"] == 21.1


def test_api_topics_calibrate_and_report_endpoints():
    """测试 WebApp API: POST /api/topics/calibrate 与 GET /api/topics/feedback-report。"""
    client = TestClient(app)

    # 1. 触发校准
    r1 = client.post("/api/topics/calibrate")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["ok"] is True
    assert "calibration" in d1

    # 2. 获取复盘报告
    r2 = client.get("/api/topics/feedback-report")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["ok"] is True
    assert "report" in d2
    assert "markdown" in d2["report"]
