"""Tests for logging setup + SecretRedactionFilter (T0.4 / issue #4)."""

import logging
import sys

from wae.logging_setup import LOGGER_NAME, SecretRedactionFilter, setup_logging

KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 64 hex


def test_64hex_in_message_renders_as_redacted(capsys):
    logger = setup_logging(verbose=False)
    logger.info("decrypting with key %s here", KEY)
    out = capsys.readouterr().out
    assert KEY not in out
    assert "***" in out


def test_64hex_embedded_in_msg_template_redacted(capsys):
    logger = setup_logging(verbose=False)
    logger.info("cmd: wtsexporter -k " + KEY + " -b backup")
    out = capsys.readouterr().out
    assert KEY not in out
    assert "***" in out


def test_verbose_emits_debug(capsys):
    logger = setup_logging(verbose=True)
    logger.debug("a debug line")
    assert "a debug line" in capsys.readouterr().out


def test_default_suppresses_debug(capsys):
    logger = setup_logging(verbose=False)
    logger.debug("a debug line")
    assert "a debug line" not in capsys.readouterr().out


def test_filter_unit_redacts_record_msg():
    f = SecretRedactionFilter()
    rec = logging.LogRecord(
        LOGGER_NAME, logging.INFO, __file__, 1, "k=" + KEY, None, None
    )
    f.filter(rec)
    assert KEY not in rec.getMessage()
    assert "***" in rec.getMessage()


def test_filter_leaves_non_key_hex_alone():
    # A short hex run (not 64) must not be redacted.
    f = SecretRedactionFilter()
    rec = logging.LogRecord(LOGGER_NAME, logging.INFO, __file__, 1, "id=deadbeef", None, None)
    f.filter(rec)
    assert "deadbeef" in rec.getMessage()


def test_only_stdout_stderr_handlers():
    logger = setup_logging(verbose=False)
    assert logger.handlers, "expected at least one handler"
    for h in logger.handlers:
        assert isinstance(h, logging.StreamHandler)
        assert h.stream in (sys.stdout, sys.stderr)


def test_idempotent_handlers_no_stacking():
    first = setup_logging(verbose=False)
    count = len(first.handlers)
    second = setup_logging(verbose=True)
    assert len(second.handlers) == count
