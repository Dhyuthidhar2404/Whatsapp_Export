"""Tests for env_check.select_device (T1.3 / issue #9)."""

import subprocess

import pytest

from wae import env_check
from wae.errors import DeviceError


def _fake_devices(stdout):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    return runner


HEADER = "List of devices attached\n"


def test_single_authorized_returned(monkeypatch):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(HEADER + "ABC123\tdevice\n"))
    assert env_check.select_device(None) == "ABC123"


def test_zero_devices_raises_with_guidance(monkeypatch):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(HEADER))
    with pytest.raises(DeviceError) as e:
        env_check.select_device(None)
    assert e.value.exit_code == 1
    assert "connect" in str(e.value).lower()


def test_multiple_without_request_lists_serials(monkeypatch):
    out = HEADER + "ABC123\tdevice\nDEF456\tdevice\n"
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(out))
    with pytest.raises(DeviceError) as e:
        env_check.select_device(None)
    assert "ABC123" in str(e.value) and "DEF456" in str(e.value)
    assert "--device" in str(e.value)


def test_unauthorized_tells_user_to_accept_prompt(monkeypatch):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(HEADER + "ABC123\tunauthorized\n"))
    with pytest.raises(DeviceError) as e:
        env_check.select_device(None)
    assert "unauthorized" in str(e.value).lower()
    assert "prompt" in str(e.value).lower()


def test_requested_authorized_returned(monkeypatch):
    out = HEADER + "ABC123\tdevice\nDEF456\tdevice\n"
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(out))
    assert env_check.select_device("DEF456") == "DEF456"


def test_requested_unauthorized_raises(monkeypatch):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(HEADER + "ABC123\tunauthorized\n"))
    with pytest.raises(DeviceError):
        env_check.select_device("ABC123")


def test_requested_missing_raises(monkeypatch):
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(HEADER + "ABC123\tdevice\n"))
    with pytest.raises(DeviceError) as e:
        env_check.select_device("NOPE999")
    assert "NOPE999" in str(e.value)


def test_daemon_chatter_ignored(monkeypatch):
    out = "* daemon not running; starting now at tcp:5037\n* daemon started successfully\n" + HEADER + "ABC123\tdevice\n"
    monkeypatch.setattr(env_check.subprocess, "run", _fake_devices(out))
    assert env_check.select_device(None) == "ABC123"
