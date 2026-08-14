#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
付费包安装器（买家机器执行）
============================
用法：
    python3 scripts/license/install.py --show-fingerprint   # 给卖家发设备码
    python3 scripts/license/install.py --bind-token <token> # 粘贴卖家发的绑定 token
    python3 scripts/license/install.py --owner              # 卖家自用机标记（不校验）
    python3 scripts/license/install.py --activate <token>   # v2 在线激活（预留接口）

授权文件写入 ~/.xiaowuliao-skills/license.json。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_lib as LL  # noqa: E402

SKILLS_DIR = os.path.expanduser("~/.xiaowuliao-skills")
LICENSE_FILE = os.path.join(SKILLS_DIR, "license.json")


def _save_license(data):
    os.makedirs(SKILLS_DIR, exist_ok=True)
    tmp = LICENSE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, LICENSE_FILE)


def main():
    ap = argparse.ArgumentParser(description="付费包安装器")
    ap.add_argument("--show-fingerprint", action="store_true")
    ap.add_argument("--bind-token", default="")
    ap.add_argument("--owner", action="store_true")
    ap.add_argument("--activate", default="", help="v2 在线激活（预留）")
    args = ap.parse_args()

    if args.show_fingerprint:
        print(LL.device_fingerprint())
        print("请把上面的设备码发给卖家，等待绑定 token 后运行 --bind-token 激活。")
        return 0
    if args.bind_token:
        payload = LL.verify_token(args.bind_token)
        if payload is None:
            print("❌ token 验签失败，请检查是否复制完整（或联系卖家重新签发）")
            return 1
        if payload.get("tier") != "owner" and payload.get("bind"):
            fp = LL.device_fingerprint()
            if payload["bind"] != fp:
                print("❌ token 绑定的是其他设备（本机指纹不匹配）。")
                print(f"   本机指纹：{fp}")
                print("   如刚换设备，请把新指纹发给卖家重签。")
                return 1
        _save_license({
            "mode": "token",
            "token": args.bind_token,
            "installed_at": LL.iso_today(),
        })
        print(f"✅ 授权激活成功（tier={payload.get('tier')}，到期 {payload.get('exp')}）")
        return 0
    if args.owner:
        _save_license({"mode": "owner", "installed_at": LL.iso_today()})
        print("✅ 已标记为 owner 模式（卖家自用机，全部功能放行）")
        return 0
    if args.activate:
        # v2 在线激活：预留接口，v1 未部署授权服务器
        print("ℹ️ 在线激活（v2）尚未部署，v1 请使用 --bind-token 手动绑定。")
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
