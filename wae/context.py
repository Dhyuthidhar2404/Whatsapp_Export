"""Immutable, non-secret run configuration shared across stages.

:class:`RunContext` is a frozen dataclass holding only non-secret config (flags,
resolved paths, device serial, temp dir). Stages receive it read-only and
*return* their outputs as values rather than mutating shared state, preserving
explicit pipes-and-filters data flow.

**The key is never stored here.** A frozen dataclass's default ``repr`` would
print every field, so keeping the key out by construction makes key-hygiene
structural rather than a convention. The key is passed separately, only to
``keyutil`` (produces) and ``decrypt_export`` (consumes).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Default ephemeral working directory (gitignored, wiped on every exit path).
DEFAULT_TMP_DIR = Path(".tmp")


@dataclass(frozen=True)
class RunContext:
    """Immutable, non-secret configuration for one export run.

    Mirrors the CLI surface (SPEC §6) minus the key. See
    ``docs/interface-contract.md`` §2 for the agreed field shapes.
    """

    output_dir: Path            # where the ZIP is written          (default ./output)
    fmt: str                    # "html" | "json" | "txt"           (default "html")
    include_media: bool         # pull media?                       (default True)
    contacts_vcf: Path | None   # vCard for name enrichment         (default None)
    device: str | None          # adb serial to target              (default None → auto)
    package: str                # WhatsApp package                  (default "com.whatsapp")
    db_path: str | None         # on-device backup path override    (default None → probe)
    media_path: str | None      # on-device media path override     (default None → probe)
    verbose: bool               # DEBUG logging                     (default False)
    keep_temp: bool             # keep temp workdir                 (default False)
    tmp_dir: Path               # ephemeral working directory


def build_context(args) -> RunContext:
    """Map an argparse ``Namespace`` to an immutable :class:`RunContext`.

    Reads only non-secret flags; ``args.key_file`` is deliberately *not* copied
    in — the key never enters the context. ``args.tmp_dir`` is optional and
    defaults to :data:`DEFAULT_TMP_DIR`.
    """
    return RunContext(
        output_dir=Path(args.output_dir),
        fmt=args.format,
        include_media=args.include_media,
        contacts_vcf=Path(args.contacts_vcf) if args.contacts_vcf else None,
        device=args.device,
        package=args.package,
        db_path=args.db_path,
        media_path=args.media_path,
        verbose=args.verbose,
        keep_temp=args.keep_temp,
        tmp_dir=Path(getattr(args, "tmp_dir", None) or DEFAULT_TMP_DIR),
    )
