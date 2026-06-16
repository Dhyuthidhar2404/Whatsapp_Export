"""Thin CLI shell for the WhatsApp Chat Exporter.

This entry point only: parses flags, configures logging, builds an immutable
:class:`~wae.context.RunContext`, obtains the key, calls the ``run_export``
facade, and maps :class:`~wae.errors.WaeError` / ``KeyboardInterrupt`` to exit
codes. It contains no business logic, no adb, and no crypto — all orchestration
lives behind ``run_export`` (see ``docs/interface-contract.md``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wae.context import build_context
from wae.errors import WaeError
from wae.keyutil import get_key
from wae.logging_setup import setup_logging
from wae.pipeline import run_export

_GUIDANCE = (
    "Before running, make sure on the phone: (a) end-to-end encrypted backup is "
    "ON with the 64-digit key, and (b) you just ran WhatsApp → Settings → Chats "
    "→ Chat backup → Back Up so the export is current."
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the full CLI surface (SPEC §6)."""
    p = argparse.ArgumentParser(
        prog="export.py",
        description="Export all your WhatsApp chats, media, and contacts to a local ZIP.",
    )
    p.add_argument("--output-dir", default="./output", help="Where the ZIP is written")
    p.add_argument("--format", choices=["html", "json", "txt"], default="html",
                   help="Export format of chats (default: html)")
    p.add_argument("--no-media", dest="include_media", action="store_false", default=True,
                   help="Skip pulling/embedding media")
    p.add_argument("--contacts-vcf", default=None, help="vCard to enrich names + power contacts CSV")
    p.add_argument("--default-country-code", default=None,
                   help="Fallback calling code for vCard numbers without one (e.g. 1, 44)")
    p.add_argument("--key-file", default=None, help="Read key from file instead of prompting")
    p.add_argument("--device", default=None, help="Select device when multiple attached")
    p.add_argument("--package", default="com.whatsapp", help="WhatsApp package to target")
    p.add_argument("--db-path", default=None, help="Override the on-device backup path")
    p.add_argument("--media-path", default=None, help="Override the on-device media path")
    p.add_argument("--verbose", action="store_true", default=False, help="DEBUG logging (redacted)")
    p.add_argument("--keep-temp", action="store_true", default=False, help="Keep temp workdir")
    return p


def main(argv: list[str] | None = None) -> int:
    """Parse args, run the export, and return a process exit code."""
    args = build_parser().parse_args(argv)
    log = setup_logging(args.verbose)
    ctx = build_context(args)

    log.info(_GUIDANCE)
    try:
        key = get_key(Path(args.key_file) if args.key_file else None)
        zip_path = run_export(ctx, key)
        print(f"Export complete: {zip_path}")
        return 0
    except WaeError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted — cleaned up temporary files.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
