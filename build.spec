# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

qt_data = collect_all('PyQt5')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_data['binaries'],
    datas=qt_data['datas'],
    hiddenimports=qt_data['hiddenimports'] + ['PyQt5.sip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='UF_Print_Cards_App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)