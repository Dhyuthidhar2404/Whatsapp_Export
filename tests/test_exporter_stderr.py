"""Tests for surfacing exporter stderr (issue #44)."""

import logging
import subprocess
from pathlib import Path

import pytest

from wae import decrypt_export
from wae.errors import DecryptionError

KEY = "ab" * 32


def _fail_with(stderr, rc=1):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr=stderr)

    return fake_run


def test_nonzero_exit_surfaces_exporter_stderr(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    err = (
        "Traceback (most recent call last):\n"
        "  File vobject/base.py ...\n"
        "UnicodeDecodeError: 'utf-8' codec can't decode bytes in position 23-25"
    )
    monkeypatch.setattr(decrypt_export.subprocess, "run", _fail_with(err))
    with pytest.raises(DecryptionError) as e:
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    # The real cause is in the message now, not a canned "backup may be corrupt".
    assert "UnicodeDecodeError" in str(e.value)
    assert "may be corrupt" not in str(e.value)


def test_full_stderr_is_logged(monkeypatch, make_ctx, tmp_path, caplog):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    monkeypatch.setattr(decrypt_export.subprocess, "run", _fail_with("line1\nline2\nboom"))
    with caplog.at_level(logging.WARNING, logger="wae"):
        with pytest.raises(DecryptionError):
            decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "boom" in logged and "line1" in logged


def test_bad_key_path_still_friendly(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    monkeypatch.setattr(
        decrypt_export.subprocess,
        "run",
        _fail_with("ValueError: The plaintext is not a SQLite database. ... correct key."),
    )
    with pytest.raises(DecryptionError) as e:
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    assert "key likely doesn't match" in str(e.value)
