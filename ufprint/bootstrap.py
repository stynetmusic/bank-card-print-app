"""Early startup: logging, Qt DLL paths, VC++ runtime check."""

import ctypes
import logging
import os
import sys

from ufprint.paths import get_app_dir


def _get_log_paths():
    paths = []
    try:
        paths.append(os.path.join(get_app_dir(), "app_debug.log"))
    except Exception:
        pass
    try:
        temp_dir = os.environ.get("TEMP", "/tmp")
        paths.append(os.path.join(temp_dir, "app_debug.log"))
    except Exception:
        pass
    return paths


def setup_early_logging():
    try:
        log_paths = _get_log_paths()
        handlers = []
        for path in log_paths:
            try:
                handlers.append(logging.FileHandler(path, mode="w", encoding="utf-8"))
            except Exception:
                pass
        handlers.append(logging.StreamHandler())
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )
    except Exception:
        pass


def setup_qt_environment():
    try:
        if sys.platform != "win32":
            return True

        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        elif hasattr(sys, "_MEIPASS"):
            base_dir = sys._MEIPASS
        else:
            base_dir = get_app_dir()

        qt_bin = os.path.join(base_dir, "PyQt5", "Qt", "bin")
        if os.path.isdir(qt_bin):
            try:
                os.add_dll_directory(qt_bin)
            except AttributeError:
                os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")

        qt_plugins = os.path.join(base_dir, "PyQt5", "Qt", "plugins")
        if os.path.isdir(qt_plugins):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(qt_plugins, "platforms")

        return True
    except Exception as e:
        logging.error(f"Qt environment setup failed: {e}")
        return False


def check_vc_runtime():
    if sys.platform != "win32":
        return True
    try:
        ctypes.windll.kernel32.LoadLibraryW("msvcp140.dll")
        ctypes.windll.kernel32.LoadLibraryW("vcruntime140.dll")
        return True
    except OSError:
        return False


def ensure_runtime_or_exit():
    """Check VC++ runtime; show message box and exit if missing."""
    if check_vc_runtime():
        return
    logging.critical("VC++ runtime missing")
    try:
        ctypes.windll.user32.MessageBoxW(
            0, "Visual C++ Redistributable required", "Error", 0x10
        )
    except Exception:
        pass
    sys.exit(1)
