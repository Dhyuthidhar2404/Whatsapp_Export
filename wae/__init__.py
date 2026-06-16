"""wae — WhatsApp Chat Exporter (local).

A local-only CLI that exports all of a user's WhatsApp chats, media, and a
contacts CSV from an Android phone into a single ZIP. No server, no network.

This package is a six-stage pipes-and-filters pipeline behind a single
package-level facade, ``run_export``. The stage modules (``env_check``,
``keyutil``, ``pull``, ``decrypt_export``, ``contacts``, ``package``) never
import one another; the orchestrator in ``pipeline`` wires them together via an
immutable :class:`~wae.context.RunContext` and each stage's returned values.

The public contract is intentionally small — see ``docs/interface-contract.md``:

* :func:`wae.pipeline.run_export` — the facade
* :class:`wae.context.RunContext` — immutable, non-secret config
* the :class:`wae.errors.WaeError` hierarchy — typed errors → exit codes
"""

__version__ = "0.1.0"
