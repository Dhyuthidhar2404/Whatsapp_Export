"""Decrypt + convert the backup into readable chats via whatsapp-chat-exporter.

``detect_format`` rejects legacy crypt12/14 clearly. ``export_chats`` invokes the
pinned exporter (``python -m Whatsapp_Chat_Exporter``) with the key, the crypt15
backup, the media path, and the chosen format. Decryption is considered
successful only when the exporter exits 0 **and** the expected output exists;
otherwise a :class:`~wae.errors.DecryptionError` is raised and any partial output
is removed. No custom crypto is performed here, and the key is logged only as
``***``.

Because the exporter emits one HTML file per chat (no index), the html path
synthesizes a small browsable ``index.html`` linking every chat — the entry the
spec's output contract promises.
"""

from __future__ import annotations

import html
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from wae.context import RunContext
from wae.errors import DecryptionError
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

#: Invoke the pinned library as a module — robust across PATH setups.
EXPORTER_CMD = [sys.executable, "-m", "Whatsapp_Chat_Exporter"]

#: stdout/stderr fragments that indicate a key mismatch rather than a tool fault.
_BAD_KEY_MARKERS = ("not a sqlite database", "correct key", "invalidkey", "inflate")


def detect_format(db_path: Path) -> str:
    """Return ``"crypt15"`` for a supported backup; raise on legacy formats."""
    name = str(db_path).lower()
    if name.endswith(".crypt15"):
        return "crypt15"
    if name.endswith((".crypt12", ".crypt14")):
        raise DecryptionError(
            "legacy crypt12/crypt14 backups are not supported. In WhatsApp, turn "
            "on end-to-end encrypted backup (this switches local backups to "
            "crypt15), run a fresh Back Up, then re-run."
        )
    raise DecryptionError(
        f"unrecognized backup format for {db_path.name}; expected a "
        "msgstore.db.crypt15 file"
    )


def _build_command(
    db_path: Path, media_dir: Path | None, key: str, ctx: RunContext, export_dir: Path
) -> list[str]:
    """Assemble the exporter argv for the chosen format."""
    cmd = [*EXPORTER_CMD, "-a", "-k", key, "-b", str(db_path), "-o", str(export_dir)]
    if media_dir is not None:
        cmd += ["-m", str(media_dir)]
    if ctx.fmt == "json":
        cmd += ["-j", str(export_dir / "result.json"), "--no-html"]
    elif ctx.fmt == "txt":
        cmd += ["--txt", str(export_dir), "--no-html"]
    # html is the exporter's default → no extra flag
    return cmd


def _redacted(cmd: list[str], key: str) -> str:
    """Render the command for logging with the key replaced by ``***``."""
    return " ".join("***" if part == key else part for part in cmd)


def _write_index(export_dir: Path) -> int:
    """Synthesize a browsable ``index.html`` linking every per-chat HTML file."""
    chats = sorted(p for p in export_dir.glob("*.html") if p.name != "index.html")
    items = "\n".join(
        f'  <li><a href="{html.escape(p.name)}">{html.escape(p.stem)}</a></li>'
        for p in chats
    )
    doc = (
        "<!doctype html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\">\n"
        "<title>WhatsApp Export</title></head>\n<body>\n"
        f"<h1>WhatsApp chats ({len(chats)})</h1>\n<ul>\n{items}\n</ul>\n"
        "</body>\n</html>\n"
    )
    (export_dir / "index.html").write_text(doc, encoding="utf-8")
    return len(chats)


def _verify_output(export_dir: Path, fmt: str) -> None:
    """Raise :class:`DecryptionError` if the expected output is missing."""
    if fmt == "json":
        ok = (export_dir / "result.json").exists()
    elif fmt == "txt":
        ok = any(export_dir.glob("*.txt"))
    else:
        ok = (export_dir / "index.html").exists()
    if not ok:
        raise DecryptionError(
            "the exporter reported success but produced no readable output; "
            "treating this as a failed decryption"
        )


def export_chats(
    db_path: Path, media_dir: Path | None, key: str, ctx: RunContext
) -> Path:
    """Decrypt and export the backup, returning the export directory.

    Verifies the backup format, runs the exporter, and confirms exit 0 plus
    expected output. On any failure the (possibly partial) export directory is
    removed so nothing half-written is left behind.
    """
    detect_format(db_path)
    export_dir = ctx.tmp_dir / "export"
    if export_dir.exists():
        shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    cmd = _build_command(db_path, media_dir, key, ctx, export_dir)
    log.info("running exporter: %s", _redacted(cmd, key))
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        shutil.rmtree(export_dir, ignore_errors=True)
        combined = ((proc.stderr or "") + (proc.stdout or "")).lower()
        if any(marker in combined for marker in _BAD_KEY_MARKERS):
            raise DecryptionError(
                "decryption failed — the key likely doesn't match this backup. "
                "Re-check the 64-hex key and that this is the backup it belongs to."
            )
        raise DecryptionError(
            f"the exporter failed (exit {proc.returncode}); the backup may be "
            "corrupt or unsupported"
        )

    if ctx.fmt == "html":
        count = _write_index(export_dir)
        log.info("exported %d chat(s); wrote browsable index.html", count)

    _verify_output(export_dir, ctx.fmt)
    return export_dir
