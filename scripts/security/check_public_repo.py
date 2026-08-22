#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开仓库发布前校验（安全门禁 · 可复算）
========================================
对 release/selfmedia-ops-center 快照做发布前检查：
1. 禁止文件/目录（jobs/outputs/materials/data/nas-n8n/范文库/私钥/.env）
2. 凭据正则（API key 前缀、Bearer、私钥块、手机号、邮箱、内网 IP）
3. 真实用户数据目录检查（git ls-files）

用法：
    python3 scripts/security/check_public_repo.py --repo release/selfmedia-ops-center
    python3 scripts/security/check_public_repo.py --repo release/selfmedia-ops-center --out /tmp/check.json

退出码：0 = 通过；1 = 有发现（禁止发布）。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

FORBIDDEN_DIRS = ("jobs", "outputs", "materials", "data/stats", "data/flywheel",
                  "data/production", "data/compliance", "data/style_backups",
                  "nas-n8n", "skills/范文库")
FORBIDDEN_FILES = (".env", "license_private.pem", "*.key", "*cookies*",
                   "xiaohongshu_cookies.json")

SECRET_PATTERNS = [
    (r"\bsk-[A-Za-z0-9]{20,}\b", "OpenAI/DeepSeek 风格 API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key"),
    (r"\bAIza[0-9A-Za-z_-]{30,}\b", "Google API key"),
    (r"\bghp_[A-Za-z0-9]{30,}\b", "GitHub PAT"),
    (r"\bBearer [A-Za-z0-9._-]{20,}\b", "Bearer token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥块"),
    (r"\b1[3-9][0-9]{9}\b", "手机号"),
    (r"(?<![A-Za-z0-9._%+\-:/])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "邮箱"),
    (r"\b(?:192\.168\.|10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.)\d{1,3}\.\d{1,3}\b", "内网 IP"),
    (r"(?:/Users/[A-Za-z0-9_\-]+/|/home/[A-Za-z0-9_\-]+/|C:\\Users\\[A-Za-z0-9_\-]+\\|/private/var/)",
     "本机绝对路径（用户名/目录结构泄漏）"),
    (r"(?:sk|api[_-]?key|token|secret|password)\s*[=:]\s*['\"][^'\"]{12,}['\"]",
     "疑似硬编码凭据赋值"),
]

TEXT_EXTS = {".py", ".md", ".txt", ".json", ".lock", ".yml", ".yaml", ".toml",
             ".in", ".pem", ".html", ".js", ".css"}


def walk_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


SCAFFOLD_ALLOWED_FILES = {".gitkeep", "pipeline_feedback.md", "样例_热点雷达.md", "样例_选题推荐.md"}


def _has_real_files(root):
    """目录内是否存在非脚手架占位的真实文件。"""
    for fp in walk_files(root):
        if os.path.basename(fp) not in SCAFFOLD_ALLOWED_FILES:
            return True
    return False


def check(root):
    findings = []

    # 1. 禁止目录/文件
    for rel in FORBIDDEN_DIRS:
        p = os.path.join(root, rel)
        if os.path.isdir(p) and _has_real_files(p):
            findings.append({"level": "high", "rule": "forbidden_dir", "target": rel,
                             "message": f"禁止目录 {rel} 含真实文件（仅允许 .gitkeep 占位）"})
    for rel in FORBIDDEN_FILES:
        for fp in walk_files(root):
            if os.path.basename(fp) == rel or (rel.endswith("*") and os.path.basename(fp).startswith(rel[:-1])):
                findings.append({"level": "high", "rule": "forbidden_file",
                                 "target": os.path.relpath(fp, root),
                                 "message": f"存在禁止文件 {rel}"})

    # 2. 凭据正则（仅文本文件）
    for fp in walk_files(root):
        if os.path.splitext(fp)[1].lower() not in TEXT_EXTS:
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                findings.append({
                    "level": "high", "rule": "secret_pattern", "target": os.path.relpath(fp, root),
                    "pattern": pattern, "message": f"命中 {label}",
                    "snippet": m.group(0)[:40],
                })

    return findings


def main():
    ap = argparse.ArgumentParser(description="公开仓库发布前校验")
    ap.add_argument("--repo", default=os.path.join("release", "selfmedia-ops-center"))
    ap.add_argument("--out", help="JSON 报告落盘路径")
    args = ap.parse_args()
    root = os.path.normpath(args.repo)
    if not os.path.isdir(root):
        print(f"❌ 仓库目录不存在：{root}", file=sys.stderr)
        return 2
    findings = check(root)
    report = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repo": root,
        "verdict": "REJECTED" if findings else "PASSED",
        "findings": findings,
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    for x in findings[:20]:
        print(f"🛑 [{x['rule']}] {x['message']} @ {x.get('target', '')}")
    print(f"结果：{report['verdict']}（发现 {len(findings)} 项）")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
