# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas_qt, binaries_qt, hidden_qt = collect_all('PyQt6')
datas_np, binaries_np, hidden_np = collect_all('numpy')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_qt + binaries_np,
    datas=datas_qt + datas_np,
    hiddenimports=hidden_qt + hidden_np + ['PIL', 'reportlab'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'tkinter'],
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
