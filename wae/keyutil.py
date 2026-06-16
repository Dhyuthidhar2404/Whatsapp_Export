"""The key: normalize and obtain the 64-hex E2E backup key.

``normalize`` is a pure function that strips only *known* noise (Unicode
whitespace, zero-width characters, wrapping smart-/straight-quotes and backticks)
then strictly validates exactly 64 hex characters — it never strips arbitrary
characters, which would mask a real typo. ``get_key`` (issue #6) reads
``--key-file`` or prompts with no echo and passes the value through ``normalize``.

The key is never logged, printed, written, or placed in
:class:`~wae.context.RunContext`. No raised message ever echoes the key.
"""

from __future__ import annotations

from wae.errors import InvalidKey

#: Zero-width characters that can sneak into a copy-pasted key.
_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}

#: Straight + smart quotes and backticks that may wrap a pasted key.
_QUOTES = {"'", '"', "`", "‘", "’", "“", "”"}

_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_noise(ch: str) -> bool:
    """True for characters we strip: any whitespace, zero-width, or quote char."""
    return ch.isspace() or ch in _ZERO_WIDTH or ch in _QUOTES


def normalize(raw: str) -> str:
    """Normalize and strictly validate a 64-hex backup key.

    Strips known noise, lowercases, then requires exactly 64 hex characters.
    Anything else raises :class:`~wae.errors.InvalidKey` (exit 2). The raised
    message never contains the key or the raw input.
    """
    cleaned = "".join(ch for ch in raw if not _is_noise(ch)).lower()
    if len(cleaned) != 64 or any(ch not in _HEX_DIGITS for ch in cleaned):
        raise InvalidKey(
            "the key must be exactly 64 hexadecimal characters "
            "(0-9, a-f) — check for typos or missing characters"
        )
    return cleaned
