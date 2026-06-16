"""Integration tests for decrypt_export against the real pinned exporter (#14).

Uses the committed crypt15 fixture and the actual ``whatsapp-chat-exporter``.
Skipped if the optional decryption extras are not installed (CI installs them).
"""

import pytest

pytest.importorskip("Crypto", reason="pycryptodome not installed")
pytest.importorskip("javaobj", reason="javaobj-py3 not installed")
pytest.importorskip("Whatsapp_Chat_Exporter", reason="whatsapp-chat-exporter not installed")

from wae import decrypt_export  # noqa: E402
from wae.errors import DecryptionError  # noqa: E402
from tests.fixtures.make_crypt15_fixture import FIXTURE_PATH, TEST_KEY_HEX  # noqa: E402


def test_fixture_exports_browsable_html_with_chat(make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html", include_media=False)
    export_dir = decrypt_export.export_chats(FIXTURE_PATH, None, TEST_KEY_HEX, ctx)

    index = export_dir / "index.html"
    assert index.exists()
    chat_files = [p for p in export_dir.glob("*.html") if p.name != "index.html"]
    assert len(chat_files) >= 1  # the one synthetic chat
    assert "WhatsApp chats" in index.read_text(encoding="utf-8")


def test_wrong_key_fails_with_no_partial_output(make_ctx, tmp_path):
    ctx = make_ctx(tmp_dir=tmp_path / "tmp", fmt="html", include_media=False)
    with pytest.raises(DecryptionError):
        decrypt_export.export_chats(FIXTURE_PATH, None, "ff" * 32, ctx)
    assert not (ctx.tmp_dir / "export").exists()
