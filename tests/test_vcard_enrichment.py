"""Tests for vCard name enrichment (T4.3 / issue #16)."""

from pathlib import Path

import pytest

from wae import decrypt_export

KEY = "ab" * 32


# --- command construction (unit) ---


def test_no_vcard_means_no_enrich_flag(make_ctx, tmp_path):
    ctx = make_ctx(contacts_vcf=None, tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert "--enrich-from-vcards" not in cmd


def test_vcard_adds_enrich_and_country_code(make_ctx, tmp_path):
    vcf = tmp_path / "c.vcf"
    ctx = make_ctx(contacts_vcf=vcf, default_country_code="44", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert "--enrich-from-vcards" in cmd
    assert str(vcf) in cmd
    assert cmd[cmd.index("--default-country-code") + 1] == "44"


def test_vcard_without_country_code_uses_fallback(make_ctx, tmp_path):
    ctx = make_ctx(contacts_vcf=tmp_path / "c.vcf", tmp_dir=tmp_path / "tmp")
    cmd = decrypt_export._build_command(Path("/x/db.crypt15"), None, KEY, ctx, tmp_path / "e")
    assert cmd[cmd.index("--default-country-code") + 1] == decrypt_export.DEFAULT_COUNTRY_CODE


# --- integration with the real exporter ---


@pytest.fixture
def _deps():
    pytest.importorskip("Crypto")
    pytest.importorskip("javaobj")
    pytest.importorskip("vobject")
    pytest.importorskip("Whatsapp_Chat_Exporter")


def _build_fixture(out_path, jid, with_contacts=False):
    from tests.fixtures.make_crypt15_fixture import TEST_KEY_HEX, generate

    generate(out_path, with_contacts=with_contacts, jid=jid)
    return out_path, TEST_KEY_HEX


def _chat_html(export_dir):
    files = [p for p in export_dir.glob("*.html") if p.name != "index.html"]
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def test_known_number_renders_as_name_with_vcard(_deps, make_ctx, tmp_path):
    fixture, key = _build_fixture(tmp_path / "f.crypt15", "15551234567@s.whatsapp.net")
    vcf = tmp_path / "c.vcf"
    vcf.write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Aunt Carol\nTEL;TYPE=CELL:+15551234567\nEND:VCARD\n",
        encoding="utf-8",
    )
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", contacts_vcf=vcf, default_country_code="1", include_media=False)
    export_dir = decrypt_export.export_chats(fixture, None, key, ctx)
    assert "Aunt Carol" in _chat_html(export_dir)


def test_without_vcard_renders_numbers(_deps, make_ctx, tmp_path):
    fixture, key = _build_fixture(tmp_path / "f.crypt15", "15551234567@s.whatsapp.net")
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", contacts_vcf=None, include_media=False)
    export_dir = decrypt_export.export_chats(fixture, None, key, ctx)
    assert "15551234567" in _chat_html(export_dir)


def test_international_digits_only_match(_deps, make_ctx, tmp_path):
    # +91 98765 43210 in the vCard must match 919876543210@s.whatsapp.net.
    fixture, key = _build_fixture(tmp_path / "f.crypt15", "919876543210@s.whatsapp.net")
    vcf = tmp_path / "c.vcf"
    vcf.write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Priya\nTEL;TYPE=CELL:+91 98765 43210\nEND:VCARD\n",
        encoding="utf-8",
    )
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", contacts_vcf=vcf, default_country_code="91", include_media=False)
    export_dir = decrypt_export.export_chats(fixture, None, key, ctx)
    assert "Priya" in _chat_html(export_dir)
