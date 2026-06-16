"""Tests for the typed error hierarchy (T0.2 / issue #2)."""

import pytest

from wae.errors import (
    DecryptionError,
    DeviceError,
    EnvError,
    InvalidKey,
    NoBackupError,
    PackagingError,
    WaeError,
)

# (exception type, expected exit code) — the locked SPEC §6 mapping.
CODE_MAP = [
    (EnvError, 1),
    (DeviceError, 1),
    (InvalidKey, 2),
    (NoBackupError, 3),
    (DecryptionError, 4),
    (PackagingError, 5),
]


@pytest.mark.parametrize("exc_type, expected_code", CODE_MAP)
def test_subclass_exit_code(exc_type, expected_code):
    err = exc_type("something went wrong")
    assert err.exit_code == expected_code


def test_all_six_mappings_distinct_and_complete():
    codes = {exc_type: exc_type("x").exit_code for exc_type, _ in CODE_MAP}
    assert codes == {
        EnvError: 1,
        DeviceError: 1,
        InvalidKey: 2,
        NoBackupError: 3,
        DecryptionError: 4,
        PackagingError: 5,
    }


@pytest.mark.parametrize("exc_type, _", CODE_MAP)
def test_subclasses_are_waeerror(exc_type, _):
    assert issubclass(exc_type, WaeError)
    assert isinstance(exc_type("x"), WaeError)


def test_str_returns_human_message():
    err = DecryptionError("the key likely doesn't match this backup")
    assert str(err) == "the key likely doesn't match this backup"
    assert err.message == "the key likely doesn't match this backup"


def test_message_carries_no_key_material():
    # A realistic failure message must never embed the 64-hex key.
    msg = "decryption failed: the key likely doesn't match this backup"
    err = DecryptionError(msg)
    assert "key" in str(err)  # the word, not the value
    assert not any(len(tok) == 64 and all(c in "0123456789abcdef" for c in tok.lower())
                   for tok in str(err).split())


def test_base_can_override_exit_code():
    err = WaeError("custom", exit_code=7)
    assert err.exit_code == 7


def test_raisable_and_catchable_as_base():
    with pytest.raises(WaeError) as excinfo:
        raise NoBackupError("no backup on device")
    assert excinfo.value.exit_code == 3
