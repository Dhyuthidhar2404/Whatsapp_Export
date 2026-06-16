"""Build the contacts CSV from decrypted chats and an optional vCard.

Extracts unique participants from the export (preferring the rich
``result.json``, falling back to per-chat file names), optionally joins a
supplied vCard on **digits-only** normalized numbers, and writes
``contacts.csv`` with columns ``name,number,source`` (``source`` ∈
``vcard|number-only``), UTF-8.

Group members are included to the extent the export exposes them as numbers
(numeric message senders); members shown only by display name cannot be
recovered as numbers and are not invented.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)


def normalize_number(n: str) -> str:
    """Reduce a number or jid to digits only (strip ``+``, spaces, dashes, jid)."""
    if not n:
        return ""
    local = n.split("@", 1)[0]  # drop @s.whatsapp.net / @g.us
    return "".join(ch for ch in local if ch.isdigit())


def _is_user_number(jid: str) -> bool:
    """True if ``jid``'s local part is a plausible phone number (all digits)."""
    local = jid.split("@", 1)[0]
    return local.isdigit() and len(local) >= 5


def extract_participants(export_dir: Path) -> set[str]:
    """Return the set of unique participant identifiers in the export.

    Reads ``result.json`` when present (top-level chat jids plus numeric message
    senders for group members); otherwise falls back to the stems of per-chat
    HTML/TXT files.
    """
    export_dir = Path(export_dir)
    participants: set[str] = set()
    result_json = export_dir / "result.json"

    if result_json.exists():
        try:
            data = json.loads(result_json.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
        if isinstance(data, dict):
            for jid, chat in data.items():
                if _is_user_number(jid):
                    participants.add(jid)
                msgs = chat.get("messages", {}) if isinstance(chat, dict) else {}
                values = msgs.values() if isinstance(msgs, dict) else msgs
                for msg in values or []:
                    sender = msg.get("sender") if isinstance(msg, dict) else None
                    if sender and _is_user_number(sender):
                        participants.add(sender)
    else:
        for p in [*export_dir.glob("*.html"), *export_dir.glob("*.txt")]:
            if p.name == "index.html":
                continue
            participants.add(p.stem)

    return participants


def parse_vcard(path: Path) -> dict[str, str]:
    """Parse a vCard file into ``{normalized_number: display_name}``.

    Delegates to the resilient :mod:`wae.vcard` parser, which tolerates vCard
    2.1 quoted-printable, embedded photos, and individual malformed entries —
    so one bad contact never sinks the CSV.
    """
    from wae.vcard import parse_vcards

    return parse_vcards(path)


def write_contacts_csv(
    participants: set[str], vmap: dict[str, str], export_dir: Path
) -> Path:
    """Write ``contacts.csv`` (``name,number,source``) into ``export_dir``.

    Each unique number appears exactly once. A vCard match yields the name and
    ``source=vcard``; otherwise the row is the bare number with
    ``source=number-only``. An empty participant set yields a header-only file.
    """
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    csv_path = export_dir / "contacts.csv"

    by_number: dict[str, str] = {}
    for p in participants:
        number = normalize_number(p)
        if number:
            by_number.setdefault(number, p)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "number", "source"])
        for number in sorted(by_number):
            name = vmap.get(number, "")
            source = "vcard" if name else "number-only"
            writer.writerow([name, number, source])

    log.info("wrote contacts.csv with %d contact(s)", len(by_number))
    return csv_path
