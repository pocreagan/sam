# -*- mode: python ; coding: utf-8 -*-

DIST_PATH = r'__DIST_PATH__'
DAT_PATH = r'__DAT_PATH__'
ENTRY_POINT = r'__ENTRY_POINT__'
ROOT_DIR = r'__ROOT_DIR__'
APP_NAME = r'__APP_NAME__'
ICON_PATH = r'__ICON_PATH__'

import PyInstaller.config
from pathlib import Path
import os

for k, v in (('distpath', Path(DIST_PATH)), ('workpath', Path(DAT_PATH) / 'dat' / 'Release')):
    if not v.exists():
        os.makedirs(v)
    PyInstaller.config.CONF[k] = str(v)

block_cipher = None

a = Analysis([ENTRY_POINT],
             pathex=[ROOT_DIR],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

from kivy_deps import sdl2, glew

exe = EXE(pyz,
          Tree(r'resources', prefix=r'resources'),
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
          name=APP_NAME,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon=ICON_PATH,
          )
