from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from ..core.auth import authenticate

class DiscountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تطبيق خصم (موافقة مدير)")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self.amount = 0
        self.reason = ""

        v = QVBoxLayout(self)
        v.addWidget(QLabel("مبلغ الخصم (بالقرش):"))
        self.sp = QSpinBox(); self.sp.setRange(0, 10_000_000); self.sp.setSingleStep(500)
        v.addWidget(self.sp)

        v.addWidget(QLabel("السبب:"))
        self.rea = QLineEdit(); self.rea.setPlaceholderText("مثال: موافقة المدير على خصم خاص")
        v.addWidget(self.rea)

        v.addWidget(QLabel("اسم مستخدم المدير:"))
        self.u = QLineEdit(); self.u.setPlaceholderText("admin"); v.addWidget(self.u)

        v.addWidget(QLabel("كلمة المرور:"))
        self.p = QLineEdit(); self.p.setEchoMode(QLineEdit.EchoMode.Password); v.addWidget(self.p)

        row = QHBoxLayout(); ok = QPushButton("تطبيق"); cancel = QPushButton("إلغاء")
        row.addWidget(ok); row.addWidget(cancel); v.addLayout(row)
        ok.clicked.connect(self._apply); cancel.clicked.connect(self.reject)

    def _apply(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if not user or user.role != "admin":
            QMessageBox.warning(self, "مرفوض", "بيانات المدير غير صحيحة."); return
        self.amount = int(self.sp.value()); self.reason = self.rea.text().strip()
        self.accept()
