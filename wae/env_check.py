"""Preflight: Python version, adb availability, and device selection.

Fails fast at the gate so a half-finished run never leaves temp data around.
``check_python`` / ``check_adb`` confirm prerequisites, ``check_adb_version``
warns (never raises) below a known-good adb version, and ``select_device``
resolves exactly one authorized device. All device interaction here is
read-only.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys

from wae.errors import EnvError
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

#: Minimum supported Python (identical behaviour on macOS and Windows).
MIN_PYTHON = (3, 9)

#: Known-good adb floor. Below this we warn but never hard-block (SPEC §11 #11).
MIN_ADB_VERSION = (1, 0, 41)

_ADB_VERSION_RE = re.compile(r"version\s+(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)


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


def _parse_adb_version(text: str) -> tuple[int, int, int] | None:
    """Extract the ``x.y.z`` adb version from ``adb version`` output, or None."""
    match = _ADB_VERSION_RE.search(text or "")
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def check_adb_version() -> None:
    """Warn (never raise) if adb is older than the known-good floor.

    Runs the read-only ``adb version``. Any failure to run or parse the output
    is downgraded to a warning so an odd toolchain never blocks the export.
    """
    try:
        proc = subprocess.run(
            ["adb", "version"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("could not run 'adb version' (%s); continuing", exc)
        return

    version = _parse_adb_version(proc.stdout)
    if version is None:
        log.warning("could not parse adb version output; continuing")
        return

    if version < MIN_ADB_VERSION:
        log.warning(
            "adb %s is older than the recommended %s; consider upgrading "
            "Android platform-tools if the pull misbehaves",
            ".".join(map(str, version)),
            ".".join(map(str, MIN_ADB_VERSION)),
        )
