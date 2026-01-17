"""Application bootstrap wiring for the Beirut POS desktop client."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from beirut_pos.core.db import init_db, maybe_run_integrity_check
from beirut_pos.core.simple_voucher import is_activated, status as voucher_status
from beirut_pos.services.backup import ensure_daily_backup
from beirut_pos.services.license import ensure_trial_allowed
from beirut_pos.apps.playstation.ui.common.branding import get_logo_icon
from beirut_pos.apps.playstation.ui.login_dialog import LoginDialog
from beirut_pos.apps.playstation.ui.main_window import MainWindow
from beirut_pos.apps.playstation.ui.recovery_center_dialog import RecoveryCenterDialog
from beirut_pos.apps.playstation.ui.voucher_dialog import VoucherDialog
from beirut_pos.utils.error_handling import (
    console_notifier,
    guarded_call,
    install_global_exception_handlers,
)


def _console_notifier(title: str, message: str, details: str) -> None:
    console_notifier(title, message, details)


def _make_qt_notifier(parent=None):
    def _notify(title: str, message: str, details: str) -> None:
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setText(message)
        box.setDetailedText(details)
        box.setIcon(QMessageBox.Icon.Critical)
        box.exec()

    return _notify


def run() -> None:
    ok, _ = guarded_call("تهيئة قاعدة البيانات", init_db, notifier=_console_notifier)
    if not ok:
        sys.exit(1)

    guarded_call(
        "إنشاء النسخة الاحتياطية اليومية",
        ensure_daily_backup,
        notifier=_console_notifier,
    )

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    icon = get_logo_icon(128)
    if icon:
        app.setWindowIcon(icon)

    qt_notifier = _make_qt_notifier()
    install_global_exception_handlers("تشغيل Beirut POS", notifier=qt_notifier)

    ok, allowed = guarded_call(
        "التحقق من حالة الترخيص", ensure_trial_allowed, notifier=qt_notifier
    )
    if not ok or not allowed:
        sys.exit(0)

    ok, integrity = guarded_call(
        "فحص سلامة قاعدة البيانات", maybe_run_integrity_check, notifier=qt_notifier
    )
    if not ok or integrity is None:
        sys.exit(1)

    integrity_ok, result = integrity
    if not integrity_ok:
        dialog = RecoveryCenterDialog(issue_details=result)
        dialog.exec()
        if dialog.restored_path:
            sys.exit(0)

    ok, activated = guarded_call("التحقق من التفعيل", is_activated, notifier=qt_notifier)
    if not ok:
        sys.exit(1)

    if not activated:
        ok, status = guarded_call("قراءة حالة القسيمة", voucher_status, notifier=qt_notifier)
        if not ok:
            sys.exit(1)
        gate = VoucherDialog(status=status, fatal=True)
        if gate.exec() != gate.DialogCode.Accepted:
            sys.exit(0)
        ok, activated = guarded_call("التحقق من التفعيل", is_activated, notifier=qt_notifier)
        if not ok or not activated:
            sys.exit(0)

    login = LoginDialog()
    if login.exec() != login.DialogCode.Accepted:
        sys.exit(0)

    mw = MainWindow(current_user=login.get_user())
    print(f"[MainWindow] windowState before showMaximized: {mw.windowState()}")
    mw.showMaximized()
    print(f"[MainWindow] windowState after showMaximized: {mw.windowState()}")
    sys.exit(app.exec())


__all__ = ["run"]
