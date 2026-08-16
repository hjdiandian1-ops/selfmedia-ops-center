# -*- coding: utf-8 -*-
"""文风文档初始化引导：默认模板、恢复、AI/模板双模式生成。"""
import json
import os
import sys

WEBAPP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"))
if WEBAPP not in sys.path:
    sys.path.insert(0, WEBAPP)

import server  # noqa: E402


TEMPLATE = "# 默认文风\n\n- 目标读者：【填写】\n"


def _setup(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    tpl_dir = root / "data" / "templates" / "style_docs"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "personal-style-guide.template.md").write_text(TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(server, "ROOT", str(root))
    monkeypatch.setattr(server, "STYLE_DOCS", [("skills/personal-style-guide.md", "个人文风指南")])
    monkeypatch.setattr(server, "STYLE_DOC_DEFAULTS", {
        "skills/personal-style-guide.md": os.path.join("data", "templates", "style_docs", "personal-style-guide.template.md"),
    })
    monkeypatch.setattr(server, "STYLE_DOC_ALLOWED_PREFIXES", ("skills/",))
    return root


def test_default_initialization_save_and_reset(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)

    docs = server.api_style_docs()["docs"]
    assert docs[0]["is_default"] is True
    assert (root / "skills" / "personal-style-guide.md").exists()

    server.api_style_doc_save(server.StyleDocPayload(
        path="skills/personal-style-guide.md", content="我的自定义文风"))
    assert server.api_style_doc(path="skills/personal-style-guide.md")["is_default"] is False

    server.api_style_doc_reset(server.StyleDocResetPayload(path="skills/personal-style-guide.md"))
    assert server.api_style_doc(path="skills/personal-style-guide.md")["content"] == TEMPLATE
    backups = list((root / "data" / "style_backups").glob("*.md"))
    assert backups, "重置前应有备份"


def test_style_guide_fallback_and_ai(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise RuntimeError("no llm")

    monkeypatch.setattr(server.llm_engine, "chat_json", fail)
    r = server.api_style_doc_guide(server.StyleGuidePayload(
        audience="上班族", platforms="小红书", tone="口语化",
        avoid="套话", keywords="Agent", redlines="不虚构"))
    assert r["mode"] == "template"
    assert "上班族" in r["content"] and "硬红线" in r["content"]

    def ok(*args, **kwargs):
        return {"content": "# AI 生成的文风指南\n\n- 目标读者：上班族"}

    monkeypatch.setattr(server.llm_engine, "chat_json", ok)
    r2 = server.api_style_doc_guide(server.StyleGuidePayload(audience="上班族"))
    assert r2["mode"] == "ai"
    assert "AI 生成的文风指南" in r2["content"]


def test_style_presets_api(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)
    (root / "data" / "templates" / "style_docs" / "tech-hands-on.template.md").write_text("# 科技实战风\n", encoding="utf-8")
    presets = server.api_style_presets()["presets"]
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "tech-hands-on" in preset_ids
    assert "business-deep-dive" in preset_ids
    assert "xhs-lifestyle" in preset_ids
    assert "career-growth" in preset_ids

