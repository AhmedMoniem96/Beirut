"""Password reset dialog for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..services.auth import reset_password


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reset Password")
        self.setModal(True)
        self.setMinimumWidth(420)

        self.result_message: str | None = None
        self.success = False

        layout = QVBoxLayout(self)

        hint = QLabel("Use admin credentials or the secret key to reset a password.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6e6a64;")
        layout.addWidget(hint)

        form_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_username_input = QLineEdit()
        self.admin_password_input = QLineEdit()
        self.admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_key_input = QLineEdit()

        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("New password:", self.new_password_input)
        form_layout.addRow("Confirm password:", self.confirm_password_input)
        form_layout.addRow("Admin username:", self.admin_username_input)
        form_layout.addRow("Admin password:", self.admin_password_input)
        form_layout.addRow("Secret key:", self.secret_key_input)
        layout.addLayout(form_layout)

        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #b22b2b;")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        reset_btn = QPushButton("Reset")
        cancel_btn = QPushButton("Cancel")
        reset_btn.clicked.connect(self._handle_reset)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)
        actions.addWidget(reset_btn)
        layout.addLayout(actions)

    def _handle_reset(self) -> None:
        self.message_label.setText("")

        username = self.username_input.text().strip()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if new_password != confirm_password:
            self._set_error("Passwords do not match.")
            return

        success, message = reset_password(
            username,
            new_password,
            admin_username=self.admin_username_input.text(),
            admin_password=self.admin_password_input.text(),
            secret_key=self.secret_key_input.text(),
        )

        self.result_message = message
        self.success = success

        if success:
            self._clear_sensitive()
            self.accept()
        else:
            self._set_error(message)

    def _set_error(self, message: str) -> None:
        self.message_label.setStyleSheet("color: #b22b2b;")
        self.message_label.setText(message)

    def _clear_sensitive(self) -> None:
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self.admin_password_input.clear()
        self.secret_key_input.clear()
