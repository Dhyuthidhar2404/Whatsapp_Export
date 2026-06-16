"""Preflight: Python version, adb availability, and device selection.

Fails fast at the gate so a half-finished run never leaves temp data around.
``check_python`` / ``check_adb`` confirm prerequisites, ``check_adb_version``
warns (never raises) below a known-good adb version, and ``select_device``
resolves exactly one authorized device. All device interaction here is
read-only.
"""

from __future__ import annotations

import shutil
import sys

from wae.errors import EnvError

#: Minimum supported Python (identical behaviour on macOS and Windows).
MIN_PYTHON = (3, 9)


def check_python() -> None:
    """Raise :class:`~wae.errors.EnvError` if Python is older than 3.9."""
    if sys.version_info < MIN_PYTHON:
        found = f"{sys.version_info[0]}.{sys.version_info[1]}"
        raise EnvError(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required, but found "
            f"Python {found}. Install a newer Python and re-run."
        )


def check_adb() -> None:
    """Raise :class:`~wae.errors.EnvError` if ``adb`` is not resolvable on PATH.

    The message names adb, gives per-platform install guidance, and reminds the
    user to enable USB debugging (Settings → System → Developer options).
    """
    if shutil.which("adb") is None:
        raise EnvError(
            "adb (Android Platform Tools) was not found on PATH.\n"
            "  • macOS:   brew install android-platform-tools\n"
            "  • Windows: download Google's SDK Platform Tools and add it to PATH\n"
            "Then connect the phone over USB and enable USB debugging under "
            "Settings → System → Developer options. If the phone isn't detected, "
            "switch the USB mode from 'Charging only' to 'File transfer' and "
            "accept the on-phone 'Allow USB debugging?' prompt."
        )
