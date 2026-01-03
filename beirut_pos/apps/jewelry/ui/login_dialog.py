"""Login dialog for Jewelry app."""

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
    QWidget,
)

from ..services.auth import authenticate_user
from ..services.session import get_bootstrap_warning, set_current_user
from .create_user_dialog import CreateUserDialog
from .forgot_password_dialog import ForgotPasswordDialog


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Jewelry Login")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        title = QLabel("Crystal Gallery Login")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #b22b2b; font-weight: bold;")
        warning_text = get_bootstrap_warning()
        if warning_text:
            self.warning_label.setText(warning_text)
            layout.addWidget(self.warning_label)

        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        layout.addWidget(form_frame)

        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #6e6a64;")
        layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self._attempt_login)
        actions.addWidget(self.login_btn)
        layout.addLayout(actions)

        links = QHBoxLayout()
        self.forgot_btn = self._build_link_button("Forgot password")
        self.new_user_btn = self._build_link_button("New user")
        links.addStretch()
        links.addWidget(self.forgot_btn)
        links.addWidget(self.new_user_btn)
        links.addStretch()
        layout.addLayout(links)

        self.forgot_btn.clicked.connect(self._open_forgot_password)
        self.new_user_btn.clicked.connect(self._open_create_user)

    def _build_link_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFlat(True)
        button.setStyleSheet(
            "QPushButton { border: none; color: #a67c52; text-decoration: underline; }"
            "QPushButton:hover { color: #8c6745; }"
        )
        return button

    def _set_message(self, message: str, *, kind: str = "info") -> None:
        palette = {
            "info": "#6e6a64",
            "error": "#b22b2b",
            "success": "#2e7d32",
        }
        self.message_label.setStyleSheet(f"color: {palette.get(kind, '#6e6a64')};")
        self.message_label.setText(message)

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        result = authenticate_user(username, password)
        if result.user:
            set_current_user(result.user)
            if get_bootstrap_warning():
                QMessageBox.warning(self, "Default Admin", get_bootstrap_warning())
            self.accept()
            return
        self._set_message(result.message, kind="error")

    def _open_forgot_password(self) -> None:
        dialog = ForgotPasswordDialog(self)
        dialog.exec()
        if dialog.result_message:
            kind = "success" if dialog.success else "error"
            self._set_message(dialog.result_message, kind=kind)
            self.password_input.clear()

    def _open_create_user(self) -> None:
        dialog = CreateUserDialog(self)
        dialog.exec()
        if dialog.result_message:
            kind = "success" if dialog.success else "error"
            self._set_message(dialog.result_message, kind=kind)
            self.password_input.clear()
        if dialog.created_username:
            self.username_input.setText(dialog.created_username)
