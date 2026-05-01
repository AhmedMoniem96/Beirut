# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = []
for pkg in (
    "reportlab.graphics",
    "reportlab.graphics.barcode",
    "reportlab.pdfbase",
    "reportlab.pdfgen",
    "reportlab.lib",
):
    hiddenimports += collect_submodules(pkg)

# Defensive explicit include for historically-missed modules in frozen builds.
hiddenimports += [
    "reportlab.graphics.barcode.usps4s",
    "reportlab.graphics.barcode.code128",
    "reportlab.graphics.barcode.code39",
    "reportlab.graphics.barcode.code93",
    "reportlab.graphics.barcode.qr",
    "reportlab.graphics.renderPM",
    "reportlab.graphics.renderPDF",
    "reportlab.graphics.shapes",
]

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
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
