"""Tests for path helpers (no GUI)."""

import os
import sys

from ufprint.paths import get_app_dir, normalize_path


def test_get_app_dir_dev_is_project_root():
    app_dir = get_app_dir()
    assert os.path.isdir(app_dir)
    # Project root contains the ufprint package and main.py
    assert os.path.isdir(os.path.join(app_dir, "ufprint"))
    assert os.path.isfile(os.path.join(app_dir, "main.py"))


def test_get_app_dir_frozen(monkeypatch):
    fake_exe = "/opt/UF_Print/UF_Print_Cards_App.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_exe)
    assert get_app_dir() == os.path.dirname(fake_exe)


def test_normalize_path_empty():
    assert normalize_path("") == ""
    assert normalize_path(None) == ""
    assert normalize_path("   ") == ""


def test_normalize_path_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "subdir" / "file.png"
    target.parent.mkdir()
    target.write_bytes(b"x")
    result = normalize_path("subdir/file.png")
    assert os.path.isabs(result)
    assert result.endswith("file.png")
    assert os.path.normpath(result) == result
