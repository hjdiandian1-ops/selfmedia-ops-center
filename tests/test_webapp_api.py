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
import dashboard_analysis  # noqa: E402
import data_stats  # noqa: E402
import fetch_hot_topics  # noqa: E402
import upgrade_agent_docs  # noqa: E402


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
    data_dir = tmp_path / "data"
    jobs_dir.mkdir()
    outputs_dir.mkdir()
    data_dir.mkdir()
    monkeypatch.setattr(server, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(server, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(server, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(data_stats, "DATA_DIR", str(data_dir))
    return jobs_dir, outputs_dir, data_dir


@pytest.fixture(autouse=True)
def _allow_license_in_tests(monkeypatch):
    """测试环境默认放行授权门禁（门禁逻辑本身由 test_license_system 覆盖）。"""
    monkeypatch.setattr(
        server.LG, "check_feature",
        lambda feature, consume=False: (True, "test", {"mode": "test"}),
    )


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


def test_import_xhs_endpoint(isolated_dirs, monkeypatch):
    captured = {}

    def fake_run(args, timeout=60):
        captured["args"] = args
        captured["timeout"] = timeout
        return {
            "ok": True, "exit": 0,
            "stdout": json.dumps({
                "ok": True, "new_notes": 30, "updated_notes": 0,
                "matched_jobs": 2, "followers_gained_total": 14,
            }, ensure_ascii=False),
            "stderr": "",
        }

    monkeypatch.setattr(server, "run_script", fake_run)
    r = server._import_xhs_xlsx("笔记列表明细表.xlsx", b"x")
    assert r["new_notes"] == 30
    assert captured["args"][0] == "import_xhs_notes.py"
    assert captured["args"][-1] == "--json"
    assert captured["timeout"] == 120

    with pytest.raises(HTTPException) as e:
        server._import_xhs_xlsx("a.csv", b"x")
    assert e.value.status_code == 400


@pytest.fixture()
def isolated_flywheel(tmp_path, monkeypatch):
    fdir = tmp_path / "flywheel"
    fdir.mkdir()
    monkeypatch.setattr(server, "FLYWHEEL_DIR", str(fdir))
    monkeypatch.setattr(server, "VIRAL_FILE", str(fdir / "viral_videos.json"))
    monkeypatch.setattr(server, "LESSONS_FILE", str(fdir / "lessons.json"))
    monkeypatch.setattr(server, "FEEDBACK_FILE", str(fdir / "pipeline_feedback.md"))
    return fdir


def test_viral_crud(isolated_flywheel):
    assert server.api_viral()["videos"] == []
    r = server.api_viral_save(server.ViralVideo(
        platform="抖音", title="爆款测试", author="A", reads=100000,
        formula="数字冲击", status="tracked"))
    assert r["action"] == "created"
    vid = r["video"]["id"]
    d = server.api_viral()
    assert len(d["videos"]) == 1
    assert d["counts"]["total"] == 1

    updated = server.api_viral_save(server.ViralVideo(
        id=vid, platform="抖音", title="爆款测试", reads=200000, status="analyzed"))
    assert updated["action"] == "updated"
    assert server.api_viral()["videos"][0]["reads"] == 200000

    assert server.api_viral_delete(vid)["ok"] is True
    assert server.api_viral()["videos"] == []
    with pytest.raises(HTTPException):
        server.api_viral_delete(vid)


def test_viral_validation(isolated_flywheel):
    with pytest.raises(HTTPException) as e:
        server.api_viral_save(server.ViralVideo(platform="微博", title="x"))
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        server.api_viral_save(server.ViralVideo(platform="抖音", title="x", reads=-1))
    assert e.value.status_code == 400


def test_lesson_crud(isolated_flywheel):
    r = server.api_lesson_save(server.LessonEntry(
        title="经验A", conclusion="结论A", evidence="证据A", apply_to="小红书标题"))
    lid = r["lesson"]["id"]
    assert server.api_flywheel()["lessons"][0]["title"] == "经验A"

    r2 = server.api_lesson_save(server.LessonEntry(
        id=lid, title="经验A改", conclusion="结论A", applied=True))
    assert r2["action"] == "updated"
    assert server.api_flywheel()["lessons"][0]["applied"] is True

    server.api_lesson_delete(lid)
    assert server.api_flywheel()["lessons"] == []


def test_flywheel_regenerate(isolated_dirs, isolated_flywheel):
    r = server.api_flywheel_regenerate()
    assert r["ok"] is True
    with open(server.FEEDBACK_FILE, encoding="utf-8") as f:
        text = f.read()
    for section in ("账户数据反馈", "市场数据快照", "已沉淀经验", "爆款公式参考", "流水线 Agent"):
        assert section in text


# ---------- 小红书式看板 ----------


def _write_dashboard_files(tmp_path):
    dash = tmp_path / "dashboard"
    dash.mkdir(exist_ok=True)
    today = datetime.now().date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    totals = [1, 0, 0, 1, 1, 1, 2]   # 6 篇发布、2 天空窗
    videos = [0, 0, 0, 0, 0, 0, 1]   # 1 篇视频 → 16.7% < 20%
    (dash / "publish.json").write_text(json.dumps({
        "kind": "publish", "account": {"总发布": 18, "发布视频": 1, "发布图文": 17},
        "series": {
            "总发布趋势": [{"date": d, "value": v} for d, v in zip(days, totals)],
            "发布视频趋势": [{"date": d, "value": v} for d, v in zip(days, videos)],
        },
    }, ensure_ascii=False))
    note_at = (today - timedelta(days=1)).strftime("%Y年%m月%d日%H时%M分%S秒")
    (tmp_path / "xhs_notes.json").write_text(json.dumps({
        "notes": {
            "n1": {"title": "测试笔记", "first_published_at": note_at,
                   "format": "图文", "exposure": 1000, "reads": 1000,
                   "ctr": 24, "likes": 5, "comments": 0, "collects": 0,
                   "followers_gained": 0, "shares": 0, "avg_watch_seconds": 8},
        },
    }, ensure_ascii=False))
    return dash


def test_dashboard_weak_points(tmp_path, monkeypatch):
    dash = _write_dashboard_files(tmp_path)
    monkeypatch.setattr(server, "DATA_DIR", str(tmp_path))
    d = dashboard_analysis.build_dashboard(range_days=7, data_dir=str(tmp_path))
    ids = {w["id"] for w in d["weak_points"]}
    assert "engagement_low" in ids          # 互动率 0.5% < 1%
    assert "follower_rate_low" in ids       # 涨粉 0
    assert "publish_gap" in ids             # 空窗 4 天
    assert "format_imbalance" in ids        # 视频占比 5.6% < 20%
    assert d["tabs"]["publish"]["trend"]
    assert d["tabs"]["watch"]["funnel"]["ctr"] == 24.0


def test_dashboard_import_parser():
    import import_dashboard_xlsx as imp
    assert imp.detect_kind(["账号总体发布数据", "总发布趋势"]) == "publish"
    assert imp.detect_kind(["观看来源", "观看时段"], forced=None) == "watch"
    s = imp._parse_sheet("总发布趋势", [["日期", "数值"], ["2026年08月11日", "4"]])
    assert s["type"] == "series" and s["series"][0]["date"] == "2026-08-11"
    a = imp._parse_sheet("账号总体发布数据", [["指标", "数值"], ["总发布", "18"]])
    assert a["type"] == "account" and a["account"]["总发布"] == 18.0
    other = imp._parse_sheet("未知表", [["A", "B", "C"], ["x", "y", "z"]])
    assert other["type"] == "other"  # 未知列不崩溃


# ---------- 新增信息源解析 ----------


def test_fetch_tophub_parser(monkeypatch):
    html = ('<div class="cc-cd" id="node-98"><div><div class="cc-cd-ih"></div>'
            '<div class="cc-cd-cb nano"><div class="cc-cd-cb-l nano-content ">'
            '<a href="https://juejin.cn/post/1" target="_blank" rel="nofollow" itemid="1">'
            '<div class="cc-cd-cb-ll"><span class="s h">1</span>'
            '<span class="t">AI 标题测试</span><span class="e">5628</span></div></a>'
            '</div></div></div></div>')
    monkeypatch.setattr(fetch_hot_topics, "fetch_http", lambda *a, **k: html.encode("utf-8"))
    items = fetch_hot_topics.fetch_tophub(5)
    assert items and items[0]["title"] == "AI 标题测试"
    assert items[0]["link"] == "https://juejin.cn/post/1"


def test_fetch_tl1_parser(monkeypatch):
    def fake(url, **kw):
        if "hours" in url:
            return b'[{"hour_key":"2026081216","count":10}]'
        return json.dumps({"items": [{
            "rank": 1, "score": 9, "topic": "英伟达AI基建融资",
            "url": "https://x.com/a/status/1", "source": "@a",
        }]}, ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr(fetch_hot_topics, "fetch_http", fake)
    items = fetch_hot_topics.fetch_tl1(5)
    assert items[0]["title"] == "英伟达AI基建融资"
    assert "海外源" in items[0]["compliance"]


def test_fetch_hex2077_parser(monkeypatch):
    index = '<a href="/docs/2026-08/2026-08-12/">日报</a>'
    article = ('<h2 id="x"><strong>今日摘要</strong></h2>'
               '<p class="my-5 text"><a href="https://example.com/a" target="_blank">链接A</a>正文</p>'
               '<h3 id="y">产品与功能更新</h3>'
               '<p class="my-5 text"><strong>标题B。</strong><a href="https://x.com/foo" target="_blank">官方原帖</a></p>')
    seq = iter([index.encode("utf-8"), article.encode("utf-8")])
    monkeypatch.setattr(fetch_hot_topics, "fetch_http", lambda *a, **k: next(seq))
    items = fetch_hot_topics.fetch_hex2077(5)
    assert len(items) >= 2
    assert any("海外源" in it.get("compliance", "") for it in items)


# ---------- 生产队列 / Agent 升级 ----------


def test_production_queue_lifecycle(tmp_path, monkeypatch, isolated_dirs):
    qfile = tmp_path / "queue.json"
    monkeypatch.setattr(server, "PRODUCTION_FILE", str(qfile))
    _write_job("2026-08-20_生产队列")

    class FakeProc:
        pid = 99999
        def poll(self):
            return 0

    captured = {}

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(server.subprocess, "Popen", fake_popen)
    server._enqueue_job("2026-08-20_生产队列")
    started = server._kick_production()
    assert started == "2026-08-20_生产队列"
    items = server._load_queue()
    assert items[0]["status"] == "running"
    server._finalize_stale(items)
    assert server._load_queue()[0]["status"] == "done"
    assert any("run_production.py" in str(x) for x in captured["cmd"])


def test_upgrade_agent_docs_idempotent(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    doc = agents_dir / "xhs-editor-小红书主编.md"
    doc.write_text("# 小红书主编\n- version: 1.0.0\n- updated_at: 2026-08-01\n## 职责\n测试\n",
                   encoding="utf-8")
    fly = tmp_path / "flywheel"
    fly.mkdir()
    (fly / "lessons.json").write_text(json.dumps({"lessons": [
        {"title": "标题带数字", "conclusion": "标题优先用数字", "evidence": "爆款8.9k",
         "apply_to": "小红书标题"},
    ]}, ensure_ascii=False), encoding="utf-8")
    (fly / "viral_videos.json").write_text(json.dumps({"videos": []}), encoding="utf-8")

    r1 = upgrade_agent_docs.upgrade_agents(str(agents_dir), str(fly))
    assert r1["agents"][0]["patches"] == 1
    v1 = r1["agents"][0]["version"]
    assert v1 != "1.0.0"
    text = doc.read_text(encoding="utf-8")
    assert "标题带数字" in text and "- [经验]" in text

    r2 = upgrade_agent_docs.upgrade_agents(str(agents_dir), str(fly))
    assert r2["agents"] == []  # 无新内容不重复升版/不写盘
