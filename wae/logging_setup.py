"""Logger configuration plus the secret-redaction backstop.

Provides ``setup_logging(verbose)`` (INFO→stdout by default, DEBUG under
``--verbose``) and ``SecretRedactionFilter``, which scrubs any 64-hex substring
from every log record so an accidental key-in-message can never leak. No
telemetry, no network handlers.

Implemented in T0.4 (issue #4).
"""
