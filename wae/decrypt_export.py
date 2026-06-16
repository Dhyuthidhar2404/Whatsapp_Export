"""Decrypt + convert the backup into readable chats via whatsapp-chat-exporter.

Detects legacy crypt12/14 (fails clearly) and runs ``wtsexporter`` with the key,
verifying success only when the exporter exits 0 *and* the expected output
exists — otherwise raises :class:`~wae.errors.DecryptionError` with no partial
output left behind. No custom crypto; the key is logged only as ``***``.

Implemented in T4.1–T4.3 (issues #14, #15, #16).
"""
