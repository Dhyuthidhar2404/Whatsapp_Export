"""Shared test fixtures."""

import logging

import pytest

from wae.context import RunContext


@pytest.fixture(autouse=True)
def _reset_wae_logger():
    """Reset the global ``wae`` logger per test so caplog can capture records.

    ``setup_logging`` sets ``propagate=False`` and attaches a stdout handler;
    because loggers are process-global singletons, that would otherwise leak
    across tests and stop ``caplog`` (which relies on propagation) from seeing
    records. We clear it before each test and restore afterward.
    """
    logger = logging.getLogger("wae")
    saved = (logger.propagate, logger.handlers[:], logger.filters[:], logger.level)
    logger.propagate = True
    logger.handlers = []
    logger.filters = []
    yield
    logger.propagate, logger.handlers, logger.filters, logger.level = saved


@pytest.fixture
def make_ctx(tmp_path):
    """Factory for a RunContext with sensible defaults, overridable per field."""

    def _make(**overrides):
        defaults = dict(
            output_dir=tmp_path / "output",
            fmt="html",
            include_media=True,
            contacts_vcf=None,
            device=None,
            package="com.whatsapp",
            db_path=None,
            media_path=None,
            verbose=False,
            keep_temp=False,
            tmp_dir=tmp_path / "tmp",
        )
        defaults.update(overrides)
        return RunContext(**defaults)

    return _make
