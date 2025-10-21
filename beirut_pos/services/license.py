"""Simple 10-day trial gate enforced via a numeric unlock code."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QLabel,
    QVBoxLayout,
)

from ..core.db import setting_get, setting_set
from . import texts
from .settings import get_client_name

_UNLOCK_CODE = 836


def _get_first_run_at() -> datetime:
    raw = setting_get("app_first_run_at", "")
    if not raw:
        now = datetime.utcnow()
        setting_set("app_first_run_at", now.isoformat())
        return now
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        now = datetime.utcnow()
        setting_set("app_first_run_at", now.isoformat())
        return now


def _is_activated() -> bool:
    return (setting_get("activated", "0") or "0") == "1"


def _set_activated() -> None:
    setting_set("activated", "1")


class _LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.get("license.block.title"))
        self.setModal(True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        client_name = get_client_name()
        message = texts.get("license.block.message", client_name=client_name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.input = QLineEdit()
        self.input.setValidator(QIntValidator(0, 999999, self))
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setMaxLength(6)
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow(texts.get("license.block.input"), self.input)

        layout.addLayout(form)

        self.error = QLabel("")
        self.error.setObjectName("licenseError")
        self.error.setStyleSheet("color: #ff6b6b; font-weight: 600;")
        self.error.setWordWrap(True)
        self.error.setVisible(False)
        layout.addWidget(self.error)

        buttons = QDialogButtonBox()
        self.btn_submit = buttons.addButton(
            texts.get("license.block.submit"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.btn_cancel = buttons.addButton(
            texts.get("license.block.cancel"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.btn_submit.clicked.connect(self._accept)
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.input.setFocus()

    def _accept(self) -> None:
        code = self.input.text().strip()
        if not code:
            self._show_error(texts.get("license.block.error"))
            return
        try:
            value = int(code)
        except ValueError:
            self._show_error(texts.get("license.block.error"))
            return
        if value == _UNLOCK_CODE:
            self.accept()
        else:
            self._show_error(texts.get("license.block.error"))

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.setVisible(True)


def ensure_trial_allowed(parent=None) -> bool:
    """Return True if the application may continue running."""

    if os.getenv("BEIRUT_DEV_LICENSE_BYPASS") == "1":
        return True

    first_run = _get_first_run_at()
    if _is_activated():
        return True

    if datetime.utcnow() <= first_run + timedelta(days=10):
        return True

    gate = _LicenseDialog(parent=parent)
    if gate.exec() == gate.DialogCode.Accepted:
        _set_activated()
        return True
    return False
