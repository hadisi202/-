# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree

block_cipher = None

# Ensure paths are relative to spec location (本地端)
_pathex = [os.path.dirname(__file__)]

# Data files: templates, custom templates, orders, configs and html preview
datas = []
datas += [('qr_settings.json', '.')]
datas += [('preview_component_display.html', '.')]
datas += Tree('templates', prefix='templates')
datas += Tree('custom_templates', prefix='custom_templates')
datas += Tree('orders', prefix='orders')

a = Analysis(
    ['main.py'],
    pathex=_pathex,
    binaries=[],
    datas=datas,
    hiddenimports=[],
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