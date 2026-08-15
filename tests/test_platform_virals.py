# -*- coding: utf-8 -*-
"""三平台爆款跟踪链路单测：解析 / 失败隔离 / 去重 / 批量拆解 / 周聚合。"""
import json
import os
import sys

import pytest

import collect_platform_virals as CPV
import run_viral_breakdown_daily as RVBD
import aggregate_viral_lessons as AVL
import upgrade_agent_docs as UAD


XHS_JSON = {
    "msg": "成功",
    "data": {
        "result": {"success": True},
        "items": [
            {"title": "用万能旅行拍照姿势美美出片", "score": "920.8w", "word_type": "热"},
            {"title": "耗时三年拍下古诗词里的中国", "score": "911.2w", "word_type": "热"},
            {"title": "我拍到了海鸥雨", "score": "887.4w", "word_type": "无"},
        ],
    },
}

DOUYIN_JSON = {
    "status_code": 0,
    "word_list": [
        {"word": "白海豚对河南的影响有多大", "hot_value": 11103354, "label": 3},
        {"word": "60秒读懂海洋经济", "hot_value": 10994872, "label": 0},
        {"word": "威少宣布退役", "hot_value": 10956981, "label": 1},
    ],
}

TOPHUB_HTML = """
<div class="zb-kc">
  <a href="/n/WnBe01o371"><div class="zb-kc-Cb">微信<span>24h热文榜</span></div></a>
  <img src="https://file.ipadown.com/tophub/assets/images/media/mp.weixin.qq.com.png_160x160.png">
</div>
<div class="cc-cd" id="node-5">
  <div class="cc-cd-ih">
    <div class="cc-cd-is"><a href="/n/WnBe01o371"><div class="cc-cd-lb">
      <img src="https://file.ipadown.com/tophub/assets/images/media/mp.weixin.qq.com.png_160x160.png">
      <span>微信</span></div></a></div>
    <div class="cc-cd-sb"><span>24h热文榜</span></div>
  </div>
  <div class="cc-cd-cb nano">
    <a href="https://mp.weixin.qq.com/s?__biz=A" target="_blank" itemid="1">
      <div class="cc-cd-cb-ll"><span class="s h">1</span><span class="t">看不懂的天价破烂时尚风</span><span class="e">10.0万</span></div>
    </a>
    <a href="https://mp.weixin.qq.com/s?__biz=B" target="_blank" itemid="2">
      <div class="cc-cd-cb-ll"><span class="s">2</span><span class="t">台风一过，海边海货满满</span><span class="e">10.0万</span></div>
    </a>
  </div>
</div>
<div class="cc-cd" id="node-9">
  <div class="cc-cd-ih"><span>抖音总榜</span></div>
  <a href="https://www.douyin.com/x"><div class="cc-cd-cb-ll"><span class="s">1</span><span class="t">别的内容</span><span class="e">1000</span></div></a>
</div>
"""


def test_fetch_xhs(monkeypatch):
    monkeypatch.setattr(CPV, "_http_get", lambda *a, **k: json.dumps(XHS_JSON))
    items = CPV.fetch_xhs(limit=2)
    assert len(items) == 2
    assert items[0]["title"] == "用万能旅行拍照姿势美美出片"
    assert items[0]["heat"] == "920.8w"
    assert items[0]["tag"] == "热"
    assert items[0]["rank"] == 1
    assert "xiaohongshu.com/search_result" in items[0]["link"]


def test_fetch_douyin(monkeypatch):
    monkeypatch.setattr(CPV, "_http_get", lambda *a, **k: json.dumps(DOUYIN_JSON))
    items = CPV.fetch_douyin(limit=3)
    assert len(items) == 3
    assert items[0]["title"] == "白海豚对河南的影响有多大"
    assert items[0]["heat"] == "1110.3w"
    assert items[0]["tag"] == "热"
    assert "douyin.com/root/search" in items[0]["link"]


def test_fetch_wechat(monkeypatch):
    monkeypatch.setattr(CPV, "_http_get", lambda *a, **k: TOPHUB_HTML)
    items = CPV.fetch_wechat(limit=2)
    assert len(items) == 2
    assert items[0]["title"] == "看不懂的天价破烂时尚风"
    assert items[0]["heat"] == "10.0w"
    assert items[0]["link"].startswith("https://mp.weixin.qq.com/s?")
    assert items[1]["rank"] == 2


def test_fmt_heat_unified_w():
    assert CPV._fmt_heat("11331229") == "1133.1w"
    assert CPV._fmt_heat("10.0万") == "10.0w"
    assert CPV._fmt_heat("920.8w") == "920.8w"
    assert CPV._fmt_heat("0") == "0"
    assert CPV._fmt_heat("") == ""


def test_collect_source_failure_isolation(tmp_path, monkeypatch):
    store = tmp_path / "platform_virals.json"
    viral = tmp_path / "viral_videos.json"

    def fake_xhs(limit):
        return [{"title": f"小红书热词{i}", "heat": "100w", "tag": "热",
                 "link": "https://xhs.cn/x", "rank": i} for i in range(1, 3)]

    def fake_douyin(limit):
        raise RuntimeError("抖音官方接口挂了")

    def fake_wechat(limit):
        return [{"title": f"公众号热文{i}", "heat": "10.0万", "tag": "10w+",
                 "link": "https://mp.weixin.qq.com/s?x", "rank": i} for i in range(1, 3)]

    def fake_mirror(platform, limit):
        raise RuntimeError("镜像也不可用")

    monkeypatch.setattr(CPV, "PLATFORM_FETCHERS", {
        "小红书": fake_xhs, "抖音": fake_douyin, "公众号": fake_wechat,
    })
    monkeypatch.setattr(CPV, "fetch_ranks_mirror", fake_mirror)

    summary = CPV.collect(str(store), str(viral), date="2026-08-14", limit=2)
    assert summary["platforms"]["小红书"]["ok"] is True
    assert summary["platforms"]["抖音"]["ok"] is False
    assert summary["platforms"]["公众号"]["ok"] is True
    data = json.loads(store.read_text(encoding="utf-8"))
    assert "抖音" not in data["days"]["2026-08-14"]
    assert len(data["days"]["2026-08-14"]["小红书"]) == 2
    assert data["source_status"]["抖音"]["ok"] is False
    videos = json.loads(viral.read_text(encoding="utf-8"))["videos"]
    assert len(videos) == 4


def test_collect_upsert_dedupe(tmp_path, monkeypatch):
    store = tmp_path / "platform_virals.json"
    viral = tmp_path / "viral_videos.json"

    def fake_xhs(limit):
        return [{"title": "同一个热词", "heat": "100w", "tag": "热",
                 "link": "https://xhs.cn/x", "rank": 1}]

    monkeypatch.setattr(CPV, "PLATFORM_FETCHERS", {
        "小红书": fake_xhs, "抖音": lambda limit: [], "公众号": lambda limit: [],
    })
    s1 = CPV.collect(str(store), str(viral), date="2026-08-14", limit=1)
    s2 = CPV.collect(str(store), str(viral), date="2026-08-14", limit=1)
    assert s1["added"] == 1
    assert s2["added"] == 0
    videos = json.loads(viral.read_text(encoding="utf-8"))["videos"]
    assert len(videos) == 1


def test_select_queue_top5(tmp_path, monkeypatch):
    viral = tmp_path / "viral_videos.json"
    viral.write_text(json.dumps({"videos": []}), encoding="utf-8")
    monkeypatch.setattr(RVBD, "VIRAL_FILE", str(viral))
    store = {"days": {"2026-08-14": {
        "小红书": [{"viral_id": f"x{i}", "title": f"小红书{i}", "link": ""} for i in range(1, 8)],
        "抖音": [{"viral_id": f"d{i}", "title": f"抖音{i}", "link": ""} for i in range(1, 8)],
        "公众号": [{"viral_id": f"g{i}", "title": f"公众号{i}", "link": ""} for i in range(1, 3)],
    }}}
    queue = RVBD.select_queue(store, date="2026-08-14", per_platform=5, limit=15)
    assert len(queue) == 12  # 5 + 5 + 2
    assert queue[0]["viral_id"] == "x1"
    assert queue[5]["viral_id"] == "d1"
    assert queue[10]["viral_id"] == "g1"


def test_select_queue_skips_analyzed(tmp_path, monkeypatch):
    viral = tmp_path / "viral_videos.json"
    viral.write_text(json.dumps({"videos": [
        {"id": "x1", "status": "analyzed"},
        {"id": "x2", "status": "tracked"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(RVBD, "VIRAL_FILE", str(viral))
    store = {"days": {"2026-08-14": {
        "小红书": [{"viral_id": "x1", "title": "A"}, {"viral_id": "x2", "title": "B"}],
    }}}
    queue = RVBD.select_queue(store, date="2026-08-14", per_platform=5, limit=15)
    assert [q["viral_id"] for q in queue] == ["x2"]


def test_run_batch_state_machine(tmp_path, monkeypatch):
    status_file = tmp_path / "batch.json"
    monkeypatch.setattr(RVBD, "update_record", lambda vid, patch: None)
    queue = [
        {"platform": "小红书", "viral_id": "a", "title": "A", "link": ""},
        {"platform": "抖音", "viral_id": "b", "title": "B", "link": ""},
        {"platform": "公众号", "viral_id": "c", "title": "C", "link": ""},
    ]

    def run_one(item):
        return item["viral_id"] != "b"

    status = RVBD.run_batch(queue, status_file=str(status_file),
                            sleep_fn=lambda s: None, run_one=run_one)
    assert status["done"] == 2
    assert status["failed"] == 1
    assert status["running"] is False
    saved = json.loads(status_file.read_text(encoding="utf-8"))
    assert saved["running"] is False
    assert saved["total"] == 3


def _make_breakdown(flywheel_dir, vid, platform, formula="数字冲击, 干货清单"):
    bd_dir = flywheel_dir / "breakdowns"
    bd_dir.mkdir(parents=True, exist_ok=True)
    (bd_dir / f"{vid}.json").write_text(json.dumps({
        "title": f"爆款{vid}", "platform": platform, "evidence_level": "title_only",
        "formula": formula, "summary": "热度高", "why_viral": "标题抓人",
    }), encoding="utf-8")
    viral = flywheel_dir / "viral_videos.json"
    if viral.exists():
        data = json.loads(viral.read_text(encoding="utf-8"))
    else:
        data = {"videos": []}
    data["videos"].append({"id": vid, "platform": platform, "title": f"爆款{vid}"})
    viral.write_text(json.dumps(data), encoding="utf-8")


def test_weekly_aggregate_idempotent(tmp_path, monkeypatch):
    flywheel_dir = tmp_path / "flywheel"
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "xhs-editor-小红书主编.md").write_text(
        "# 小红书主编\n- version: 1.0.0\n- updated_at: 2026-08-01\n", encoding="utf-8")
    _make_breakdown(flywheel_dir, "v1", "小红书")
    calls = []

    def fake_upgrade(agents_dir_, flywheel_dir_):
        calls.append((agents_dir_, flywheel_dir_))
        return {"agents": [{"file": "xhs-editor-小红书主编.md", "version": "1.0.1"}]}

    monkeypatch.setattr(UAD, "upgrade_agents", fake_upgrade)
    r1 = AVL.aggregate(str(flywheel_dir), str(agents_dir))
    r2 = AVL.aggregate(str(flywheel_dir), str(agents_dir))
    lessons = json.loads((flywheel_dir / "lessons.json").read_text(encoding="utf-8"))["lessons"]
    assert r1["lessons"] == 1 and r2["lessons"] == 1
    assert len(lessons) == 1
    assert lessons[0]["source"] == "viral_weekly"
    assert lessons[0]["apply_to"] == "小红书主编"
    assert (flywheel_dir / f"viral_weekly_{r1['week']}.md").exists()
    assert len(calls) == 2


def test_weekly_aggregate_no_breakdown(tmp_path, monkeypatch):
    flywheel_dir = tmp_path / "flywheel"
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    monkeypatch.setattr(UAD, "upgrade_agents", lambda a, f: {"agents": []})
    r = AVL.aggregate(str(flywheel_dir), str(agents_dir))
    assert r["lessons"] == 0
    assert r["platforms"] == {}


def test_upsert_lessons_idempotent():
    store = {"lessons": []}
    nl = {
        "title": "t", "conclusion": "c", "evidence": "e",
        "apply_to": "小红书主编", "source": "viral_weekly", "week": "2026-W33",
    }
    AVL.upsert_lessons(store, [nl], "2026-08-14 10:00:00")
    AVL.upsert_lessons(store, [nl], "2026-08-14 11:00:00")
    assert len(store["lessons"]) == 1
    assert store["lessons"][0]["updated_at"] == "2026-08-14 11:00:00"


def test_upsert_lessons_unique_ids_per_platform():
    store = {"lessons": []}
    now = "2026-08-14 10:00:00"
    for apply_to in ("小红书主编", "公众号主编", "短视频导演"):
        AVL.upsert_lessons(store, [{
            "title": apply_to, "conclusion": "c", "evidence": "e",
            "apply_to": apply_to, "source": "viral_weekly", "week": "2026-W33",
        }], now)
    ids = [l["id"] for l in store["lessons"]]
    assert len(ids) == len(set(ids)) == 3
    assert any(i.endswith("_xhs") for i in ids)
    assert any(i.endswith("_gzh") for i in ids)
    assert any(i.endswith("_dy") for i in ids)


def test_server_viral_api_shape():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"))
    import server  # noqa: F401
    d = server.api_viral()
    assert "daily" in d
    assert "source_status" in d
    assert "breakdown_batch" in d
    assert "videos" in d and "candidates" in d
