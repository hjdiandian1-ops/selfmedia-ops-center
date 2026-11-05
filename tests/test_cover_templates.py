# -*- coding: utf-8 -*-
"""
封面提示词库 Router 与静态资源测试
"""
import os
import sys

from fastapi.testclient import TestClient

WEBAPP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "webapp"))
if WEBAPP_DIR not in sys.path:
    sys.path.insert(0, WEBAPP_DIR)

from server import app

client = TestClient(app)


def test_cover_templates_list():
    res = client.get("/api/cover-templates")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total"] >= 31
    assert "categories" in data
    assert len(data["items"]) >= 31

    item = data["items"][0]
    assert "id" in item
    assert "title" in item
    assert "prompt" in item
    assert len(item["prompt"]) > 100
    assert "aspect_ratio" in item


def test_cover_templates_category_filter():
    res = client.get("/api/cover-templates?category=人物封面")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total"] > 0
    for it in data["items"]:
        assert it["category"] == "人物封面"


def test_cover_templates_search():
    res = client.get("/api/cover-templates?search=自拍")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total"] >= 1
    found = any("自拍" in it["title"] or "自拍" in it["prompt"] for it in data["items"])
    assert found


def test_cover_templates_categories():
    res = client.get("/api/cover-templates/categories")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total"] >= 31
    assert len(data["categories"]) >= 5


def test_cover_templates_detail():
    list_res = client.get("/api/cover-templates")
    first_id = list_res.json()["items"][0]["id"]

    res = client.get(f"/api/cover-templates/{first_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["template"]["id"] == first_id
    assert len(data["template"]["prompt"]) > 50


def test_cover_templates_detail_not_found():
    res = client.get("/api/cover-templates/non-existent-template-id-999")
    assert res.status_code == 404


def test_cover_templates_static_asset():
    list_res = client.get("/api/cover-templates")
    items = list_res.json()["items"]
    # 找到任意有 local_thumbnail 的模板
    thumb_url = None
    for it in items:
        if it.get("local_thumbnail") and it["local_thumbnail"].startswith("/assets/cover_templates/"):
            thumb_url = it["local_thumbnail"]
            break
    assert thumb_url is not None
    res = client.get(thumb_url)
    assert res.status_code == 200
    assert len(res.content) > 1024
