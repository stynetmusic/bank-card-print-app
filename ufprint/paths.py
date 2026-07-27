"""Application path helpers (no Qt dependency)."""

import os
import sys
from pathlib import Path


def get_app_dir():
    """Return the application root directory.

    Frozen (PyInstaller): directory containing the executable.
    Dev: parent of the ``ufprint`` package (project root).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_path(path):
    """Expand, resolve, and normalize a filesystem path to native separators."""
    if not path:
        return ""

    raw_path = str(path).strip()
    if not raw_path:
        return ""

    try:
        normalized = Path(raw_path).expanduser().resolve(strict=False)
        return os.path.normpath(str(normalized))
    except Exception:
        return os.path.normpath(raw_path)
