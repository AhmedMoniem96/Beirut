# launcher.py — stable Windows entrypoint for PyInstaller

import os, sys, traceback, datetime


def _run_frozen_smoke_test() -> None:
    """Fail fast when Windows printing support is incomplete in a frozen build."""
    import pywintypes
    import win32print

    if not getattr(pywintypes, "__file__", None):
        raise RuntimeError("pywintypes DLL has no runtime path")
    if not hasattr(win32print, "EnumPrinters"):
        raise RuntimeError("win32print is missing EnumPrinters")


if "--frozen-smoke-test" in sys.argv:
    _run_frozen_smoke_test()
    raise SystemExit(0)

# Safe Qt defaults (software rendering, Windows platform)
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")


# Backward-compat shim for a recurring typo in some frozen builds.
# Packaging must still include the real ReportLab barcode/graphics submodules;
# this alias only preserves legacy typo imports ("barcorde"), not full dependency collection.
try:
    import reportlab.graphics.barcode as _rl_barcode
    sys.modules.setdefault("reportlab.graphics.barcorde", _rl_barcode)
    # Some ReportLab releases expose `usps4s` but not `usps`.
    # Keep typo-compat imports working by aliasing whichever exists.
    _legacy_usps = getattr(_rl_barcode, "usps", None) or getattr(_rl_barcode, "usps4s", None)
    if _legacy_usps is not None:
        # ReportLab widgets may import `reportlab.graphics.barcode.usps` directly,
        # while some versions only ship `usps4s`. Provide both aliases.
        sys.modules.setdefault("reportlab.graphics.barcode.usps", _legacy_usps)
        sys.modules.setdefault("reportlab.graphics.barcorde.usps", _legacy_usps)
except Exception:
    pass

def _write_crash(prefix: str, exc: BaseException | None = None) -> None:
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        fn = f"BeirutPOS-crash-{prefix}-{ts}.log"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"[{ts}] argv: {sys.argv}\n")
            for k in sorted(os.environ):
                if k.startswith("QT_") or k in ("PATH",):
                    f.write(f"{k}={os.environ.get(k)}\n")
            if exc:
                f.write("\n--- TRACEBACK ---\n")
                traceback.print_exc(file=f)
    except Exception:
        pass

try:
    from PyQt6.QtCore import QCoreApplication, Qt
    # must be set BEFORE QApplication is created
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
except Exception as e:
    _write_crash("pre-qt", e)
    raise

try:
    from beirut_pos.app_launcher import run
except Exception as e:
    _write_crash("import-app", e)
    raise

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        _write_crash("runtime", e)
        raise
