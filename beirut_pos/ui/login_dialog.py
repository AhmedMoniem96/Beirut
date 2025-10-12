from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ..core.auth import authenticate
from .forgot_password_dialog import ForgotPasswordDialog
from .common.branding import get_logo_pixmap, get_logo_icon

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تسجيل الدخول — Beirut POS")
        self._user = None
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        icon = get_logo_icon(96)
        if icon:
            self.setWindowIcon(icon)

        v = QVBoxLayout(self)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_logo()
        v.addWidget(self.logo)
        self.msg = QLabel("من فضلك أدخل بيانات الدخول")
        self.u = QLineEdit(); self.u.setPlaceholderText("اسم المستخدم")
        self.p = QLineEdit(); self.p.setPlaceholderText("كلمة المرور"); self.p.setEchoMode(QLineEdit.EchoMode.Password)
        row = QHBoxLayout()
        self.btn = QPushButton("دخول")
        self.forgot = QPushButton("نسيت كلمة المرور؟")
        self.forgot.setFlat(True)
        row.addWidget(self.btn); row.addWidget(self.forgot)
        v.addWidget(self.msg); v.addWidget(self.u); v.addWidget(self.p); v.addLayout(row)

        self.btn.clicked.connect(self._do_login)
        self.p.returnPressed.connect(self._do_login)
        self.forgot.clicked.connect(self._open_forgot)

    def _do_login(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if user:
            self._user = user
            self.accept()
        else:
            self.msg.setText("بيانات غير صحيحة. حاول مرة أخرى.")

    def _open_forgot(self):
        dlg = ForgotPasswordDialog()
        dlg.exec()

    def get_user(self): return self._user

    def _apply_logo(self):
        pix = get_logo_pixmap(120)
        if pix:
            self.logo.setPixmap(pix)
            self.logo.setText("")
            self.logo.setStyleSheet("")
        else:
            self.logo.clear()
            self.logo.setText("Beirut POS")
            self.logo.setStyleSheet("font-size: 20pt; font-weight: 600;")
