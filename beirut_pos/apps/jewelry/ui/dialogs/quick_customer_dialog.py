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


class QuickCustomerDialog(QDialog):
    def __init__(self, parent=None, *, name: str = "", phone: str = "") -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowTitle("Add New Customer")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit(name)
        self.phone_input = QLineEdit(phone)
        self.email_input = QLineEdit()
        self.notes_input = QLineEdit()

        self.name_label = QLabel("Name")
        self.phone_label = QLabel("Phone")
        self.email_label = QLabel("Email (optional)")
        self.notes_label = QLabel("Notes (optional)")
        form_layout.addRow(self.name_label, self.name_input)
        form_layout.addRow(self.phone_label, self.phone_input)
        form_layout.addRow(self.email_label, self.email_input)
        form_layout.addRow(self.notes_label, self.notes_input)
        layout.addLayout(form_layout)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
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
