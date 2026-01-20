"""Jewelry application entrypoint."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from beirut_pos.core.db import init_db
from beirut_pos.utils.error_handling import (
    console_notifier,
    guarded_call,
    install_global_exception_handlers,
)

from .services.db import init_jewelry_db
from .ui.login_dialog import LoginDialog
from .ui.main_window import JewelryMainWindow


def _make_notifier(parent=None):
    def _notify(title: str, message: str, details: str) -> None:
        if QApplication.instance() is None:
            console_notifier(title, message, details)
            return
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(message)
        box.setDetailedText(details)
        box.setIcon(QMessageBox.Icon.Critical)
        box.exec()

    return _notify


def run() -> None:
    notifier = _make_notifier()
    ok, _ = guarded_call("تهيئة قاعدة البيانات", init_db, notifier=notifier)
    if not ok:
        sys.exit(1)
    ok, _ = guarded_call("تهيئة قاعدة بيانات المجوهرات", init_jewelry_db, notifier=notifier)
    if not ok:
        sys.exit(1)
    app = QApplication(sys.argv)
    install_global_exception_handlers("تشغيل Beirut POS", notifier=_make_notifier())
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    window = JewelryMainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["run"]
