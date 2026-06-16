"""Tests for pull.pull_media (T3.3 / issue #12)."""

import logging
import subprocess
import types

import pytest

from wae import pull
from wae.errors import DeviceError

MEDIA_REMOTE = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media"


@pytest.fixture(autouse=True)
def _paths(monkeypatch):
    monkeypatch.setattr(pull, "resolve_paths", lambda ctx, serial: ("/db", MEDIA_REMOTE))


def test_no_media_returns_none(make_ctx):
    assert pull.pull_media(make_ctx(include_media=False), "S") is None


def test_default_pulls_media_tree(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_du", lambda r, s: None)

    def fake_pull_media(remote, local, serial):
        local.mkdir(parents=True, exist_ok=True)
        (local / "photo.jpg").write_bytes(b"x")
        return []

    monkeypatch.setattr(pull, "_adb_pull_media", fake_pull_media)
    out = pull.pull_media(make_ctx(), "S")
    assert out is not None and out.exists()
    assert (out / "photo.jpg").exists()


def test_insufficient_space_aborts_before_pulling(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_du", lambda r, s: 10**12)  # ~1 TB
    monkeypatch.setattr(
        pull.shutil, "disk_usage", lambda p: types.SimpleNamespace(total=0, used=0, free=10**6)
    )
    monkeypatch.setattr(pull, "_confirm_continue", lambda prompt: False)
    pulled = {"called": False}

    def should_not_pull(*a, **k):
        pulled["called"] = True
        return []

    monkeypatch.setattr(pull, "_adb_pull_media", should_not_pull)
    with pytest.raises(DeviceError):
        pull.pull_media(make_ctx(), "S")
    assert pulled["called"] is False


def test_insufficient_space_continue_when_user_accepts(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_du", lambda r, s: 10**12)
    monkeypatch.setattr(
        pull.shutil, "disk_usage", lambda p: types.SimpleNamespace(total=0, used=0, free=10**6)
    )
    monkeypatch.setattr(pull, "_confirm_continue", lambda prompt: True)
    monkeypatch.setattr(pull, "_adb_pull_media", lambda r, l, s: (l.mkdir(parents=True, exist_ok=True), [])[1])
    assert pull.pull_media(make_ctx(), "S") is not None


def test_unreadable_files_skipped_with_summary(monkeypatch, make_ctx, caplog):
    monkeypatch.setattr(pull, "_remote_du", lambda r, s: None)

    def fake(remote, local, serial):
        local.mkdir(parents=True, exist_ok=True)
        return ["adb: error: failed to copy '/x/Media/a.jpg': Permission denied"]

    monkeypatch.setattr(pull, "_adb_pull_media", fake)
    with caplog.at_level(logging.WARNING, logger="wae"):
        out = pull.pull_media(make_ctx(), "S")
    assert out is not None
    assert any("skipped" in r.message for r in caplog.records)


def test_locked_phone_raises_unlock_message(monkeypatch, make_ctx):
    monkeypatch.setattr(pull, "_remote_du", lambda r, s: None)

    def denied(args, serial, read_only=True, timeout=None):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="adb: error: failed to stat remote object: Permission denied"
        )

    monkeypatch.setattr(pull, "adb", denied)
    with pytest.raises(DeviceError) as e:
        pull.pull_media(make_ctx(), "S")
    assert "unlock" in str(e.value).lower()
