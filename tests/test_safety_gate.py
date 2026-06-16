"""Tests for the static safety gate (T6.4 / issue #21)."""

from scripts import safety_gate


def test_repo_passes_the_gate():
    assert safety_gate.run() == []


# --- network imports ---


def test_detects_socket_import():
    assert safety_gate.network_violations("x.py", "import socket\n")


def test_detects_requests_import():
    assert safety_gate.network_violations("x.py", "import requests\n")


def test_detects_from_urllib_import():
    assert safety_gate.network_violations("x.py", "from urllib import request\n")


def test_allows_clean_imports():
    assert safety_gate.network_violations("x.py", "import os\nimport subprocess\n") == []


# --- key logging ---


def test_detects_key_passed_to_print():
    assert safety_gate.key_logging_violations("x.py", "print(key)\n")


def test_detects_key_passed_to_log_info():
    assert safety_gate.key_logging_violations("x.py", "log.info(key)\n")


def test_detects_key_in_fstring():
    assert safety_gate.key_logging_violations("x.py", 'log.info(f"the key is {key}")\n')


def test_detects_key_as_logging_arg():
    assert safety_gate.key_logging_violations("x.py", 'log.debug("%s", key)\n')


def test_allows_redacted_key_wrapper():
    # The redacted wrapper passes a sanitized string, not the key itself.
    src = 'log.info("running: %s", _redacted(cmd, key))\n'
    assert safety_gate.key_logging_violations("x.py", src) == []


def test_allows_non_key_logging():
    assert safety_gate.key_logging_violations("x.py", 'log.info("serial %s", serial)\n') == []


# --- gitignore ---


def test_gitignore_missing_entry_detected():
    violations = safety_gate.gitignore_violations("key\n*.zip\n")
    assert violations  # most required entries are missing
    assert any("*.crypt15" in v for v in violations)


def test_full_gitignore_passes():
    text = "\n".join(safety_gate.REQUIRED_GITIGNORE) + "\n"
    assert safety_gate.gitignore_violations(text) == []
