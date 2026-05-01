# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "beirut_pos.apps.playstation.ui.theme.tokens",
    "beirut_pos.apps.playstation.ui.theme.components",
    "beirut_pos.apps.playstation.ui.common.branding",
    "beirut_pos.apps.playstation.ui.settings_branding",
]

hiddenimports.extend(collect_submodules("reportlab.graphics"))
hiddenimports.extend(collect_submodules("reportlab.graphics.barcode"))
hiddenimports.extend(collect_submodules("reportlab.pdfbase"))
hiddenimports.extend(collect_submodules("reportlab.pdfgen"))
hiddenimports.extend(collect_submodules("reportlab.lib"))
hiddenimports = sorted(set(hiddenimports))


a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BeirutPOS",
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
