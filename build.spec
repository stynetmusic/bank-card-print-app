# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import PyQt5

# Получаем путь к установленной библиотеке PyQt5 в окружении
pyqt5_path = os.path.dirname(PyQt5.__file__)
qt_plugins_path = os.path.join(pyqt5_path, 'Qt', 'plugins')

added_binaries = []
if sys.platform == 'win32':
    # Добавляем необходимые папки с плагинами Qt для корректной работы GUI
    if os.path.exists(qt_plugins_path):
        added_binaries.append((os.path.join(qt_plugins_path, 'platforms'), 'PyQt5/Qt/plugins/platforms'))
        added_binaries.append((os.path.join(qt_plugins_path, 'styles'), 'PyQt5/Qt/plugins/styles'))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=added_binaries,
    datas=[],
    hiddenimports=['PyQt5.sip'],
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
