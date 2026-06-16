"""Typed error hierarchy mapping failures to process exit codes.

Stages raise :class:`WaeError` subclasses; the ``export.py`` shell catches them,
prints ``.message``, and exits with ``.exit_code``. No stage calls ``sys.exit``.

Implemented in T0.2 (issue #2).
"""
