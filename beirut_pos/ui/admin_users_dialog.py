from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import Qt
from ..core.db import get_conn
from ..core.auth import set_secret_key

class AdminUsersDialog(QDialog):
    def __init__(self, admin_user: str):
        super().__init__()
        self.setWindowTitle("إدارة المستخدمين (مفاتيح سرية)")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.admin_user = admin_user

        v = QVBoxLayout(self)
        v.addWidget(QLabel("اختر الكاشير وحدد المفتاح السري:"))

        self.users = QComboBox()
        for u in self._cashiers():
            self.users.addItem(u)
        v.addWidget(self.users)

        self.key = QLineEdit()
        self.key.setPlaceholderText("المفتاح السري الجديد")
        v.addWidget(self.key)

        row = QHBoxLayout()
        save = QPushButton("حفظ")
        close = QPushButton("إغلاق")
        row.addWidget(save); row.addWidget(close)
        v.addLayout(row)

        save.clicked.connect(self._save)
        close.clicked.connect(self.accept)

    def _cashiers(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE role='cashier' ORDER BY username")
        names = [r["username"] for r in cur.fetchall()]
        conn.close()
        return names

    def _save(self):
        user = self.users.currentText().strip()
        key = self.key.text().strip()
        if not user or not key:
            QMessageBox.warning(self, "بيانات ناقصة", "اختر المستخدم وأدخل المفتاح السري.")
            return
        set_secret_key(self.admin_user, user, key)
        QMessageBox.information(self, "تم", "تم تحديث المفتاح السري.")
        self.key.clear()
