# -*- coding: utf-8 -*-
"""小红书人工发布流程单测：素材包生成 + 手动发布标记。"""
import json
import os
import sys

import pytest

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import prepare_xhs_material as PXM  # noqa: E402
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


def test_prepare_xhs_material(tmp_path):
    jobs, outputs = _dirs(tmp_path)
    job_id = "2026-08-07_测试"
    _write_state(jobs, job_id)
    _write_log(jobs, job_id)
    _write_xhs_outputs(outputs, job_id)

    dest, info = PXM.prepare(job_id, outputs, jobs)
    assert os.path.isdir(dest)
    names = set(os.listdir(dest))
    assert {"xhs-01.png", "xhs-02.png", "xhs-03.png", "xhs-04.png", "文案.md", "发布说明.md"} <= names
    assert info["images"] == 4
    assert info["title"] == "30 块钱、5 小时、500 万播放：AI 把视频创作的门槛拆了"
    assert info["tags"] == ["#AI视频", "#一人公司"]

    guide = open(os.path.join(dest, "发布说明.md"), encoding="utf-8").read()
    assert "禁止使用任何自动化工具" in guide
    assert "手动发布步骤" in guide
    assert "#AI视频" in guide and "#一人公司" in guide

    # 幂等覆盖：文件数不翻倍
    dest2, _ = PXM.prepare(job_id, outputs, jobs)
    assert dest2 == dest
    assert len(os.listdir(dest2)) == 6


def test_prepare_xhs_material_missing_outputs(tmp_path):
    jobs, outputs = _dirs(tmp_path)
    _write_state(jobs, "2026-08-07_无小红书产出")
    with pytest.raises(ValueError, match="未找到小红书产出目录"):
        PXM.prepare("2026-08-07_无小红书产出", outputs, jobs)


def test_prepare_xhs_material_no_images(tmp_path):
    jobs, outputs = _dirs(tmp_path)
    job_id = "2026-08-07_无图片"
    _write_state(jobs, job_id)
    os.makedirs(os.path.join(outputs, job_id, "小红书"))
    with pytest.raises(ValueError, match="没有图片"):
        PXM.prepare(job_id, outputs, jobs)


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
