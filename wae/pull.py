"""The only module that shells out to the device — read-only, via adb.

Wraps ``adb`` (forbidding write verbs), resolves on-device backup/media paths,
and pulls the ``msgstore.db.crypt15`` and media tree into the temp workdir with
bounded retry, size-integrity, and freshness reporting. The device is never
written to.

Implemented in T3.1–T3.3 (issues #10, #11, #12).
"""
