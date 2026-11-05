# -*- coding: utf-8 -*-
"""
Skills 技能库 API 单元测试 (test_skills_repo.py)
"""
import os
import sys

WEBAPP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "webapp"))
if WEBAPP_DIR not in sys.path:
    sys.path.insert(0, WEBAPP_DIR)

from fastapi.testclient import TestClient

import server

client = TestClient(server.app)


def test_api_skills_repo_list():
    """测试获取全量 Skills 列表"""
    resp = client.get("/api/skills-repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["all_total"] >= 30
    assert len(data["items"]) == data["all_total"]
    assert "全部" in data["categories"]
    assert len(data["category_counts"]) > 0


def test_api_skills_repo_category_filter():
    """测试分类筛选过滤"""
    resp = client.get("/api/skills-repo", params={"category": "小红书爆款"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] > 0
    assert all(item["category"] == "小红书爆款" for item in data["items"])


def test_api_skills_repo_search():
    """测试关键字检索"""
    resp = client.get("/api/skills-repo", params={"search": "封面"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] > 0


def test_api_skills_repo_categories():
    """测试分类与标签统计接口"""
    resp = client.get("/api/skills-repo/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["categories"]) > 0
    assert "top_tags" in data


def test_api_skills_repo_detail():
    """测试单条技能详情与完整 SKILL.md 读取"""
    resp = client.get("/api/skills-repo/atutun-xhs-cover")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    skill = data["skill"]
    assert skill["slug"] == "atutun-xhs-cover"
    assert "阿囤囤" in skill["title"] or "阿囤囤" in skill["author"]
    assert len(skill["skill_md"]) > 100
    assert "name: atutun-xhs-cover" in skill["skill_md"]


def test_api_skills_repo_detail_not_found():
    """测试不存在的 Skill ID"""
    resp = client.get("/api/skills-repo/non-existent-skill-xyz")
    assert resp.status_code == 404
