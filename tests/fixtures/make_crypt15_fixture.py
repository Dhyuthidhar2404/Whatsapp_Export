"""Generate a known-good ``msgstore.db.crypt15`` test fixture.

This builds a tiny but schema-valid WhatsApp Android ``msgstore.db`` (legacy
schema, a few messages in one 1:1 chat), then wraps it in a real **crypt15**
container so the pinned ``whatsapp-chat-exporter`` can decrypt and export it.

The crypt15 MESSAGE format, as consumed by ``Whatsapp_Chat_Exporter`` 0.12.x:

* the 32-byte backup key is run through HMAC-SHA256 twice to derive the AES key
  (``HMAC(HMAC(0*32, key), b"backup encryption\\x01")``),
* the 16-byte IV lives at bytes ``[8:24]`` of the file,
* the ciphertext starts at ``file[0] + 2`` and is AES-256-GCM over a
  zlib-compressed SQLite database.

The key here is a **throwaway test value**, intentionally in source — it unlocks
nothing real (the wrapped data is synthetic). It is never written to a ``key``
file, satisfying the secret-commit rules. Regenerate the committed fixture with::

    python -m tests.fixtures.make_crypt15_fixture
"""

from __future__ import annotations

import hmac
import sqlite3
import zlib
from hashlib import sha256
from pathlib import Path

#: Throwaway 64-hex test key. NOT a real backup key — see module docstring.
TEST_KEY_HEX = "0f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0"

#: Deterministic 16-byte IV so regeneration is byte-stable.
_IV = bytes(range(16))

#: Header-length indicator byte; ciphertext begins at ``_HEADER_N + 2``.
_HEADER_N = 28

#: The committed fixture path.
FIXTURE_PATH = Path(__file__).with_name("msgstore.db.crypt15")

#: The synthetic contact + messages baked into the fixture.
TEST_JID = "15551234567@s.whatsapp.net"
TEST_CONTACT_NAME = "Test Contact"
EXPECTED_MESSAGE_COUNT = 3


def _build_msgstore_db(path: Path) -> None:
    """Create a minimal but exporter-compatible WhatsApp Android msgstore.db."""
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, raw_string TEXT, type INTEGER);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                           hidden INTEGER DEFAULT 0);
        CREATE TABLE messages (
            _id INTEGER PRIMARY KEY, key_remote_jid TEXT, key_from_me INTEGER,
            timestamp INTEGER, data TEXT, status INTEGER, edit_version INTEGER,
            thumb_image TEXT, remote_resource TEXT, media_wa_type TEXT,
            latitude REAL, longitude REAL, key_id TEXT, media_caption TEXT,
            received_timestamp INTEGER, read_device_timestamp INTEGER,
            needs_push INTEGER DEFAULT 0, quoted_row_id INTEGER DEFAULT 0,
            media_name TEXT, broadcast INTEGER DEFAULT 0);
        CREATE TABLE messages_quotes (_id INTEGER PRIMARY KEY, key_id TEXT, data TEXT);
        CREATE TABLE missed_call_logs (message_row_id INTEGER, video_call INTEGER);
        CREATE TABLE message_system (message_row_id INTEGER, action_type INTEGER);
        CREATE TABLE message_system_group (message_row_id INTEGER, is_me_joined INTEGER);
        CREATE TABLE message_system_number_change (message_row_id INTEGER,
            old_jid_row_id INTEGER, new_jid_row_id INTEGER);
        CREATE TABLE receipt_user (message_row_id INTEGER, receipt_timestamp INTEGER,
            read_timestamp INTEGER, played_timestamp INTEGER);
        CREATE TABLE wa_contacts (jid TEXT, display_name TEXT, wa_name TEXT, status TEXT);
        CREATE TABLE message_media (message_row_id INTEGER, file_path TEXT,
            message_url TEXT, mime_type TEXT, media_key TEXT, file_hash TEXT,
            thumbnail BLOB);
        CREATE TABLE media_hash_thumbnail (media_hash TEXT, thumb_data BLOB);
        CREATE TABLE call_log (_id INTEGER PRIMARY KEY, jid_row_id INTEGER,
            from_me INTEGER, call_id TEXT, timestamp INTEGER, video_call INTEGER,
            duration INTEGER, call_result INTEGER, bytes_transferred INTEGER);
        CREATE TABLE messages_vcards (_id INTEGER PRIMARY KEY, message_row_id INTEGER,
            vcard TEXT);
        """
    )
    db.execute("INSERT INTO jid (_id, raw_string, type) VALUES (1, ?, 0)", (TEST_JID,))
    db.execute("INSERT INTO chat (_id, jid_row_id, subject, hidden) VALUES (1, 1, NULL, 0)")
    rows = [
        (1, 0, 1700000000000, "Hello from the test fixture!"),
        (2, 1, 1700000060000, "Reply: it works."),
        (3, 0, 1700000120000, "Third message for the chat count."),
    ]
    for _id, from_me, ts, text in rows:
        db.execute(
            """INSERT INTO messages (_id, key_remote_jid, key_from_me, timestamp, data,
                   status, edit_version, media_wa_type, key_id, needs_push,
                   quoted_row_id, received_timestamp, broadcast)
               VALUES (?,?,?,?,?,0,0,'0',?,0,0,?,0)""",
            (_id, TEST_JID, from_me, ts, text, f"KEYID{_id}", ts),
        )
    db.execute(
        "INSERT INTO wa_contacts (jid, display_name, wa_name, status) VALUES (?,?,?,?)",
        (TEST_JID, TEST_CONTACT_NAME, "Test WA", "available"),
    )
    db.commit()
    db.close()


def _derive_main_key(key32: bytes) -> bytes:
    """Mirror the exporter's crypt15 key derivation (HMAC of HMAC)."""
    intermediate = hmac.new(b"\x00" * 32, key32, sha256).digest()
    return hmac.new(intermediate, b"backup encryption\x01", sha256).digest()


def _encrypt_crypt15(db_bytes: bytes, key_hex: str) -> bytes:
    """Wrap a plaintext SQLite db into a crypt15 MESSAGE container."""
    from Crypto.Cipher import AES  # imported lazily so the module imports without it

    main_key = _derive_main_key(bytes.fromhex(key_hex))
    compressed = zlib.compress(db_bytes)
    cipher = AES.new(main_key, AES.MODE_GCM, nonce=_IV)
    ciphertext, tag = cipher.encrypt_and_digest(compressed)

    header = bytearray(_HEADER_N + 2)  # ciphertext starts at file[0] + 2
    header[0] = _HEADER_N
    header[8:24] = _IV
    return bytes(header) + ciphertext + tag


def generate(out_path: Path = FIXTURE_PATH) -> Path:
    """Build the msgstore.db and write the crypt15 fixture to ``out_path``."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "msgstore.db"
        _build_msgstore_db(db_path)
        blob = _encrypt_crypt15(db_path.read_bytes(), TEST_KEY_HEX)
    out_path.write_bytes(blob)
    return out_path


if __name__ == "__main__":
    path = generate()
    print(f"wrote {path} ({path.stat().st_size} bytes)")
