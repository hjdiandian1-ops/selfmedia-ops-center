# -*- coding: utf-8 -*-
"""授权体系单测：签名/验签、篡改、过期、设备绑定、tier 门禁、免费额度、owner 模式。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "license"))
import license_lib as LL  # noqa: E402
import license_gate as LG  # noqa: E402
import token_mint as TM  # noqa: E402


@pytest.fixture()
def license_env(tmp_path, monkeypatch):
    """在临时目录生成密钥对，并隔离授权文件路径。"""
    priv = tmp_path / "license_private.pem"
    pub = tmp_path / "public_key.pem"
    monkeypatch.setattr(LL, "LICENSE_DIR", str(tmp_path))
    monkeypatch.setattr(LL, "PRIVATE_KEY_FILE", str(priv))
    monkeypatch.setattr(LL, "PUBLIC_KEY_FILE", str(pub))
    monkeypatch.setattr(TM, "ALL_FEATURES", TM.ALL_FEATURES)
    LL.generate_keypair()
    skills = tmp_path / "skills"
    skills.mkdir()
    monkeypatch.setattr(LG, "SKILLS_DIR", str(skills))
    monkeypatch.setattr(LG, "LICENSE_FILE", str(skills / "license.json"))
    monkeypatch.setattr(LG, "QUOTA_FILE", str(skills / "quota.json"))
    monkeypatch.setattr(LL, "device_fingerprint", lambda: "fp_test_device")
    return tmp_path


def _write_license(token, mode="token"):
    with open(LG.LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump({"mode": mode, "token": token}, f, ensure_ascii=False)


def test_keygen_and_verify_roundtrip(license_env):
    token = TM.mint("order-001", "pro", "2030-01-01", "fp_test_device")
    payload = LL.verify_token(token)
    assert payload["uid"] == "order-001"
    assert payload["tier"] == "pro"
    assert payload["bind"] == "fp_test_device"
    assert payload["exp"] == "2030-01-01"


def test_tampered_token_rejected(license_env):
    token = TM.mint("order-002", "pro", "2030-01-01", "fp_test_device")
    head, sig = token.split(".", 1)
    tampered = head[:-2] + ("AA" if not head.endswith("AA") else "BB") + "." + sig
    assert LL.verify_token(tampered) is None


def test_expired_token_denied(license_env):
    token = TM.mint("order-003", "pro", "2020-01-01", "fp_test_device")
    _write_license(token)
    ok, reason, detail = LG.check_feature("production")
    assert not ok
    assert "到期" in reason


def test_bind_mismatch_denied(license_env):
    token = TM.mint("order-004", "pro", "2030-01-01", "fp_other_device")
    _write_license(token)
    ok, reason, detail = LG.check_feature("production")
    assert not ok
    assert "绑定" in reason or "设备" in reason


def test_free_feature_without_license_allowed(license_env):
    ok, reason, detail = LG.check_feature("topics")
    assert ok
    assert detail["mode"] == "free"


def test_pro_feature_without_license_denied(license_env):
    ok, reason, detail = LG.check_feature("production")
    assert not ok
    assert "Pro" in reason


def test_quota_three_per_month(license_env, monkeypatch):
    months = iter(["2026-08"] * 8 + ["2026-09"] * 3)
    monkeypatch.setattr(LG, "_current_month", lambda: next(months))
    for i in range(3):
        ok, _, _ = LG.check_feature("viral_breakdown", consume=True)
        assert ok, f"第 {i + 1} 次应放行"
    ok, reason, detail = LG.check_feature("viral_breakdown", consume=True)
    assert not ok
    assert "额度" in reason
    # 跨月重置
    ok, _, detail = LG.check_feature("viral_breakdown", consume=True)
    assert ok
    assert detail["mode"] == "free"


def test_pro_token_unlimited_breakdown(license_env):
    token = TM.mint("order-005", "pro", "2030-01-01", "fp_test_device")
    _write_license(token)
    for _ in range(5):  # 超过免费额度仍放行
        ok, reason, detail = LG.check_feature("viral_breakdown", consume=True)
        assert ok
        assert detail["mode"] == "pro"


def test_owner_mode_allows_all(license_env):
    with open(LG.LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump({"mode": "owner"}, f, ensure_ascii=False)
    ok, _, detail = LG.check_feature("production")
    assert ok
    assert detail["mode"] == "owner"


def test_pro_any_requires_license(license_env):
    ok, reason, _ = LG.check_feature("pro_any")
    assert not ok
    token = TM.mint("order-006", "pro", "2030-01-01", "fp_test_device")
    _write_license(token)
    ok, _, _ = LG.check_feature("pro_any")
    assert ok
