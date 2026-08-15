#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖漏洞审计（OSV API 直查）
============================
pip-audit 在部分受管 Python 环境（如 .workbuddy）会因 ensurepip 异常失败，
本脚本直接用 OSV API 按 requirements.lock 的固定版本批量查询漏洞，输出 JSON。

用法：
    python3 scripts/security/osv_audit.py                    # 审计 requirements.lock
    python3 scripts/security/osv_audit.py -r requirements.lock -o /tmp/osv.json

退出码：0 = 无已知漏洞；1 = 存在漏洞或查询失败。
"""
import argparse
import json
import re
import sys
import urllib.request

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
PKG_RE = re.compile(r"^([A-Za-z0-9._-]+)==([A-Za-z0-9._+!-]+)$")


def parse_lock(path):
    """解析 pip-compile 锁文件中的 name==version 行。"""
    pkgs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = PKG_RE.match(line)
            if m:
                pkgs.append({"name": m.group(1), "version": m.group(2)})
    return pkgs


def query_osv(pkgs):
    """按批查询 OSV，返回 {index: [vuln_ids]}。"""
    queries = [{"package": {"name": p["name"], "ecosystem": "PyPI"},
                "version": p["version"]} for p in pkgs]
    req = urllib.request.Request(
        OSV_BATCH_URL,
        data=json.dumps({"queries": queries}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "selfmedia-ops-security/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected  # 固定官方 OSV API 常量地址
        data = json.loads(resp.read().decode("utf-8"))
    out = {}
    for i, item in enumerate(data.get("results", [])):
        vulns = item.get("vulns") or []
        if vulns:
            out[i] = [v["id"] for v in vulns]
    return out


def main():
    ap = argparse.ArgumentParser(description="OSV 依赖漏洞审计")
    ap.add_argument("-r", "--requirements", default="requirements.lock")
    ap.add_argument("-o", "--out", help="JSON 报告落盘路径")
    args = ap.parse_args()
    pkgs = parse_lock(args.requirements)
    if not pkgs:
        print("❌ 未从锁文件解析到依赖", file=sys.stderr)
        return 2
    try:
        hits = query_osv(pkgs)
    except Exception as e:
        print(f"❌ OSV 查询失败: {e}", file=sys.stderr)
        return 1
    report = {
        "tool": "osv_audit.py",
        "requirements": args.requirements,
        "checked": len(pkgs),
        "vulnerable": [],
        "raw_hits": hits,
    }
    for i in sorted(hits):
        report["vulnerable"].append({
            "package": pkgs[i]["name"],
            "version": pkgs[i]["version"],
            "vuln_ids": hits[i],
        })
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if report["vulnerable"]:
        print("🛑 发现已知漏洞：")
        for v in report["vulnerable"]:
            print(f"  - {v['package']}=={v['version']}: {', '.join(v['vuln_ids'])}")
        return 1
    print(f"✅ 已检查 {len(pkgs)} 个依赖，无已知漏洞")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
