# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Beirut POS.

Canonical build command:
    pyinstaller --noconfirm --clean BeirutPOS.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent

# Keep deterministic ordering so repeated builds generate stable TOCs.
datas = []
binaries = []

a = Analysis(
    ['launcher.py'],
    pathex=[str(project_root)],
    binaries=sorted(binaries, key=lambda item: tuple(str(part) for part in item)),
    datas=sorted(datas, key=lambda item: tuple(str(part) for part in item)),
    hiddenimports=sorted(
        set(
            collect_submodules('reportlab.graphics.barcode')
            + collect_submodules('reportlab.graphics')
        )
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BeirutPOS',
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
)
