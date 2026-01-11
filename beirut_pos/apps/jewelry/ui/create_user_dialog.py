"""User creation dialog for Jewelry app."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..services.auth import ADMIN_ROLE, UsernameExistsError, authenticate_user, create_user
from ..services.i18n import get_ui_language, t


class CreateUserDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setWindowTitle(t("user_create.window_title", language=self._language))
        self.setModal(True)
        self.setMinimumWidth(460)

        self.result_message: str | None = None
        self.success = False
        self.created_username: str | None = None

        layout = QVBoxLayout(self)

        hint = QLabel()
        hint.setStyleSheet("color: #6e6a64;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.hint_label = hint

        form_layout = QFormLayout()
        self.admin_username_input = QLineEdit()
        self.admin_password_input = QLineEdit()
        self.admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.username_input = QLineEdit()
        self.full_name_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.role_input = QComboBox()
        self.role_input.addItem("", "Cashier")
        self.role_input.addItem("", "Admin")

        self.active_input = QCheckBox()
        self.active_input.setChecked(True)

        self.admin_username_label = QLabel()
        self.admin_password_label = QLabel()
        self.username_label = QLabel()
        self.full_name_label = QLabel()
        self.password_label = QLabel()
        self.confirm_password_label = QLabel()
        self.role_label = QLabel()
        form_layout.addRow(self.admin_username_label, self.admin_username_input)
        form_layout.addRow(self.admin_password_label, self.admin_password_input)
        form_layout.addRow(self.username_label, self.username_input)
        form_layout.addRow(self.full_name_label, self.full_name_input)
        form_layout.addRow(self.password_label, self.password_input)
        form_layout.addRow(self.confirm_password_label, self.confirm_password_input)
        form_layout.addRow(self.role_label, self.role_input)
        form_layout.addRow("", self.active_input)
        layout.addLayout(form_layout)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #b22b2b;")
        layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton()
        create_btn = QPushButton()
        cancel_btn.clicked.connect(self.reject)
        create_btn.clicked.connect(self._handle_create)
        actions.addWidget(cancel_btn)
        actions.addWidget(create_btn)
        layout.addLayout(actions)
        self.cancel_btn = cancel_btn
        self.create_btn = create_btn
        self.apply_language(self._language)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("user_create.window_title", language=language))
        self.hint_label.setText(t("user_create.hint", language=language))
        self.admin_username_label.setText(t("user_create.admin_username", language=language))
        self.admin_password_label.setText(t("user_create.admin_password", language=language))
        self.username_label.setText(t("user_create.username", language=language))
        self.full_name_label.setText(t("user_create.full_name", language=language))
        self.password_label.setText(t("user_create.password", language=language))
        self.confirm_password_label.setText(t("user_create.confirm_password", language=language))
        self.role_label.setText(t("user_create.role", language=language))
        self.active_input.setText(t("user_create.active", language=language))
        self.role_input.setItemText(0, t("user_create.role_cashier", language=language))
        self.role_input.setItemText(1, t("user_create.role_admin", language=language))
        self.cancel_btn.setText(t("user_create.cancel", language=language))
        self.create_btn.setText(t("user_create.create", language=language))

    def _handle_create(self) -> None:
        self.message_label.setText("")

        admin_result = authenticate_user(
            self.admin_username_input.text().strip(),
            self.admin_password_input.text(),
        )
        if not admin_result.user or admin_result.user.role != ADMIN_ROLE:
            self._set_error(t("user_create.admin_invalid", language=self._language))
            return

        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_password_input.text()

        if password != confirm:
            self._set_error(t("user_create.password_mismatch", language=self._language))
            return

        try:
            user = create_user(
                username,
                password,
                full_name=full_name,
                role=self.role_input.currentData(),
                is_active=self.active_input.isChecked(),
            )
        except UsernameExistsError as exc:
            self._set_error(str(exc))
            return
        except ValueError as exc:
            self._set_error(str(exc))
            return

        self.created_username = user.username
        self.result_message = t("user_create.success", language=self._language)
        self.success = True
        self._clear_sensitive()
        self.accept()

    def _set_error(self, message: str) -> None:
        self.message_label.setStyleSheet("color: #b22b2b;")
        self.message_label.setText(message)
        self.result_message = message
        self.success = False

    def _clear_sensitive(self) -> None:
        self.admin_password_input.clear()
        self.password_input.clear()
        self.confirm_password_input.clear()
