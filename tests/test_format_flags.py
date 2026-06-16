"""Tests for format-flag passthrough json/txt/html (T4.2 / issue #15)."""

import subprocess
from pathlib import Path

import pytest

from wae import decrypt_export

KEY = "ab" * 32


# --- command construction (unit) ---


def test_html_default_has_no_format_flag(make_ctx, tmp_path):
    ctx = make_ctx(fmt="html", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert "-j" not in cmd and "--txt" not in cmd
    assert "--no-html" not in cmd


def test_json_flag_passthrough(make_ctx, tmp_path):
    ctx = make_ctx(fmt="json", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert "-j" in cmd and "--no-html" in cmd


def test_txt_flag_passthrough(make_ctx, tmp_path):
    ctx = make_ctx(fmt="txt", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert "--txt" in cmd and "--no-html" in cmd


def test_media_flag_included_when_media_dir_present(make_ctx, tmp_path):
    ctx = make_ctx(fmt="html", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(
        Path("/x/db.crypt15"), Path("/x/Media"), KEY, ctx, tmp_path / "e"
    )
    assert "-m" in cmd and "/x/Media" in cmd


# --- verification respects format (unit, mocked) ---


def test_json_verification_requires_result_json(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(fmt="json", tmp_dir=tmp_path / "tmp")
    export_dir = ctx.tmp_dir / "export"

    def fake_run(cmd, **kw):
        (export_dir / "result.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    out = decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    assert (out / "result.json").exists()
    assert not (out / "index.html").exists()  # no html synthesized for json


# --- integration with the real exporter ---


@pytest.fixture
def _real_export():
    pytest.importorskip("Crypto")
    pytest.importorskip("javaobj")
    pytest.importorskip("Whatsapp_Chat_Exporter")
    from tests.fixtures.make_crypt15_fixture import FIXTURE_PATH, TEST_KEY_HEX

    return FIXTURE_PATH, TEST_KEY_HEX


def test_integration_json_output(_real_export, make_ctx, tmp_path):
    fixture, key = _real_export
    ctx = make_ctx(fmt="json", tmp_dir=tmp_path / "tmp", include_media=False)
    out = decrypt_export.export_chats(fixture, None, key, ctx)
    assert (out / "result.json").exists()


def test_integration_txt_output(_real_export, make_ctx, tmp_path):
    fixture, key = _real_export
    ctx = make_ctx(fmt="txt", tmp_dir=tmp_path / "tmp", include_media=False)
    out = decrypt_export.export_chats(fixture, None, key, ctx)
    assert any(out.glob("*.txt"))


def test_integration_html_default(_real_export, make_ctx, tmp_path):
    fixture, key = _real_export
    ctx = make_ctx(fmt="html", tmp_dir=tmp_path / "tmp", include_media=False)
    out = decrypt_export.export_chats(fixture, None, key, ctx)
    assert (out / "index.html").exists()
