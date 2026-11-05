import json
import os
import pytest
from fastapi.testclient import TestClient

import sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "webapp"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from webapp.server import app
import run_production


client = TestClient(app)


def test_get_pipeline_slots():
    resp = client.get("/api/pipeline/slots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "slots" in data
    assert "researcher" in data["slots"]
    assert "xhs_editor" in data["slots"]
    assert "gzh_editor" in data["slots"]
    assert "video_director" in data["slots"]
    assert "cover_template" in data["slots"]
    assert len(data["available_skills"]) >= 30
    assert len(data["available_covers"]) >= 20


def test_update_pipeline_slot_global():
    resp = client.post("/api/pipeline/slots", json={
        "role_key": "xhs_editor",
        "item_id": "dbs-xhs-title"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["slots"]["xhs_editor"]["skill_slug"] == "dbs-xhs-title"

    # Read back
    resp_get = client.get("/api/pipeline/slots")
    assert resp_get.json()["slots"]["xhs_editor"]["skill_slug"] == "dbs-xhs-title"

    # Restore default
    client.post("/api/pipeline/slots", json={
        "role_key": "xhs_editor",
        "item_id": "atutun-xhs-cover"
    })


def test_job_custom_pipeline_slots(tmp_path):
    job_id = "test_custom_job_001"
    job_dir = os.path.join(ROOT, "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    try:
        resp = client.post("/api/pipeline/slots", json={
            "role_key": "gzh_editor",
            "item_id": "dbs-content-system",
            "job_id": job_id
        })
        assert resp.status_code == 200
        assert resp.json()["slots"]["gzh_editor"]["skill_slug"] == "dbs-content-system"

        # Check GET with job_id
        resp_get = client.get(f"/api/pipeline/slots?job_id={job_id}")
        assert resp_get.json()["is_job_custom"] is True
        assert resp_get.json()["slots"]["gzh_editor"]["skill_slug"] == "dbs-content-system"

        # Check run_production config loader
        cfg = run_production._get_pipeline_config(job_id)
        assert cfg["slots"]["gzh_editor"]["skill_slug"] == "dbs-content-system"
    finally:
        import shutil
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)


def test_skill_instructions_and_cover_template_loader():
    skill_rules = run_production._load_skill_instructions("human-writing")
    assert len(skill_rules) > 100
    assert "人" in skill_rules or "写作" in skill_rules or "AI" in skill_rules

    cover_tpl = run_production._load_cover_template("selfie-bag-sticker-cover")
    assert cover_tpl is not None
    assert cover_tpl.get("id") == "selfie-bag-sticker-cover"
    assert "prompt" in cover_tpl
