# -*- coding: utf-8 -*-
"""大V关注与趋势雷达单测：KOL CRUD、Google Trends、徽章识别与打分。"""
import json
import os
import sys
from fastapi.testclient import TestClient

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
WEBAPP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if WEBAPP not in sys.path:
    sys.path.insert(0, WEBAPP)

import fetch_hot_topics as FHT  # noqa: E402
import suggest_topics as ST  # noqa: E402
from server import app  # noqa: E402

client = TestClient(app)


def test_kol_subscriptions_crud(tmp_path, monkeypatch):
    """测试关注大V的获取、添加、修改与删除闭环。"""
    test_kol_file = str(tmp_path / "kol_subscriptions.json")
    test_posts_file = str(tmp_path / "kol_posts.json")
    monkeypatch.setattr(FHT, "KOL_FILE", test_kol_file)
    monkeypatch.setattr(FHT, "KOL_POSTS_FILE", test_posts_file)

    # 1. 初始为空
    kols = FHT.load_kol_subscriptions()
    assert kols == []

    # 2. 保存大V
    initial = [
        {"handle": "sama", "name": "Sam Altman", "category": "AI大模型", "enabled": True},
        {"handle": "karpathy", "name": "Andrej Karpathy", "category": "AI与教育", "enabled": False},
    ]
    FHT.save_kol_subscriptions(initial)
    loaded = FHT.load_kol_subscriptions()
    assert len(loaded) == 2
    assert loaded[0]["handle"] == "sama"

    # 3. 抓取推文过滤（仅返回 enabled 的大V）
    fake_posts = [
        {"handle": "sama", "text": "Compute surprise", "views": 10000, "likes": 500, "views_per_hour": 5000},
        {"handle": "karpathy", "text": "Disabled tweet", "views": 20000, "likes": 900, "views_per_hour": 8000},
    ]
    FHT.save_cached_kol_posts(fake_posts)
    items = FHT.fetch_x_kol_posts(10)
    assert len(items) == 1
    assert items[0]["author"] == "sama"
    assert items[0]["source"] == "X关注大V"
    assert items[0]["badge"] == "𝕏 大V精选"


def test_suggest_topics_kol_and_trends_boost():
    """验证大V推文与谷歌暴增词在 suggest_topics 中获得流速与独特性/搜索加分。"""
    rows = [
        ("@sama（Sam Altman）：OpenAI o3 思考模型重大突破", "X关注大V", "https://x.com/sama", 1, "2026-09-20 18:00", 50000.0, "极速推理与上下文测试"),
        ("DeepSeek R1 本地私有化推理部署 `[Breakout (+650%)]`", "谷歌趋势", "https://trends.google.com", 2, "2026-09-20 18:00", 99999.0, "端侧大模型部署实战"),
        ("普通热点报道", "少数派热门", "https://sspai.com", 3, "2026-09-20 18:00", None, "常规软件更新"),
    ]
    scored = ST.score_rows(rows)
    assert len(scored) == 3

    # 大V条目检验
    kol_item = scored[0]
    assert kol_item["badge"] == "𝕏 大V精选"
    assert kol_item["is_kol"] is True
    assert kol_item["dims"]["unique"] >= 2.0  # 大V前沿背书
    assert kol_item["heat_score"] >= 10.0      # 流速加分

    # 谷歌趋势暴增条目检验
    g_item = scored[1]
    assert g_item["badge"] == "🔥 谷歌暴增"
    assert g_item["dims"]["search"] >= 2.5     # 暴增搜索意图
    assert g_item["heat_score"] >= 10.0

    # 常规条目
    normal_item = scored[2]
    assert normal_item["badge"] == ""
    assert normal_item["is_kol"] is False


def test_fastapi_kol_endpoints(monkeypatch, tmp_path):
    """测试 FastAPI 后端 KOL 路由交互。"""
    test_topics_dir = str(tmp_path / "topics")
    os.makedirs(test_topics_dir, exist_ok=True)
    import core
    monkeypatch.setattr(core, "TOPICS_DIR", test_topics_dir)

    # 1. 初始列表
    res = client.get("/api/topics/kols")
    assert res.status_code == 200
    assert res.json()["kols"] == []

    # 2. 添加大V
    add_payload = {
        "handle": "@sama",
        "name": "Sam Altman",
        "category": "AI大模型",
        "enabled": True,
        "note": "OpenAI CEO",
    }
    res = client.post("/api/topics/kols", json=add_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["kol"]["handle"] == "sama"

    # 3. 重复添加应报错 400
    res_dup = client.post("/api/topics/kols", json=add_payload)
    assert res_dup.status_code == 400

    # 4. 更新大V状态
    update_payload = {"enabled": False, "category": "超级智能"}
    res_up = client.put("/api/topics/kols/sama", json=update_payload)
    assert res_up.status_code == 200
    assert res_up.json()["kol"]["enabled"] is False
    assert res_up.json()["kol"]["category"] == "超级智能"

    # 5. 删除大V
    res_del = client.delete("/api/topics/kols/sama")
    assert res_del.status_code == 200
    assert res_del.json()["remaining_count"] == 0

    # 6. 获取 Google Trends
    res_gt = client.get("/api/topics/trends/google")
    assert res_gt.status_code == 200
    assert "trends" in res_gt.json()
