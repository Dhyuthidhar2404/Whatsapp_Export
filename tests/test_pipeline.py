"""Tests for the run_export facade + teardown (T6.2 / issue #19)."""

import zipfile

import pytest

from wae import contacts, decrypt_export, env_check, package, pipeline, pull
from wae.errors import NoBackupError


@pytest.fixture
def stub_stages(monkeypatch):
    """Stub the device + exporter stages; keep contacts + package real."""
    monkeypatch.setattr(env_check, "check_python", lambda: None)
    monkeypatch.setattr(env_check, "check_adb", lambda: None)
    monkeypatch.setattr(env_check, "check_adb_version", lambda: None)
    monkeypatch.setattr(env_check, "select_device", lambda requested: "SERIAL")
    monkeypatch.setattr(pull, "pull_backup", lambda ctx, serial: ctx.tmp_dir / "msgstore.db.crypt15")
    monkeypatch.setattr(pull, "pull_media", lambda ctx, serial: None)

    def fake_export(db_path, media_dir, key, ctx):
        export_dir = ctx.tmp_dir / "export"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "index.html").write_text("<h1>chats</h1>", encoding="utf-8")
        (export_dir / "15551234567.html").write_text("<p>hi</p>", encoding="utf-8")
        return export_dir

    monkeypatch.setattr(decrypt_export, "export_chats", fake_export)


def _seed_temp(ctx):
    ctx.tmp_dir.mkdir(parents=True, exist_ok=True)
    (ctx.tmp_dir / "msgstore.db.crypt15").write_bytes(b"secret-backup")


def test_happy_path_returns_zip_and_wipes_temp(stub_stages, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", output_dir=tmp_path / "out")
    _seed_temp(ctx)
    zip_path = pipeline.run_export(ctx, "ab" * 32)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "index.html" in names and "contacts.csv" in names
    assert not ctx.tmp_dir.exists()  # temp wiped, no crypt15 residue


def test_stage_error_propagates_and_wipes_temp(stub_stages, make_ctx, tmp_path, monkeypatch):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", output_dir=tmp_path / "out")
    _seed_temp(ctx)

    def boom(ctx, serial):
        raise NoBackupError("no backup")

    monkeypatch.setattr(pull, "pull_backup", boom)
    with pytest.raises(NoBackupError) as e:
        pipeline.run_export(ctx, "ab" * 32)
    assert e.value.exit_code == 3
    assert not ctx.tmp_dir.exists()  # temp still cleaned on failure


def test_keyboard_interrupt_still_wipes_temp(stub_stages, make_ctx, tmp_path, monkeypatch):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", output_dir=tmp_path / "out")
    _seed_temp(ctx)

    def interrupt(ctx, serial):
        raise KeyboardInterrupt

    monkeypatch.setattr(pull, "pull_backup", interrupt)
    with pytest.raises(KeyboardInterrupt):
        pipeline.run_export(ctx, "ab" * 32)
    assert not ctx.tmp_dir.exists()  # no key/crypt15 residue after Ctrl-C


def test_keep_temp_preserves_workdir(stub_stages, make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", output_dir=tmp_path / "out", keep_temp=True)
    _seed_temp(ctx)
    pipeline.run_export(ctx, "ab" * 32)
    assert ctx.tmp_dir.exists()  # preserved for debugging


def test_vcard_join_applied_when_supplied(stub_stages, make_ctx, tmp_path, monkeypatch):
    vcf = tmp_path / "c.vcf"
    vcf.write_text("BEGIN:VCARD\nVERSION:3.0\nFN:Carol\nTEL:+15551234567\nEND:VCARD\n", encoding="utf-8")
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", output_dir=tmp_path / "out", contacts_vcf=vcf)
    _seed_temp(ctx)
    # extract_participants reads from the per-chat filename fallback (15551234567.html)
    monkeypatch.setattr(contacts, "parse_vcard", lambda p: {"15551234567": "Carol"})
    zip_path = pipeline.run_export(ctx, "ab" * 32)
    with zipfile.ZipFile(zip_path) as zf:
        csv_text = zf.read("contacts.csv").decode("utf-8")
    assert "Carol" in csv_text and "vcard" in csv_text
