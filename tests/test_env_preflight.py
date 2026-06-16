"""Tests for env_check preflight: check_python / check_adb (T1.1 / issue #7)."""

import sys

import pytest

from wae import env_check
from wae.errors import EnvError


def test_check_python_too_old_raises(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 8, 0))
    with pytest.raises(EnvError) as e:
        env_check.check_python()
    assert e.value.exit_code == 1
    assert "3.9" in str(e.value)


def test_check_python_current_passes():
    # Running interpreter is >= 3.9 (CI guaranteed); must not raise.
    assert env_check.check_python() is None


def test_check_adb_missing_raises(monkeypatch):
    monkeypatch.setattr(env_check.shutil, "which", lambda name: None)
    with pytest.raises(EnvError) as e:
        env_check.check_adb()
    assert e.value.exit_code == 1
    assert "adb" in str(e.value).lower()
    assert "install" in str(e.value).lower() or "brew" in str(e.value).lower()


def test_check_adb_present_passes(monkeypatch):
    monkeypatch.setattr(env_check.shutil, "which", lambda name: "/usr/local/bin/adb")
    assert env_check.check_adb() is None
