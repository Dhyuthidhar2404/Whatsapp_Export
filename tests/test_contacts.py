"""Tests for contacts CSV generation (T5.1 / issue #17)."""

import csv
import json

import pytest

from wae import contacts


# --- normalize_number ---


@pytest.mark.parametrize("raw, expected", [
    ("+91 98765-43210", "919876543210"),
    ("919876543210@s.whatsapp.net", "919876543210"),
    ("+1 (555) 123-4567", "15551234567"),
    ("", ""),
    ("name-only", ""),
])
def test_normalize_number(raw, expected):
    assert contacts.normalize_number(raw) == expected


def test_intl_and_jid_normalize_equal():
    assert contacts.normalize_number("+91 98765 43210") == contacts.normalize_number(
        "919876543210@s.whatsapp.net"
    )


# --- extract_participants ---


def test_extract_from_result_json_includes_group_numeric_senders(tmp_path):
    data = {
        "15551234567@s.whatsapp.net": {"messages": {}},
        "1111-2222@g.us": {  # group jid itself is not a contact number
            "messages": {
                "1": {"sender": "Bob"},  # name-only sender → excluded
                "2": {"sender": "919876543210@s.whatsapp.net"},  # numeric → included
            }
        },
    }
    (tmp_path / "result.json").write_text(json.dumps(data), encoding="utf-8")
    got = contacts.extract_participants(tmp_path)
    assert got == {"15551234567@s.whatsapp.net", "919876543210@s.whatsapp.net"}


def test_extract_falls_back_to_chat_filenames(tmp_path):
    (tmp_path / "15551234567.html").write_text("x", encoding="utf-8")
    (tmp_path / "447700900123.html").write_text("x", encoding="utf-8")
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    got = contacts.extract_participants(tmp_path)
    assert got == {"15551234567", "447700900123"}


# --- parse_vcard ---


def test_parse_vcard_maps_number_to_name(tmp_path):
    pytest.importorskip("vobject")
    vcf = tmp_path / "c.vcf"
    vcf.write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Aunt Carol\nTEL;TYPE=CELL:+1 555-123-4567\nEND:VCARD\n"
        "BEGIN:VCARD\nVERSION:3.0\nFN:Priya Σ\nTEL:+91 98765 43210\nEND:VCARD\n",
        encoding="utf-8",
    )
    vmap = contacts.parse_vcard(vcf)
    assert vmap["15551234567"] == "Aunt Carol"
    assert vmap["919876543210"] == "Priya Σ"


# --- write_contacts_csv ---


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_csv_with_vcard_marks_matched_rows(tmp_path):
    participants = {"15551234567@s.whatsapp.net"}
    vmap = {"15551234567": "Aunt Carol"}
    path = contacts.write_contacts_csv(participants, vmap, tmp_path)
    rows = _read_csv(path)
    assert rows[0] == ["name", "number", "source"]
    assert rows[1] == ["Aunt Carol", "15551234567", "vcard"]


def test_csv_without_vcard_is_number_only(tmp_path):
    participants = {"15551234567@s.whatsapp.net"}
    path = contacts.write_contacts_csv(participants, {}, tmp_path)
    rows = _read_csv(path)
    assert rows[1] == ["", "15551234567", "number-only"]


def test_csv_dedupes_each_number_once(tmp_path):
    participants = {"15551234567@s.whatsapp.net", "+1 555 123 4567", "15551234567"}
    path = contacts.write_contacts_csv(participants, {}, tmp_path)
    rows = _read_csv(path)
    assert len(rows) == 2  # header + one unique number


def test_csv_empty_participants_header_only(tmp_path):
    path = contacts.write_contacts_csv(set(), {}, tmp_path)
    rows = _read_csv(path)
    assert rows == [["name", "number", "source"]]


def test_csv_non_ascii_name_roundtrips(tmp_path):
    participants = {"919876543210@s.whatsapp.net"}
    vmap = {"919876543210": "Priya Σ café"}
    path = contacts.write_contacts_csv(participants, vmap, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "Priya Σ café" in text
