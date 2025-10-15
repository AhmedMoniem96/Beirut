from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..core.simple_voucher import activate, format_voucher, status as voucher_status


class VoucherDialog(QDialog):
    """Prompt the operator to enter a voucher code to unlock the POS."""

    def __init__(self, status: dict | None = None, *, fatal: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تفعيل البرنامج")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._fatal = fatal

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        intro = QLabel(
            "أدخل رمز القسيمة من مزود البرنامج بصيغة <b>BEIRUT-XXXX-XXXX-XXXX-X</b>."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        form = QFormLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("مثال: BEIRUT-ABCD-EFGH-IJKL-M")
        self.input.setMaxLength(32)
        self.input.returnPressed.connect(self._attempt_activate)
        form.addRow("رمز القسيمة:", self.input)
        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_activate = QPushButton("تفعيل")
        self.btn_activate.clicked.connect(self._attempt_activate)
        btn_row.addWidget(self.btn_activate)

        self.btn_close = QPushButton("خروج" if fatal else "إغلاق")
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        root.addLayout(btn_row)

        self._update_status(status or voucher_status())

        if fatal:
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
            self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    def _attempt_activate(self):
        code = self.input.text().strip()
        ok, message = activate(code)
        formatted = format_voucher(code)
        self.input.setText(formatted)
        current = voucher_status()
        self._update_status(current)
        if ok:
            QMessageBox.information(self, "تم", message)
            self.accept()
        else:
            QMessageBox.warning(self, "فشل", message)
            self.input.selectAll()
            self.input.setFocus()

    def _update_status(self, status: dict):
        active = status.get("activated", False)
        if active:
            suffix = status.get("voucher_suffix")
            activated_at = status.get("activated_at")
            message = "✅ البرنامج مفعل." 
            if suffix:
                message += f"\nرمز مفعل منتهي بـ {suffix}."
            if activated_at:
                message += f"\nآخر تفعيل: {activated_at}"
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #16a34a; font-weight: 600;")
            self.btn_activate.setEnabled(False)
            self.input.setEnabled(False)
            self.btn_close.setText("متابعة")
        else:
            self.status_label.setText("❌ لم يتم تفعيل النسخة بعد.")
            self.status_label.setStyleSheet("color: #dc2626; font-weight: 600;")
            self.btn_activate.setEnabled(True)
            self.input.setEnabled(True)
            if not self._fatal:
                self.btn_close.setText("إغلاق")
            else:
                self.btn_close.setText("خروج")
