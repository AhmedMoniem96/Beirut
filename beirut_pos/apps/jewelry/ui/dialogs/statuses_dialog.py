"""Dialog for managing delivery/payment statuses."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QCheckBox,
)

from ...services.db import (
    JewelryStatusItem,
    create_status,
    disable_status,
    list_statuses,
    update_status,
)
from ...services.i18n import get_ui_language, t


class StatusFormDialog(QDialog):
    def __init__(
        self,
        status_group: str,
        status: Optional[JewelryStatusItem] = None,
        default_sort_order: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self._status_group = status_group
        self._status = status
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.group_value = QLabel()
        self.name_ar_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.sort_order_input = QSpinBox()
        self.sort_order_input.setRange(0, 9999)
        self.active_check = QCheckBox()

        self.group_label = QLabel()
        self.name_ar_label = QLabel()
        self.name_en_label = QLabel()
        self.sort_order_label = QLabel()

        form_layout.addRow(self.group_label, self.group_value)
        form_layout.addRow(self.name_ar_label, self.name_ar_input)
        form_layout.addRow(self.name_en_label, self.name_en_input)
        form_layout.addRow(self.sort_order_label, self.sort_order_input)
        form_layout.addRow("", self.active_check)
        layout.addLayout(form_layout)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_btn = QPushButton()
        self.save_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)

        self._load_status(default_sort_order)
        self.apply_language(self._language)

    def _load_status(self, default_sort_order: int) -> None:
        if self._status is None:
            self.active_check.setChecked(True)
            self.sort_order_input.setValue(int(default_sort_order))
            return
        self.name_ar_input.setText(self._status.name_ar)
        self.name_en_input.setText(self._status.name_en)
        self.sort_order_input.setValue(int(self._status.sort_order))
        self.active_check.setChecked(self._status.active)

    def _is_duplicate(self, name_ar: str, name_en: str) -> bool:
        normalized_ar = name_ar.casefold()
        normalized_en = name_en.casefold()
        for status in list_statuses(self._status_group, include_inactive=True):
            if self._status and status.id == self._status.id:
                continue
            if status.name_ar.casefold() == normalized_ar or status.name_en.casefold() == normalized_en:
                return True
        return False

    def _save(self) -> None:
        name_ar = self.name_ar_input.text().strip()
        name_en = self.name_en_input.text().strip()
        if not name_ar or not name_en:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("statuses.validation_required", language=self._language),
            )
            return
        if self._is_duplicate(name_ar, name_en):
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("statuses.validation_duplicate", language=self._language),
            )
            return
        sort_order = int(self.sort_order_input.value())
        active = self.active_check.isChecked()
        if self._status is None:
            create_status(self._status_group, name_ar, name_en, sort_order)
        else:
            update_status(self._status.id, self._status_group, name_ar, name_en, sort_order, active)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("statuses.saved_message", language=self._language),
        )
        self.accept()

    def apply_language(self, language: str) -> None:
        self._language = language
        group_label = t(
            "statuses.group.delivery" if self._status_group == "DELIVERY" else "statuses.group.payment",
            language=language,
        )
        title_key = "statuses.edit_title" if self._status else "statuses.add_title"
        self.setWindowTitle(t(title_key, language=language, group=group_label))
        self.group_label.setText(t("statuses.group_label", language=language))
        self.group_value.setText(group_label)
        self.name_ar_label.setText(t("statuses.name_ar", language=language))
        self.name_en_label.setText(t("statuses.name_en", language=language))
        self.sort_order_label.setText(t("statuses.sort_order", language=language))
        self.active_check.setText(t("statuses.active", language=language))
        self.cancel_btn.setText(t("common.cancel", language=language))
        self.save_btn.setText(t("common.save", language=language))


class StatusesGroupTab(QWidget):
    def __init__(self, status_group: str, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self._status_group = status_group
        self._statuses: list[JewelryStatusItem] = []

        layout = QVBoxLayout(self)

        table = QTableWidget(0, 4)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        self.table = table

        actions = QHBoxLayout()
        self.add_btn = QPushButton()
        self.edit_btn = QPushButton()
        self.disable_btn = QPushButton()
        self.refresh_btn = QPushButton()
        actions.addWidget(self.add_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.disable_btn)
        actions.addStretch()
        actions.addWidget(self.refresh_btn)
        layout.addLayout(actions)

        self.add_btn.clicked.connect(self._add_status)
        self.edit_btn.clicked.connect(self._edit_status)
        self.disable_btn.clicked.connect(self._disable_status)
        self.refresh_btn.clicked.connect(self._refresh_table)

        self._refresh_table()
        self.apply_language(self._language)

    def _refresh_table(self) -> None:
        self._statuses = list_statuses(self._status_group, include_inactive=True)
        self.table.setRowCount(0)
        for status in self._statuses:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_ar_item = QTableWidgetItem(status.name_ar)
            name_ar_item.setData(Qt.ItemDataRole.UserRole, status.id)
            self.table.setItem(row, 0, name_ar_item)
            self.table.setItem(row, 1, QTableWidgetItem(status.name_en))
            self.table.setItem(row, 2, QTableWidgetItem(str(status.sort_order)))
            active_label = t("common.yes", language=self._language) if status.active else t(
                "common.no", language=self._language
            )
            self.table.setItem(row, 3, QTableWidgetItem(active_label))
        self.table.resizeRowsToContents()

    def _selected_status(self) -> Optional[JewelryStatusItem]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._statuses):
            return None
        return self._statuses[row]

    def _next_sort_order(self) -> int:
        if not self._statuses:
            return 0
        return max(status.sort_order for status in self._statuses) + 1

    def _add_status(self) -> None:
        dialog = StatusFormDialog(self._status_group, default_sort_order=self._next_sort_order(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _edit_status(self) -> None:
        status = self._selected_status()
        if status is None:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("statuses.select_prompt", language=self._language),
            )
            return
        dialog = StatusFormDialog(self._status_group, status=status, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _disable_status(self) -> None:
        status = self._selected_status()
        if status is None:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("statuses.select_prompt", language=self._language),
            )
            return
        confirm = QMessageBox.question(
            self,
            t("common.select", language=self._language),
            t("statuses.confirm_disable", language=self._language),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        disable_status(status.id)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("statuses.disabled_message", language=self._language),
        )
        self._refresh_table()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.table.setHorizontalHeaderLabels(
            [
                t("statuses.name_ar", language=language),
                t("statuses.name_en", language=language),
                t("statuses.sort_order", language=language),
                t("statuses.active", language=language),
            ]
        )
        self.add_btn.setText(t("common.add", language=language))
        self.edit_btn.setText(t("common.edit", language=language))
        self.disable_btn.setText(t("common.disable", language=language))
        self.refresh_btn.setText(t("common.refresh", language=language))
        self._refresh_table()


class StatusesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setModal(True)
        self.setMinimumWidth(820)
        self.setMinimumHeight(480)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.delivery_tab = StatusesGroupTab("DELIVERY", parent=self)
        self.payment_tab = StatusesGroupTab("PAYMENT", parent=self)
        tabs.addTab(self.delivery_tab, "")
        tabs.addTab(self.payment_tab, "")
        layout.addWidget(tabs)

        actions = QHBoxLayout()
        actions.addStretch()
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.accept)
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

        self.tabs = tabs
        self.apply_language(self._language)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("statuses.title", language=language))
        self.tabs.setTabText(0, t("statuses.tab.delivery", language=language))
        self.tabs.setTabText(1, t("statuses.tab.payment", language=language))
        self.delivery_tab.apply_language(language)
        self.payment_tab.apply_language(language)
        self.close_btn.setText(t("common.close", language=language))
