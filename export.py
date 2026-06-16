"""Thin CLI shell for the WhatsApp Chat Exporter.

This entry point only parses flags, builds a :class:`~wae.context.RunContext`,
obtains the key, calls the ``run_export`` facade, and maps
:class:`~wae.errors.WaeError` / ``KeyboardInterrupt`` to exit codes. It contains
no business logic, no adb, and no crypto — see ``docs/interface-contract.md``.

Full implementation in T6.3 (issue #20).
"""


def main() -> int:
    """CLI entry point. Wired up in issue #20; scaffold placeholder for now."""
    raise NotImplementedError("export.py is implemented in issue #20")


if __name__ == "__main__":
    raise SystemExit(main())
