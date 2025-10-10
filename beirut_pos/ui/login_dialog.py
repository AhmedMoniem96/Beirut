from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from ..core.auth import authenticate
from .forgot_password_dialog import ForgotPasswordDialog

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تسجيل الدخول — Beirut POS")
        self._user = None
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        v = QVBoxLayout(self)
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
