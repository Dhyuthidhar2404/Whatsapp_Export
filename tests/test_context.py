"""Tests for the immutable RunContext + build_context (T0.3 / issue #3)."""

import dataclasses
from argparse import Namespace
from pathlib import Path

import pytest

from wae.context import DEFAULT_TMP_DIR, RunContext, build_context


def sample_namespace(**overrides):
    base = dict(
        output_dir="./output",
        format="html",
        include_media=True,
        contacts_vcf=None,
        key_file="/secret/key.txt",  # present but must NOT reach the context
        device=None,
        package="com.whatsapp",
        db_path=None,
        media_path=None,
        verbose=False,
        keep_temp=False,
    )
    base.update(overrides)
    return Namespace(**base)


def test_sample_namespace_builds_expected_context():
    ctx = build_context(sample_namespace())
    assert ctx == RunContext(
        output_dir=Path("./output"),
        fmt="html",
        include_media=True,
        contacts_vcf=None,
        device=None,
        package="com.whatsapp",
        db_path=None,
        media_path=None,
        verbose=False,
        keep_temp=False,
        tmp_dir=DEFAULT_TMP_DIR,
    )


def test_mutating_a_field_raises_frozen_instance_error():
    ctx = build_context(sample_namespace())
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.fmt = "json"


def test_context_has_no_key_field():
    fields = {f.name for f in dataclasses.fields(RunContext)}
    assert "key" not in fields
    assert not any("key" in f and f != "key_file" for f in fields)


def test_repr_contains_no_secret():
    # key_file is provided on the namespace but must not appear in the context repr.
    ctx = build_context(sample_namespace(key_file="/secret/key.txt"))
    assert "secret" not in repr(ctx)
    assert "key.txt" not in repr(ctx)


def test_paths_are_coerced_to_path_objects():
    ctx = build_context(sample_namespace(output_dir="/tmp/out", contacts_vcf="/c.vcf"))
    assert ctx.output_dir == Path("/tmp/out")
    assert ctx.contacts_vcf == Path("/c.vcf")
    assert isinstance(ctx.tmp_dir, Path)


def test_no_media_flag_propagates():
    ctx = build_context(sample_namespace(include_media=False))
    assert ctx.include_media is False


def test_explicit_tmp_dir_override_honored():
    ns = sample_namespace()
    ns.tmp_dir = "/var/run/wae-tmp"
    ctx = build_context(ns)
    assert ctx.tmp_dir == Path("/var/run/wae-tmp")
