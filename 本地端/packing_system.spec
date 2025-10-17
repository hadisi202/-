# -*- mode: python ; coding: utf-8 -*-

import os
import glob
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

# Ensure paths are relative to spec location (本地端)
# Use working directory to avoid __file__ issues when loading spec
_pathex = [os.getcwd()]

# Data files: templates, custom templates, orders, configs and html preview
datas = [
    ('qr_settings.json', '.'),
    ('preview_component_display.html', '.'),
    ('templates', 'templates'),
    ('custom_templates', 'custom_templates'),
    ('orders', 'orders'),
]

# Collect pyzbar DLLs (libiconv.dll, libzbar*.dll) to fix runtime load
pyzbar_binaries = []
try:
    import pyzbar
    _pyzbar_dir = os.path.dirname(pyzbar.__file__)
    for dll in glob.glob(os.path.join(_pyzbar_dir, '*.dll')):
        pyzbar_binaries.append((dll, 'pyzbar'))
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=_pathex,
    binaries=pyzbar_binaries,
    datas=datas,
    hiddenimports=['pyzbar', 'pyzbar.pyzbar', 'pyzbar.wrapper'],
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
    name='PackingSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='ico10.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PackingSystem'
)