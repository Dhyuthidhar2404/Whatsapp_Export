"""Tests for package.make_zip + check_output_writable (T6.1 / issue #18)."""

import types
import zipfile
from datetime import date

import pytest

from wae import package
from wae.errors import PackagingError


def _make_export(tmp_path):
    export = tmp_path / "export"
    export.mkdir()
    (export / "index.html").write_text("<h1>chats</h1>", encoding="utf-8")
    (export / "15551234567.html").write_text("<p>hi</p>", encoding="utf-8")
    (export / "contacts.csv").write_text("name,number,source\n", encoding="utf-8")
    return export


def test_make_zip_one_file_at_documented_path(tmp_path):
    export = _make_export(tmp_path)
    out = tmp_path / "output"
    zip_path = package.make_zip(export, out)
    assert zip_path.parent == out
    assert zip_path.name == f"whatsapp-export-{date.today().isoformat()}.zip"
    assert zip_path.exists()


def test_zip_has_index_and_contacts_at_root(tmp_path):
    export = _make_export(tmp_path)
    zip_path = package.make_zip(export, tmp_path / "output")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "index.html" in names
    assert "contacts.csv" in names
    assert "15551234567.html" in names


def test_second_same_day_run_suffixes_2(tmp_path):
    export = _make_export(tmp_path)
    out = tmp_path / "output"
    first = package.make_zip(export, out)
    second = package.make_zip(export, out)
    assert first.name.endswith(f"{date.today().isoformat()}.zip")
    assert second.name.endswith("-2.zip")
    assert first.exists() and second.exists()  # never overwritten


def test_third_run_suffixes_3(tmp_path):
    export = _make_export(tmp_path)
    out = tmp_path / "output"
    package.make_zip(export, out)
    package.make_zip(export, out)
    third = package.make_zip(export, out)
    assert third.name.endswith("-3.zip")


def test_unwritable_output_raises(tmp_path):
    # Point output_dir at an existing *file* so mkdir fails.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(PackagingError) as e:
        package.check_output_writable(blocker)
    assert e.value.exit_code == 5


def test_insufficient_space_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(
        package.shutil, "disk_usage", lambda p: types.SimpleNamespace(total=0, used=0, free=10)
    )
    with pytest.raises(PackagingError) as e:
        package.check_output_writable(tmp_path / "out")
    assert e.value.exit_code == 5
