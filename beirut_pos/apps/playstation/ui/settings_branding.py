"""Settings tab for editing client branding and dynamic UI texts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction, QKeySequence
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QColorDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from ..services import texts
from ..services import settings as settings_service
from .common import branding
from .common.async_utils import Debouncer


class BrandingTextsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.client_name = QLineEdit(settings_service.get_client_name())
        self.client_name.setPlaceholderText(texts.get("settings.branding.client_name"))
        form.addRow(texts.get("settings.branding.client_name"), self.client_name)

        logo_row = QHBoxLayout()
        self.logo_path = QLineEdit(settings_service.get_client_logo_path())
        self.logo_path.setPlaceholderText(texts.get("settings.branding.logo"))
        btn_logo = QPushButton(texts.get("settings.branding.browse"))
        btn_logo.clicked.connect(self._choose_logo)
        logo_row.addWidget(self.logo_path, 1)
        logo_row.addWidget(btn_logo, 0)
        logo_widget = QWidget(); logo_widget.setLayout(logo_row)
        form.addRow(texts.get("settings.branding.logo"), logo_widget)

        color_row = QHBoxLayout()
        self.primary_color = QLineEdit(settings_service.get_primary_color())
        self.primary_color.setPlaceholderText(texts.get("settings.branding.primary_color"))
        btn_color = QPushButton(texts.get("settings.branding.browse"))
        btn_color.clicked.connect(self._choose_primary_color)
        color_row.addWidget(self.primary_color, 1)
        color_row.addWidget(btn_color, 0)
        color_widget = QWidget(); color_widget.setLayout(color_row)
        form.addRow(texts.get("settings.branding.primary_color"), color_widget)

        layout.addLayout(form)

        self.search = QLineEdit()
        self.search.setPlaceholderText(texts.get("settings.branding.search_placeholder"))
        layout.addWidget(self.search)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([
            texts.get("settings.branding.table_key"),
            texts.get("settings.branding.table_value"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton(texts.get("settings.branding.add_row"))
        self.btn_add.clicked.connect(self._add_row)
        self.btn_reset_selected = QPushButton(texts.get("settings.branding.reset_selected"))
        self.btn_reset_selected.clicked.connect(self._reset_selected)
        self.btn_reset_all = QPushButton(texts.get("settings.branding.reset_all"))
        self.btn_reset_all.clicked.connect(self._reset_all)
        self.btn_import = QPushButton(texts.get("settings.branding.import"))
        self.btn_import.clicked.connect(self._import_json)
        self.btn_export = QPushButton(texts.get("settings.branding.export"))
        self.btn_export.clicked.connect(self._export_json)

        for btn in (
            self.btn_add,
            self.btn_reset_selected,
            self.btn_reset_all,
            self.btn_import,
            self.btn_export,
        ):
            btn_row.addWidget(btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._load_texts()
        self._search_debouncer = Debouncer(self._apply_search_filter, delay_ms=220, parent=self)
        self.search.textChanged.connect(self._search_debouncer.trigger)

        # Shortcuts for convenience
        act_add = QAction(self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self._add_row)
        self.addAction(act_add)

    # ------------------------------------------------------------------ UI --
    def _choose_logo(self) -> None:
        current = self.logo_path.text().strip()
        start_dir = str(Path(current).parent) if current else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            texts.get("settings.branding.logo"),
            start_dir,
            "Images (*.png *.jpg *.jpeg *.ico)",
        )
        if file_path:
            self.logo_path.setText(file_path)

    def _choose_primary_color(self) -> None:
        current = QColor(self.primary_color.text().strip() or settings_service.DEFAULT_PRIMARY_COLOR)
        color = QColorDialog.getColor(current, self, texts.get("settings.branding.primary_color"))
        if color.isValid():
            self.primary_color.setText(color.name())

    def _apply_search_filter(self, needle: str) -> None:
        needle = (needle or "").strip().lower()
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            key_text = key_item.text().lower() if key_item else ""
            value_text = value_item.text().lower() if value_item else ""
            visible = not needle or needle in key_text or needle in value_text
            self.table.setRowHidden(row, not visible)

    def _add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.scrollToBottom()
        self.table.setCurrentCell(row, 0)

    def _reset_selected(self) -> None:
        rows = {index.row() for index in self.table.selectedIndexes()}
        if not rows:
            return
        for row in rows:
            key_item = self.table.item(row, 0)
            if key_item is None:
                continue
            key = key_item.text()
            default = texts.DEFAULT_TEXTS.get(key, "")
            self._ensure_value_item(row).setText(default)

    def _reset_all(self) -> None:
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            if key_item is None:
                continue
            key = key_item.text()
            default = texts.DEFAULT_TEXTS.get(key, "")
            self._ensure_value_item(row).setText(default)

    def _ensure_value_item(self, row: int) -> QTableWidgetItem:
        item = self.table.item(row, 1)
        if item is None:
            item = QTableWidgetItem("")
            self.table.setItem(row, 1, item)
        return item

    def _import_json(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            texts.get("settings.branding.import"),
            "",
            "JSON (*.json)",
        )
        if not file_path:
            return
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            overrides = texts.import_json(content)
        except Exception:
            QMessageBox.warning(
                self,
                texts.get("settings.branding.import"),
                texts.get("settings.branding.import_error"),
            )
            return

        merged = texts.get_all()
        merged.update(overrides)
        self._populate_from_dict(merged)
        QMessageBox.information(
            self,
            texts.get("settings.branding.import"),
            texts.get("settings.branding.import_success"),
        )

    def _export_json(self) -> None:
        try:
            data = self._collect_table_data(show_dialog=True)
        except ValueError:
            return
        overrides = texts.calculate_overrides(data)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            texts.get("settings.branding.export"),
            "",
            "JSON (*.json)",
        )
        if not file_path:
            return
        Path(file_path).write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load_texts(self) -> None:
        self._populate_from_dict(texts.get_all())

    def _populate_from_dict(self, data: Dict[str, str]) -> None:
        self.table.setRowCount(0)
        for key in sorted(data):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(key))
            self.table.setItem(row, 1, QTableWidgetItem(data[key]))

    def _collect_table_data(self, *, show_dialog: bool = False) -> Dict[str, str]:
        data: Dict[str, str] = {}
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            if key_item is None:
                continue
            key = key_item.text().strip()
            value = value_item.text() if value_item else ""
            if not key:
                continue
            if key in data:
                message = texts.get("settings.branding.duplicate_key", key=key)
                if show_dialog:
                    QMessageBox.warning(
                        self,
                        texts.get("settings.branding.tab"),
                        message,
                    )
                raise ValueError(message)
            data[key] = value
        return data

    # ----------------------------------------------------------------- Save --
    def apply_changes(self) -> None:
        data = self._collect_table_data()

        overrides = texts.calculate_overrides(data)
        texts.replace_overrides(overrides)

        settings_service.set_client_name(self.client_name.text())
        settings_service.set_client_logo_path(self.logo_path.text())
        settings_service.set_primary_color(self.primary_color.text())
        branding.clear_branding_cache()

