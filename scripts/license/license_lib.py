#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
授权签名核心库（Ed25519）
=========================
token 结构：base64url(payload_json) + "." + base64url(signature)
payload = {ver, uid, tier, exp, bind, features[], iat}

- tier: free / pro / owner
- bind: 设备指纹（可空=未绑定，安装时按卖家签发为准）
- features: 允许的功能清单（pro 未列明时视为全部 Pro 功能）

私钥只存在于本机 ~/.xiaowuliao-license/，公钥随付费包分发（public_key.pem）。
"""
import base64
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

LICENSE_DIR = os.path.expanduser("~/.xiaowuliao-license")
PRIVATE_KEY_FILE = os.path.join(LICENSE_DIR, "license_private.pem")
PUBLIC_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public_key.pem")
TOKEN_VERSION = 1


def ensure_license_dir():
    os.makedirs(LICENSE_DIR, mode=0o700, exist_ok=True)


def generate_keypair():
    """生成 Ed25519 密钥对；私钥写本机，公钥写 scripts/license/public_key.pem。"""
    ensure_license_dir()
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(PRIVATE_KEY_FILE, "wb") as f:
        os.chmod(PRIVATE_KEY_FILE, 0o600)
        f.write(private_bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_bytes)
    return PRIVATE_KEY_FILE, PUBLIC_KEY_FILE


def load_private_key():
    if not os.path.isfile(PRIVATE_KEY_FILE):
        raise FileNotFoundError(f"缺少私钥：{PRIVATE_KEY_FILE}（先运行 token_mint.py --keygen）")
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key(path=None):
    path = path or PUBLIC_KEY_FILE
    if not os.path.isfile(path):
        raise FileNotFoundError(f"缺少公钥：{path}")
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign_payload(payload, private_key=None):
    private_key = private_key or load_private_key()
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = private_key.sign(raw)
    return f"{_b64(raw)}.{_b64(sig)}"


def verify_token(token, public_key=None):
    """验签并返回 payload；任何异常（格式/签名/载荷）返回 None。"""
    try:
        public_key = public_key or load_public_key()
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _unb64(raw_b64)
        sig = _unb64(sig_b64)
        public_key.verify(sig, raw)
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("ver") != TOKEN_VERSION:
            return None
        return payload
    except Exception:
        return None


def device_fingerprint():
    """设备指纹：macOS IOPlatformUUID 优先，降级 uuid.getnode()+hostname 哈希。"""
    if os.path.isdir("/System/Library/CoreServices"):
        try:
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=10,
            )
            for line in out.stdout.splitlines():
                line = line.strip()
                if '"IOPlatformUUID"' in line:
                    val = line.split("=", 1)[1].strip().strip('"')
                    if val:
                        return "mac_" + hashlib.sha256(val.encode("utf-8")).hexdigest()[:24]
        except Exception:
            pass
    raw = f"{uuid.getnode()}|{os.uname().nodename}".encode("utf-8")
    return "dev_" + hashlib.sha256(raw, usedforsecurity=False).hexdigest()[:24]


def iso_today():
    return datetime.now().strftime("%Y-%m-%d")
