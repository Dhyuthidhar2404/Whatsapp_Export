"""Build the contacts CSV from decrypted chats and an optional vCard.

Extracts unique participants (including group members), parses a supplied vCard,
and joins on digits-only normalized numbers to write ``contacts.csv`` with
columns ``name,number,source`` (``source`` in ``vcard|number-only``), UTF-8.

Implemented in T5.1 (issue #17).
"""
