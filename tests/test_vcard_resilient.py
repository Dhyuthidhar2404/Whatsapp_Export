"""Tests for the resilient vCard parser/sanitizer (issue #43)."""

import pytest

from wae import vcard

# A vCard 2.1 with quoted-printable non-ASCII names + an embedded PHOTO blob,
# exactly the shape that crashed the exporter's vobject parser.
VCARD_21 = (
    "BEGIN:VCARD\n"
    "VERSION:2.1\n"
    "N;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Jos=C3=A9;;;\n"
    "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Jos=C3=A9\n"
    "TEL;CELL:+1 555-123-4567\n"
    "PHOTO;ENCODING=BASE64;JPEG:/9j/4AAQSkZJRgABAQAAAQABAAD\n"
    " continuationbase64data==\n"
    "END:VCARD\n"
    "BEGIN:VCARD\n"
    "VERSION:2.1\n"
    "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Priya=20=E0=A4=AA\n"
    "TEL;CELL:+91 98765 43210\n"
    "END:VCARD\n"
)


def _write(tmp_path, text):
    p = tmp_path / "c.vcf"
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_quoted_printable_names(tmp_path):
    vmap = vcard.parse_vcards(_write(tmp_path, VCARD_21))
    assert vmap["15551234567"] == "José"
    assert vmap["919876543210"].startswith("Priya")


def test_photo_blob_is_ignored(tmp_path):
    cards, _ = vcard.parse_cards(_write(tmp_path, VCARD_21))
    # José card: name decoded, exactly one tel, no base64 leaking in as a number.
    name, tels = cards[0]
    assert name == "José"
    assert tels == ["+1 555-123-4567"]


def test_malformed_entry_is_skipped_not_fatal(tmp_path):
    # Second card is fine; the parser must not be derailed by odd content.
    text = (
        "BEGIN:VCARD\nVERSION:2.1\nFN:\x00\x01broken\nEND:VCARD\n"
        "BEGIN:VCARD\nVERSION:3.0\nFN:Good Person\nTEL:+15550001111\nEND:VCARD\n"
    )
    vmap = vcard.parse_vcards(_write(tmp_path, text))
    assert vmap.get("15550001111") == "Good Person"


def test_sanitize_to_vcard3_is_clean(tmp_path):
    out, written, skipped = vcard.sanitize_to_vcard3(
        _write(tmp_path, VCARD_21), tmp_path / "clean.vcf"
    )
    text = out.read_text(encoding="utf-8")
    assert "VERSION:3.0" in text
    assert "QUOTED-PRINTABLE" not in text
    assert "PHOTO" not in text
    assert "José" in text
    assert written == 2


def test_sanitize_garbage_yields_zero_written(tmp_path):
    out, written, skipped = vcard.sanitize_to_vcard3(
        _write(tmp_path, "this is not a vcard\n"), tmp_path / "clean.vcf"
    )
    assert written == 0


# --- end-to-end: a 2.1 QP vCard must enrich, not crash, via the real exporter ---


@pytest.fixture
def _deps():
    pytest.importorskip("Crypto")
    pytest.importorskip("javaobj")
    pytest.importorskip("vobject")
    pytest.importorskip("Whatsapp_Chat_Exporter")


def test_2_1_quoted_printable_vcard_enriches_end_to_end(_deps, make_ctx, tmp_path):
    from wae import decrypt_export
    from tests.fixtures.make_crypt15_fixture import TEST_KEY_HEX, generate

    fixture = generate(tmp_path / "f.crypt15", with_contacts=False, jid="15551234567@s.whatsapp.net")
    vcf = tmp_path / "c.vcf"
    vcf.write_text(
        "BEGIN:VCARD\nVERSION:2.1\n"
        "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Jos=C3=A9 Friend\n"
        "TEL;CELL:+1 555-123-4567\nEND:VCARD\n",
        encoding="utf-8",
    )
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", contacts_vcf=vcf, default_country_code="1", include_media=False)
    export_dir = decrypt_export.export_chats(fixture, None, TEST_KEY_HEX, ctx)
    html = "\n".join(
        p.read_text(encoding="utf-8")
        for p in export_dir.glob("*.html")
        if p.name != "index.html"
    )
    assert "José" in html  # the QP name survived sanitization → enrichment


def test_garbage_vcard_degrades_to_numbers_only(_deps, make_ctx, tmp_path):
    from wae import decrypt_export
    from tests.fixtures.make_crypt15_fixture import TEST_KEY_HEX, generate

    fixture = generate(tmp_path / "f.crypt15", with_contacts=False, jid="15551234567@s.whatsapp.net")
    vcf = tmp_path / "c.vcf"
    vcf.write_text("totally not a vcard\n", encoding="utf-8")
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", contacts_vcf=vcf, default_country_code="1", include_media=False)
    # Must NOT raise — degrades to numbers-only.
    export_dir = decrypt_export.export_chats(fixture, None, TEST_KEY_HEX, ctx)
    assert (export_dir / "index.html").exists()
