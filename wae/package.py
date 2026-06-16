"""Bundle the export directory into the final dated ZIP.

``check_output_writable`` verifies the output directory can be created, written
to, and has free space. ``make_zip`` zips the export dir to
``whatsapp-export-YYYY-MM-DD.zip`` with ``index.html`` and ``contacts.csv`` at
the ZIP root, suffixing ``-2``, ``-3``, … on a same-day collision so an earlier
export is never overwritten.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from datetime import date
from pathlib import Path

from wae.errors import PackagingError
from wae.logging_setup import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

#: Minimum free space (bytes) we insist on before packaging.
_MIN_FREE_BYTES = 1_000_000


def check_output_writable(output_dir: Path) -> None:
    """Raise :class:`~wae.errors.PackagingError` if output isn't usable.

    Confirms the directory can be created and written to (via a probe file) and
    that there is at least a minimal amount of free space.
    """
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".wae-write-test"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as exc:
        raise PackagingError(f"output directory is not writable: {output_dir} ({exc})")

    if shutil.disk_usage(output_dir).free < _MIN_FREE_BYTES:
        raise PackagingError(
            f"insufficient free space to write the ZIP in {output_dir}"
        )


def _dated_zip_path(output_dir: Path, today: str) -> Path:
    """Return a non-colliding dated ZIP path, suffixing -2, -3, … as needed."""
    base = f"whatsapp-export-{today}"
    candidate = output_dir / f"{base}.zip"
    suffix = 2
    while candidate.exists():
        candidate = output_dir / f"{base}-{suffix}.zip"
        suffix += 1
    return candidate


def make_zip(export_dir: Path, output_dir: Path) -> Path:
    """Zip ``export_dir`` into a dated ZIP under ``output_dir`` and return it.

    Files are stored relative to ``export_dir`` so ``index.html`` and
    ``contacts.csv`` land at the ZIP root. Never overwrites a same-day ZIP.
    """
    export_dir = Path(export_dir)
    output_dir = Path(output_dir)
    check_output_writable(output_dir)

    zip_path = _dated_zip_path(output_dir, date.today().isoformat())
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(export_dir.rglob("*")):
                if item.is_file():
                    zf.write(item, item.relative_to(export_dir))
    except OSError as exc:
        if zip_path.exists():
            zip_path.unlink()
        raise PackagingError(f"failed to write the ZIP {zip_path.name}: {exc}")

    log.info("wrote %s", zip_path)
    return zip_path
