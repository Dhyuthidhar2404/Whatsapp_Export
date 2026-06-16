"""Shared test fixtures."""

from pathlib import Path

import pytest

from wae.context import RunContext


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
