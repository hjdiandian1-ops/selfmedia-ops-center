# -*- coding: utf-8 -*-
"""小红书人工发布流程单测：手动发布标记（素材包已下线，直接交付 小红书/ 产出文件夹）。"""
import json
import os
import sys

import pytest

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import record_manual_publish as RMP  # noqa: E402


def _dirs(tmp_path):
    jobs = tmp_path / "jobs"
    outputs = tmp_path / "outputs"
    jobs.mkdir()
    outputs.mkdir()
    return str(jobs), str(outputs)


def _write_state(jobs_dir, job_id, theme="30块做视频500万人看：AI把内容门槛拆了"):
    jdir = os.path.join(jobs_dir, job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "state.json"), "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id, "theme": theme, "state": "archive",
            "created_at": "2026-08-07 08:00:00", "updated_at": "2026-08-07 09:00:00",
            "reject_count": 0, "scores": {"review": 95},
        }, f, ensure_ascii=False)


def _write_log(jobs_dir, job_id, title="30 块钱、5 小时、500 万播放：AI 把视频创作的门槛拆了"):
    jdir = os.path.join(jobs_dir, job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "publish_log.json"), "w", encoding="utf-8") as f:
        json.dump({"job_id": job_id, "title": title, "records": [], "publish": []},
                  f, ensure_ascii=False, indent=2)


def _write_xhs_outputs(outputs_dir, job_id, n=4):
    xhs = os.path.join(outputs_dir, job_id, "小红书")
    os.makedirs(xhs, exist_ok=True)
    for i in range(1, n + 1):
        with open(os.path.join(xhs, f"xhs-0{i}.png"), "wb") as f:
            f.write(b"")
    with open(os.path.join(xhs, "文案.md"), "w", encoding="utf-8") as f:
        f.write(
            "---\nplatform: 小红书\n---\n\n# 标题\n\n"
            "## 📝 笔记正文：\n\n正文第一句。\n\n数据来源：测试\n\n#37 #AI视频 #一人公司\n")


def test_record_manual_publish(tmp_path):
    jobs, _ = _dirs(tmp_path)
    job_id = "2026-08-07_测试"
    _write_state(jobs, job_id)

    p1 = RMP.record(job_id, "小红书", title="标题A", note="手机端已发", jobs_dir=jobs)
    data = json.load(open(p1, encoding="utf-8"))
    assert data["title"] == "标题A"
    assert data["published_at"]
    assert data["platforms"] == ["小红书"]
    assert data["publish"][-1]["mode"] == "manual"
    assert data["publish"][-1]["note"] == "手机端已发"

    p2 = RMP.record(job_id, "公众号", jobs_dir=jobs)
    data = json.load(open(p2, encoding="utf-8"))
    assert len(data["publish"]) == 2
    assert data["platforms"] == ["公众号", "小红书"]
    assert data["publish"][-1]["platform"] == "公众号"
    assert data["publish"][-1]["mode"] == "manual"


def test_record_manual_publish_validation(tmp_path):
    jobs, _ = _dirs(tmp_path)
    with pytest.raises(ValueError, match="任务不存在"):
        RMP.record("不存在", "小红书", jobs_dir=jobs)
    _write_state(jobs, "2026-08-07_测试")
    with pytest.raises(ValueError, match="平台不合法"):
        RMP.record("2026-08-07_测试", "微博", jobs_dir=jobs)
