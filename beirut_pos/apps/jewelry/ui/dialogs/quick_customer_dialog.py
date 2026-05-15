"""Lightweight dialog to quickly add a new customer."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from ...services.i18n import get_ui_language, t


class QuickCustomerDialog(QDialog):
    def __init__(self, parent=None, *, name: str = "", phone: str = "") -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(420)
        language = get_ui_language()
        self.setWindowTitle(t("invoice.add_new_customer", language=language))

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit(name)
        self.phone_input = QLineEdit(phone)
        self.email_input = QLineEdit()
        self.notes_input = QLineEdit()

        self.name_label = QLabel(t("customers.customer_name", language=language))
        self.phone_label = QLabel(t("customers.phone", language=language))
        self.email_label = QLabel(t("quick_customer.email_optional", language=language))
        self.notes_label = QLabel(t("quick_customer.notes_optional", language=language))
        form_layout.addRow(self.name_label, self.name_input)
        form_layout.addRow(self.phone_label, self.phone_input)
        form_layout.addRow(self.email_label, self.email_input)
        form_layout.addRow(self.notes_label, self.notes_input)
        layout.addLayout(form_layout)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_btn = QPushButton(t("common.cancel", language=language))
        self.save_btn = QPushButton(t("common.save", language=language))
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

    def values(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "notes": self.notes_input.text().strip(),
        }
