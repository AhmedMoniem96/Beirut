from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.db import (
    add_worker,
    create_purchase,
    delete_purchase,
    delete_worker,
    list_materials,
    list_purchases,
    list_workers,
    update_purchase,
    update_worker,
)
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


class PurchasesTab(BaseTabContainer):
    CATEGORIES = [
        "Material Purchase",
        "Electricity Bill",
        "Shop Bill",
        "Worker Wage",
        "Rent",
        "Packaging",
        "Maintenance",
        "Other",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        self._selected_purchase_id: int | None = None
        self._materials = []
        self._workers: list[tuple[int, str]] = []

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.set_content_layout(self.content_layout)

        self._build_form()
        self._build_table()

        self.set_page_content_widget(content)
        self.apply_language(self._language)
        self._reload_dropdowns()
        self.refresh_table()

    def _build_form(self) -> None:
        form_box = QGroupBox()
        form_layout = QGridLayout(form_box)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(date.today())
        self.category_input = QComboBox()
        self.category_input.addItems(self.CATEGORIES)
        for i, value in enumerate(self.CATEGORIES):
            self.category_input.setItemData(i, value)
        self.category_input.currentTextChanged.connect(self._toggle_conditional_fields)
        self.vendor_input = QLineEdit()
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 999999999)
        self.amount_input.setDecimals(2)
        self.payment_method_input = QLineEdit()
        self.description_input = QLineEdit()
        self.notes_input = QLineEdit()

        self.material_input = QComboBox()
        self.material_qty_input = QDoubleSpinBox()
        self.material_qty_input.setRange(0, 999999)
        self.material_qty_input.setDecimals(2)
        self.add_stock_check = QCheckBox()

        self.worker_input = QComboBox()
        self.wage_period_input = QComboBox()
        self.wage_period_input.addItems(["Daily", "Weekly", "Monthly", "Custom"])
        for i, value in enumerate(["Daily", "Weekly", "Monthly", "Custom"]):
            self.wage_period_input.setItemData(i, value)

        labels = [QLabel() for _ in range(12)]
        (
            self.date_label,
            self.category_label,
            self.vendor_label,
            self.amount_label,
            self.payment_method_label,
            self.description_label,
            self.notes_label,
            self.material_label,
            self.material_qty_label,
            self.worker_label,
            self.wage_period_label,
            self.stock_label,
        ) = labels

        form_layout.addWidget(self.date_label, 0, 0); form_layout.addWidget(self.date_input, 0, 1)
        form_layout.addWidget(self.category_label, 0, 2); form_layout.addWidget(self.category_input, 0, 3)
        form_layout.addWidget(self.vendor_label, 1, 0); form_layout.addWidget(self.vendor_input, 1, 1)
        form_layout.addWidget(self.amount_label, 1, 2); form_layout.addWidget(self.amount_input, 1, 3)
        form_layout.addWidget(self.payment_method_label, 2, 0); form_layout.addWidget(self.payment_method_input, 2, 1)
        form_layout.addWidget(self.description_label, 2, 2); form_layout.addWidget(self.description_input, 2, 3)
        form_layout.addWidget(self.notes_label, 3, 0); form_layout.addWidget(self.notes_input, 3, 1, 1, 3)

        form_layout.addWidget(self.material_label, 4, 0); form_layout.addWidget(self.material_input, 4, 1)
        form_layout.addWidget(self.material_qty_label, 4, 2); form_layout.addWidget(self.material_qty_input, 4, 3)
        form_layout.addWidget(self.stock_label, 5, 0); form_layout.addWidget(self.add_stock_check, 5, 1)
        form_layout.addWidget(self.worker_label, 6, 0); form_layout.addWidget(self.worker_input, 6, 1)
        form_layout.addWidget(self.wage_period_label, 6, 2); form_layout.addWidget(self.wage_period_input, 6, 3)

        self.add_content_widget(form_box)

        workers_box = QGroupBox("Workers")
        workers_layout = QGridLayout(workers_box)
        self.worker_name_input = QLineEdit()
        self.worker_phone_input = QLineEdit()
        self.worker_role_input = QLineEdit()
        self.worker_default_wage_input = QDoubleSpinBox(); self.worker_default_wage_input.setRange(0, 999999999); self.worker_default_wage_input.setDecimals(2)
        self.worker_wage_type_input = QComboBox(); self.worker_wage_type_input.addItems(["Daily", "Weekly", "Monthly"])
        self.worker_notes_input = QLineEdit()
        self.worker_manage_input = QComboBox(); self.worker_manage_input.currentIndexChanged.connect(self._load_worker_form)
        self.worker_add_btn = QPushButton("Add Worker"); self.worker_add_btn.clicked.connect(self._add_worker)
        self.worker_save_btn = QPushButton("Update Worker"); self.worker_save_btn.clicked.connect(self._update_worker)
        self.worker_delete_btn = QPushButton("Delete Worker"); self.worker_delete_btn.clicked.connect(self._delete_worker)
        workers_layout.addWidget(QLabel("Worker"),0,0); workers_layout.addWidget(self.worker_manage_input,0,1,1,3)
        workers_layout.addWidget(QLabel("Name"),1,0); workers_layout.addWidget(self.worker_name_input,1,1)
        workers_layout.addWidget(QLabel("Phone"),1,2); workers_layout.addWidget(self.worker_phone_input,1,3)
        workers_layout.addWidget(QLabel("Role"),2,0); workers_layout.addWidget(self.worker_role_input,2,1)
        workers_layout.addWidget(QLabel("Default Wage"),2,2); workers_layout.addWidget(self.worker_default_wage_input,2,3)
        workers_layout.addWidget(QLabel("Wage Type"),3,0); workers_layout.addWidget(self.worker_wage_type_input,3,1)
        workers_layout.addWidget(QLabel("Notes"),3,2); workers_layout.addWidget(self.worker_notes_input,3,3)
        actions = QHBoxLayout(); actions.addWidget(self.worker_add_btn); actions.addWidget(self.worker_save_btn); actions.addWidget(self.worker_delete_btn); actions.addStretch(1)
        workers_layout.addLayout(actions,4,0,1,4)
        self.add_content_widget(workers_box)

        self.add_btn = QPushButton("Add Purchase")
        self.save_btn = QPushButton("Save Purchase")
        self.delete_btn = QPushButton("Delete Purchase")
        self.clear_btn = QPushButton("Clear")
        self.add_btn.clicked.connect(self._add_purchase)
        self.save_btn.clicked.connect(self._save_purchase)
        self.delete_btn.clicked.connect(self._delete_purchase)
        self.clear_btn.clicked.connect(self._clear_form)

        for b in [self.clear_btn, self.delete_btn, self.save_btn, self.add_btn]:
            self.footer_layout.addWidget(b)

    def _build_table(self) -> None:
        self.table = QTableWidget(0, 9)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellClicked.connect(self._load_selected_row)
        self.add_content_widget(self.table)

    def _reload_dropdowns(self) -> None:
        self._materials = list_materials()
        self.material_input.clear()
        self.material_input.addItem("", None)
        for material in self._materials:
            self.material_input.addItem(choose_name(material.name_ar, material.name_en, language=self._language), material.id)

        self._workers = [(w.id, w.name) for w in list_workers()]
        self.worker_input.clear()
        self.worker_input.addItem("", None)
        self.worker_manage_input.blockSignals(True)
        self.worker_manage_input.clear()
        self.worker_manage_input.addItem("", None)
        for wid, name in self._workers:
            self.worker_input.addItem(name, wid)
            self.worker_manage_input.addItem(name, wid)
        self.worker_manage_input.blockSignals(False)
        self._toggle_conditional_fields()

    def _toggle_conditional_fields(self) -> None:
        is_material = self.category_input.currentData() == "Material Purchase"
        is_wage = self.category_input.currentData() == "Worker Wage"
        for w in [self.material_label, self.material_input, self.material_qty_label, self.material_qty_input, self.stock_label, self.add_stock_check]:
            w.setVisible(is_material)
        for w in [self.worker_label, self.worker_input, self.wage_period_label, self.wage_period_input]:
            w.setVisible(is_wage)

    def _current_payload(self):
        return {
            "date": self.date_input.date().toString("yyyy-MM-dd"),
            "category": self.category_input.currentData() or self.category_input.currentText(),
            "vendor": self.vendor_input.text().strip(),
            "description": self.description_input.text().strip(),
            "amount": float(self.amount_input.value()),
            "payment_method": self.payment_method_input.text().strip(),
            "notes": self.notes_input.text().strip(),
            "linked_material_id": self.material_input.currentData() if self.category_input.currentData() == "Material Purchase" else None,
            "material_qty": float(self.material_qty_input.value()) if self.category_input.currentData() == "Material Purchase" else None,
            "worker_id": self.worker_input.currentData() if self.category_input.currentData() == "Worker Wage" else None,
            "wage_period": (self.wage_period_input.currentData() or self.wage_period_input.currentText()) if self.category_input.currentData() == "Worker Wage" else "",
        }

    def _add_purchase(self) -> None:
        payload = self._current_payload()
        if payload["category"] == "Material Purchase" and not self.add_stock_check.isChecked():
            payload["linked_material_id"] = None
            payload["material_qty"] = None
        try:
            create_purchase(**payload)
            self.refresh_table(); self._clear_form()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _save_purchase(self) -> None:
        if not self._selected_purchase_id:
            return self._add_purchase()
        payload = self._current_payload()
        if payload["category"] == "Material Purchase" and not self.add_stock_check.isChecked():
            payload["linked_material_id"] = None
            payload["material_qty"] = None
        try:
            update_purchase(self._selected_purchase_id, **payload)
            self.refresh_table(); self._clear_form()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _delete_purchase(self) -> None:
        if not self._selected_purchase_id:
            return
        purchase = next((p for p in list_purchases() if p.id == self._selected_purchase_id), None)
        reverse_stock = False
        if purchase and purchase.category == "Material Purchase" and purchase.linked_material_id and purchase.material_qty:
            answer = QMessageBox.question(
                self,
                "Reverse Stock",
                "Reverse this purchase material quantity from stock before deleting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            reverse_stock = answer == QMessageBox.StandardButton.Yes
        delete_purchase(self._selected_purchase_id, reverse_stock=reverse_stock)
        self.refresh_table(); self._clear_form()

    def _clear_form(self) -> None:
        self._selected_purchase_id = None
        self.date_input.setDate(date.today())
        self.category_input.setCurrentIndex(0)
        self.vendor_input.clear(); self.amount_input.setValue(0)
        self.payment_method_input.clear(); self.description_input.clear(); self.notes_input.clear()
        self.material_input.setCurrentIndex(0); self.material_qty_input.setValue(0); self.add_stock_check.setChecked(False)
        self.worker_input.setCurrentIndex(0); self.wage_period_input.setCurrentIndex(0)
        self._toggle_conditional_fields()

    def refresh_table(self) -> None:
        purchases = list_purchases()
        self.table.setRowCount(0)
        for p in purchases:
            row = self.table.rowCount(); self.table.insertRow(row)
            worker_name = next((w[1] for w in self._workers if w[0] == p.worker_id), "")
            vendor_or_worker = worker_name or p.vendor
            material_name = ""
            if p.linked_material_id:
                material_name = next((choose_name(m.name_ar, m.name_en, language=self._language) for m in self._materials if m.id == p.linked_material_id), "")
            values = [p.date, p.category, vendor_or_worker, p.description, f"{p.amount:.2f}", p.payment_method, material_name, f"{float(p.material_qty or 0):.2f}" if p.material_qty else "", p.notes]
            for c, value in enumerate(values):
                self.table.setItem(row, c, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, p.id)

    def _load_selected_row(self, row: int, _col: int) -> None:
        purchase_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        purchase = next((p for p in list_purchases() if p.id == purchase_id), None)
        if not purchase:
            return
        self._selected_purchase_id = purchase.id
        self.date_input.setDate(date.fromisoformat(purchase.date))
        idx = self.category_input.findData(purchase.category)
        self.category_input.setCurrentIndex(idx if idx >= 0 else 0)
        self.vendor_input.setText(purchase.vendor)
        self.amount_input.setValue(float(purchase.amount))
        self.payment_method_input.setText(purchase.payment_method)
        self.description_input.setText(purchase.description)
        self.notes_input.setText(purchase.notes)
        if purchase.linked_material_id:
            idx = self.material_input.findData(purchase.linked_material_id)
            if idx >= 0: self.material_input.setCurrentIndex(idx)
            self.material_qty_input.setValue(float(purchase.material_qty or 0))
            self.add_stock_check.setChecked(True)
        if purchase.worker_id:
            idx = self.worker_input.findData(purchase.worker_id)
            if idx >= 0: self.worker_input.setCurrentIndex(idx)
        if purchase.wage_period:
            w_idx = self.wage_period_input.findData(purchase.wage_period)
            self.wage_period_input.setCurrentIndex(w_idx if w_idx >= 0 else 0)
        self._toggle_conditional_fields()

    def _selected_worker_id(self) -> int | None:
        return self.worker_manage_input.currentData()

    def _load_worker_form(self) -> None:
        worker_id = self._selected_worker_id()
        worker = next((w for w in list_workers() if w.id == worker_id), None)
        if not worker:
            self.worker_name_input.clear(); self.worker_phone_input.clear(); self.worker_role_input.clear(); self.worker_default_wage_input.setValue(0); self.worker_wage_type_input.setCurrentIndex(0); self.worker_notes_input.clear()
            return
        self.worker_name_input.setText(worker.name); self.worker_phone_input.setText(worker.phone); self.worker_role_input.setText(worker.role)
        self.worker_default_wage_input.setValue(float(worker.default_wage)); ww_idx = self.worker_wage_type_input.findText(worker.wage_type); self.worker_wage_type_input.setCurrentIndex(ww_idx if ww_idx >= 0 else 0); self.worker_notes_input.setText(worker.notes)

    def _worker_payload(self):
        return {"name": self.worker_name_input.text().strip(), "phone": self.worker_phone_input.text().strip(), "role": self.worker_role_input.text().strip(), "default_wage": float(self.worker_default_wage_input.value()), "wage_type": self.worker_wage_type_input.currentText(), "notes": self.worker_notes_input.text().strip()}

    def _add_worker(self) -> None:
        try:
            add_worker(**self._worker_payload()); self._reload_dropdowns(); self.worker_manage_input.setCurrentIndex(0)
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _update_worker(self) -> None:
        worker_id = self._selected_worker_id()
        if not worker_id:
            return
        try:
            update_worker(worker_id, **self._worker_payload()); self._reload_dropdowns()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))

    def _delete_worker(self) -> None:
        worker_id = self._selected_worker_id()
        if not worker_id:
            return
        delete_worker(worker_id); self._reload_dropdowns()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("purchases.header", language=language))
        self.date_label.setText("Date")
        self.category_label.setText("Category")
        self.vendor_label.setText(f"{t("purchases.vendor", language=language)} / {t("purchases.supplier", language=language)}")
        self.amount_label.setText("Amount")
        self.payment_method_label.setText("Payment Method")
        self.description_label.setText("Description")
        self.notes_label.setText("Notes")
        self.material_label.setText("Material")
        self.material_qty_label.setText("Material Qty")
        self.stock_label.setText(t("purchases.add_qty_to_material_stock", language=language))
        self.worker_label.setText(t("purchases.worker", language=language))
        self.wage_period_label.setText(t("purchases.wage_period", language=language))
        self.table.setHorizontalHeaderLabels(["Date", "Category", "Vendor/Worker", "Description", "Amount", "Payment Method", "Linked Material", "Qty", "Notes"])
        self.add_btn.setText(t("purchases.add_purchase", language=language))
        self.save_btn.setText(t("purchases.save_purchase", language=language))
        self.delete_btn.setText(t("purchases.delete_purchase", language=language))
        category_labels = {
            "Material Purchase": t("purchases.material_purchase", language=language),
            "Electricity Bill": t("purchases.electricity_bill", language=language),
            "Worker Wage": t("purchases.worker_wage", language=language),
            "Rent": t("purchases.rent", language=language),
            "Packaging": t("purchases.packaging", language=language),
            "Maintenance": t("purchases.maintenance", language=language),
            "Other": t("purchases.other", language=language),
            "Shop Bill": t("purchases.expenses", language=language),
        }
        for i, value in enumerate(self.CATEGORIES):
            self.category_input.setItemText(i, category_labels.get(value, value))
        period_labels = {
            "Daily": t("purchases.daily", language=language),
            "Weekly": t("purchases.weekly", language=language),
            "Monthly": t("purchases.monthly", language=language),
            "Custom": t("purchases.other", language=language),
        }
        for i, value in enumerate(["Daily", "Weekly", "Monthly", "Custom"]):
            self.wage_period_input.setItemText(i, period_labels.get(value, value))
        for i, value in enumerate(["Daily", "Weekly", "Monthly"]):
            self.worker_wage_type_input.setItemText(i, period_labels.get(value, value))
        self.clear_btn.setText(t("common.clear", language=language))
