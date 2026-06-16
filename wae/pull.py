"""The only module that shells out to the device — read-only, via adb.

Wraps ``adb`` (forbidding write verbs as a structural guard), resolves the
on-device backup/media paths by probing candidate locations, and (in later
issues) pulls the ``msgstore.db.crypt15`` and media tree into the temp workdir.
The device is never written to: ``adb shell`` is allowed only for read-only
probes (``ls``, ``stat``, ``du``).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from wae.context import RunContext
from wae.errors import DeviceError, NoBackupError
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

#: Retry policy for transport-level pull failures (SPEC §5 / DECISIONS).
PULL_ATTEMPTS = 3
#: Linear backoff between attempts 1→2 and 2→3.
BACKOFF_SECONDS = (2, 4)
#: A backup modified within this many seconds may still be mid-write.
FRESH_THRESHOLD_SECONDS = 30

#: stderr fragments that indicate a logical (non-retryable) missing-file error.
_NOTFOUND_MARKERS = ("does not exist", "no such file", "not a directory")


class _TransportError(Exception):
    """Internal: a retryable transport-level pull failure."""

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


def _adb_pull(remote: str, local: Path, serial: str) -> None:
    """``adb pull`` one remote path to ``local``; classify failures.

    A missing-file error raises :class:`~wae.errors.NoBackupError` (not
    retried); any other non-zero result raises :class:`_TransportError`
    (retried by the caller).
    """
    proc = adb(["pull", remote, str(local)], serial)
    if proc.returncode == 0:
        return
    err = ((proc.stderr or "") + (proc.stdout or "")).strip()
    if any(marker in err.lower() for marker in _NOTFOUND_MARKERS):
        raise NoBackupError(
            f"the backup file was not found on the device at {remote}; run a "
            "fresh Back Up in WhatsApp and re-run."
        )
    raise _TransportError(err or f"adb pull failed (exit {proc.returncode})")


def _remote_stat(remote: str, serial: str, fmt: str) -> int | None:
    """Read-only ``stat -c <fmt>`` on the device, returning an int or None."""
    proc = adb(["shell", "stat", "-c", fmt, remote], serial)
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except (ValueError, AttributeError):
        return None


def _remote_size(remote: str, serial: str) -> int | None:
    """Size of the remote file in bytes, or None if unavailable."""
    return _remote_stat(remote, serial, "%s")


def _remote_mtime(remote: str, serial: str) -> int | None:
    """Last-modified epoch seconds of the remote file, or None if unavailable."""
    return _remote_stat(remote, serial, "%Y")


def _report_freshness(remote: str, serial: str, local: Path) -> None:
    """Log the backup's age; warn if it looks like it may still be writing."""
    mtime = _remote_mtime(remote, serial)
    if mtime is None:
        log.info("pulled backup to %s (backup age unknown)", local)
        return
    age = time.time() - mtime
    log.info("pulled backup to %s (last backed up ~%.0f min ago)", local, age / 60)
    if age < FRESH_THRESHOLD_SECONDS:
        log.warning(
            "the backup was modified %.0fs ago and may still be writing; if the "
            "export looks truncated, wait for Back Up to finish and re-run",
            age,
        )


def pull_backup(ctx: RunContext, serial: str) -> Path:
    """Pull the encrypted backup into ``ctx.tmp_dir`` and return its local path.

    Retries up to :data:`PULL_ATTEMPTS` times with linear backoff on transport
    errors only (never on missing-file). Verifies the local size matches the
    remote size when obtainable, treating a mismatch as a partial pull to retry.
    Reports the backup's freshness.
    """
    db_remote, _ = resolve_paths(ctx, serial)
    ctx.tmp_dir.mkdir(parents=True, exist_ok=True)
    local = ctx.tmp_dir / "msgstore.db.crypt15"
    remote_size = _remote_size(db_remote, serial)

    last_err: Exception | None = None
    for attempt in range(1, PULL_ATTEMPTS + 1):
        try:
            _adb_pull(db_remote, local, serial)
            if remote_size is not None and local.stat().st_size != remote_size:
                raise _TransportError(
                    f"incomplete pull: local {local.stat().st_size} bytes != "
                    f"remote {remote_size} bytes"
                )
            break
        except _TransportError as exc:
            last_err = exc
            log.warning("backup pull attempt %d/%d failed: %s", attempt, PULL_ATTEMPTS, exc)
            if attempt < PULL_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS[attempt - 1])
    else:
        raise DeviceError(
            f"failed to pull the backup after {PULL_ATTEMPTS} attempts: {last_err}"
        )

    _report_freshness(db_remote, serial, local)
    return local


def _human(num: float) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.0f}{unit}"
        num /= 1024
    return f"{num:.0f}PB"


def _remote_du(remote: str, serial: str) -> int | None:
    """Estimate the remote media size in bytes via read-only ``du -s -k``."""
    proc = adb(["shell", "du", "-s", "-k", remote], serial)
    if proc.returncode != 0:
        return None
    tokens = (proc.stdout or "").strip().split()
    if not tokens:
        return None
    try:
        return int(tokens[0]) * 1024
    except ValueError:
        return None


def _confirm_continue(prompt: str) -> bool:
    """Ask the user to proceed; non-interactive / declined → False."""
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _parse_skipped(output: str) -> list[str]:
    """Collect per-file error/skip lines from adb pull output."""
    skipped = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if "error:" in low or "skipping" in low or "permission denied" in low:
            skipped.append(line)
    return skipped


def _adb_pull_media(remote: str, local: Path, serial: str) -> list[str]:
    """Pull the media tree, returning a list of skipped-file messages.

    A blanket permission denial with nothing pulled means the phone is locked
    (file-based encryption) → :class:`~wae.errors.DeviceError`. Individual
    unreadable files are collected and the run continues.
    """
    local.mkdir(parents=True, exist_ok=True)
    proc = adb(["pull", remote, str(local)], serial)
    output = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and "permission denied" in output.lower():
        if not any(local.iterdir()):
            raise DeviceError(
                "permission denied pulling media — unlock the phone screen "
                "(file-based encryption blocks access while locked) and re-run"
            )
    return _parse_skipped(output)


def pull_media(ctx: RunContext, serial: str) -> Path | None:
    """Pull the media tree into ``ctx.tmp_dir/Media``, or None if media is off.

    Estimates the remote size and warns + offers abort if it exceeds free disk
    space; pulls the tree, continuing past individual unreadable files and
    summarizing what was skipped.
    """
    if not ctx.include_media:
        log.info("skipping media (--no-media)")
        return None

    _, media_remote = resolve_paths(ctx, serial)
    ctx.tmp_dir.mkdir(parents=True, exist_ok=True)
    local_media = ctx.tmp_dir / "Media"

    remote_size = _remote_du(media_remote, serial)
    if remote_size is not None:
        free = shutil.disk_usage(ctx.tmp_dir).free
        log.info("media is ~%s; ~%s free on disk", _human(remote_size), _human(free))
        if remote_size > free:
            log.warning(
                "media (~%s) may not fit in the ~%s of free disk space",
                _human(remote_size),
                _human(free),
            )
            if not _confirm_continue("Continue pulling media anyway? [y/N] "):
                raise DeviceError(
                    "aborted: insufficient disk space for the media pull "
                    "(re-run with --no-media to skip media)"
                )

    skipped = _adb_pull_media(media_remote, local_media, serial)
    if skipped:
        preview = "\n  ".join(skipped[:10])
        more = "" if len(skipped) <= 10 else f"\n  …and {len(skipped) - 10} more"
        log.warning("skipped %d unreadable media file(s):\n  %s%s", len(skipped), preview, more)
    return local_media
