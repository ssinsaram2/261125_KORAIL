# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정 — pyinstaller prompt98.spec --clean --noconfirm  →  dist\Prompt98.exe
# --onedir 판이 필요하면(백신 오탐 대비):  set PROMPT98_ONEDIR=1 후 같은 명령 → dist\Prompt98\Prompt98.exe
import os

ONEDIR = os.environ.get("PROMPT98_ONEDIR") == "1"

a = Analysis(
    ['prompt98/__main__.py'],
    pathex=['.'],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    excludes=['numpy', 'PIL', 'pytest', 'unittest', 'pydoc', 'test'],
    noarchive=False,
)
pyz = PYZ(a.pure)

if ONEDIR:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
              name='Prompt98', icon='resources/icons/app.ico',
              console=False, upx=False, version='version_info.txt')
    coll = COLLECT(exe, a.binaries, a.datas, name='Prompt98', upx=False)
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas,
              name='Prompt98', icon='resources/icons/app.ico',
              console=False, upx=False, version='version_info.txt')
