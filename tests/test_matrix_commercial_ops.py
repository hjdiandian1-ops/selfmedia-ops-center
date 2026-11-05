# -*- coding: utf-8 -*-
"""工业级自媒体运营中台（日更 SLA / 矩阵号一鱼多吃 / 商业化闭环 ROI）全链路测试。"""
import json
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

from webapp import core, server
from webapp.routers import matrix_commercial, publish, topics, production
import run_production
import run_daily_pipeline


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """隔离 data / jobs / outputs / production 目录，防止污染真实工作区。"""
    data_dir = tmp_path / "data"
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    prod_dir = data_dir / "production"
    fly_dir = data_dir / "flywheel"
    matrix_dir = data_dir / "matrix"
    comm_dir = data_dir / "commercial"

    for d in (data_dir, jobs_dir, outputs_dir, prod_dir, fly_dir, matrix_dir, comm_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(core, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(core, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(core, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(core, "PRODUCTION_FILE", str(prod_dir / "queue.json"))
    monkeypatch.setattr(core, "FLYWHEEL_DIR", str(fly_dir))
    monkeypatch.setattr(core, "FEEDBACK_FILE", str(fly_dir / "pipeline_feedback.md"))
    monkeypatch.setattr(core, "MATRIX_DIR", str(matrix_dir))
    monkeypatch.setattr(core, "MATRIX_ACCOUNTS_FILE", str(matrix_dir / "accounts.json"))
    monkeypatch.setattr(core, "DAILY_SCHEDULE_FILE", str(matrix_dir / "daily_schedule.json"))
    monkeypatch.setattr(core, "COMMERCIAL_DIR", str(comm_dir))
    monkeypatch.setattr(core, "COMMERCIAL_OFFERS_FILE", str(comm_dir / "offers.json"))
    monkeypatch.setattr(core, "COMMERCIAL_LEDGER_FILE", str(comm_dir / "ledger.json"))
    monkeypatch.setattr(core, "_kick_production", lambda: {"started": False, "pid": 99999})
    monkeypatch.setattr(core, "_license_guard", lambda feature="production": {"tier": "pro"})

    monkeypatch.setattr(run_production, "JOBS_DIR", str(jobs_dir))
    monkeypatch.setattr(run_production, "OUTPUTS_DIR", str(outputs_dir))
    monkeypatch.setattr(run_production, "MATRIX_ACCOUNTS_FILE", str(matrix_dir / "accounts.json"))
    monkeypatch.setattr(run_production, "COMMERCIAL_OFFERS_FILE", str(comm_dir / "offers.json"))

    return {
        "data_dir": data_dir,
        "jobs_dir": jobs_dir,
        "outputs_dir": outputs_dir,
        "prod_dir": prod_dir,
        "fly_dir": fly_dir,
        "matrix_dir": matrix_dir,
        "comm_dir": comm_dir,
    }


# =========================================================================
# 1. 矩阵号管理与「一鱼多吃」多号裂变测试
# =========================================================================
def test_matrix_accounts_crud_and_secret_masking(isolated_env):
    # 默认自动初始化 3 个矩阵号
    res = server.api_matrix_accounts()
    assert res["ok"] is True
    assert len(res["accounts"]) == 3
    ids = {a["id"] for a in res["accounts"]}
    assert {"acc_main", "acc_geek_tools", "acc_side_hustle"} <= ids

    # 新增一个带公众号凭据的矩阵号
    created = server.api_matrix_account_save(
        matrix_commercial.MatrixAccountPayload(
            id="acc_video_lab",
            name="AI视频拆解实验室",
            handle="@ai_video_lab",
            platforms=["小红书", "短视频"],
            niche="AI视频生成与分镜工程",
            persona="硬核AIGC导演",
            target_audience="视频创作者与电商团队",
            angle="分镜脚本拆解 + 提示词参数实测",
            style_preset="tech-hands-on",
            daily_target=2,
            default_offer_id="offer_lead_magnet",
            gzh_app_id="wx_test_appid_01",
            gzh_app_secret="test_secret_val",
            enabled=True,
        )
    )
    assert created["ok"] is True
    assert created["action"] == "created"
    acc_out = created["account"]
    assert acc_out["id"] == "acc_video_lab"
    assert acc_out["gzh_configured"] is True
    assert "gzh_app_secret" not in acc_out

    # 更新该矩阵号但留空 secret，确认原 secret 得以保留
    updated = server.api_matrix_account_save(
        matrix_commercial.MatrixAccountPayload(
            id="acc_video_lab",
            name="AI视频拆解实验室Pro",
            platforms=["小红书", "公众号"],
            daily_target=3,
            gzh_app_id="wx_test_appid_01",
            gzh_app_secret="",
        )
    )
    assert updated["action"] == "updated"
    assert updated["account"]["name"] == "AI视频拆解实验室Pro"
    assert updated["account"]["daily_target"] == 3
    assert updated["account"]["gzh_configured"] is True

    # 删除账号，并验证至少保留 1 个账号的保护门禁
    del_res = server.api_matrix_account_delete("acc_video_lab")
    assert del_res["ok"] is True
    server.api_matrix_account_delete("acc_side_hustle")
    server.api_matrix_account_delete("acc_geek_tools")
    with pytest.raises(HTTPException) as exc:
        server.api_matrix_account_delete("acc_main")
    assert exc.value.status_code == 400


def test_matrix_account_validation_errors(isolated_env):
    with pytest.raises(HTTPException) as e1:
        server.api_matrix_account_save(matrix_commercial.MatrixAccountPayload(name="   "))
    assert e1.value.status_code == 400

    with pytest.raises(HTTPException) as e2:
        server.api_matrix_account_save(
            matrix_commercial.MatrixAccountPayload(name="测试号", daily_target=-1)
        )
    assert e2.value.status_code == 400

    with pytest.raises(HTTPException) as e3:
        server.api_matrix_account_save(
            matrix_commercial.MatrixAccountPayload(name="测试号", platforms=["未知平台"])
        )
    assert e3.value.status_code == 400


def test_matrix_fission_dispatch_creates_differentiated_jobs(isolated_env, monkeypatch):
    """测试「一鱼多吃」：1 个母题裂变为 3 个矩阵号的差异化任务并入队。"""
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": False})
    res = server.api_matrix_dispatch(
        matrix_commercial.MatrixDispatchPayload(
            title="DeepSeek R2 开源推理成本暴降 70%",
            link="https://example.com/deepseek-r2",
            notes="重点对比 API 成本与本地部署门槛",
            account_ids=["acc_main", "acc_geek_tools", "acc_side_hustle"],
            auto_start=True,
        )
    )
    assert res["ok"] is True
    assert res["dispatched_count"] == 3
    jobs = res["jobs"]
    job_ids = [j["job_id"] for j in jobs]
    assert len(set(job_ids)) == 3

    # 校验每个矩阵号生成的差异化标题、pipeline_config.json 与 brief.md
    themes = set()
    for j in jobs:
        jid = j["job_id"]
        themes.add(j["theme"])
        cfg = core.read_json(os.path.join(core.JOBS_DIR, jid, "pipeline_config.json"))
        assert cfg["account_id"] == j["account_id"]
        assert cfg["account_persona"]
        assert cfg["account_angle"]
        assert cfg["offer_id"]

        brief = core.read_text(os.path.join(core.JOBS_DIR, jid, "brief.md"))
        assert "DeepSeek R2 开源推理成本暴降 70%" in brief
        assert j["account_name"] in brief
        assert j["angle"] in brief

    # 3 个账号生成的主题应各自带有差异化切角后缀，互不相同
    assert len(themes) == 3

    # 校验生产队列均已入队
    q = core.read_json(core.PRODUCTION_FILE)
    q_ids = [item["job_id"] for item in q["items"]]
    for jid in job_ids:
        assert jid in q_ids


# =========================================================================
# 2. 日更排期、Streak 连续日更与 SLA 无人值守补齐测试
# =========================================================================
def test_daily_sla_streak_and_autopilot_closed_loop(isolated_env, monkeypatch):
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": False})
    # 初始无任务时，SLA 应处于 at_risk 状态
    sla0 = server.api_daily_sla()
    assert sla0["ok"] is True
    assert sla0["sla_status"] == "at_risk"
    assert sla0["today_produced"] == 0
    assert sla0["streak_days"] == 0
    assert len(sla0["calendar_30d"]) == 30

    # 模拟过去连续 3 天均有历史任务，验证 Streak 计算
    today_dt = datetime.now().date()
    for delta in (1, 2, 3):
        d_str = (today_dt - timedelta(days=delta)).isoformat()
        jid = f"{d_str}_hist_{delta}"
        jdir = os.path.join(core.JOBS_DIR, jid)
        os.makedirs(jdir, exist_ok=True)
        core._atomic_write_json(
            os.path.join(jdir, "state.json"),
            {
                "job_id": jid,
                "theme": f"历史日更主题{delta}",
                "state": "publish",
                "created_at": f"{d_str} 10:00:00",
                "history": [],
            },
        )

    sla1 = server.api_daily_sla()
    assert sla1["streak_days"] == 3

    # 触发「一键日更无人值守补齐」(/api/ops/daily-autopilot)
    auto_res = server.api_daily_autopilot(
        matrix_commercial.DailyAutopilotPayload(max_jobs=3)
    )
    assert auto_res["ok"] is True
    assert auto_res["created_count"] >= 2

    # 补齐后再次查询 SLA：今日已产出 >= 目标配额，Streak 应升级为 4 天，SLA 达标
    sla2 = server.api_daily_sla()
    assert sla2["today_produced"] == auto_res["created_count"]
    assert sla2["streak_days"] == 4
    assert sla2["sla_status"] in ("in_progress", "achieved")
    assert sla2["completion_rate"] > 0


def test_schedule_slot_lifecycle(isolated_env, monkeypatch):
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": False})
    today_str = datetime.now().strftime("%Y-%m-%d")
    saved = server.api_schedule_save(
        matrix_commercial.ScheduleSlotPayload(
            date=today_str,
            time="18:30",
            account_id="acc_geek_tools",
            title="3个零代码自动化神器实测",
            platform="小红书",
            offer_id="offer_lead_magnet",
            notes="突出小白友好",
        )
    )
    assert saved["ok"] is True
    slot_id = saved["slot"]["id"]
    assert saved["slot"]["status"] == "planned"

    # 执行该排期槽位 -> 自动建单入队并更新状态为 queued
    executed = server.api_schedule_execute(slot_id)
    assert executed["ok"] is True
    assert executed["slot"]["status"] == "queued"
    assert executed["job"]["job_id"]
    assert os.path.isfile(os.path.join(core.JOBS_DIR, executed["job"]["job_id"], "brief.md"))

    # 删除排期槽位
    deleted = server.api_schedule_delete(slot_id)
    assert deleted["ok"] is True
    with pytest.raises(HTTPException) as exc:
        server.api_schedule_delete(slot_id)
    assert exc.value.status_code == 404


def test_run_daily_pipeline_auto_select_enqueues_sanitized_job(isolated_env, monkeypatch):
    """验证 CLI run_daily_pipeline.py --topics --auto-select 能清洗非法字符、写 brief.md 并入队。"""
    mat_sub = isolated_env["data_dir"] / "materials" / "2026-11"
    mat_sub.mkdir(parents=True, exist_ok=True)
    suggest_md = mat_sub / "2026-11-02_选题推荐.md"
    suggest_md.write_text(
        "# 今日推荐\n- 主题方向：AI Agent: 为什么 90% 的公司落地失败？\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_daily_pipeline, "JOBS_DIR", str(isolated_env["jobs_dir"]))
    monkeypatch.setattr(run_daily_pipeline, "MATERIALS_DIR", str(isolated_env["data_dir"] / "materials"))
    monkeypatch.setattr(run_daily_pipeline, "PRODUCTION_FILE", str(isolated_env["prod_dir"] / "queue.json"))
    monkeypatch.setattr(run_daily_pipeline, "run", lambda *a, **kw: True)
    monkeypatch.setattr(run_daily_pipeline, "spawn", lambda *a, **kw: None)

    class _Args:
        auto_select = True

    ok = run_daily_pipeline.cmd_topics(_Args())
    assert ok is True
    created_dirs = os.listdir(isolated_env["jobs_dir"])
    assert len(created_dirs) == 1
    jid = created_dirs[0]
    # 校验 job_id 合法（不含冒号、问号、空格）
    assert core._require_job_id(jid) == jid
    assert os.path.isfile(os.path.join(str(isolated_env["jobs_dir"]), jid, "brief.md"))
    q = core.read_json(str(isolated_env["prod_dir"] / "queue.json"))
    assert any(item["job_id"] == jid for item in q["items"])


# =========================================================================
# 3. 商业化闭环、变现台账、48h 回填联动与 ROI 漏斗测试
# =========================================================================
def test_commercial_offers_and_ledger_roi_funnel(isolated_env, monkeypatch):
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": True, "stdout": "ok", "stderr": "", "exit": 0})
    # 默认内置 4 个商业化转化组件
    offers_res = server.api_commercial_offers()
    assert offers_res["ok"] is True
    assert len(offers_res["offers"]) == 4

    # 新增一个高客单价企业咨询组件
    saved_offer = server.api_commercial_offer_save(
        matrix_commercial.CommercialOfferPayload(
            id="offer_consulting_vip",
            name="企业AI工作流内训定制",
            type="consulting",
            price_yuan=9800.0,
            lead_value_yuan=200.0,
            keyword="内训",
            cta_xhs="企业定制方案见置顶合集",
            cta_gzh="公众号后台回复【内训】预约架构师1v1诊断",
            cta_video="评论区置顶查看企业落地案例",
        )
    )
    assert saved_offer["ok"] is True
    assert saved_offer["offer"]["id"] == "offer_consulting_vip"

    # 先通过采纳选题建立一个绑定 acc_side_hustle + offer_consulting_vip 的任务
    adopted = server.api_adopt(
        topics.AdoptTopic(
            title="制造企业如何落地私有化大模型知识库",
            account_id="acc_side_hustle",
            offer_id="offer_consulting_vip",
        )
    )
    job_id = adopted["job_id"]

    # 记入一笔商业化转化（不手填 revenue_yuan，但填 conversions=2，验证按组件单价 9800*2=19600 自动核算）
    ledger_res = server.api_commercial_ledger_add(
        matrix_commercial.CommercialLedgerPayload(
            job_id=job_id,
            account_id="",
            platform="公众号",
            revenue_type="consulting",
            reads=12000,
            leads=25,
            conversions=2,
            revenue_yuan=0.0,
            note="两家制造业客户签约内训",
        )
    )
    entry = ledger_res["entry"]
    assert entry["account_id"] == "acc_side_hustle"
    assert entry["offer_id"] == "offer_consulting_vip"
    assert entry["revenue_yuan"] == 19600.0

    # 验证同步写入了 jobs/<job_id>/publish_log.json
    pub_log = core.read_json(os.path.join(core.JOBS_DIR, job_id, "publish_log.json"))
    assert len(pub_log.get("commercial", [])) == 1
    assert pub_log["commercial"][0]["revenue_yuan"] == 19600.0

    # 验证 48h 数据回填接口 (/api/stats/backfill) 附带 leads/revenue_yuan 时自动同步记入商业化台账
    bf_res = server.api_stats_backfill(
        publish.StatsBackfill(
            job_id=job_id,
            platform="小红书",
            reads=8000,
            likes=320,
            collects=210,
            comments=45,
            leads=15,
            conversions=1,
            revenue_yuan=299.0,
            revenue_type="course_community",
        )
    )
    assert bf_res["ok"] is True
    assert bf_res["commercial_entry"]["leads"] == 15
    assert bf_res["commercial_entry"]["revenue_yuan"] == 299.0

    # 查询商业化全景大盘 (/api/commercial/overview)
    overview = server.api_commercial_overview()
    assert overview["ok"] is True
    assert overview["kpis"]["total_revenue_yuan"] == 19899.0
    assert overview["kpis"]["total_leads"] == 40
    assert overview["kpis"]["total_conversions"] == 3
    assert overview["kpis"]["rpm_yuan"] > 0
    assert overview["funnel"]["reads"] >= 20000

    # 验证数据飞轮反馈文档 (_build_feedback_md) 包含第六章「商业化闭环与矩阵变现反馈」
    fb_md = core._build_feedback_md()
    assert "## 六、商业化闭环与矩阵变现反馈" in fb_md
    assert "19899.00" in fb_md
    assert "制造企业如何落地私有化大模型知识库" in fb_md


# =========================================================================
# 4. Stage 2 写作流水线人设/CTA自动注入与多矩阵号公众号独立凭据测试
# =========================================================================
def test_stage2_draft_injects_matrix_persona_and_commercial_cta(isolated_env, monkeypatch):
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": True, "stdout": "ok", "stderr": "", "exit": 0})
    adopted = server.api_adopt(
        topics.AdoptTopic(
            title="Claude Code 自动化重构实战",
            account_id="acc_geek_tools",
            offer_id="offer_lead_magnet",
        )
    )
    job_id = adopted["job_id"]

    # 验证 _resolve_matrix_and_offer_context 能解析出对应矩阵号人设、切角、文风模板与三端 CTA
    acc_info, offer_info, style_override = run_production._resolve_matrix_and_offer_context(job_id)
    assert acc_info["id"] == "acc_geek_tools"
    assert "极客" in acc_info["name"] or "工具" in acc_info["name"]
    assert acc_info["persona"]
    assert offer_info["cta_xhs"]
    assert offer_info["cta_gzh"]
    assert offer_info["cta_video"]
    assert len(style_override) > 20

    # 验证 LLM 提示词与降级生成中均包含矩阵号人设与商业化 CTA 钩子
    captured_systems = []

    def _failing_generate(jid, system, user_prompt, *a, **kw):
        captured_systems.append(system)
        raise RuntimeError("mock llm offline")

    monkeypatch.setattr(run_production, "_generate", _failing_generate)
    log_path = str(isolated_env["jobs_dir"] / job_id / "production.log")
    xhs_md = run_production._generate_xhs_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", "", log_path)
    gzh_md = run_production._generate_gzh_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", "", log_path)
    vid_md = run_production._generate_video_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", log_path)

    assert len(captured_systems) == 3
    for sys_prompt in captured_systems:
        assert acc_info["name"] in sys_prompt
    assert offer_info["cta_xhs"] in xhs_md
    assert offer_info["cta_gzh"] in gzh_md
    assert offer_info["cta_video"] in vid_md


    # 验证当 LLM 成功返回但遗漏了商业化 CTA 时，Stage 2 仍会自动补齐 CTA，且视觉 HTML 自动注入矩阵号品牌名
    monkeypatch.setattr(
        run_production,
        "_generate",
        lambda jid, sys_p, usr_p, *a, **kw: "---\ntitle: 测试标题\nplatform: 公众号\ndigest: 摘要\n---\n\n正文段落\n\n## 参考来源\n1. 来源",
    )
    xhs_ok = run_production._generate_xhs_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", "", log_path)
    gzh_ok = run_production._generate_gzh_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", "", log_path)
    vid_ok = run_production._generate_video_draft(job_id, "Claude Code 自动化重构实战", "素材正文", "文风规则", log_path)
    assert offer_info["cta_xhs"] in xhs_ok
    assert offer_info["cta_gzh"] in gzh_ok
    assert offer_info["cta_video"] in vid_ok

    run_production._generate_visual_artifacts(job_id, "Claude Code 自动化重构实战", xhs_ok, gzh_ok, log_path)
    xhs_slides_files = [
        f for f in os.listdir(os.path.join(core.OUTPUTS_DIR, job_id, "小红书")) if f.endswith(".html")
    ]
    gzh_html_files = [
        f for f in os.listdir(os.path.join(core.OUTPUTS_DIR, job_id, "公众号")) if f.endswith(".html") and "_预览" not in f
    ]
    assert xhs_slides_files and gzh_html_files
    slides_html = core.read_text(os.path.join(core.OUTPUTS_DIR, job_id, "小红书", xhs_slides_files[0]))
    wechat_html = core.read_text(os.path.join(core.OUTPUTS_DIR, job_id, "公众号", gzh_html_files[0]))
    assert "极客效率工具控" in slides_html
    assert "极客效率工具控" in wechat_html


def test_gzh_draft_uses_matrix_account_credentials(isolated_env, monkeypatch):
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": True, "stdout": "ok", "stderr": "", "exit": 0})
    # 为 acc_side_hustle 配置独立公众号凭据
    server.api_matrix_account_save(
        matrix_commercial.MatrixAccountPayload(
            id="acc_side_hustle",
            name="商业深潜号",
            platforms=["公众号"],
            gzh_app_id="wx_matrix_custom_id",
            gzh_app_secret="matrix_custom_secret_val",
        )
    )
    adopted = server.api_adopt(
        topics.AdoptTopic(
            title="SaaS 行业 AI 转型研报",
            account_id="acc_side_hustle",
        )
    )
    job_id = adopted["job_id"]
    out_dir = os.path.join(core.OUTPUTS_DIR, job_id, "公众号")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "排版预览.html"), "w", encoding="utf-8") as f:
        f.write("<p>正文</p>")

    captured_env = {}
    os.environ["GZH_APP_ID"] = "global_untouched_id"

    def _fake_run_script(args, timeout=60, extra_env=None):
        captured_env["extra_env"] = dict(extra_env or {})
        captured_env["process_env_during_call"] = os.environ.get("GZH_APP_ID")
        return {"ok": True, "stdout": "pushed media_id=123", "stderr": "", "exit": 0}

    monkeypatch.setattr(core, "run_script", _fake_run_script)
    try:
        res = server.api_gzh_draft(publish.GzhDraftRequest(job_id=job_id, title="测试标题"))
        assert res["ok"] is True
        assert captured_env["extra_env"].get("GZH_APP_ID") == "wx_matrix_custom_id"
        assert captured_env["extra_env"].get("GZH_APP_SECRET") == "matrix_custom_secret_val"
        # 确认未污染主进程全局 os.environ（并发安全）
        assert captured_env["process_env_during_call"] == "global_untouched_id"
    finally:
        os.environ.pop("GZH_APP_ID", None)


def test_daily_target_zero_and_autopilot_dedup_differentiated_themes(isolated_env, monkeypatch):
    """验证 daily_target=0 的账号配额为 0（不强行变 1），且无人值守补齐对带差异化后缀的已建主题能正确去重。"""
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": False})
    server.api_matrix_account_save(
        matrix_commercial.MatrixAccountPayload(
            id="acc_geek_tools",
            name="极客效率工具控",
            platforms=["小红书", "公众号"],
            daily_target=0,
            enabled=True,
        )
    )
    accs = {a["id"]: a for a in server.api_matrix_accounts()["accounts"]}
    assert accs["acc_geek_tools"]["daily_target"] == 0
    assert accs["acc_geek_tools"]["quota_met"] is True

    sla = server.api_daily_sla()
    q_map = {q["account_id"]: q for q in sla["account_quotas"]}
    assert q_map["acc_geek_tools"]["daily_target"] == 0
    assert q_map["acc_geek_tools"]["gap"] == 0
    assert q_map["acc_geek_tools"]["met"] is True
    assert sum(q["daily_target"] for q in sla["account_quotas"]) == sla["daily_target_total"]

    # 连续两次调用 daily-autopilot (force=True)，第二次不应重复选择第一次已建过的候选母题
    r1 = server.api_daily_autopilot(
        matrix_commercial.DailyAutopilotPayload(account_ids=["acc_main"], force=True, max_jobs=1)
    )
    r2 = server.api_daily_autopilot(
        matrix_commercial.DailyAutopilotPayload(account_ids=["acc_main"], force=True, max_jobs=1)
    )
    assert r1["jobs"][0]["theme"] != r2["jobs"][0]["theme"]


def test_commercial_ledger_upsert_and_delete_syncs_publish_log(isolated_env, monkeypatch):
    """验证按相同 id 更新商业化台账不会在 publish_log.json 中重复追加，且删除台账会同步清理 publish_log.json。"""
    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": True, "stdout": "ok", "stderr": "", "exit": 0})
    adopted = server.api_adopt(topics.AdoptTopic(title="商业台账幂等同步测试", account_id="acc_main"))
    job_id = adopted["job_id"]

    res1 = server.api_commercial_ledger_add(
        matrix_commercial.CommercialLedgerPayload(
            id="comm_fixed_01",
            job_id=job_id,
            platform="小红书",
            revenue_type="lead_magnet",
            leads=10,
            conversions=1,
            revenue_yuan=199.0,
        )
    )
    assert res1["ok"] is True

    # 用同一个 id 更新金额与线索
    res2 = server.api_commercial_ledger_add(
        matrix_commercial.CommercialLedgerPayload(
            id="comm_fixed_01",
            job_id=job_id,
            platform="小红书",
            revenue_type="lead_magnet",
            leads=20,
            conversions=2,
            revenue_yuan=398.0,
        )
    )
    assert res2["ok"] is True

    lg_path = os.path.join(core.JOBS_DIR, job_id, "publish_log.json")
    lg = core.read_json(lg_path)
    assert len(lg["commercial"]) == 1
    assert lg["commercial"][0]["leads"] == 20
    assert lg["commercial"][0]["revenue_yuan"] == 398.0

    # 删除该台账后，publish_log.json 中的对应记录也应被移除
    server.api_commercial_ledger_delete("comm_fixed_01")
    lg_after = core.read_json(lg_path)
    assert lg_after["commercial"] == []


def test_real_subprocess_run_script_respects_isolated_jobs_dir(isolated_env):
    """不 mock core.run_script，真实执行 job_state.py 与 collect_post_stats.py，验证 SELFMEDIA_JOBS_DIR 隔离生效。"""
    adopted = server.api_adopt(
        topics.AdoptTopic(title="真实子进程目录隔离测试", account_id="acc_main")
    )
    job_id = adopted["job_id"]
    assert os.path.isfile(os.path.join(core.JOBS_DIR, job_id, "state.json"))

    bf = server.api_stats_backfill(
        publish.StatsBackfill(
            job_id=job_id,
            platform="小红书",
            reads=3600,
            likes=180,
            collects=90,
            comments=22,
            leads=8,
            conversions=1,
            revenue_yuan=199.0,
        )
    )
    assert bf["ok"] is True
    pub_log = core.read_json(os.path.join(core.JOBS_DIR, job_id, "publish_log.json"))
    assert pub_log["records"][0]["reads"] == 3600
    assert pub_log["commercial"][0]["revenue_yuan"] == 199.0


def test_http_endpoints_and_boundary_edge_cases(isolated_env, monkeypatch):
    """通过 FastAPI TestClient 验证 HTTP 路由、前端 HTML 挂载与异常边界。"""
    from fastapi.testclient import TestClient
    from webapp import scheduler

    monkeypatch.setattr(core, "run_script", lambda *a, **kw: {"ok": True, "stdout": "ok", "stderr": "", "exit": 0})
    client = TestClient(server.app)

    # 1. 验证首页 HTML 包含矩阵与商业化视图及关键 DOM 节点
    html_res = client.get("/")
    assert html_res.status_code == 200
    assert 'data-view="matrix-ops"' in html_res.text
    assert 'id="view-matrix-ops"' in html_res.text
    assert 'id="dispatch-topic-title"' in html_res.text
    assert 'id="comm-funnel-box"' in html_res.text

    # 2. 验证 Scheduler 已注册 autopilot 日更无人值守任务
    assert "autopilot" in scheduler.TASKS_META

    # 3. 边界测试：空母题裂变、无效排期日期、负数价格/负数营收拦截
    r_empty_dispatch = client.post("/api/matrix/dispatch", json={"title": "   "})
    assert r_empty_dispatch.status_code == 400

    r_bad_date = client.post("/api/ops/schedule", json={"title": "排期测试", "date": "2026/11/02"})
    assert r_bad_date.status_code == 400

    r_neg_offer = client.post("/api/commercial/offers", json={"name": "测试组件", "type": "lead_magnet", "price_yuan": -10})
    assert r_neg_offer.status_code == 400

    r_bad_offer_type = client.post("/api/commercial/offers", json={"name": "测试组件", "type": "unknown_type"})
    assert r_bad_offer_type.status_code == 400

    r_neg_ledger = client.post("/api/commercial/ledger", json={"leads": -1, "revenue_yuan": 100})
    assert r_neg_ledger.status_code == 400

    # 4. 正常 HTTP 闭环：记账 -> 列表过滤 -> 删除 -> 再删 404
    r_add = client.post(
        "/api/commercial/ledger",
        json={
            "title": "小红书置顶笔记私域引流",
            "account_id": "acc_main",
            "platform": "小红书",
            "revenue_type": "lead_magnet",
            "reads": 5000,
            "leads": 42,
            "conversions": 3,
            "revenue_yuan": 597.0,
        },
    )
    assert r_add.status_code == 200
    eid = r_add.json()["entry"]["id"]

    r_list = client.get("/api/commercial/ledger?account_id=acc_main&revenue_type=lead_magnet")
    assert r_list.status_code == 200
    assert r_list.json()["count"] == 1

    r_del = client.delete(f"/api/commercial/ledger/{eid}")
    assert r_del.status_code == 200
    r_del_404 = client.delete(f"/api/commercial/ledger/{eid}")
    assert r_del_404.status_code == 404


def test_playwright_matrix_ops_ui_e2e(isolated_env, monkeypatch):
    """启动真实临时 HTTP 服务并通过 Headless Playwright 验证 #view-matrix-ops 三大子面板真实浏览器交互。"""
    import socket
    import threading
    import time
    import uvicorn
    from playwright.sync_api import sync_playwright

    # 找一个空闲端口启动临时 uvicorn 服务
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="error")
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()
    time.sleep(0.6)

    page_errors = []
    try:
        with sync_playwright() as p:
            browser = None
            for kwargs in ({"headless": True}, {"headless": True, "channel": "chrome"}):
                try:
                    browser = p.chromium.launch(**kwargs)
                    break
                except Exception:
                    continue
            if browser is None:
                pytest.skip("无可用 Chromium/Chrome 内核")

            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.add_init_script("localStorage.setItem('selfmedia_onboarded_v1', '1'); localStorage.setItem('onboarding_done', '1');")
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            # 若新手向导仍显示则跳过
            skip_btn = page.locator(".onboard-btn-skip")
            if skip_btn.is_visible():
                skip_btn.click()

            # 1. 点击导航栏「🏢 矩阵与商业化」
            page.click("button[data-view='matrix-ops']")
            page.wait_for_selector("#view-matrix-ops.active", timeout=5000)
            assert page.locator("#sla-kpi-grid .kpi").count() == 4
            assert page.locator("#sla-heatmap-30d > div").count() == 30

            # 新增一条日更排期并验证表格渲染
            page.fill("#sched-slot-title", "Playwright 自动化排期测试")
            page.click("button:has-text('加入日更排期表')")
            page.wait_for_selector("#sched-slot-table tr:has-text('Playwright 自动化排期测试')", timeout=5000)

            # 2. 切换到「🏢 矩阵号与一鱼多吃」子面板
            page.click("#matrix-ops-tabs button[data-mtab='matrix']")
            page.wait_for_selector("#matrix-tab-matrix:not(.hidden)", timeout=5000)
            assert page.locator("#matrix-accounts-grid .card").count() == 3

            # 点击编辑 acc_side_hustle（原 platforms=["小红书", "短视频"]），将 daily_target 设为 0 并保存
            page.evaluate("editMatrixAccount('acc_side_hustle')")
            page.fill("#mat-acc-target", "0")
            page.click("button:has-text('保存矩阵账号')")
            page.wait_for_timeout(400)
            accs_after = {a["id"]: a for a in core._load_matrix_accounts()}
            assert accs_after["acc_side_hustle"]["daily_target"] == 0
            assert accs_after["acc_side_hustle"]["platforms"] == ["小红书", "短视频"]

            # 3. 切换到「💰 商业化闭环与 ROI」子面板
            page.click("#matrix-ops-tabs button[data-mtab='commercial']")
            page.wait_for_selector("#matrix-tab-commercial:not(.hidden)", timeout=5000)
            assert page.locator("#comm-kpi-grid .kpi").count() == 4

            # 点击编辑 offer_private_community（原 lead_value_yuan=35.0），验证 details 自动展开且保存后保留 lead_value_yuan
            page.evaluate("editCommercialOffer('offer_private_community')")
            is_open = page.evaluate("document.querySelector('#offer-form-name').closest('details').open")
            assert is_open is True
            page.fill("#offer-form-price", "399")
            page.click("button:has-text('保存组件')")
            page.wait_for_timeout(400)
            offers_after = {o["id"]: o for o in core._load_commercial_offers()}
            assert offers_after["offer_private_community"]["price_yuan"] == 399.0
            assert offers_after["offer_private_community"]["lead_value_yuan"] == 35.0

            browser.close()
    finally:
        uv_server.should_exit = True
        thread.join(timeout=3)

    assert page_errors == []


