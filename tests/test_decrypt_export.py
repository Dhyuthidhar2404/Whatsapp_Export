"""Unit tests for decrypt_export (T4.1 / issue #14) — exporter mocked."""

import logging
import subprocess
from pathlib import Path

import pytest

from wae import decrypt_export
from wae.errors import DecryptionError

KEY = "ab" * 32  # 64-hex


# --- detect_format ---


def test_detect_format_crypt15():
    assert decrypt_export.detect_format(Path("x/msgstore.db.crypt15")) == "crypt15"


@pytest.mark.parametrize("ext", [".crypt12", ".crypt14"])
def test_detect_format_legacy_raises(ext):
    with pytest.raises(DecryptionError) as e:
        decrypt_export.detect_format(Path("x/msgstore.db" + ext))
    assert e.value.exit_code == 4
    assert "crypt15" in str(e.value)


def test_detect_format_unknown_raises():
    with pytest.raises(DecryptionError):
        decrypt_export.detect_format(Path("x/foo.db"))


# --- export_chats (mocked subprocess) ---


def test_success_html_synthesizes_index(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    export_dir = ctx.tmp_dir / "export"

    def fake_run(cmd, **kw):
        (export_dir / "alice.html").write_text("<p>hi</p>", encoding="utf-8")
        (export_dir / "bob.html").write_text("<p>yo</p>", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    out = decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "alice" in index and "bob" in index
    assert "WhatsApp chats (2)" in index


def test_command_logs_redacted_key_but_passes_real_key(monkeypatch, make_ctx, tmp_path, caplog):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    with caplog.at_level(logging.INFO, logger="wae"):
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert KEY not in logged
    assert "***" in logged
    assert KEY in seen["cmd"]  # the real subprocess still received the key


def test_wrong_key_raises_and_removes_partial_output(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")
    export_dir = ctx.tmp_dir / "export"

    def fake_run(cmd, **kw):
        (export_dir / "partial.html").write_text("x", encoding="utf-8")  # partial
        return subprocess.CompletedProcess(
            cmd, 1, stdout="",
            stderr="ValueError: The plaintext is not a SQLite database. Ensure you are using the correct key.",
        )

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    with pytest.raises(DecryptionError) as e:
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
    assert e.value.exit_code == 4
    assert "key likely" in str(e.value)
    assert not export_dir.exists()  # no partial output left behind


def test_generic_exporter_failure_raises(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html")

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="boom")

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    with pytest.raises(DecryptionError):
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)


def test_success_but_no_output_is_treated_as_failure(monkeypatch, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="json")  # expects result.json

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")  # writes nothing

    monkeypatch.setattr(decrypt_export.subprocess, "run", fake_run)
    with pytest.raises(DecryptionError):
        decrypt_export.export_chats(Path("/x/msgstore.db.crypt15"), None, KEY, ctx)
