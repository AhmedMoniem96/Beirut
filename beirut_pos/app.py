"""Application bootstrap wiring for the Beirut POS desktop client."""

import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from .core.db import init_db, maybe_run_integrity_check
from .core.simple_voucher import is_activated, status as voucher_status
from .services.backup import ensure_daily_backup
from .ui.common.branding import get_logo_icon
from .ui.login_dialog import LoginDialog
from .ui.main_window import MainWindow
from .ui.voucher_dialog import VoucherDialog
from .ui.recovery_center_dialog import RecoveryCenterDialog
from .services.license import ensure_trial_allowed

def _qt_excepthook(exctype, value, tb):
    # Show the exception instead of killing the app silently
    msg = "".join(traceback.format_exception(exctype, value, tb))
    box = QMessageBox()
    box.setWindowTitle("Unexpected Error")
    box.setText("حدث خطأ غير متوقع.\nسيظل البرنامج يعمل.")
    box.setDetailedText(msg)
    box.setIcon(QMessageBox.Icon.Critical)
    box.exec()

def main():
    sys.excepthook = _qt_excepthook

    init_db()
    ensure_daily_backup()

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    icon = get_logo_icon(128)
    if icon:
        app.setWindowIcon(icon)

    if not ensure_trial_allowed():
        sys.exit(0)

    ok, result = maybe_run_integrity_check()
    if not ok:
        dialog = RecoveryCenterDialog(issue_details=result)
        dialog.exec()
        if dialog.restored_path:
            sys.exit(0)

    if not is_activated():
        gate = VoucherDialog(status=voucher_status(), fatal=True)
        if gate.exec() != gate.DialogCode.Accepted:
            sys.exit(0)
        if not is_activated():
            sys.exit(0)

    login = LoginDialog()
    if login.exec() != login.DialogCode.Accepted:
        sys.exit(0)

    mw = MainWindow(current_user=login.get_user())
    mw.show()
    sys.exit(app.exec())
