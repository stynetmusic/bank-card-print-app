# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec — Win7 x64 compatible packaging.

Critical: do NOT ship ucrtbase / api-ms-win-* / MSVC CRT DLLs collected from a
windows-2022 build host. Those binaries import GetSystemTimePreciseAsFileTime
(Win8+). On Win7 the loader prefers the app directory and dies before Python
starts. Target machines should install VC++ Redistributable x64 (+ UCRT update).
"""
from PyInstaller.utils.hooks import collect_all
import os

datas_qt, binaries_qt, hidden_qt = collect_all('PyQt5')
datas_np, binaries_np, hidden_np = collect_all('numpy')

WIN7_FORBIDDEN_EXACT = {
    'ucrtbase.dll',
    'ucrtbased.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'concrt140.dll',
    'vccorlib140.dll',
    'libpq.dll',
}


def _is_forbidden_dll(path_or_name):
    base = os.path.basename(path_or_name).lower()
    if base in WIN7_FORBIDDEN_EXACT:
        return True
    if base.startswith('api-ms-win-'):
        return True
    return False


def _keep_toc_entry(toc_entry):
    """Drop CRT/API-set entries from binaries or datas TOC."""
    # TOC: (dest_name, src_path, typecode) after Analysis; Analysis input uses (src, dest_dir)
    for part in toc_entry[:2]:
        if isinstance(part, str) and _is_forbidden_dll(part):
            return False
    return True


try:
    import PyQt5
    pyqt_root = os.path.dirname(PyQt5.__file__)
    qt_bin_dir = os.path.join(pyqt_root, 'Qt', 'bin')
    if os.path.isdir(qt_bin_dir):
        for entry in os.listdir(qt_bin_dir):
            if _is_forbidden_dll(entry):
                continue
            full_path = os.path.join(qt_bin_dir, entry)
            if os.path.isfile(full_path) and full_path.lower().endswith('.dll'):
                binaries_qt.append((full_path, 'PyQt5/Qt/bin'))
    qt_plugins_dir = os.path.join(pyqt_root, 'Qt', 'plugins')
    if os.path.isdir(qt_plugins_dir):
        for root, dirs, files in os.walk(qt_plugins_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_root = os.path.relpath(root, pyqt_root)
                datas_qt.append((full_path, os.path.join(rel_root)))
except Exception:
    pass

try:
    import numpy as np
    numpy_root = os.path.dirname(np.__file__)
    numpy_libs_dir = os.path.join(numpy_root, 'libs')
    if os.path.isdir(numpy_libs_dir):
        for entry in os.listdir(numpy_libs_dir):
            if _is_forbidden_dll(entry):
                continue
            full_path = os.path.join(numpy_libs_dir, entry)
            if os.path.isfile(full_path):
                binaries_np.append((full_path, 'numpy/libs'))
except Exception:
    pass

# Filter collect_all results up front (CRT often lands in datas).
binaries_qt = [b for b in binaries_qt if _keep_toc_entry(b)]
binaries_np = [b for b in binaries_np if _keep_toc_entry(b)]
datas_qt = [d for d in datas_qt if _keep_toc_entry(d)]
datas_np = [d for d in datas_np if _keep_toc_entry(d)]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_qt + binaries_np,
    datas=[('Arial.ttf', '.')] + datas_qt + datas_np,
    hiddenimports=hidden_qt + hidden_np + [
        'PIL',
        'reportlab',
        'ufprint',
        'ufprint.bootstrap',
        'ufprint.paths',
        'ufprint.framing',
        'ufprint.styles',
        'ufprint.orders',
        'ufprint.company_config',
        'ufprint.pdf_export',
        'ufprint.editor',
        'ufprint.app_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PySide6', 'tkinter'],
    noarchive=False,
)

a.binaries = [b for b in a.binaries if _keep_toc_entry(b)]
a.datas = [d for d in a.datas if _keep_toc_entry(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UF_Print_Cards_App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='UF_Print_Cards_App',
)
