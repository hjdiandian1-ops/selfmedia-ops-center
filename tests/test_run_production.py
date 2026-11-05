"""run_production：用户模板偏好、文风注入与 4 阶段解耦流水线测试。"""
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


def test_four_stage_decoupled_pipeline(tmp_path, monkeypatch):
    """测试 4 阶段解耦流水线 (Stage 1~4) 与中间产物落盘。"""
    job_id = "2026-08-19_测试4阶段流水线"
    job_dir = tmp_path / "jobs" / job_id
    outputs_dir = tmp_path / "outputs" / job_id
    mat_dir = tmp_path / "materials"
    job_dir.mkdir(parents=True)
    outputs_dir.mkdir(parents=True)
    mat_dir.mkdir(parents=True)

    state_file = job_dir / "state.json"
    state_file.write_text(json.dumps({"job_id": job_id, "theme": "AI 四阶段流水线测试", "state": "topic"}), encoding="utf-8")
    (job_dir / "brief.md").write_text("# 简报\n- 核心事实：4 阶段流水线解耦测试\n- 关键指标：效率提升 80%", encoding="utf-8")

    monkeypatch.setattr(rp, "JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(rp, "OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(rp, "MATERIALS_DIR", str(mat_dir))
    monkeypatch.setattr(rp, "_prefer_codex", lambda: False)
    monkeypatch.setattr(rp, "codex_bin", lambda: "")

    # Mock llm_engine
    def mock_chat(messages, **kwargs):
        sys_content = messages[0]["content"] if messages else ""
        if "资深采编" in sys_content:
            return (
                "# AI 四阶段流水线 结构化素材包\n\n"
                "## 一、核心事实与时间节点\n"
                "- [M1] [source_type: 官方发布] [priority: 核心] 四阶段生产流水线重构正式完成。\n"
                "- [M2] [source_type: 技术分析] [priority: 核心] 单步单责消除大模型 Token 遗忘。\n\n"
                "## 二、关键数据指标\n"
                "- [M3] [source_type: 行业研报] [priority: 核心] 效率提升 80%，吞吐量翻倍。\n"
                "- [M4] [source_type: 评测数据] [priority: 参考] 错误率降低 65%。\n\n"
                "## 三、核心实体\n"
                "- [M5] [source_type: 案例调研] [priority: 核心] 自媒体自动化运营工厂。\n\n"
                "## 四、引流切入点\n"
                "- [M6] [source_type: 痛点洞察] [priority: 参考] 单次 Prompt 截断与素材衰减。\n\n"
                "## 五、真实来源\n"
                "1. [M7] [source_type: 官方文档] [priority: 背景] 官方工程白皮书"
            )
        elif "小红书主编" in sys_content:
            return (
                "---\ntitle: 一键多步解耦生产彻底跑通\nplatform: 小红书\ntags: [AI, 生产力, 效率]\n"
                "series: 自媒体实战系列 01\nfollow_cta: 关注小吴聊，下期拆解…\n"
                "consumed_materials: [M1, M2, M3, M5]\n---\n\n"
                "别再手动写稿了！一套流水线直接把效率拉满。\n\n<!-- viz: stat-card -->\n"
                "实测数据提升 80% 以上，干货满满建议收藏。"
            )
        elif "公众号主编" in sys_content:
            return (
                "---\ntitle: 为什么四阶段独立流水线比单次Prompt强10倍\nplatform: 公众号\n"
                "digest: 深度拆解流水线解耦架构与核心数据\nconsumed_materials: [M1, M2, M3, M5, M7]\n---\n\n"
                "# 为什么四阶段流水线更稳\n\n<!-- viz: stat-card -->\n<!-- viz: bar-chart -->\n\n"
                "## 01 / 解耦的核心价值\n单步单责消除素材衰减。\n\n"
                "## 02 / 实测数据佐证\n核心指标提升 80%。\n\n"
                "## 03 / 落地总结与启示\n工业级闭环。\n\n"
                "## 参考来源\n1. 官方工程白皮书"
            )
        elif "短视频导演" in sys_content:
            return (
                "# 分镜脚本\n\n"
                "## 0-3s 黄金钩子\n- 画面：特写\n- 旁白：你敢信吗？一套流水线替代了一个运营团队！\n\n"
                "## 3-15s 痛点共鸣\n- 画面：写稿痛点\n- 旁白：痛点\n\n"
                "## 15-75s 干货演示\n- 画面：界面演示\n- 旁白：实操\n\n"
                "## 75-105s 转折升华\n- 画面：成果对比\n- 旁白：升华\n\n"
                "## 105-120s 行动召唤\n- 画面：关注引导\n- 旁白：关注小吴聊，获取完整模板"
            )
        return "mock content"

    monkeypatch.setattr(rp.llm_engine, "chat", mock_chat)

    # 运行 _api_production / execute_multi_step_pipeline
    ok = rp._api_production(job_id)
    assert ok is True

    # 1. 校验 Stage 1 产物 (materials)
    mat_files = list(mat_dir.glob("*/*素材包.md"))
    assert len(mat_files) >= 1
    mat_content = mat_files[0].read_text(encoding="utf-8")
    assert "[source_type: 官方发布]" in mat_content
    assert "[priority: 核心]" in mat_content

    # 2. 校验 Stage 2 产物 (draft + visual)
    assert (outputs_dir / "小红书" / "文案.md").exists()
    assert (outputs_dir / "公众号" / "文案.md").exists()
    assert (outputs_dir / "短视频" / "120s黄金分镜脚本.md").exists()
    xhs_text = (outputs_dir / "小红书" / "文案.md").read_text(encoding="utf-8")
    assert "consumed_materials:" in xhs_text

    slides_html = list((outputs_dir / "小红书").glob("rednote_*_slides.html"))
    assert len(slides_html) >= 1
    slides_content = slides_html[0].read_text(encoding="utf-8")
    assert "实测数据提升 80% 以上" in slides_content

    gzh_html = list((outputs_dir / "公众号").glob("gzh_*_排版_*.html"))
    assert len(gzh_html) >= 1
    gzh_content = gzh_html[0].read_text(encoding="utf-8")
    assert "01 / 解耦的核心价值" in gzh_content
    assert "单步单责消除素材衰减" in gzh_content

    # 3. 校验 Stage 3 & 4 最终状态已推进
    final_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert final_state["state"] in ("review", "archive")


def test_normalize_materials_and_polish_draft_regressions(tmp_path, monkeypatch):
    """回归测试：素材包 URL 不粘连中文括号、二元对比不产生双逗号或断句、幂等润色不重复追加 CTA、小红书标签不被误判为标题。"""
    import validate_materials_contract as VMC

    raw_mat = (
        "# 测试素材包\n"
        "- M1｜核心突破：结构化 XML 比自然语言更可靠，配套 12 个模版 来源：https://x.com/dotey/123（source_type: 真实数据 | priority: 核心）\n"
        "- M2｜架构演进：标签化结构约束模型行为 来源：https://github.com/trending（source_type: 真实数据 | priority: 核心）\n"
        "- M3｜量化基准：日选题总分 15.6，是当日唯一同时进榜候选 来源：https://github.com/trending（source_type: 真实数据 | priority: 核心）\n"
        "- M4｜落地场景：上下文削减 98%（source_type: 真实数据 | priority: 核心） 来源：https://github.com/mksglu/context-mode\n"
    )
    norm_mat = rp._normalize_materials_contract(raw_mat, "提示词工程实战", "")
    assert "唯一" not in norm_mat
    items, ok = VMC.parse_materials(norm_mat)
    assert ok is True
    for it in items:
        assert it["url"] and "（" not in it["url"] and "x.com" not in it["url"]

    monkeypatch.setattr(rp, "OUTPUTS_DIR", str(tmp_path / "outputs"))
    raw_gzh = (
        "---\ntitle: 我把提示词从散文改成XML，6组实测效率涨了30\nplatform: 公众号\n---\n"
        "# 我把提示词从散文改成XML，6组实测效率涨了30%\n\n"
        "我用 Claude 实测了 6 组样本，效率提升 30%！他们的痛点不是不会用工具，工具满地都是。这不是巧合。它是必然趋势。不是把需求说清楚，而是把边界约束死。\n"
    )
    p1 = rp._polish_draft_for_qa(raw_gzh, "公众号", "2026-11-02_test", "提示词工程", norm_mat)
    p2 = rp._polish_draft_for_qa(p1, "公众号", "2026-11-02_test", "提示词工程", norm_mat)
    assert "，，" not in p2
    assert "。，" not in p2
    assert "工具满地都是。" in p2
    assert "title: 我把提示词从散文改成XML，6组实测效率涨了30%" in p2
    assert p2.count("### 核心实测数据对照") == 1

    raw_xhs = (
        "---\ntitle: 实测6组数据：大模型落地业务的提示词工\nplatform: 小红书\n---\n"
        "我用 FastAPI 与 Claude 跑了 6 组实验，效率提升 30%！\n\n"
        "#AI工具 #效率神器 #自媒体运营 #生产力工具 #个人IP\n"
    )
    x1 = rp._polish_draft_for_qa(
        raw_xhs, "小红书", "2026-11-02_test", "大模型落地业务的提示词工程", norm_mat,
        default_cta="这套工作台已开放，评论区扣「工作台」解锁！",
    )
    x2 = rp._polish_draft_for_qa(x1, "小红书", "2026-11-02_test", "大模型落地业务的提示词工程", norm_mat)
    assert "评论区扣" not in x2
    assert "提示词工\n" not in x2
    slides_html = rp._compile_xhs_slides_from_md(x2, "大模型落地业务的提示词工程", "实测6组数据")
    assert "▍AI工具" not in slides_html
    assert "#AI工具" in slides_html
    assert "&gt; 注：" not in slides_html

