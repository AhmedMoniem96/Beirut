"""Placeholder Jewelry application entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow


def run() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Jewelry (Coming Soon)")
    window.show()
    sys.exit(app.exec())


__all__ = ["run"]
