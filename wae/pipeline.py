"""The facade and pipeline orchestrator.

``run_export(ctx, key) -> Path`` is the single programmatic entry point. It
sequences env_check → pull → decrypt_export → contacts → package, passing the
immutable :class:`~wae.context.RunContext` and each stage's returned values
forward, and passing the key only to ``decrypt_export``. A ``try/finally``
guarantees temp wipe and key drop on every exit path, including Ctrl-C (→ 130).

Implemented in T6.2 (issue #19).
"""
