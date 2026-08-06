# -*- coding: utf-8 -*-
"""Job 状态机单测。通过 monkeypatch JOBS_DIR 到临时目录，避免污染真实 jobs/。"""
import argparse
from datetime import datetime, timedelta

import job_state as JS


def test_fmt_remaining_past():
    past = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    assert JS.fmt_remaining(past) == "已到期"


def test_fmt_remaining_future():
    future = (datetime.now() + timedelta(minutes=2, seconds=10)).strftime("%Y-%m-%d %H:%M:%S")
    assert "分" in JS.fmt_remaining(future)


def test_state_transition_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(JS, "JOBS_DIR", str(tmp_path))
    job_id = "2026-08-06_测试Job"
    JS.cmd_init(argparse.Namespace(job_id=job_id, theme="测试主题", deadline_minutes=30))
    data = JS.load(job_id)
    assert data["state"] == "topic"

    JS.cmd_set(argparse.Namespace(job_id=job_id, state="draft", note="已写稿", score=88))
    data = JS.load(job_id)
    assert data["state"] == "draft"
    assert data["scores"]["draft"] == 88
    assert len(data["history"]) == 2


def test_auto_advance_when_deadline_passed(tmp_path, monkeypatch):
    monkeypatch.setattr(JS, "JOBS_DIR", str(tmp_path))
    job_id = "2026-08-06_超时Job"
    JS.cmd_init(argparse.Namespace(job_id=job_id, theme="", deadline_minutes=30))
    # 把决策截止时间改成过去，使其满足 auto-advance 条件
    data = JS.load(job_id)
    data["decision_deadline"] = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    JS.save(job_id, data)

    JS.cmd_auto_advance(argparse.Namespace(job_id=job_id))
    assert JS.load(job_id)["state"] == "materials"
