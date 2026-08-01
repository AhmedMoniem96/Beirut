# Frozen Build Sanity Checklist (Windows)

## Known-good build recipe

```powershell
pyinstaller --noconfirm --clean BeirutPOS.spec
```

## Release smoke checklist

- [ ] Build completed without PyInstaller import warnings for `reportlab.graphics.barcode.*`.
- [ ] `build/BeirutPOS/warn-BeirutPOS.txt` has no missing-module warning for `win32print` or `pywintypes`.
- [ ] `dist/BeirutPOS.exe --frozen-smoke-test` exits successfully (this imports both modules and validates the pywintypes DLL runtime path).
- [ ] `dist/BeirutPOS.exe` starts successfully.
- [ ] App reaches main UI without "failed to execute script launcher" error.
- [ ] Barcode label generation works for: Code128, Code39, Code93, QR.
- [ ] PDF invoice export succeeds.
- [ ] PDF daily report export succeeds.
- [ ] Generated PDF opens and displays barcode section.

## Failure triage

If startup fails with missing ReportLab modules:
1. Rebuild from clean with the spec command above.
2. Confirm `BeirutPOS.spec` still includes ReportLab collect rules.
3. Treat launcher runtime aliases as fallback only; do not remove packaging hidden-import rules.
