# -*- mode: python ; coding: utf-8 -*-
"""Build a Windows onedir bundle; user data stays under LOCALAPPDATA."""

from pathlib import Path

project_root = Path(SPECPATH).parent.parent
analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True,
          name="NotiAutomation", console=False)
coll = COLLECT(exe, analysis.binaries, analysis.datas,
               strip=False, upx=False, name="NotiAutomation")
