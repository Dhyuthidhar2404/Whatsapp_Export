"""The only module that shells out to the device — read-only, via adb.

Wraps ``adb`` (forbidding write verbs as a structural guard), resolves the
on-device backup/media paths by probing candidate locations, and (in later
issues) pulls the ``msgstore.db.crypt15`` and media tree into the temp workdir.
The device is never written to: ``adb shell`` is allowed only for read-only
probes (``ls``, ``stat``, ``du``).
"""

from __future__ import annotations

import logging
import subprocess

from wae.context import RunContext
from wae.errors import NoBackupError
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

#: adb top-level verbs that mutate the device or its apps — never allowed.
_WRITE_VERBS = {
    "push", "install", "install-multiple", "install-multi-package", "uninstall",
    "rm", "mv", "cp", "sync", "reboot", "root", "unroot", "remount", "emu",
    "restore", "backup", "disable-verity", "enable-verity",
}

#: shell utilities that write to the filesystem/device — never allowed.
_WRITE_SHELL_CMDS = {
    "rm", "mv", "cp", "mkdir", "rmdir", "touch", "dd", "chmod", "chown",
    "ln", "truncate", "pm", "am", "settings", "svc", "input", "setprop",
    "content", "monkey", "screencap", "screenrecord",
}

# --- On-device path layout -------------------------------------------------

#: Path of the encrypted backup relative to a WhatsApp base directory.
DB_REL = "Databases/msgstore.db.crypt15"
#: Path of the media tree relative to a WhatsApp base directory.
MEDIA_REL = "Media"


def _whatsapp_bases(package: str) -> list[str]:
    """Candidate WhatsApp base dirs, scoped-storage first, then legacy/OEM."""
    return [
        f"/storage/emulated/0/Android/media/{package}/WhatsApp",
        f"/sdcard/Android/media/{package}/WhatsApp",
        "/storage/emulated/0/WhatsApp",  # legacy (pre-Android 11)
        "/sdcard/WhatsApp",              # legacy alias
    ]


def _assert_read_only(args: list[str]) -> None:
    """Raise ``ValueError`` if ``args`` would write to the device.

    Structural enforcement of the read-only-device rule: blocks write verbs and
    write-capable ``adb shell`` commands (including output redirection).
    """
    if not args:
        return
    verb = args[0]
    if verb in _WRITE_VERBS:
        raise ValueError(f"refusing to run a device-writing adb verb: {verb!r}")
    if verb == "shell":
        shell_tokens = args[1:]
        if any(tok in (">", ">>", "1>", "2>") or ">" in tok for tok in shell_tokens):
            raise ValueError("refusing an adb shell command with output redirection")
        if shell_tokens:
            base = shell_tokens[0].rsplit("/", 1)[-1]  # handle /system/bin/rm
            if base in _WRITE_SHELL_CMDS:
                raise ValueError(
                    f"refusing a device-writing adb shell command: {shell_tokens[0]!r}"
                )


def adb(
    args: list[str], serial: str, read_only: bool = True, timeout: float | None = None
) -> subprocess.CompletedProcess:
    """Run ``adb -s <serial> <args...>`` and return the CompletedProcess.

    When ``read_only`` (the default and only intended mode), refuses any write
    verb or write-capable shell command. The command is logged at DEBUG; the
    redaction filter scrubs any stray secret as a backstop.
    """
    if read_only:
        _assert_read_only(args)
    cmd = ["adb", "-s", serial, *args]
    log.debug("adb -s %s %s", serial, " ".join(args))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _remote_exists(remote_path: str, serial: str) -> bool:
    """True if ``remote_path`` exists on the device (read-only ``ls`` probe)."""
    proc = adb(["shell", "ls", remote_path], serial)
    return proc.returncode == 0


def _probe_db(package: str, serial: str) -> str | None:
    """Return the first existing crypt15 backup path among candidates, or None."""
    for base in _whatsapp_bases(package):
        path = f"{base}/{DB_REL}"
        if _remote_exists(path, serial):
            return path
    return None


def _probe_media(package: str, serial: str, db_remote: str) -> str:
    """Return the media dir: first existing candidate, else derived from db path."""
    for base in _whatsapp_bases(package):
        path = f"{base}/{MEDIA_REL}"
        if _remote_exists(path, serial):
            return path
    if db_remote.endswith(DB_REL):
        return db_remote[: -len(DB_REL)] + MEDIA_REL
    return f"{_whatsapp_bases(package)[0]}/{MEDIA_REL}"


def resolve_paths(ctx: RunContext, serial: str) -> tuple[str, str]:
    """Resolve ``(db_remote, media_remote)`` on the device.

    Honors ``--db-path`` / ``--media-path`` overrides; otherwise probes the
    candidate locations for the given ``--package``. Raises
    :class:`~wae.errors.NoBackupError` (exit 3) if no backup can be found.
    """
    db_remote = ctx.db_path or _probe_db(ctx.package, serial)
    if db_remote is None:
        raise NoBackupError(
            "no WhatsApp backup (msgstore.db.crypt15) was found on the device. "
            "In WhatsApp, go to Settings → Chats → Chat backup and tap Back Up, "
            "then re-run. If your phone stores it in a non-standard location, "
            "pass --db-path."
        )
    media_remote = ctx.media_path or _probe_media(ctx.package, serial, db_remote)
    return db_remote, media_remote
