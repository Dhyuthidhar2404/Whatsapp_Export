"""Scaffold smoke tests (T0.1 / issue #1).

Locks the package layout: ``import wae`` works and every stage + cross-cutting
module imports without error. These guard the structure the rest of the build
depends on; behaviour is added in later issues.
"""

import importlib

import pytest

WAE_SUBMODULES = [
    "wae.errors",
    "wae.context",
    "wae.logging_setup",
    "wae.keyutil",
    "wae.env_check",
    "wae.pull",
    "wae.decrypt_export",
    "wae.contacts",
    "wae.package",
    "wae.pipeline",
]


def test_import_wae_package():
    import wae

    assert hasattr(wae, "__version__")


@pytest.mark.parametrize("module_name", WAE_SUBMODULES)
def test_each_submodule_imports(module_name):
    assert importlib.import_module(module_name) is not None


def test_export_entry_point_imports():
    export = importlib.import_module("export")
    assert hasattr(export, "main")
