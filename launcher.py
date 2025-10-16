# launcher.py — stable Windows entrypoint for PyInstaller

import os, sys, traceback, datetime

# Force safe Qt defaults (pre-GUI)
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_ANGLE_PLATFORM", "swiftshader")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-software-rasterizer")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

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
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
except Exception as e:
    _write_crash("pre-qt", e)
    raise

try:
    from beirut_pos.app import main
except Exception as e:
    _write_crash("import-app", e)
    raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _write_crash("runtime", e)
        raise
