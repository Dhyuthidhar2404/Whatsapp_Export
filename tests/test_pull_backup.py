"""Tests for pull.pull_backup (T3.2 / issue #11)."""

import logging

import pytest

from wae import pull
from wae.errors import DeviceError, NoBackupError

DB_REMOTE = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15"


@pytest.fixture(autouse=True)
def _no_sleep_and_paths(monkeypatch):
    monkeypatch.setattr(pull.time, "sleep", lambda s: None)
    monkeypatch.setattr(pull, "resolve_paths", lambda ctx, serial: (DB_REMOTE, "/x/Media"))


def test_successful_pull_lands_file_and_reports_freshness(monkeypatch, make_ctx, caplog):
    def fake_pull(remote, local, serial):
        local.write_bytes(b"x" * 40)

    monkeypatch.setattr(pull, "_adb_pull", fake_pull)
    monkeypatch.setattr(pull, "_remote_size", lambda r, s: 40)
    monkeypatch.setattr(pull, "_remote_mtime", lambda r, s: 1_000_000)
    monkeypatch.setattr(pull.time, "time", lambda: 1_000_000 + 3600)  # 1h old

    with caplog.at_level(logging.INFO, logger="wae"):
        local = pull.pull_backup(make_ctx(), "S")

    assert local.exists()
    assert local.stat().st_size == 40
    assert any("pulled backup" in r.message for r in caplog.records)


def test_transport_error_retries_then_deviceerror(monkeypatch, make_ctx):
    calls = {"n": 0}

    def always_transport(remote, local, serial):
        calls["n"] += 1
        raise pull._TransportError("device offline")

    monkeypatch.setattr(pull, "_adb_pull", always_transport)
    monkeypatch.setattr(pull, "_remote_size", lambda r, s: None)

    with pytest.raises(DeviceError) as e:
        pull.pull_backup(make_ctx(), "S")
    assert e.value.exit_code == 1
    assert calls["n"] == pull.PULL_ATTEMPTS  # retried exactly 3x


def test_size_mismatch_treated_as_partial_then_retried(monkeypatch, make_ctx):
    state = {"n": 0}

    def flaky(remote, local, serial):
        state["n"] += 1
        local.write_bytes(b"x" * (50 if state["n"] == 1 else 100))

    monkeypatch.setattr(pull, "_adb_pull", flaky)
    monkeypatch.setattr(pull, "_remote_size", lambda r, s: 100)
    monkeypatch.setattr(pull, "_remote_mtime", lambda r, s: 1)
    monkeypatch.setattr(pull.time, "time", lambda: 1_000_000)

    local = pull.pull_backup(make_ctx(), "S")
    assert local.stat().st_size == 100
    assert state["n"] == 2  # first (partial) retried, second succeeded


def test_midwrite_warning_when_mtime_recent(monkeypatch, make_ctx, caplog):
    monkeypatch.setattr(pull, "_adb_pull", lambda r, l, s: l.write_bytes(b"x" * 10))
    monkeypatch.setattr(pull, "_remote_size", lambda r, s: None)
    monkeypatch.setattr(pull, "_remote_mtime", lambda r, s: 1_000_000 - 10)  # 10s ago
    monkeypatch.setattr(pull.time, "time", lambda: 1_000_000)

    with caplog.at_level(logging.WARNING, logger="wae"):
        pull.pull_backup(make_ctx(), "S")
    assert any("still be writing" in r.message for r in caplog.records)


def test_missing_file_is_not_retried(monkeypatch, make_ctx):
    calls = {"n": 0}

    def notfound(remote, local, serial):
        calls["n"] += 1
        raise NoBackupError("the backup file was not found on the device")

    monkeypatch.setattr(pull, "_adb_pull", notfound)
    monkeypatch.setattr(pull, "_remote_size", lambda r, s: None)

    with pytest.raises(NoBackupError):
        pull.pull_backup(make_ctx(), "S")
    assert calls["n"] == 1  # logical error → no retry
