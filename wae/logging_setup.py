"""Logger configuration plus the secret-redaction backstop.

One configured logger: INFO→stdout by default, DEBUG under ``--verbose``. The key
is never passed to the logger by any stage; :class:`SecretRedactionFilter` is a
defense-in-depth backstop that scrubs any 64-hex substring from every record, so
an accidental key-in-message can never leak. No telemetry, no network handlers.
"""

from __future__ import annotations

import logging
import re
import sys

#: The single logger name used throughout the tool.
LOGGER_NAME = "wae"

#: Replacement token for redacted secrets.
REDACTION = "***"

#: Matches a standalone 64-hex run (the key) without swallowing longer hex runs.
_HEX64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def _redact(value):
    """Redact a 64-hex substring from ``value`` if it is a string; else passthrough."""
    if isinstance(value, str):
        return _HEX64.sub(REDACTION, value)
    return value


class SecretRedactionFilter(logging.Filter):
    """Replace any 64-hex substring in a log record with ``***``.

    Applied to both the message template (``record.msg``) and the interpolation
    args, so neither ``"key=<hex>"`` nor ``"key=%s" % hex`` can leak. Redaction
    is idempotent, so attaching the filter more than once is harmless.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact(v) for k, v in record.args.items()}
            else:
                record.args = tuple(_redact(a) for a in record.args)
        return True


def setup_logging(verbose: bool) -> logging.Logger:
    """Configure and return the single ``wae`` logger.

    INFO→stdout by default; DEBUG under ``verbose``. Idempotent: repeated calls
    reconfigure the same logger without stacking handlers. The
    :class:`SecretRedactionFilter` is attached to both the logger and its
    handler as a backstop.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    # Reset on repeated calls so handlers/filters never accumulate.
    logger.handlers.clear()
    logger.filters.clear()

    redaction = SecretRedactionFilter()
    logger.addFilter(redaction)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(redaction)
    logger.addHandler(handler)

    return logger
