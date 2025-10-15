"""Application bootstrap wiring for the Beirut POS desktop client."""

import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from .core.db import init_db, maybe_run_integrity_check
from .core.simple_voucher import is_activated, status as voucher_status
from .services.backup import ensure_daily_backup, latest_backup_path, restore_backup
from .ui.common.branding import get_logo_icon
from .ui.login_dialog import LoginDialog
from .ui.main_window import MainWindow
from .ui.voucher_dialog import VoucherDialog

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

    ok, result = maybe_run_integrity_check()
    if not ok:
        latest = latest_backup_path()
        box = QMessageBox()
        box.setWindowTitle("تحذير سلامة قاعدة البيانات")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("تم اكتشاف مشكلة في قاعدة البيانات.")
        box.setInformativeText(result)
        restore_button = None
        if latest and latest.exists():
            restore_button = box.addButton("استرجاع أحدث نسخة", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("متابعة (غير مستحسن)", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if restore_button and box.clickedButton() == restore_button:
            try:
                restore_backup(latest)
            except Exception as exc:
                QMessageBox.critical(
                    None,
                    "فشل الاستعادة",
                    f"تعذر استرجاع النسخة الاحتياطية:\n{exc}",
                )
            else:
                QMessageBox.information(
                    None,
                    "تم الاستعادة",
                    "تمت استعادة قاعدة البيانات من النسخة الأخيرة. سيتم إغلاق التطبيق الآن، الرجاء إعادة تشغيله.",
                )
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
