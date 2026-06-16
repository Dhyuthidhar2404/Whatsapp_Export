"""Tests for pull.adb guard + resolve_paths (T3.1 / issue #10)."""

import subprocess

import pytest

from wae import pull
from wae.errors import NoBackupError

DEFAULT_DB = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15"
DEFAULT_MEDIA = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media"
LEGACY_DB = "/storage/emulated/0/WhatsApp/Databases/msgstore.db.crypt15"


# --- adb() read-only guard ---


@pytest.mark.parametrize("args", [
    ["push", "a", "b"],
    ["install", "app.apk"],
    ["uninstall", "com.whatsapp"],
    ["shell", "rm", "-rf", "/sdcard/x"],
    ["shell", "mv", "a", "b"],
    ["shell", "/system/bin/rm", "x"],
    ["shell", "echo", "hi", ">", "/sdcard/f"],
])
def test_adb_rejects_write_operations(args):
    with pytest.raises(ValueError):
        pull.adb(args, "SERIAL")


def test_adb_allows_readonly_shell(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(pull.subprocess, "run", fake_run)
    proc = pull.adb(["shell", "ls", "/sdcard"], "SERIAL")
    assert proc.returncode == 0
    assert captured["cmd"][:3] == ["adb", "-s", "SERIAL"]


# --- resolve_paths ---


def _exists_only(*existing):
    existing = set(existing)
    return lambda path, serial: path in existing


def test_default_path_resolves(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_exists", _exists_only(DEFAULT_DB, DEFAULT_MEDIA))
    db, media = pull.resolve_paths(make_ctx(), "SERIAL")
    assert db == DEFAULT_DB
    assert media == DEFAULT_MEDIA


def test_oem_fallback_path_resolves(monkeypatch, make_ctx):
    # Only the legacy location exists.
    monkeypatch.setattr(pull, "_remote_exists", _exists_only(LEGACY_DB))
    db, media = pull.resolve_paths(make_ctx(), "SERIAL")
    assert db == LEGACY_DB
    # media derived from the same base when no media dir probe matched
    assert media == "/storage/emulated/0/WhatsApp/Media"


def test_db_and_media_overrides_honored(monkeypatch, make_ctx):
    # Overrides mean we should never probe.
    def boom(*a, **k):
        raise AssertionError("should not probe when overrides are set")

    monkeypatch.setattr(pull, "_remote_exists", boom)
    ctx = make_ctx(db_path="/custom/db.crypt15", media_path="/custom/Media")
    db, media = pull.resolve_paths(ctx, "SERIAL")
    assert db == "/custom/db.crypt15"
    assert media == "/custom/Media"


def test_business_package_path_resolves(monkeypatch, make_ctx):
    w4b_db = "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp/Databases/msgstore.db.crypt15"
    monkeypatch.setattr(pull, "_remote_exists", _exists_only(w4b_db))
    db, _ = pull.resolve_paths(make_ctx(package="com.whatsapp.w4b"), "SERIAL")
    assert db == w4b_db


def test_no_backup_found_raises(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_exists", lambda path, serial: False)
    with pytest.raises(NoBackupError) as e:
        pull.resolve_paths(make_ctx(), "SERIAL")
    assert e.value.exit_code == 3
    assert "Back Up" in str(e.value)
