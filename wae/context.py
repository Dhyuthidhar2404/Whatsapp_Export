"""Immutable, non-secret run configuration shared across stages.

Defines the frozen :class:`RunContext` dataclass and ``build_context`` mapping an
argparse ``Namespace`` to it. **The key is never stored here** — it is passed as a
separate argument only to ``keyutil`` (produces) and ``decrypt_export`` (consumes).

Implemented in T0.3 (issue #3).
"""
