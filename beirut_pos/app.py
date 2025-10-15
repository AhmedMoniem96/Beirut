from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from .core.db import init_db, maybe_run_integrity_check
from .core.license import license_status
from .ui.license_dialog import LicenseDialog
from .ui.login_dialog import LoginDialog
from .ui.main_window import MainWindow
from .ui.common.branding import get_logo_icon
import sys
import traceback

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

    login = LoginDialog()
    if login.exec() != login.DialogCode.Accepted:
        sys.exit(0)

    mw = MainWindow(current_user=login.get_user())
    mw.show()
    sys.exit(app.exec())
