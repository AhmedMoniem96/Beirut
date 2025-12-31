"""Jewelry application entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QDialog

from beirut_pos.core.db import init_db

from .services.db import init_jewelry_db
from .ui.login_dialog import LoginDialog
from .ui.main_window import JewelryMainWindow


def run() -> None:
    init_db()
    init_jewelry_db()
    app = QApplication(sys.argv)
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    window = JewelryMainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["run"]
