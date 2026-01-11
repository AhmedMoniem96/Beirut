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
from ..services.i18n import get_ui_language, t


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setWindowTitle(t("forgot.window_title", language=self._language))
        self.setModal(True)
        self.setMinimumWidth(420)

        self.result_message: str | None = None
        self.success = False

        layout = QVBoxLayout(self)

        hint = QLabel()
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6e6a64;")
        layout.addWidget(hint)
        self.hint_label = hint

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

        self.username_label = QLabel()
        self.new_password_label = QLabel()
        self.confirm_password_label = QLabel()
        self.admin_username_label = QLabel()
        self.admin_password_label = QLabel()
        self.secret_key_label = QLabel()
        form_layout.addRow(self.username_label, self.username_input)
        form_layout.addRow(self.new_password_label, self.new_password_input)
        form_layout.addRow(self.confirm_password_label, self.confirm_password_input)
        form_layout.addRow(self.admin_username_label, self.admin_username_input)
        form_layout.addRow(self.admin_password_label, self.admin_password_input)
        form_layout.addRow(self.secret_key_label, self.secret_key_input)
        layout.addLayout(form_layout)

        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #b22b2b;")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        reset_btn = QPushButton()
        cancel_btn = QPushButton()
        reset_btn.clicked.connect(self._handle_reset)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)
        actions.addWidget(reset_btn)
        layout.addLayout(actions)
        self.reset_btn = reset_btn
        self.cancel_btn = cancel_btn
        self.apply_language(self._language)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("forgot.window_title", language=language))
        self.hint_label.setText(t("forgot.hint", language=language))
        self.username_label.setText(t("forgot.username", language=language))
        self.new_password_label.setText(t("forgot.new_password", language=language))
        self.confirm_password_label.setText(t("forgot.confirm_password", language=language))
        self.admin_username_label.setText(t("forgot.admin_username", language=language))
        self.admin_password_label.setText(t("forgot.admin_password", language=language))
        self.secret_key_label.setText(t("forgot.secret_key", language=language))
        self.reset_btn.setText(t("forgot.reset", language=language))
        self.cancel_btn.setText(t("forgot.cancel", language=language))

    def _handle_reset(self) -> None:
        self.message_label.setText("")

        username = self.username_input.text().strip()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if new_password != confirm_password:
            self._set_error(t("forgot.password_mismatch", language=self._language))
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
