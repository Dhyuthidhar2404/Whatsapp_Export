"""Tests for the export.py thin CLI shell (T6.3 / issue #20)."""

from pathlib import Path

import pytest

import export
from wae.errors import DecryptionError, InvalidKey, PackagingError


# --- flag parsing → RunContext ---


def test_defaults_build_expected_context():
    args = export.build_parser().parse_args([])
    ctx = export.build_context(args)
    assert ctx.output_dir == Path("./output")
    assert ctx.fmt == "html"
    assert ctx.include_media is True
    assert ctx.package == "com.whatsapp"


def test_all_flags_take_effect():
    args = export.build_parser().parse_args([
        "--output-dir", "/tmp/o", "--format", "json", "--no-media",
        "--contacts-vcf", "/c.vcf", "--default-country-code", "44",
        "--device", "SER1", "--package", "com.whatsapp.w4b",
        "--db-path", "/d", "--media-path", "/m", "--verbose", "--keep-temp",
    ])
    ctx = export.build_context(args)
    assert ctx.output_dir == Path("/tmp/o")
    assert ctx.fmt == "json"
    assert ctx.include_media is False
    assert ctx.contacts_vcf == Path("/c.vcf")
    assert ctx.default_country_code == "44"
    assert ctx.device == "SER1"
    assert ctx.package == "com.whatsapp.w4b"
    assert ctx.db_path == "/d" and ctx.media_path == "/m"
    assert ctx.verbose is True and ctx.keep_temp is True


# --- exit-code mapping ---


def test_happy_path_returns_0_and_prints_zip(monkeypatch, capsys, tmp_path):
    zip_path = tmp_path / "whatsapp-export-2026-06-16.zip"
    zip_path.write_bytes(b"zip")
    monkeypatch.setattr(export, "get_key", lambda kf: "ab" * 32)
    monkeypatch.setattr(export, "run_export", lambda ctx, key: zip_path)
    rc = export.main(["--key-file", "/whatever"])
    assert rc == 0
    assert str(zip_path) in capsys.readouterr().out


@pytest.mark.parametrize("exc, code", [
    (InvalidKey("bad key"), 2),
    (DecryptionError("wrong key"), 4),
    (PackagingError("no space"), 5),
])
def test_waeerror_maps_to_exit_code(monkeypatch, capsys, exc, code):
    monkeypatch.setattr(export, "get_key", lambda kf: "ab" * 32)

    def boom(ctx, key):
        raise exc

    monkeypatch.setattr(export, "run_export", boom)
    rc = export.main([])
    assert rc == code
    assert exc.message in capsys.readouterr().err


def test_invalid_key_from_get_key_maps_to_2(monkeypatch, capsys):
    def bad_key(kf):
        raise InvalidKey("not 64 hex")

    monkeypatch.setattr(export, "get_key", bad_key)
    rc = export.main([])
    assert rc == 2


def test_keyboard_interrupt_maps_to_130(monkeypatch):
    monkeypatch.setattr(export, "get_key", lambda kf: "ab" * 32)

    def interrupt(ctx, key):
        raise KeyboardInterrupt

    monkeypatch.setattr(export, "run_export", interrupt)
    assert export.main([]) == 130
