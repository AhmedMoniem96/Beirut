# launcher.py — safe entry for PyInstaller on Windows

import os

# ---- Force software rendering (prevents GPU/driver crashes) ----
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("QT_ANGLE_PLATFORM", "swiftshader")  # ANGLE software path
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-software-rasterizer")

from PyQt6.QtCore import QCoreApplication, Qt
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

# ---- Import your real app via package (so relative imports work) ----
from beirut_pos.app import main

if __name__ == "__main__":
    main()
