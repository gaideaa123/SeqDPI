# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

datas = [('SeqDPI.pyw', '.')]
if os.path.exists('hello.mp3'):
    datas.append(('hello.mp3', '.'))
if os.path.exists('dns.mp3'):
    datas.append(('dns.mp3', '.'))

a = Analysis(
    ['SeqDPI_tray.pyw'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['tkinter', '_tkinter', 'tkinter.ttk', 'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw'],
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
    name='SeqDPI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    version='version_info.txt',
)
