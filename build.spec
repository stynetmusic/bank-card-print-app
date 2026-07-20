# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_all
import os

pyqt_binaries = collect_dynamic_libs('PyQt6')
pyqt_datas = collect_data_files('PyQt6')
pyqt_hiddenimports = []
try:
    _, _, _hidden = collect_all('PyQt6')
    pyqt_hiddenimports = _hidden
except Exception:
    pass

try:
    import PyQt6
    pyqt_root = os.path.dirname(PyQt6.__file__)
    qt_bin_dir = os.path.join(pyqt_root, 'Qt', 'bin')
    if os.path.isdir(qt_bin_dir):
        for entry in os.listdir(qt_bin_dir):
            full_path = os.path.join(qt_bin_dir, entry)
            if os.path.isfile(full_path):
                pyqt_binaries.append((full_path, 'PyQt6/Qt/bin'))
except Exception:
    pass

vc_dlls = []
system_root = os.environ.get('SystemRoot', 'C:\\Windows')
for dll_name in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
    dll_path = os.path.join(system_root, 'System32', dll_name)
    if os.path.exists(dll_path):
        vc_dlls.append((dll_path, '.'))

datas = [('Arial.ttf', '.')] + pyqt_datas
binaries = pyqt_binaries + vc_dlls
hiddenimports = ['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'] + pyqt_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
