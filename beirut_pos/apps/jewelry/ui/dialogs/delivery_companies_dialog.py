"""Dialog for managing delivery companies."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from ...services.db import (
    JewelryDeliveryCompany,
    create_delivery_company,
    disable_delivery_company,
    list_delivery_companies,
    update_delivery_company,
)
from ...services.i18n import get_ui_language, t


class DeliveryCompanyFormDialog(QDialog):
    def __init__(self, company: Optional[JewelryDeliveryCompany] = None, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self._company = company
        self._company_type_value: Optional[str] = None
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.type_combo = QComboBox()
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.default_fee_input = QDoubleSpinBox()
        self.default_fee_input.setDecimals(2)
        self.default_fee_input.setRange(0.0, 999999.0)
        self.default_fee_input.setSingleStep(1.0)
        self.active_check = QCheckBox()

        self.name_label = QLabel()
        self.type_label = QLabel()
        self.phone_label = QLabel()
        self.address_label = QLabel()
        self.default_fee_label = QLabel()

        form_layout.addRow(self.name_label, self.name_input)
        form_layout.addRow(self.type_label, self.type_combo)
        form_layout.addRow(self.phone_label, self.phone_input)
        form_layout.addRow(self.address_label, self.address_input)
        form_layout.addRow(self.default_fee_label, self.default_fee_input)
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

        self._load_company()
        self.apply_language(self._language)

    def _load_company(self) -> None:
        self.type_combo.clear()
        if self._company is None:
            self.active_check.setChecked(True)
            return
        self.name_input.setText(self._company.name)
        self.phone_input.setText(self._company.phone)
        self.address_input.setText(self._company.address)
        self.default_fee_input.setValue(float(self._company.default_fee))
        self.active_check.setChecked(self._company.active)
        self._company_type_value = self._company.company_type

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value:
                combo.setCurrentIndex(idx)
                return

    def _save(self) -> None:
        name = self.name_input.text().strip()
        company_type = self.type_combo.currentData() or ""
        if not name or not company_type:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("delivery_companies.validation_required", language=self._language),
            )
            return
        phone = self.phone_input.text().strip()
        address = self.address_input.text().strip()
        default_fee = float(self.default_fee_input.value())
        active = self.active_check.isChecked()
        if self._company is None:
            create_delivery_company(name, company_type, phone, address, default_fee)
        else:
            update_delivery_company(
                self._company.id,
                name,
                company_type,
                phone,
                address,
                default_fee,
                active,
            )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("delivery_companies.saved_message", language=self._language),
        )
        self.accept()

    def apply_language(self, language: str) -> None:
        self._language = language
        title_key = "delivery_companies.edit_title" if self._company else "delivery_companies.add_title"
        self.setWindowTitle(t(title_key, language=language))
        self.name_label.setText(t("delivery_company.name", language=language))
        self.type_label.setText(t("delivery_company.type", language=language))
        self.phone_label.setText(t("delivery_company.phone", language=language))
        self.address_label.setText(t("delivery_company.address", language=language))
        self.default_fee_label.setText(t("delivery_company.default_fee", language=language))
        self.active_check.setText(t("delivery_company.active", language=language))
        current_value = self._company_type_value or self.type_combo.currentData()
        self.type_combo.clear()
        self.type_combo.addItem(t("delivery_company.type.self", language=language), "SELF")
        self.type_combo.addItem(t("delivery_company.type.external", language=language), "EXTERNAL")
        if current_value:
            self._set_combo_value(self.type_combo, current_value)
        self.cancel_btn.setText(t("common.cancel", language=language))
        self.save_btn.setText(t("common.save", language=language))


class DeliveryCompaniesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self._companies: list[JewelryDeliveryCompany] = []
        self.setModal(True)
        self.setMinimumWidth(820)
        self.setMinimumHeight(480)

        layout = QVBoxLayout(self)

        table = QTableWidget(0, 6)
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
        self.close_btn = QPushButton()
        self.add_btn.clicked.connect(self._add_company)
        self.edit_btn.clicked.connect(self._edit_company)
        self.disable_btn.clicked.connect(self._disable_company)
        self.refresh_btn.clicked.connect(self._refresh_table)
        self.close_btn.clicked.connect(self.accept)

        actions.addWidget(self.add_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.disable_btn)
        actions.addStretch()
        actions.addWidget(self.refresh_btn)
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

        self._refresh_table()
        self.apply_language(self._language)

    def _type_label(self, company_type: str) -> str:
        if company_type == "SELF":
            return t("delivery_company.type.self", language=self._language)
        if company_type == "EXTERNAL":
            return t("delivery_company.type.external", language=self._language)
        return company_type

    def _refresh_table(self) -> None:
        self._companies = list_delivery_companies(include_inactive=True)
        self.table.setRowCount(0)
        for company in self._companies:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(company.name)
            name_item.setData(Qt.ItemDataRole.UserRole, company.id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(self._type_label(company.company_type)))
            self.table.setItem(row, 2, QTableWidgetItem(company.phone))
            self.table.setItem(row, 3, QTableWidgetItem(company.address))
            self.table.setItem(row, 4, QTableWidgetItem(f"{company.default_fee:.2f}"))
            active_label = t("common.yes", language=self._language) if company.active else t(
                "common.no", language=self._language
            )
            self.table.setItem(row, 5, QTableWidgetItem(active_label))
        self.table.resizeRowsToContents()

    def _selected_company(self) -> Optional[JewelryDeliveryCompany]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._companies):
            return None
        return self._companies[row]

    def _add_company(self) -> None:
        dialog = DeliveryCompanyFormDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _edit_company(self) -> None:
        company = self._selected_company()
        if company is None:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("delivery_companies.select_prompt", language=self._language),
            )
            return
        dialog = DeliveryCompanyFormDialog(company, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_table()

    def _disable_company(self) -> None:
        company = self._selected_company()
        if company is None:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("delivery_companies.select_prompt", language=self._language),
            )
            return
        confirm = QMessageBox.question(
            self,
            t("common.select", language=self._language),
            t("delivery_companies.confirm_disable", language=self._language),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        disable_delivery_company(company.id)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("delivery_companies.disabled_message", language=self._language),
        )
        self._refresh_table()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("delivery_companies.title", language=language))
        self.table.setHorizontalHeaderLabels(
            [
                t("delivery_company.name", language=language),
                t("delivery_company.type", language=language),
                t("delivery_company.phone", language=language),
                t("delivery_company.address", language=language),
                t("delivery_company.default_fee", language=language),
                t("delivery_company.active", language=language),
            ]
        )
        self.add_btn.setText(t("common.add", language=language))
        self.edit_btn.setText(t("common.edit", language=language))
        self.disable_btn.setText(t("common.disable", language=language))
        self.refresh_btn.setText(t("common.refresh", language=language))
        self.close_btn.setText(t("common.close", language=language))
        self._refresh_table()
