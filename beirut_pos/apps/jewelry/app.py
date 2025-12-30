"""Jewelry application entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from beirut_pos.core.db import init_db

from .services.db import init_jewelry_db
from .ui.main_window import JewelryMainWindow


def run() -> None:
    init_db()
    init_jewelry_db()
    app = QApplication(sys.argv)
    window = JewelryMainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["run"]
