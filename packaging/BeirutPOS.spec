# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

spec_dir = Path(SPECPATH).resolve()
project_root = spec_dir if (spec_dir / "launcher.py").is_file() else spec_dir.parent

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

# pywin32 is Windows-only in requirements.txt. Its imports are partly dynamic, so
# make them explicit on Windows and collect pywin32_system32 (including the
# versioned pywintypes DLL) without making Linux/macOS builds require pywin32.
binaries = []
if sys.platform == "win32":
    hiddenimports += ["win32print", "pywintypes"]
    binaries += collect_dynamic_libs("pywin32_system32")

hiddenimports = sorted(set(hiddenimports))

escpos_datas = collect_data_files("escpos")


a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=[] + escpos_datas,
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
