"""Tests for keyutil.normalize (T2.1 / issue #5)."""

import pytest

from wae.errors import InvalidKey
from wae.keyutil import normalize

# A canonical valid 64-hex key (lowercase form).
VALID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def test_plain_valid_key_passthrough():
    assert normalize(VALID) == VALID


def test_uppercase_is_lowercased():
    assert normalize(VALID.upper()) == VALID


def test_spaces_and_newlines_stripped():
    spaced = VALID[:16] + " " + VALID[16:32] + "\t" + VALID[32:] + "\n"
    assert normalize(spaced) == VALID


def test_wrapping_smart_quotes_stripped():
    assert normalize("“" + VALID + "”") == VALID
    assert normalize("'" + VALID + "'") == VALID
    assert normalize("`" + VALID + "`") == VALID


def test_zero_width_chars_stripped():
    noisy = "​" + VALID[:10] + "‌" + VALID[10:] + "﻿"
    assert normalize(noisy) == VALID


def test_rejects_63_chars():
    with pytest.raises(InvalidKey) as e:
        normalize(VALID[:-1])
    assert e.value.exit_code == 2


def test_rejects_65_chars():
    with pytest.raises(InvalidKey):
        normalize(VALID + "a")


def test_rejects_non_hex_char():
    bad = VALID[:-1] + "z"
    with pytest.raises(InvalidKey):
        normalize(bad)


def test_rejects_empty():
    with pytest.raises(InvalidKey):
        normalize("")


def test_does_not_strip_arbitrary_chars_so_typo_fails():
    # A '-' is not in the noise set, so a hyphenated 64-run stays >64 / non-hex
    # and is rejected rather than silently "repaired".
    with pytest.raises(InvalidKey):
        normalize(VALID[:32] + "-" + VALID[32:])


def test_raised_message_never_echoes_the_key():
    bad = "g" * 64
    with pytest.raises(InvalidKey) as e:
        normalize(bad)
    assert bad not in str(e.value)
    assert "g" * 10 not in str(e.value)
