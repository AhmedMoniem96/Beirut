"""Dialog for loyalty program settings."""

from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...services.i18n import get_ui_language, t


class LoyaltySettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.points_per_100_input = QDoubleSpinBox()
        self.points_per_100_input.setDecimals(2)
        self.points_per_100_input.setRange(0.0, 1000000.0)
        self.points_per_100_input.setSingleStep(0.25)

        self.alert_threshold_input = QSpinBox()
        self.alert_threshold_input.setRange(0, 1000000)
        self.alert_threshold_input.setSingleStep(10)

        self.auto_print_input = QCheckBox()

        self.points_per_100_label = QLabel()
        self.alert_threshold_label = QLabel()
        form_layout.addRow(self.points_per_100_label, self.points_per_100_input)
        form_layout.addRow(self.alert_threshold_label, self.alert_threshold_input)
        form_layout.addRow("", self.auto_print_input)
        layout.addLayout(form_layout)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton()
        save_btn = QPushButton()
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._save_settings)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        layout.addLayout(actions)

        self.cancel_btn = cancel_btn
        self.save_btn = save_btn

        self._load_settings()
        self.apply_language(self._language)

    def _load_settings(self) -> None:
        settings = QSettings()
        points_per_100 = settings.value("loyalty_points_per_100", 1.0, float)
        alert_threshold = settings.value("loyalty_alert_threshold", 0, int)
        auto_print = settings.value("loyalty_auto_print", False, bool)
        self.points_per_100_input.setValue(points_per_100)
        self.alert_threshold_input.setValue(alert_threshold)
        self.auto_print_input.setChecked(auto_print)

    def _save_settings(self) -> None:
        settings = QSettings()
        settings.setValue("loyalty_points_per_100", self.points_per_100_input.value())
        settings.setValue("loyalty_alert_threshold", self.alert_threshold_input.value())
        settings.setValue("loyalty_auto_print", self.auto_print_input.isChecked())
        self.accept()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("loyalty.settings.title", language=language))
        self.points_per_100_label.setText(t("loyalty.settings.points_per_100", language=language))
        self.alert_threshold_label.setText(t("loyalty.settings.alert_threshold", language=language))
        self.auto_print_input.setText(t("loyalty.settings.auto_print", language=language))
        self.cancel_btn.setText(t("loyalty.settings.cancel", language=language))
        self.save_btn.setText(t("loyalty.settings.save", language=language))
