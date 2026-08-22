# -*- coding: utf-8 -*-
"""敏感数据残留门禁：本地跟踪文件与 release 快照均不得含凭据/内网地址。"""
import os
import re
import subprocess

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RELEASE = os.path.join(ROOT, "release", "selfmedia-ops-center")

# 高信号模式：真实密钥/令牌形态；文档示例（sk-xxx、your_key）不会命中
PATTERNS = [
    re.compile(r"\bNAS_PASS\s*=\s*['\"][^'\"]{6,}['\"]"),
    re.compile(r"\bGZH_APP_SECRET\s*=\s*['\"][^'\"]{6,}['\"]"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\bBearer [A-Za-z0-9._~+/=-]{30,}"),
    re.compile(r"\b(?:192\.168\.|10\.\d+\.\d+\.\d+)"),
]

# 允许的假阳性：SSRF 安全测试里的内网 IP、后台配置/安全审查文档里说明内网 IP 的示例
ALLOWLIST = {
    "tests/test_security_utils.py",
    "docs/发布与后台配置.md",
    "docs/安全审查报告.md",
    "nas-n8n/.env.example",
    "nas-n8n/README.md",
    "scripts/_archive/add_webhook_id.py",
    "scripts/_archive/execute_full_test.py",
}


def _scan_file(path, rel):
    hits = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for lineno, line in enumerate(f, 1):
                for pat in PATTERNS:
                    if pat.search(line):
                        hits.append((rel, lineno, pat.pattern))
                        break
    except OSError:
        pass
    return hits


def _is_allowed(rel: str, pattern: str) -> bool:
    if rel in ALLOWLIST:
        return True
    if rel.startswith("scripts/_archive/") or rel.startswith("nas-n8n/"):
        return True
    # 私有 NAS 运维脚本仅在内网 IP 模式下放行，真实凭据/Key 仍严格拦截
    if "192" in pattern and (rel.startswith("scripts/") or rel.startswith("docs/")):
        return True
    return False


def test_local_tracked_files_have_no_secrets():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True)
    files = [f for f in out.stdout.split("\0") if f]
    bad = []
    for rel in files:
        full = os.path.join(ROOT, rel)
        for r, n, p in _scan_file(full, rel):
            if not _is_allowed(r, p):
                bad.append((r, n, p))
    assert not bad, "发现敏感残留: " + "; ".join(f"{r}:{n} ({p})" for r, n, p in bad[:10])


def test_release_snapshot_has_no_secrets():
    if not os.path.isdir(RELEASE):
        return  # 未生成 release 快照时跳过
    bad = []
    for dirpath, dirnames, names in os.walk(RELEASE):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".pytest_cache")]
        for name in names:
            if name.endswith((".pyc", ".pyo", ".pyd", ".png", ".jpg", ".jpeg", ".ico")):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, RELEASE)
            for r, n, p in _scan_file(full, rel):
                if not _is_allowed(r, p):
                    bad.append((r, n, p))
    assert not bad, "release 快照发现敏感残留: " + "; ".join(f"{r}:{n} ({p})" for r, n, p in bad[:10])
