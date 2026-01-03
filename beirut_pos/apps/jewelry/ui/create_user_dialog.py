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


class CreateUserDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New User")
        self.setModal(True)
        self.setMinimumWidth(460)

        self.result_message: str | None = None
        self.success = False
        self.created_username: str | None = None

        layout = QVBoxLayout(self)

        hint = QLabel("Admin credentials are required to create new users.")
        hint.setStyleSheet("color: #6e6a64;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

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
        self.role_input.addItem("Cashier", "Cashier")
        self.role_input.addItem("Admin", "Admin")

        self.active_input = QCheckBox("Active")
        self.active_input.setChecked(True)

        form_layout.addRow("Admin username:", self.admin_username_input)
        form_layout.addRow("Admin password:", self.admin_password_input)
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Full name:", self.full_name_input)
        form_layout.addRow("Password:", self.password_input)
        form_layout.addRow("Confirm password:", self.confirm_password_input)
        form_layout.addRow("Role:", self.role_input)
        form_layout.addRow("", self.active_input)
        layout.addLayout(form_layout)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #b22b2b;")
        layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton("Cancel")
        create_btn = QPushButton("Create")
        cancel_btn.clicked.connect(self.reject)
        create_btn.clicked.connect(self._handle_create)
        actions.addWidget(cancel_btn)
        actions.addWidget(create_btn)
        layout.addLayout(actions)

    def _handle_create(self) -> None:
        self.message_label.setText("")

        admin_result = authenticate_user(
            self.admin_username_input.text().strip(),
            self.admin_password_input.text(),
        )
        if not admin_result.user or admin_result.user.role != ADMIN_ROLE:
            self._set_error("Admin credentials are invalid.")
            return

        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_password_input.text()

        if password != confirm:
            self._set_error("Passwords do not match.")
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
        self.result_message = "User created successfully."
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
