"""
端到端自动化测试 (E2E Pipeline Test Suite)
===========================================
覆盖自媒体运营工厂从「选题采纳 → 素材生产 → 文案初稿 → 质检门禁/自愈 → 归档收尾」全流程。
"""
import argparse
import json
import os
import subprocess  # nosec B404
import sys
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
WEBAPP = os.path.join(ROOT, "webapp")

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, WEBAPP)

import core  # noqa: E402
import job_state  # noqa: E402
import run_production as rp  # noqa: E402
from server import app  # noqa: E402


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """测试环境隔离 Fixture：构建独立的 jobs, outputs, materials, data 目录。"""
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    materials_dir = tmp_path / "materials"
    data_dir = tmp_path / "data"

    jobs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    materials_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch core & job_state
    monkeypatch.setenv("SELFMEDIA_JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(core, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(core, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(core, "MATERIALS_DIR", str(materials_dir))
    monkeypatch.setattr(job_state, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(rp, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(rp, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(rp, "MATERIALS_DIR", str(materials_dir))

    # Mock 授权守卫恒为通过
    monkeypatch.setattr(core, "_license_guard", lambda feature: None)

    return {
        "jobs": jobs_dir,
        "outputs": outputs_dir,
        "materials": materials_dir,
        "data": data_dir,
        "root": tmp_path,
    }


def test_full_pipeline_happy_path(test_env, monkeypatch):
    """
    E2E 场景 1: Happy Path 全流程
    创建 Job (job_state init) -> 放置素材包 -> 放置三平台合规成稿 -> 逐步推进状态机到 archive -> 验证流转历史完整
    """
    job_id = "2026-08-19_全流程E2E测试"
    theme = "AI自动化工厂落地实战"
    
    # 1. 初始化 Job
    init_cmd = [sys.executable, os.path.join(SCRIPTS, "job_state.py"), "init", job_id, "--theme", theme]
    env = dict(os.environ, SELFMEDIA_JOBS_DIR=str(test_env["jobs"]))
    r = subprocess.run(init_cmd, capture_output=True, text=True, env=env)  # nosec B603
    assert r.returncode == 0
    assert "Job 已创建" in r.stdout

    # 2. 放置 Stage 1 素材包
    month = datetime.now().strftime("%Y-%m")
    mat_folder = test_env["materials"] / month
    mat_folder.mkdir(parents=True, exist_ok=True)
    mat_file = mat_folder / f"{job_id}素材包.md"
    mat_content = (
        f"# {theme} 结构化素材包\n\n"
        "## 一、核心事实与时间节点\n"
        "- M1｜自媒体自动化工厂架构重构完成（source_type: 真实数据 | priority: 核心）\n"
        "  来源：https://example.com/fact1\n"
        "- M2｜多步解耦生产流水线消除Token遗忘（source_type: 真实数据 | priority: 核心）\n"
        "  来源：https://example.com/fact2\n\n"
        "## 二、关键数据指标\n"
        "- M3｜效率提升85%，日吞吐量翻倍（source_type: 真实数据 | priority: 核心）\n"
        "  来源：https://example.com/fact3\n"
        "- M4｜综合错误率降低65%（source_type: 用户投喂 | priority: 辅助）\n"
        "  来源：https://example.com/fact4\n\n"
        "## 三、核心实体\n"
        "- M5｜自媒体运营工厂多Agent架构（source_type: 真实数据 | priority: 核心）\n"
        "  来源：https://example.com/fact5\n"
    )
    mat_file.write_text(mat_content, encoding="utf-8")
    job_state.cmd_set(argparse.Namespace(job_id=job_id, state="materials", score=None, note="素材包已就绪"))

    # 3. 放置 Stage 2 三平台文案与排版
    out_job_dir = test_env["outputs"] / job_id
    (out_job_dir / "小红书").mkdir(parents=True, exist_ok=True)
    (out_job_dir / "公众号").mkdir(parents=True, exist_ok=True)
    (out_job_dir / "短视频").mkdir(parents=True, exist_ok=True)

    # 小红书成稿
    (out_job_dir / "小红书" / "文案.md").write_text(
        "---\n"
        "title: 一键自动化工厂彻底跑通\n"
        "platform: 小红书\n"
        "tags: [#AI, #自媒体, #效率神器, #商业实战]\n"
        "series: 实战系列 | 第 1 篇\n"
        "follow_cta: 关注小吴聊，下期拆解公众号深度排版实战\n"
        "consumed_materials: [M1, M2, M3, M5]\n"
        "---\n\n"
        "别再手动写稿了！一套流水线直接把效率拉满。\n\n"
        "<!-- viz: stat-card -->\n\n"
        "实测日吞吐量提升 85%，核心逻辑单步单责。\n\n"
        "建议收藏点赞，在评论区交流！",
        encoding="utf-8"
    )
    (out_job_dir / "小红书" / "rednote_slides.html").write_text(
        '<div data-viz="h-bar-chart">小红书卡片数据可视化</div>', encoding="utf-8"
    )

    # 公众号长文
    (out_job_dir / "公众号" / "文案.md").write_text(
        "---\n"
        "title: 为什么多步解耦生产流水线比单次Prompt强10倍\n"
        "platform: 公众号\n"
        "digest: 深度拆解自媒体自动化流水线解耦架构与核心指标\n"
        "consumed_materials: [M1, M2, M3, M5]\n"
        "---\n\n"
        "# 为什么多步解耦生产流水线比单次Prompt强10倍\n\n"
        "<!-- viz: bar-chart -->\n<!-- viz: stat-grid -->\n\n"
        "## 01 / 架构解耦的核心价值\n单步单责消除长Prompt素材衰减。\n\n"
        "## 02 / 实测数据佐证\n全链路效率提升85%。\n\n"
        "## 03 / 落地总结与启示\n工业级闭环。\n\n"
        "## 参考来源\n1. https://example.com/fact1",
        encoding="utf-8"
    )
    (out_job_dir / "公众号" / "gzh_layout.html").write_text(
        '<section data-viz="bar-chart"></section><section data-viz="stat-grid"></section>', encoding="utf-8"
    )

    # 短视频脚本
    (out_job_dir / "短视频" / "120s黄金分镜脚本.md").write_text(
        "# 分镜脚本\n\n"
        "## 0-3s 黄金钩子\n- 画面：特写\n- 旁白：你敢信吗？一套流水线替代了一个运营团队！\n\n"
        "## 3-15s 痛点共鸣\n- 旁白：痛点\n\n"
        "## 15-75s 干货演示\n- 旁白：实操\n\n"
        "## 75-105s 转折升华\n- 旁白：升华\n\n"
        "## 105-120s 行动召唤\n- 旁白：关注小吴聊",
        encoding="utf-8"
    )

    # 4. 推进状态机至 draft -> visual -> review -> archive
    job_state.cmd_set(argparse.Namespace(job_id=job_id, state="draft", score=None, note="三平台文案就绪"))
    job_state.cmd_set(argparse.Namespace(job_id=job_id, state="visual", score=None, note="视觉排版就绪"))
    job_state.cmd_set(argparse.Namespace(job_id=job_id, state="review", score=90, note="质检全部通过"))
    job_state.cmd_set(argparse.Namespace(job_id=job_id, state="archive", score=None, note="成品归档完成"))

    # 5. 校验状态机完整历史
    data = job_state.load(job_id)
    assert data["state"] == "archive"
    assert data["scores"].get("review") == 90
    history_states = [h["state"] for h in data["history"]]
    assert history_states == ["topic", "materials", "draft", "visual", "review", "archive"]


def test_quality_gate_rejection_and_fix(test_env):
    """
    E2E 场景 2: 质检门禁打回与自愈修复
    创建 Job -> 放置含广告法违规与违禁词文案 -> 运行合规质检 -> 验证 REJECTED -> 修正文案 -> 验证 PASSED
    """
    job_id = "2026-08-19_合规质检自愈测试"
    out_job_dir = test_env["outputs"] / job_id
    (out_job_dir / "小红书").mkdir(parents=True, exist_ok=True)
    report_file = out_job_dir / "compliance_report.json"

    # 1. 放置含严重违规词文案（广告法绝对化词汇与金融保证收益词）
    bad_xhs = (
        "---\ntitle: 全网第一神课稳赚不赔\nplatform: 小红书\ntags: [#搞钱]\n---\n\n"
        "保证日入过万，绝对稳赚不赔，顶级投资建议，加V私信领取！"
    )
    (out_job_dir / "小红书" / "文案.md").write_text(bad_xhs, encoding="utf-8")

    # 运行合规检查
    cmd = [
        sys.executable, os.path.join(SCRIPTS, "compliance_check.py"),
        str(out_job_dir), "--out", str(report_file)
    ]
    r1 = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    assert r1.returncode != 0
    rep1 = json.loads(report_file.read_text(encoding="utf-8"))
    assert rep1["verdict"] == "REJECTED"
    assert len(rep1["checks"]) > 0

    # 2. 修复文案为合规文案
    good_xhs = (
        "---\ntitle: 探索AI内容生产的新实践\nplatform: 小红书\ntags: [#AI工具, #效率提升]\n"
        "series: 系列 | 第 1 篇\nfollow_cta: 关注小吴聊，下期拆解更多技巧\n---\n\n"
        "实测生产流能显著提高写作效率，建议收藏交流！"
    )
    (out_job_dir / "小红书" / "文案.md").write_text(good_xhs, encoding="utf-8")

    r2 = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    assert r2.returncode == 0
    rep2 = json.loads(report_file.read_text(encoding="utf-8"))
    assert rep2["verdict"] == "PASSED"


def test_materials_contract_enforcement(test_env):
    """
    E2E 场景 3: 素材契约强制校验
    素材包声明 3 条核心素材，文案只在 consumed_materials 中报关 1 条 -> 验证契约拦截
    """
    job_id = "2026-08-19_契约拦截测试"
    out_job_dir = test_env["outputs"] / job_id
    (out_job_dir / "小红书").mkdir(parents=True, exist_ok=True)
    (out_job_dir / "公众号").mkdir(parents=True, exist_ok=True)

    month = datetime.now().strftime("%Y-%m")
    mat_folder = test_env["materials"] / month
    mat_folder.mkdir(parents=True, exist_ok=True)
    mat_file = mat_folder / f"{job_id}素材包.md"
    mat_file.write_text(
        "# 素材包\n\n"
        "- M1｜核心事实1（source_type: 真实数据 | priority: 核心）\n  来源：https://example.com/1\n"
        "- M2｜核心事实2（source_type: 真实数据 | priority: 核心）\n  来源：https://example.com/2\n"
        "- M3｜核心事实3（source_type: 真实数据 | priority: 核心）\n  来源：https://example.com/3\n",
        encoding="utf-8"
    )

    # 文案仅消费 M1，遗漏 M2 和 M3
    (out_job_dir / "小红书" / "文案.md").write_text(
        "---\ntitle: 契约测试\nplatform: 小红书\ntags: [#AI]\nseries: 系列 | 第 1 篇\n"
        "follow_cta: 关注小吴聊，下期拆解更多\nconsumed_materials: [M1]\n---\n\n正文",
        encoding="utf-8"
    )
    (out_job_dir / "公众号" / "文案.md").write_text(
        "---\ntitle: 契约测试\nplatform: 公众号\ndigest: 摘要\nconsumed_materials: [M1]\n---\n\n"
        "# 标题\n\n<!-- viz: stat-card -->\n<!-- viz: bar-chart -->\n\n## 01 / 章节\n内容\n\n## 参考来源\n1. https://example.com/1",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, os.path.join(SCRIPTS, "validate_materials_contract.py"),
        str(out_job_dir), "--materials", str(mat_file), "--json"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    # 核心素材消费率不足 100% 会产出素材衰减 FAIL 报告
    out_json = json.loads(r.stdout)
    decay_issues = [it for it in out_json.get("results", []) if it.get("code") in ("C3-decay", "C3-rate") or "素材衰减" in it.get("message", "")]
    assert len(decay_issues) >= 1
    assert r.returncode != 0



def test_topic_adopt_creates_job(test_env):
    """
    E2E 场景 4: 选题采纳创建 Job
    通过 FastAPI TestClient POST /api/topics/adopt -> 验证 state.json 创建及 brief.md 写入
    """
    client = TestClient(app)
    payload = {
        "title": "2026 AI自媒体新趋势实战",
        "link": "https://36kr.com/p/123456",
        "notes": "优先输出小红书图文卡片与公众号深度长文",
    }
    resp = client.post("/api/topics/adopt", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # 验证 state.json
    state_file = test_env["jobs"] / job_id / "state.json"
    assert state_file.exists()
    st = json.loads(state_file.read_text(encoding="utf-8"))
    assert st["state"] == "topic"
    assert "2026 AI自媒体新趋势实战" in st["theme"]

    # 验证 brief.md
    brief_file = test_env["jobs"] / job_id / "brief.md"
    assert brief_file.exists()
    brief_text = brief_file.read_text(encoding="utf-8")
    assert "2026 AI自媒体新趋势实战" in brief_text
    assert "https://36kr.com/p/123456" in brief_text


def test_reject_twice_triggers_human_escalation(test_env):
    """
    E2E 场景 5: 连续 2 次打回触发人工仲裁
    创建 Job -> reject 两次 -> 验证 exit code 2 与输出包含「人工仲裁」
    """
    job_id = "2026-08-19_人工仲裁测试"
    env = dict(os.environ, SELFMEDIA_JOBS_DIR=str(test_env["jobs"]))
    
    # 1. 创建 Job
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"), "init", job_id, "--theme", "仲裁测试"], env=env, check=True)  # nosec B603

    # 2. 第一次打回
    r1 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"), "reject", job_id, "--note", "初次素材不达标"], env=env, capture_output=True, text=True)  # nosec B603
    assert r1.returncode == 0
    assert "第 1 次" in r1.stdout

    # 3. 第二次打回 -> 触发 exit code 2 与 人工仲裁
    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"), "reject", job_id, "--note", "二次结构AI腔太浓"], env=env, capture_output=True, text=True)  # nosec B603
    assert r2.returncode == 2
    assert "人工仲裁" in r2.stdout


def test_auto_advance_on_timeout(test_env):
    """
    E2E 场景 6: 决策超时自动推进
    创建 Job (deadline 设为过去时间) -> auto-advance -> 验证状态从 topic 自动推进到 materials
    """
    job_id = "2026-08-19_超时自动推进测试"
    env = dict(os.environ, SELFMEDIA_JOBS_DIR=str(test_env["jobs"]))
    
    # 1. 创建 Job 并手动修改 deadline 为过去 5 分钟
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"), "init", job_id, "--theme", "超时测试"], env=env, check=True)  # nosec B603
    st_path = test_env["jobs"] / job_id / "state.json"
    st = json.loads(st_path.read_text(encoding="utf-8"))
    st["decision_deadline"] = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    st_path.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")

    # 2. 运行 auto-advance
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "job_state.py"), "auto-advance", job_id], env=env, capture_output=True, text=True)  # nosec B603
    assert r.returncode == 0
    assert "自动推进" in r.stdout

    # 3. 验证状态已流转到 materials
    st_after = json.loads(st_path.read_text(encoding="utf-8"))
    assert st_after["state"] == "materials"
    assert "决策超时自动推进" in st_after["history"][-1]["note"]
