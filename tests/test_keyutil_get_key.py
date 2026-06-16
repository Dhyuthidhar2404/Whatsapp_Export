"""Tests for keyutil.get_key (T2.2 / issue #6)."""

import pytest

from wae.errors import InvalidKey
from wae.keyutil import get_key

VALID = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def test_keyfile_read_and_normalized(tmp_path):
    f = tmp_path / "key.txt"
    f.write_text("  " + VALID.upper() + "\n", encoding="utf-8")
    assert get_key(f) == VALID


def test_interactive_prompt_no_echo(monkeypatch, capsys):
    seen = {}

    def fake_getpass(prompt=""):
        seen["prompt"] = prompt
        return "“" + VALID + "”"  # smart-quote wrapped, normalized away

    monkeypatch.setattr("wae.keyutil.getpass.getpass", fake_getpass)
    assert get_key(None) == VALID
    # getpass was used (no-echo), and nothing leaked to stdout/stderr.
    assert "prompt" in seen
    captured = capsys.readouterr()
    assert VALID not in captured.out
    assert VALID not in captured.err


def test_interactive_invalid_input_raises(monkeypatch):
    monkeypatch.setattr("wae.keyutil.getpass.getpass", lambda prompt="": "too-short")
    with pytest.raises(InvalidKey):
        get_key(None)


def test_missing_keyfile_raises_invalidkey(tmp_path):
    with pytest.raises(InvalidKey) as e:
        get_key(tmp_path / "does-not-exist")
    assert e.value.exit_code == 2


def test_invalid_keyfile_contents_raise(tmp_path):
    f = tmp_path / "key.txt"
    f.write_text("not-a-valid-key", encoding="utf-8")
    with pytest.raises(InvalidKey):
        get_key(f)


def test_key_not_printed_or_logged(monkeypatch, capsys):
    # Capture any print/logging output and assert the key value never appears.
    monkeypatch.setattr("wae.keyutil.getpass.getpass", lambda prompt="": VALID)
    key = get_key(None)
    out = capsys.readouterr()
    assert key not in out.out
    assert key not in out.err
