# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import sys

datas_qt, binaries_qt, hidden_qt = collect_all('PyQt5')
datas_np, binaries_np, hidden_np = collect_all('numpy')

try:
    import PyQt5
    pyqt_root = os.path.dirname(PyQt5.__file__)
    qt_bin_dir = os.path.join(pyqt_root, 'Qt', 'bin')
    if os.path.isdir(qt_bin_dir):
        for entry in os.listdir(qt_bin_dir):
            full_path = os.path.join(qt_bin_dir, entry)
            if os.path.isfile(full_path):
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
            full_path = os.path.join(numpy_libs_dir, entry)
            if os.path.isfile(full_path):
                binaries_np.append((full_path, 'numpy/libs'))
except Exception:
    pass

vc_runtime_dlls = []
if sys.platform == 'win32':
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    for dll_name in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll'):
        dll_path = os.path.join(system_root, 'System32', dll_name)
        if os.path.exists(dll_path):
            vc_runtime_dlls.append((dll_path, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_qt + binaries_np + vc_runtime_dlls,
    datas=[('Arial.ttf', '.')] + datas_qt + datas_np,
    hiddenimports=hidden_qt + hidden_np + ['PIL', 'reportlab'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PySide6', 'tkinter'],
    noarchive=False,
)

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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='UF_Print_Cards_App',
)
