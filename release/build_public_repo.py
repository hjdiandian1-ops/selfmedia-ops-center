#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开仓库快照生成器（发布前安全门禁的一部分）
============================================
从本仓库按白名单复制「开源核心」资产到 release/selfmedia-ops-center/，
生成 demo 数据，初始化干净 git 历史（不携带本仓库任何历史/真实数据）。

用法：
    python3 release/build_public_repo.py            # 生成快照（覆盖重建）
    python3 release/build_public_repo.py --no-git   # 不初始化 git

白名单原则：
- 只复制自产、无凭据、无个人数据的文件；
- 任何 jobs/outputs/materials/data/nas/第三方 skill 都不进公开仓库；
- 生成后必须跑 security/check_public_repo.py 确认零泄露再推送。
"""
import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RELEASE_DIR = os.path.join(ROOT, "release")
REPO_NAME = "selfmedia-ops-center"
TARGET = os.path.join(RELEASE_DIR, REPO_NAME)
TEMPLATES = os.path.join(RELEASE_DIR, "templates")

# 公开快照白名单（源路径 → 目标路径）：免费工作台 = webapp + 免费模块 + 通用 Agent/工作流
WHITELIST = {
    # 文档与仓库卫生
    "release/templates/README.md": "README.md",
    "release/templates/WHITEPAPER.md": "WHITEPAPER.md",
    "release/templates/LICENSE": "LICENSE",
    "release/templates/SECURITY.md": "SECURITY.md",
    "CONTRIBUTING.md": "CONTRIBUTING.md",
    "CHANGELOG.md": "CHANGELOG.md",
    "release/templates/SECURITY_CHECKLIST.md": "SECURITY_CHECKLIST.md",
    "docs/发布与后台配置.md": "docs/发布与后台配置.md",
    "docs/screenshots/README.md": "docs/screenshots/README.md",
    "docs/screenshots/00-onboarding-demo.png": "docs/screenshots/00-onboarding-demo.png",
    "docs/screenshots/01-dashboard-overview.png": "docs/screenshots/01-dashboard-overview.png",
    "docs/screenshots/02-topics-radar.png": "docs/screenshots/02-topics-radar.png",
    "docs/screenshots/03-viral-breakdown.png": "docs/screenshots/03-viral-breakdown.png",
    "docs/screenshots/04-production-pipeline.png": "docs/screenshots/04-production-pipeline.png",
    "docs/screenshots/05-outputs-preview.png": "docs/screenshots/05-outputs-preview.png",
    "docs/screenshots/06-qa-trends.png": "docs/screenshots/06-qa-trends.png",
    "docs/screenshots/07-theme-showcase.png": "docs/screenshots/07-theme-showcase.png",
    ".github/ISSUE_TEMPLATE/bug_report.yml": ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml": ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/topic_suggestion.yml": ".github/ISSUE_TEMPLATE/topic_suggestion.yml",
    ".github/pull_request_template.md": ".github/pull_request_template.md",
    ".pre-commit-config.yaml": ".pre-commit-config.yaml",
    "release/templates/.gitignore": ".gitignore",
    "release/templates/.env.example": ".env.example",
    "release/templates/start.sh": "start.sh",
    "release/templates/start.bat": "start.bat",
    "release/templates/.github/workflows/security.yml": ".github/workflows/security.yml",
    "release/templates/.github/workflows/codeql.yml": ".github/workflows/codeql.yml",
    # 运行时依赖
    "requirements.in": "requirements.in",
    "requirements.lock": "requirements.lock",
    "pyproject.toml": "pyproject.toml",
    # 工作台（免费版核心 UI + 后端）
    "webapp/server.py": "webapp/server.py",
    "webapp/core.py": "webapp/core.py",
    "webapp/scheduler.py": "webapp/scheduler.py",
    "webapp/routers/__init__.py": "webapp/routers/__init__.py",
    "webapp/routers/overview.py": "webapp/routers/overview.py",
    "webapp/routers/agents.py": "webapp/routers/agents.py",
    "webapp/routers/viral.py": "webapp/routers/viral.py",
    "webapp/routers/flywheel.py": "webapp/routers/flywheel.py",
    "webapp/routers/topics.py": "webapp/routers/topics.py",
    "webapp/routers/production.py": "webapp/routers/production.py",
    "webapp/routers/settings.py": "webapp/routers/settings.py",
    "webapp/routers/publish.py": "webapp/routers/publish.py",
    "webapp/routers/outputs.py": "webapp/routers/outputs.py",
    "webapp/routers/scheduler.py": "webapp/routers/scheduler.py",
    "webapp/static/index.html": "webapp/static/index.html",
    "webapp/static/app.js": "webapp/static/app.js",
    "webapp/static/style.css": "webapp/static/style.css",
    "webapp/static/themes/doraemon-mascot.svg": "webapp/static/themes/doraemon-mascot.svg",
    "webapp/static/themes/chanel-camellia.svg": "webapp/static/themes/chanel-camellia.svg",
    "webapp/static/themes/chanel-chain.svg": "webapp/static/themes/chanel-chain.svg",
    "webapp/static/themes/chanel-pearl.svg": "webapp/static/themes/chanel-pearl.svg",
    "webapp/static/themes/hermes-ribbon.svg": "webapp/static/themes/hermes-ribbon.svg",
    "webapp/static/themes/hermes-stitch.svg": "webapp/static/themes/hermes-stitch.svg",
    "webapp/static/themes/lv-bow.svg": "webapp/static/themes/lv-bow.svg",
    "webapp/static/themes/lv-chain.svg": "webapp/static/themes/lv-chain.svg",
    "webapp/static/themes/lv-lock.svg": "webapp/static/themes/lv-lock.svg",
    "webapp/static/themes/lv-monogram.svg": "webapp/static/themes/lv-monogram.svg",
    # 数据模板与偏好配置
    "data/templates.json": "data/templates.json",
    "data/topics/niches.json": "data/topics/niches.json",
    "data/templates/style_docs/personal-style-guide.template.md": "data/templates/style_docs/personal-style-guide.template.md",
    "data/templates/style_docs/tech-hands-on.template.md": "data/templates/style_docs/tech-hands-on.template.md",
    "data/templates/style_docs/business-deep-dive.template.md": "data/templates/style_docs/business-deep-dive.template.md",
    "data/templates/style_docs/xhs-lifestyle.template.md": "data/templates/style_docs/xhs-lifestyle.template.md",
    "data/templates/style_docs/career-growth.template.md": "data/templates/style_docs/career-growth.template.md",
    "materials/样例_热点雷达.md": "materials/样例_热点雷达.md",
    "materials/样例_选题推荐.md": "materials/样例_选题推荐.md",
    # 后端依赖脚本（不含 NAS/私有工具）
    "scripts/data_stats.py": "scripts/data_stats.py",
    "scripts/dashboard_analysis.py": "scripts/dashboard_analysis.py",
    "scripts/upgrade_agent_docs.py": "scripts/upgrade_agent_docs.py",
    "scripts/job_state.py": "scripts/job_state.py",
    "scripts/retention.py": "scripts/retention.py",
    "scripts/validate_materials_contract.py": "scripts/validate_materials_contract.py",
    "scripts/harsh_critic_score.py": "scripts/harsh_critic_score.py",
    "scripts/ai_flavor_check.py": "scripts/ai_flavor_check.py",
    "scripts/compliance_check.py": "scripts/compliance_check.py",
    "scripts/quick_check.py": "scripts/quick_check.py",
    "scripts/generate_score_report.py": "scripts/generate_score_report.py",
    "scripts/fetch_hot_topics.py": "scripts/fetch_hot_topics.py",
    "scripts/suggest_topics.py": "scripts/suggest_topics.py",
    "scripts/collect_platform_virals.py": "scripts/collect_platform_virals.py",
    "scripts/collect_viral_candidates.py": "scripts/collect_viral_candidates.py",
    "scripts/run_production.py": "scripts/run_production.py",
    "scripts/run_viral_analysis.py": "scripts/run_viral_analysis.py",
    "scripts/run_viral_breakdown_daily.py": "scripts/run_viral_breakdown_daily.py",
    "scripts/aggregate_viral_lessons.py": "scripts/aggregate_viral_lessons.py",
    "scripts/run_daily_pipeline.py": "scripts/run_daily_pipeline.py",
    "scripts/collect_post_stats.py": "scripts/collect_post_stats.py",
    "scripts/record_manual_publish.py": "scripts/record_manual_publish.py",
    "scripts/gzh_draft_api.py": "scripts/gzh_draft_api.py",
    "scripts/nas_config.py": "scripts/nas_config.py",
    "scripts/import_dashboard_xlsx.py": "scripts/import_dashboard_xlsx.py",
    "scripts/import_xhs_notes.py": "scripts/import_xhs_notes.py",
    "scripts/security_utils.py": "scripts/security_utils.py",
    "scripts/security/osv_audit.py": "scripts/security/osv_audit.py",
    "scripts/llm_engine.py": "scripts/llm_engine.py",
    "scripts/topic_feedback.py": "scripts/topic_feedback.py",
    "scripts/fetch_source_content.py": "scripts/fetch_source_content.py",
    "scripts/workbench_install.py": "scripts/workbench_install.py",
    # 授权基础设施（公钥随包，私钥永不上传）
    "scripts/license/__init__.py": "scripts/license/__init__.py",
    "scripts/license/license_lib.py": "scripts/license/license_lib.py",
    "scripts/license/token_mint.py": "scripts/license/token_mint.py",
    "scripts/license/install.py": "scripts/license/install.py",
    "scripts/license/license_gate.py": "scripts/license/license_gate.py",
    "scripts/license/public_key.pem": "scripts/license/public_key.pem",
    # 自产免费 skill（去AI味规则弹窗 + 爆款拆解 + 主题设计规范）
    "skills/anti-ai-flavor-skill/SKILL.md": "skills/anti-ai-flavor-skill/SKILL.md",
    "skills/viral-breakdown-skill/SKILL.md": "skills/viral-breakdown-skill/SKILL.md",
    "skills/theme-design-skill/SKILL.md": "skills/theme-design-skill/SKILL.md",
    "skills/theme-design-skill/references/palettes.json": "skills/theme-design-skill/references/palettes.json",
    "skills/theme-design-skill/scripts/theme_contrast_check.py": "skills/theme-design-skill/scripts/theme_contrast_check.py",
    # 通用 Agent SOP 与工作流（不含私有方法论/范文/个人风格）
    "release/templates/public_agents/orchestrator-总编.md": "agents/orchestrator-总编.md",
    "release/templates/public_agents/researcher-资深采编.md": "agents/researcher-资深采编.md",
    "release/templates/public_agents/xhs-editor-小红书主编.md": "agents/xhs-editor-小红书主编.md",
    "release/templates/public_agents/gzh-editor-公众号主编.md": "agents/gzh-editor-公众号主编.md",
    "release/templates/public_agents/video-director-短视频导演.md": "agents/video-director-短视频导演.md",
    "release/templates/public_agents/visual-director-美术总监.md": "agents/visual-director-美术总监.md",
    "release/templates/public_agents/reviewer-资深校对排版.md": "agents/reviewer-资深校对排版.md",
    "release/templates/public_agents/compliance-内容合规审核.md": "agents/compliance-内容合规审核.md",
    "release/templates/public_agents/distro-归档发布员.md": "agents/distro-归档发布员.md",
    "release/templates/public_workflows/自媒体运营工厂.md": "workflows/自媒体运营工厂.md",
    "release/templates/public_workflows/contract-schema.md": "workflows/contract-schema.md",
    # 单测
    "tests/test_ai_flavor_check.py": "tests/test_ai_flavor_check.py",
    "tests/test_compliance_check.py": "tests/test_compliance_check.py",
    "tests/test_license_system.py": "tests/test_license_system.py",
    "tests/test_security_utils.py": "tests/test_security_utils.py",
    "tests/test_webapp_api.py": "tests/test_webapp_api.py",
    "tests/test_style_docs_api.py": "tests/test_style_docs_api.py",
    "tests/test_theme_consistency.py": "tests/test_theme_consistency.py",
    "tests/test_hot_topics_sources.py": "tests/test_hot_topics_sources.py",
    "tests/test_suggest_topics.py": "tests/test_suggest_topics.py",
    "tests/test_topic_feedback.py": "tests/test_topic_feedback.py",
    "tests/test_fetch_source_content.py": "tests/test_fetch_source_content.py",
    # demo 数据生成器
    "release/templates/demo/generate_demo.py": "demo/generate_demo.py",
}

# 空目录脚手架（git 不跟踪空目录，用 .gitkeep 占位）
SCAFFOLD_DIRS = (
    "jobs", "outputs", "materials",
    "data/stats/dashboard", "data/flywheel/breakdowns",
    "data/flywheel", "data/production", "data/compliance/words",
)


def main():
    ap = argparse.ArgumentParser(description="公开仓库快照生成器")
    ap.add_argument("--no-git", action="store_true", help="不初始化 git")
    args = ap.parse_args()

    if os.path.isdir(TARGET):
        shutil.rmtree(TARGET)
    os.makedirs(TARGET, exist_ok=True)

    missing = []
    for src, dst in WHITELIST.items():
        s = os.path.join(ROOT, src)
        if not os.path.isfile(s):
            missing.append(src)
            continue
        d = os.path.join(TARGET, dst)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
    if missing:
        print("❌ 白名单文件缺失：")
        for m in missing:
            print(f"   - {m}")
        return 1

    # 数据/产出目录脚手架（服务器按需读写，先占位）
    for rel in SCAFFOLD_DIRS:
        d = os.path.join(TARGET, rel)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, ".gitkeep"), "w", encoding="utf-8") as f:
            f.write("")
    feedback = os.path.join(TARGET, "data", "flywheel", "pipeline_feedback.md")
    if not os.path.exists(feedback):
        with open(feedback, "w", encoding="utf-8") as f:
            f.write("（数据飞轮反哺指令包：重新生成后写入）\n")
    os.chmod(os.path.join(TARGET, "start.sh"), 0o755)

    # 生成 demo 数据
    demo_script = os.path.join(TARGET, "demo", "generate_demo.py")
    subprocess.run([sys.executable, demo_script], cwd=TARGET, check=True)

    # 生成 .gitignore 额外加固（防后续误提交真实数据）
    _append_gitignore(TARGET)

    if not args.no_git:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=TARGET, check=True)
        subprocess.run(["git", "add", "-A"], cwd=TARGET, check=True)
        subprocess.run(
            ["git", "-c", "user.name=SelfMedia Ops", "-c", "user.email=selfmedia-ops@users.noreply.github.com",
             "commit", "-q", "-m", "feat: 自媒体运营工厂（全功能工作台 + 质检授权体系 + 高级主题）"],
            cwd=TARGET, check=True,
        )

    print(f"✅ 公开仓库快照已生成：{TARGET}")
    print("下一步：")
    print("  1) python3 scripts/security/check_public_repo.py --repo release/selfmedia-ops-center")
    print("  2) gh auth login 后创建仓库并推送（当前 gh token 已失效）")
    return 0


def _append_gitignore(target):
    path = os.path.join(target, ".gitignore")
    with open(path, "a", encoding="utf-8") as f:
        f.write(
            "\n# 发布加固：防止误提交真实数据/凭据\n"
            ".env\n*.pem\n*.key\n*cookies*\n"
            "nas-n8n/\nskills/范文库/\n"
        )


if __name__ == "__main__":
    raise SystemExit(main())
