#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卖家发码工具（仅卖家本机使用，私钥不出本机）
============================================
用法：
    python3 scripts/license/token_mint.py --keygen
    python3 scripts/license/token_mint.py --mint --uid 订单号 --tier pro \
        --expiry 2027-12-31 --bind <设备指纹> --out /tmp/token.txt
    python3 scripts/license/token_mint.py --verify --token <token> [--fingerprint <指纹>]

说明：
- --bind 传入买家 `install.py --show-fingerprint` 输出的设备指纹，实现设备绑定。
- 不传 --bind 为未绑定 token（仅 v2 在线激活流程使用，v1 一律绑定后发货）。
- owner 档：卖家自用/内部机器，跳过指纹校验（--tier owner 时忽略 --bind）。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_lib as LL  # noqa: E402

TIERS = ("free", "pro", "owner")
ALL_FEATURES = (
    "topics", "layout", "viral_breakdown",
    "production", "flywheel", "viral_top5", "compliance_full",
    "anti_ai_full", "agent_upgrade", "gzh_push", "unlimited",
)


def mint(uid, tier, expiry, bind="", features=None):
    if tier not in TIERS:
        raise ValueError(f"tier 必须是 {TIERS}")
    if tier != "owner" and not bind:
        raise ValueError("v1 流程必须 --bind 设备指纹（owner 档除外）")
    features = list(features or (ALL_FEATURES if tier == "pro" else []))
    payload = {
        "ver": LL.TOKEN_VERSION,
        "uid": str(uid)[:80],
        "tier": tier,
        "exp": expiry or (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
        "bind": bind or "",
        "features": features,
        "iat": LL.iso_today(),
    }
    return LL.sign_payload(payload)


def main():
    ap = argparse.ArgumentParser(description="卖家发码工具（Ed25519 签名 token）")
    ap.add_argument("--keygen", action="store_true", help="首次生成密钥对")
    ap.add_argument("--mint", action="store_true", help="签发 token")
    ap.add_argument("--uid", default="")
    ap.add_argument("--tier", default="pro", choices=TIERS)
    ap.add_argument("--expiry", default="")
    ap.add_argument("--bind", default="")
    ap.add_argument("--features", default="", help="逗号分隔；默认 pro=全部功能")
    ap.add_argument("--out", default="", help="token 落盘路径（不传则打印 stdout）")
    ap.add_argument("--verify", dest="verify", metavar="TOKEN", default="")
    ap.add_argument("--fingerprint", default="")
    args = ap.parse_args()

    if args.keygen:
        priv, pub = LL.generate_keypair()
        print(f"✅ 密钥已生成：\n  私钥 {priv}（严禁外传）\n  公钥 {pub}（随付费包分发）")
        return 0
    if args.verify:
        payload = LL.verify_token(args.verify)
        if payload is None:
            print("❌ 验签失败或 token 已损坏")
            return 1
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.fingerprint and payload.get("bind") and payload["bind"] != args.fingerprint:
            print("❌ 指纹不匹配")
            return 1
        print("✅ 验签通过")
        return 0
    if args.mint:
        token = mint(
            args.uid or "test",
            args.tier,
            args.expiry,
            args.bind,
            [x.strip() for x in args.features.split(",") if x.strip()],
        )
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(token + "\n")
            print(f"✅ token 已落盘：{args.out}")
        else:
            print(token)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
