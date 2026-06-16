"""The facade and pipeline orchestrator.

``run_export(ctx, key) -> Path`` is the single programmatic entry point. It
sequences env_check → pull → decrypt_export → contacts → package, passing the
immutable :class:`~wae.context.RunContext` and each stage's returned values
forward, and passing the key only to ``decrypt_export``. A ``try/finally``
guarantees the temp workdir is wiped and the key reference dropped on every exit
path — success, handled failure, or Ctrl-C (which the shell maps to exit 130).

This module is the *only* place that imports every stage; the stages never
import one another.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from wae import contacts, decrypt_export, env_check, package, pull
from wae.context import RunContext
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)


def _teardown(ctx: RunContext) -> None:
    """Wipe the temp workdir unless ``--keep-temp`` was given."""
    if ctx.keep_temp:
        log.info("keeping temp workdir (--keep-temp): %s", ctx.tmp_dir)
        return
    if ctx.tmp_dir.exists():
        shutil.rmtree(ctx.tmp_dir, ignore_errors=True)
        log.debug("removed temp workdir %s", ctx.tmp_dir)


def run_export(ctx: RunContext, key: str) -> Path:
    """Run the full export pipeline and return the path to the produced ZIP.

    Raises a :class:`~wae.errors.WaeError` subclass on any stage failure (the
    shell maps it to an exit code). Temp cleanup and key drop always run.
    """
    try:
        env_check.check_python()
        env_check.check_adb()
        env_check.check_adb_version()
        serial = env_check.select_device(ctx.device)

        backup_path = pull.pull_backup(ctx, serial)
        media_dir = pull.pull_media(ctx, serial)

        export_dir = decrypt_export.export_chats(backup_path, media_dir, key, ctx)

        participants = contacts.extract_participants(export_dir)
        vmap: dict[str, str] = {}
        if ctx.contacts_vcf is not None:
            try:
                vmap = contacts.parse_vcard(ctx.contacts_vcf)
            except Exception as exc:  # malformed vCard must not kill the export
                log.warning("could not parse vCard (%s); continuing with numbers only", exc)
        contacts.write_contacts_csv(participants, vmap, export_dir)

        return package.make_zip(export_dir, ctx.output_dir)
    finally:
        # Drop our reference to the key and always wipe temp.
        key = None  # noqa: F841 — intentional key-hygiene drop
        _teardown(ctx)
