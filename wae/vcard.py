"""Resilient vCard parsing + sanitization (cross-cutting helper).

Tolerant of vCard **2.1** quoted-printable + ``CHARSET`` values, embedded
``PHOTO`` base64 blobs, and individual malformed entries (skipped with a count)
— so one bad contact can never sink the export. Used by ``contacts`` (for the
CSV) and ``decrypt_export`` (which sanitizes to a clean vCard 3.0 file before
handing it to the fragile exporter parser).

No third-party dependency: the exporter still needs ``vobject`` to read the
*sanitized* 3.0 file, but our own parsing no longer depends on it.
"""

from __future__ import annotations

import logging
import quopri
from pathlib import Path

from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)


def _strip_eol(s: str) -> str:
    return s.rstrip("\r\n")


def _header_is_qp(logical_line: str) -> bool:
    return "QUOTED-PRINTABLE" in logical_line.split(":", 1)[0].upper()


def _unfold(raw_bytes: bytes) -> list[str]:
    """Turn physical lines into logical vCard lines.

    Handles RFC folding (leading space/TAB continues the previous line — this
    also swallows indented PHOTO base64) and vCard 2.1 quoted-printable soft
    breaks (a QP value ending in ``=`` continues on the next physical line).
    """
    text = raw_bytes.decode("utf-8", errors="replace")
    logical: list[str] = []
    for raw in text.split("\n"):
        line = _strip_eol(raw)
        if not logical:
            logical.append(line)
            continue
        prev = logical[-1]
        if raw[:1] in (" ", "\t"):
            logical[-1] = prev + line[1:]
            continue
        if _header_is_qp(prev) and prev.endswith("="):
            logical[-1] = prev[:-1] + line
            continue
        logical.append(line)
    return logical


def _decode_value(header: str, value: str) -> str:
    """Decode a property value, honoring QUOTED-PRINTABLE + CHARSET leniently."""
    charset = "utf-8"
    for param in header.upper().split(";")[1:]:
        if param.startswith("CHARSET="):
            charset = param.split("=", 1)[1].strip() or "utf-8"
    if "QUOTED-PRINTABLE" in header.upper():
        try:
            raw = quopri.decodestring(value.encode("latin-1", errors="replace"))
            return raw.decode(charset, errors="replace").strip()
        except Exception:
            return value.strip()
    return value.strip()


def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _escape(text: str) -> str:
    """Escape a vCard 3.0 text value (backslash, comma, semicolon, newline)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", " ")
        .strip()
    )


def _card_blocks(logical: list[str]):
    """Yield the lines between each BEGIN:VCARD / END:VCARD."""
    block: list[str] | None = None
    for line in logical:
        upper = line.upper()
        if upper.startswith("BEGIN:VCARD"):
            block = []
        elif upper.startswith("END:VCARD"):
            if block is not None:
                yield block
            block = None
        elif block is not None:
            block.append(line)


def _parse_block(block: list[str]) -> tuple[str, list[str]]:
    """Parse one card block into ``(name, [raw_tel, ...])``."""
    fn = ""
    name = ""
    tels: list[str] = []
    for line in block:
        if ":" not in line:
            continue
        header, value = line.split(":", 1)
        prop = header.split(";", 1)[0].upper()
        if prop == "FN":
            fn = _decode_value(header, value)
        elif prop == "N" and not fn:
            decoded = _decode_value(header, value)
            parts = [p for p in decoded.split(";") if p]
            name = " ".join(reversed(parts[:2])) if parts else decoded
        elif prop == "TEL":
            tels.append(_decode_value(header, value))
        # PHOTO and every other property are ignored
    return (fn or name), tels


def parse_cards(path: Path) -> tuple[list[tuple[str, list[str]]], int]:
    """Return ``(cards, skipped)`` — resilient; unreadable entries are counted."""
    logical = _unfold(Path(path).read_bytes())
    cards: list[tuple[str, list[str]]] = []
    skipped = 0
    for block in _card_blocks(logical):
        try:
            cards.append(_parse_block(block))
        except Exception:
            skipped += 1
    return cards, skipped


def parse_vcards(path: Path) -> dict[str, str]:
    """Resiliently parse a vCard into ``{digits_only_number: name}``."""
    cards, skipped = parse_cards(path)
    if skipped:
        log.warning("vCard: skipped %d unreadable entr(ies)", skipped)
    mapping: dict[str, str] = {}
    for name, tels in cards:
        if not name.strip():
            continue
        for tel in tels:
            number = _digits(tel)
            if number:
                mapping.setdefault(number, name)
    return mapping


def sanitize_to_vcard3(path: Path, out_path: Path) -> tuple[Path, int, int]:
    """Rewrite a (possibly messy 2.1) vCard as clean UTF-8 vCard 3.0.

    Returns ``(out_path, written, skipped)``. Drops PHOTO blobs and entries with
    neither a name nor a number; emits FN + TEL only so the exporter's parser
    never meets quoted-printable or base64.
    """
    cards, skipped = parse_cards(path)
    lines: list[str] = []
    written = 0
    for name, tels in cards:
        clean_tels = [t.replace("\n", " ").strip() for t in tels if _digits(t)]
        if not name.strip() and not clean_tels:
            continue
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        lines.append(f"FN:{_escape(name) if name.strip() else 'Unknown'}")
        for tel in clean_tels:
            lines.append(f"TEL;TYPE=CELL:{tel}")
        lines.append("END:VCARD")
        written += 1
    out = Path(out_path)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out, written, skipped
