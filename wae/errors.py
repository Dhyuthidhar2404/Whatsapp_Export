"""Typed error hierarchy mapping failures to process exit codes.

Stages raise :class:`WaeError` subclasses; the ``export.py`` shell catches them,
prints ``.message``, and exits with ``.exit_code``. No stage calls ``sys.exit``.

Each subclass binds a fixed exit code so SPEC §6's codes cannot drift:

==================  =========  ====================================
Exception           exit_code  Meaning
==================  =========  ====================================
``EnvError``        1          Python/adb prerequisite missing
``DeviceError``     1          No/ambiguous/unauthorized device, or
                               transport failure after retries
``InvalidKey``      2          Key not 64-hex after normalization
``NoBackupError``   3          No backup file found on device
``DecryptionError`` 4          Wrong key, or legacy/unsupported format
``PackagingError``  5          Output unwritable / insufficient space
==================  =========  ====================================

``KeyboardInterrupt`` → exit ``130`` is handled by the shell, not modelled here.
"""

from __future__ import annotations


class WaeError(Exception):
    """Base for all tool errors. Carries a human ``message`` and an ``exit_code``.

    Subclasses fix ``exit_code`` as a class attribute so callers raise them with
    a message only (``raise InvalidKey("...")``). The ``exit_code`` argument
    remains available for the rare case a caller needs to override it.
    """

    #: Default exit code; every concrete subclass overrides this.
    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message


class EnvError(WaeError):
    """Missing prerequisite: Python too old, or ``adb`` not on PATH."""

    exit_code = 1


class DeviceError(WaeError):
    """No/ambiguous/unauthorized device, or a transport failure after retries."""

    exit_code = 1


class InvalidKey(WaeError):
    """The key is not exactly 64 hex characters after normalization."""

    exit_code = 2


class NoBackupError(WaeError):
    """No ``msgstore.db.crypt15`` backup found on the device."""

    exit_code = 3


class DecryptionError(WaeError):
    """Decryption failed: wrong key, or a legacy/unsupported backup format."""

    exit_code = 4


class PackagingError(WaeError):
    """The output ZIP could not be written (unwritable dir / insufficient space)."""

    exit_code = 5
