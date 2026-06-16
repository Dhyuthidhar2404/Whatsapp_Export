"""Verify the committed crypt15 fixture decrypts with the pinned library (T4.0 / #13).

This resolves the project's single open premise: that a crypt15 backup decrypts
with the 64-hex key using the pinned ``whatsapp-chat-exporter``. Skipped only if
the optional decryption extras are not installed (CI installs requirements.txt).
"""

import pytest

pytest.importorskip("Crypto", reason="pycryptodome not installed")
pytest.importorskip("javaobj", reason="javaobj-py3 not installed")
crypt = pytest.importorskip("Whatsapp_Chat_Exporter.android_crypt")
from Whatsapp_Chat_Exporter.utility import Crypt  # noqa: E402

from tests.fixtures.make_crypt15_fixture import (  # noqa: E402
    FIXTURE_PATH,
    TEST_KEY_HEX,
)


def test_committed_fixture_exists():
    assert FIXTURE_PATH.exists()
    assert FIXTURE_PATH.stat().st_size > 131  # crypt15 minimum


def test_fixture_decrypts_with_known_key(tmp_path):
    out = tmp_path / "decrypted.db"
    rc = crypt.decrypt_backup(
        FIXTURE_PATH.read_bytes(),
        bytes.fromhex(TEST_KEY_HEX),
        output=str(out),
        crypt=Crypt.CRYPT15,
    )
    assert rc == 0
    assert out.read_bytes()[:15] == b"SQLite format 3"


def test_wrong_key_fails(tmp_path):
    wrong = "ff" * 32
    out = tmp_path / "decrypted.db"
    with pytest.raises(Exception):
        crypt.decrypt_backup(
            FIXTURE_PATH.read_bytes(),
            bytes.fromhex(wrong),
            output=str(out),
            crypt=Crypt.CRYPT15,
        )
    assert not out.exists()
