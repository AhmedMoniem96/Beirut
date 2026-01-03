from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from beirut_pos.services import customers as customers_service


class CustomerDialog(QDialog):
    def __init__(self, parent=None, *, customer_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("بيانات العميل")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)

        self.customer_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(10)
        layout.addLayout(form)

        phone_row = QHBoxLayout()
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("رقم الهاتف")
        self.phone_edit.setMinimumHeight(34)
        self.search_btn = QPushButton("بحث")
        self.search_btn.setMinimumHeight(34)
        self.search_btn.clicked.connect(self._lookup_phone)
        phone_row.addWidget(self.phone_edit, 1)
        phone_row.addWidget(self.search_btn, 0)
        form.addRow("الهاتف", phone_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("الاسم الكامل")
        self.name_edit.setMinimumHeight(34)
        form.addRow("الاسم", self.name_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("البريد الإلكتروني")
        self.email_edit.setMinimumHeight(34)
        form.addRow("البريد", self.email_edit)

        self.birthday_edit = QLineEdit()
        self.birthday_edit.setPlaceholderText("مثال: 1990-05-10")
        self.birthday_edit.setMinimumHeight(34)
        form.addRow("تاريخ الميلاد", self.birthday_edit)

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("ملاحظات")
        self.notes_edit.setMinimumHeight(34)
        form.addRow("ملاحظات", self.notes_edit)

        self.balance_label = QLabel("نقاط الولاء: —")
        self.balance_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.balance_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok.setText("حفظ")
        cancel.setText("إلغاء")
        buttons.accepted.connect(self._save_customer)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if customer_id:
            self._load_customer(customer_id)

    def _load_customer(self, customer_id: int) -> None:
        customer = customers_service.get_customer(customer_id)
        if not customer:
            return
        self.customer_id = int(customer["id"])
        self.phone_edit.setText(customer.get("phone") or "")
        self.name_edit.setText(customer.get("name") or "")
        self.email_edit.setText(customer.get("email") or "")
        self.birthday_edit.setText(customer.get("birthday") or "")
        self.notes_edit.setText(customer.get("notes") or "")
        balance = customers_service.get_loyalty_balance(self.customer_id)
        self.balance_label.setText(f"نقاط الولاء: {balance}")

    def _lookup_phone(self) -> None:
        phone = (self.phone_edit.text() or "").strip()
        if not phone:
            QMessageBox.information(self, "بحث العملاء", "أدخل رقم الهاتف أولاً.")
            return
        customer = customers_service.get_customer_by_phone(phone)
        if not customer:
            QMessageBox.information(self, "بحث العملاء", "لا يوجد عميل بهذا الرقم.")
            self.customer_id = None
            self.balance_label.setText("نقاط الولاء: —")
            return
        self._load_customer(int(customer["id"]))

    def _save_customer(self) -> None:
        name = (self.name_edit.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "حفظ العميل", "يرجى إدخال اسم العميل.")
            return
        phone = (self.phone_edit.text() or "").strip()
        email = (self.email_edit.text() or "").strip()
        birthday = (self.birthday_edit.text() or "").strip()
        notes = (self.notes_edit.text() or "").strip()
        if self.customer_id:
            customers_service.update_customer(
                self.customer_id,
                name=name,
                phone=phone,
                email=email,
                birthday=birthday,
                notes=notes,
            )
        else:
            self.customer_id = customers_service.create_customer(
                name,
                phone=phone,
                email=email,
                birthday=birthday,
                notes=notes,
            )
        balance = customers_service.get_loyalty_balance(self.customer_id)
        self.balance_label.setText(f"نقاط الولاء: {balance}")
        self.accept()
