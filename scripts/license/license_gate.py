#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行时授权门禁（付费包内置，买家机器执行）
==========================================
用法：
    python3 scripts/license/license_gate.py check --feature production
    python3 scripts/license/license_gate.py check --feature viral_breakdown
    python3 scripts/license/license_gate.py status
    python3 scripts/license/license_gate.py quota --feature viral_breakdown --limit 3 --consume

判定规则：
- 本地授权文件 ~/.xiaowuliao-skills/license.json 存在且 mode=owner → 全部放行。
- 无授权文件：免费功能放行（viral_breakdown 按月度额度），Pro 功能拒绝并提示升级。
- 有 token：验签 + 到期 + 指纹比对 + tier/features 判定，全部通过才放行。

退出码：0 = 放行；1 = 拒绝（输出原因与升级链接）；2 = 参数错误。
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_lib as LL  # noqa: E402

SKILLS_DIR = os.path.expanduser("~/.xiaowuliao-skills")
LICENSE_FILE = os.path.join(SKILLS_DIR, "license.json")
QUOTA_FILE = os.path.join(SKILLS_DIR, "quota.json")
UPGRADE_URL = "https://mianbaoduo.com"  # 商品链接，后续可替换

FREE_FEATURES = {"topics", "layout", "viral_breakdown"}
QUOTA_FEATURES = {"viral_breakdown": 3}  # 免费额度：爆款拆解 3 次/月


def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_license():
    return _load(LICENSE_FILE, None)


def _current_month():
    return datetime.now().strftime("%Y-%m")


def quota_left(feature, limit):
    q = _load(QUOTA_FILE, {}) or {}
    entry = q.get(feature) or {}
    if entry.get("month") != _current_month():
        return limit
    return max(0, limit - int(entry.get("count", 0)))


def consume_quota(feature, limit):
    q = _load(QUOTA_FILE, {}) or {}
    entry = q.get(feature) or {}
    if entry.get("month") != _current_month():
        entry = {"month": _current_month(), "count": 0}
    entry["count"] = int(entry.get("count", 0)) + 1
    q[feature] = entry
    _save(QUOTA_FILE, q)


def check_feature(feature, consume=False, quiet=False):
    """返回 (allowed: bool, reason: str, detail: dict)。不抛异常。"""
    lic = _read_license()
    if lic and lic.get("mode") == "owner":
        return True, "owner 模式（卖家自用）", {"mode": "owner"}

    if lic is None:
        if feature not in FREE_FEATURES:
            return False, f"「{feature}」是 Pro 功能，需要订阅授权（{UPGRADE_URL}）", {"mode": "none"}
        # 免费功能：走月度额度
        limit = QUOTA_FEATURES.get(feature)
        if limit is not None:
            left = quota_left(feature, limit)
            if left <= 0:
                return False, f"免费额度已用完（{limit} 次/月），升级 Pro 可无限使用（{UPGRADE_URL}）", {"mode": "free", "left": left}
            if consume:
                consume_quota(feature, limit)
            return True, f"免费功能放行（本月剩余 {max(0, left - 1 if consume else left)} 次）", {"mode": "free", "left": left}
        return True, "免费功能放行", {"mode": "free"}

    if feature == "pro_any" and lic.get("mode") == "free":
        return False, "需要 Pro 订阅授权（%s）" % UPGRADE_URL, {"mode": "free"}
    token = lic.get("token", "")
    payload = LL.verify_token(token)
    if payload is None:
        return False, "授权 token 验签失败，请重新安装（联系客服换绑）", {"mode": "bad_token"}
    if payload.get("tier") == "owner":
        return True, "owner token 放行", {"mode": "owner"}
    exp = payload.get("exp", "")
    if exp and exp < LL.iso_today():
        return False, f"授权已于 {exp} 到期，请续费（{UPGRADE_URL}）", {"mode": "expired"}
    bind = payload.get("bind", "")
    if bind and bind != LL.device_fingerprint():
        return False, "授权已绑定其他设备，请提供设备码联系客服换绑", {"mode": "bind_mismatch"}
    if payload.get("tier") != "pro":
        return False, "当前授权不是 Pro 档", {"mode": "tier"}
    feats = payload.get("features") or []
    if feats and feature not in feats and feature != "pro_any":
        return False, f"当前授权不含「{feature}」功能", {"mode": "feature"}
    if feature == "viral_breakdown":
        return True, "Pro 用户无限拆解", {"mode": "pro"}
    return True, "Pro 功能放行", {"mode": "pro"}


def main():
    ap = argparse.ArgumentParser(description="运行时授权门禁")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("--feature", required=True)
    p.add_argument("--consume", action="store_true", help="消耗一次免费额度")
    p.set_defaults(fn="check")
    sub.add_parser("status").set_defaults(fn="status")
    p = sub.add_parser("quota")
    p.add_argument("--feature", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--consume", action="store_true")
    p.set_defaults(fn="quota")
    args = ap.parse_args()

    if args.fn == "check":
        ok, reason, detail = check_feature(args.feature, consume=args.consume)
        print(json.dumps({"ok": ok, "feature": args.feature, "reason": reason, **detail},
                         ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if args.fn == "quota":
        limit = args.limit or QUOTA_FEATURES.get(args.feature)
        if limit is None:
            print(json.dumps({"ok": False, "reason": "该功能无免费额度配置"}))
            return 1
        left = quota_left(args.feature, limit)
        if args.consume:
            if left <= 0:
                print(json.dumps({"ok": False, "left": left, "reason": "额度已用完"}))
                return 1
            consume_quota(args.feature, limit)
            left -= 1
        print(json.dumps({"ok": True, "feature": args.feature, "limit": limit, "left": left}))
        return 0
    if args.fn == "status":
        lic = _read_license()
        print(json.dumps({
            "license_file": LICENSE_FILE,
            "installed": bool(lic),
            "mode": (lic or {}).get("mode", "none"),
            "fingerprint": LL.device_fingerprint(),
        }, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
