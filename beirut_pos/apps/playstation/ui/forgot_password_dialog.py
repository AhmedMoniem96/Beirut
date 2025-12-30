# beirut_pos/ui/forgot_password_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from ..core.auth import reset_password_with_secret

class ForgotPasswordDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("استعادة كلمة المرور")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        v = QVBoxLayout(self)

        v.addWidget(QLabel("أدخل اسم المستخدم والمفتاح السري ثم كلمة المرور الجديدة:"))

        self.u = QLineEdit()
        self.u.setPlaceholderText("اسم المستخدم")
        v.addWidget(self.u)

        self.k = QLineEdit()
        self.k.setPlaceholderText("المفتاح السري")
        v.addWidget(self.k)

        self.n = QLineEdit()
        self.n.setPlaceholderText("كلمة مرور جديدة")
        self.n.setEchoMode(QLineEdit.EchoMode.Password)
        v.addWidget(self.n)

        save = QPushButton("حفظ")
        save.clicked.connect(self._do_reset)
        v.addWidget(save)

    def _do_reset(self):
        ok = reset_password_with_secret(
            self.u.text().strip(),
            self.k.text().strip(),
            self.n.text()
        )
        if ok:
            QMessageBox.information(self, "تم", "تم تغيير كلمة المرور بنجاح.")
            self.accept()
        else:
            QMessageBox.warning(self, "فشل", "المفتاح السري أو اسم المستخدم غير صحيح.")
