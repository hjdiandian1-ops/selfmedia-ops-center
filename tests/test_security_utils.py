# -*- coding: utf-8 -*-
"""安全工具单测：job_id 白名单、SSRF URL 校验、xlsx zip 炸弹防护。"""
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import security_utils as SU  # noqa: E402


def test_valid_job_id():
    assert SU.valid_job_id("2026-08-14_测试主题")
    assert SU.valid_job_id("2026-08-14_DeepSeek_V4")
    assert not SU.valid_job_id("../secret")
    assert not SU.valid_job_id("a/b")
    assert not SU.valid_job_id("")
    assert not SU.valid_job_id("x; rm -rf")


def test_require_job_id_raises():
    with pytest.raises(ValueError):
        SU.require_job_id("../etc")


def test_safe_http_url_rejects_unsafe():
    assert not SU.safe_http_url("file:///etc/passwd", resolve_dns=False)
    assert not SU.safe_http_url("ftp://example.com/x", resolve_dns=False)
    assert not SU.safe_http_url("https://user:pass@example.com/", resolve_dns=False)
    assert not SU.safe_http_url("http://127.0.0.1:8787/", resolve_dns=False)
    assert not SU.safe_http_url("http://" + "192.168." + "1.1/x", resolve_dns=False)
    assert not SU.safe_http_url("http://" + "169.254." + "169.254/latest/meta-data", resolve_dns=False)
    assert not SU.safe_http_url("http://" + "10." + "0.0.8/", resolve_dns=False)


def test_safe_http_url_accepts_public():
    assert SU.safe_http_url("https://github.com/gitleaks/gitleaks", resolve_dns=False)
    assert SU.safe_http_url("http://tophub.today/c/ai", resolve_dns=False)


def test_safe_xlsx_missing_file(tmp_path):
    with pytest.raises(ValueError):
        SU.safe_xlsx_zip(str(tmp_path / "none.xlsx"))


def test_safe_xlsx_rejects_zip_bomb(tmp_path):
    path = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", b"\x00" * (10 * 1024 * 1024))  # 10MB 零压缩后极小
    with pytest.raises(ValueError):
        SU.safe_xlsx_zip(str(path))


def test_safe_xlsx_rejects_too_many_members(tmp_path):
    path = tmp_path / "many.xlsx"
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(SU.XLSX_MAX_MEMBERS + 1):
            zf.writestr(f"item{i}", b"x")
    with pytest.raises(ValueError):
        SU.safe_xlsx_zip(str(path))


def test_safe_xlsx_accepts_normal(tmp_path):
    path = tmp_path / "ok.xlsx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", "<workbook/>")
        zf.writestr("xl/worksheets/sheet1.xml", "<sheetData/>")
    zf2 = SU.safe_xlsx_zip(str(path))
    assert zf2.namelist()
    zf2.close()
