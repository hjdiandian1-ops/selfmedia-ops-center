"""run_production：用户模板偏好与文风注入生产提示词。"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import run_production as rp  # noqa: E402


def test_user_template_prefs_returns_refs(tmp_path, monkeypatch):
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({
        "templates": {
            "xhs_card": "ikb-blue",
            "gzh_layout": "red-white",
            "cover_style": "product-hero",
        }
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rp, "USER_PREFS_FILE", str(prefs))
    text = rp.user_template_prefs()
    assert "小红书图文卡片：IKB 蓝" in text
    assert "theme-presets.md" in text
    assert "公众号排版：红白" in text
    assert "theme-red-white.md" in text
    assert "封面构图风格：产品主视觉风" in text
    assert "style-templates.md" in text


def test_build_prompt_injects_prefs_and_style_guide(tmp_path, monkeypatch):
    job_dir = tmp_path / "jobs" / "demo_job"
    job_dir.mkdir(parents=True)
    (job_dir / "state.json").write_text(json.dumps({"theme": "测试主题"}), encoding="utf-8")
    (job_dir / "brief.md").write_text("# 简报\n\n内容", encoding="utf-8")
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"templates": {"gzh_layout": "graphite-minimal"}}), encoding="utf-8")
    style = tmp_path / "style.md"
    style.write_text("我的独特文风：拒绝空话。", encoding="utf-8")
    monkeypatch.setattr(rp, "JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(rp, "USER_PREFS_FILE", str(prefs))
    monkeypatch.setattr(rp, "STYLE_GUIDE_FILE", str(style))
    prompt = rp.build_prompt("demo_job")
    assert "## 用户偏好模板（必须遵循）" in prompt
    assert "公众号排版：石墨极简" in prompt
    assert "theme-graphite-minimal.md" in prompt
    assert "## 用户文风指南（必须遵循）" in prompt
    assert "拒绝空话" in prompt
    assert "## 生产简报" in prompt


def test_build_prompt_fallback_without_prefs(tmp_path, monkeypatch):
    job_dir = tmp_path / "jobs" / "demo_job"
    job_dir.mkdir(parents=True)
    (job_dir / "state.json").write_text(json.dumps({"theme": "测试主题"}), encoding="utf-8")
    (job_dir / "brief.md").write_text("无简报", encoding="utf-8")
    missing = tmp_path / "missing.json"
    missing_style = tmp_path / "missing-style.md"
    monkeypatch.setattr(rp, "JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(rp, "USER_PREFS_FILE", str(missing))
    monkeypatch.setattr(rp, "STYLE_GUIDE_FILE", str(missing_style))
    prompt = rp.build_prompt("demo_job")
    assert "沿用各 Agent 默认模板" in prompt
    assert "未设置个人文风指南" in prompt
