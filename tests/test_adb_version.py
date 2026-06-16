"""Tests for env_check.check_adb_version (T1.2 / issue #8)."""

import logging
import subprocess

from wae import env_check


def _fake_run(stdout):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return runner


def test_below_minimum_warns_not_raises(monkeypatch, caplog):
    monkeypatch.setattr(
        env_check.subprocess, "run", _fake_run("Android Debug Bridge version 1.0.39")
    )
    with caplog.at_level(logging.WARNING, logger="wae"):
        assert env_check.check_adb_version() is None
    assert any("older" in r.message for r in caplog.records)


def test_at_or_above_minimum_no_warning(monkeypatch, caplog):
    monkeypatch.setattr(
        env_check.subprocess, "run", _fake_run("Android Debug Bridge version 1.0.41")
    )
    with caplog.at_level(logging.WARNING, logger="wae"):
        assert env_check.check_adb_version() is None
    assert not any("older" in r.message for r in caplog.records)


def test_unparseable_output_warns_and_continues(monkeypatch, caplog):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_run("totally unexpected"))
    with caplog.at_level(logging.WARNING, logger="wae"):
        assert env_check.check_adb_version() is None
    assert any("parse" in r.message for r in caplog.records)


def test_run_failure_warns_and_continues(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise OSError("adb vanished")

    monkeypatch.setattr(env_check.subprocess, "run", boom)
    with caplog.at_level(logging.WARNING, logger="wae"):
        assert env_check.check_adb_version() is None
    assert any("could not run" in r.message for r in caplog.records)
