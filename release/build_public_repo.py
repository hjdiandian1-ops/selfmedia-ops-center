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
    "release/templates/CONTRIBUTING.md": "CONTRIBUTING.md",
    "release/templates/SECURITY_CHECKLIST.md": "SECURITY_CHECKLIST.md",
    "docs/发布与后台配置.md": "docs/发布与后台配置.md",
    "release/templates/.gitignore": ".gitignore",
    "release/templates/.env.example": ".env.example",
    "release/templates/start.sh": "start.sh",
    "release/templates/.github/workflows/security.yml": ".github/workflows/security.yml",
    "release/templates/.github/workflows/codeql.yml": ".github/workflows/codeql.yml",
    # 运行时依赖
    "requirements.in": "requirements.in",
    "requirements.lock": "requirements.lock",
    "pyproject.toml": "pyproject.toml",
    # 工作台（免费版核心 UI + 后端）
    "webapp/server.py": "webapp/server.py",
    "webapp/static/index.html": "webapp/static/index.html",
    "webapp/static/app.js": "webapp/static/app.js",
    "webapp/static/style.css": "webapp/static/style.css",
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
    "scripts/workbench_install.py": "scripts/workbench_install.py",
    # 授权基础设施（公钥随包，私钥永不上传）
    "scripts/license/__init__.py": "scripts/license/__init__.py",
    "scripts/license/license_lib.py": "scripts/license/license_lib.py",
    "scripts/license/token_mint.py": "scripts/license/token_mint.py",
    "scripts/license/install.py": "scripts/license/install.py",
    "scripts/license/license_gate.py": "scripts/license/license_gate.py",
    "scripts/license/public_key.pem": "scripts/license/public_key.pem",
    # 自产免费 skill（去AI味规则弹窗 + 爆款拆解）
    "skills/anti-ai-flavor-skill/SKILL.md": "skills/anti-ai-flavor-skill/SKILL.md",
    "skills/viral-breakdown-skill/SKILL.md": "skills/viral-breakdown-skill/SKILL.md",
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
            ["git", "-c", "user.name=小吴聊", "-c", "user.email=xiaowuliao@users.noreply.github.com",
             "commit", "-q", "-m", "feat: 自媒体运营工厂开源核心（质检+授权基础设施）"],
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
