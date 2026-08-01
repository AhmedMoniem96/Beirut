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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.db import add_worker, create_purchase, delete_purchase, delete_worker, list_materials, list_purchases, list_workers, update_purchase, update_worker
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


class PurchasesTab(BaseTabContainer):
    EXPENSE_CATEGORIES = ["Electricity Bill", "Rent", "Maintenance", "Packaging", "Other", "Shop Bill"]

    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        self._selected_expense_id: int | None = None
        self._selected_material_purchase_id: int | None = None
        self._selected_wage_payment_id: int | None = None
        self._material_delete_in_progress = False
        self._materials = []
        self._workers = []

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.set_content_layout(self.content_layout)

        self.tabs = QTabWidget()
        self._build_expenses_tab()
        self._build_material_tab()
        self._build_workers_tab()
        self.add_content_widget(self.tabs)

        self.set_page_content_widget(content)
        self.apply_language(self._language)
        self._reload_dropdowns()
        self.refresh_table()

    def _build_expenses_tab(self) -> None:
        self.expenses_tab = QWidget(); layout = QVBoxLayout(self.expenses_tab)
        form_box = QGroupBox(); form = QGridLayout(form_box)
        self.expense_date = QDateEdit(); self.expense_date.setCalendarPopup(True); self.expense_date.setDate(date.today())
        self.expense_category = QComboBox()
        for c in self.EXPENSE_CATEGORIES: self.expense_category.addItem(c, c)
        self.expense_vendor = QLineEdit(); self.expense_amount = QDoubleSpinBox(); self.expense_amount.setRange(0, 999999999); self.expense_amount.setDecimals(2)
        self.expense_payment = QLineEdit(); self.expense_description = QLineEdit(); self.expense_notes = QLineEdit()
        self.expense_labels = [QLabel() for _ in range(7)]
        form.addWidget(self.expense_labels[0],0,0); form.addWidget(self.expense_date,0,1)
        form.addWidget(self.expense_labels[1],0,2); form.addWidget(self.expense_category,0,3)
        form.addWidget(self.expense_labels[2],1,0); form.addWidget(self.expense_vendor,1,1)
        form.addWidget(self.expense_labels[3],1,2); form.addWidget(self.expense_amount,1,3)
        form.addWidget(self.expense_labels[4],2,0); form.addWidget(self.expense_payment,2,1)
        form.addWidget(self.expense_labels[5],2,2); form.addWidget(self.expense_description,2,3)
        form.addWidget(self.expense_labels[6],3,0); form.addWidget(self.expense_notes,3,1,1,3)
        layout.addWidget(form_box)
        btns = QHBoxLayout()
        self.expense_add_btn = QPushButton(); self.expense_add_btn.clicked.connect(self._add_expense)
        self.expense_save_btn = QPushButton(); self.expense_save_btn.clicked.connect(self._save_expense)
        self.expense_del_btn = QPushButton(); self.expense_del_btn.clicked.connect(self._delete_expense)
        self.expense_clear_btn = QPushButton(); self.expense_clear_btn.clicked.connect(self._clear_expense)
        for b in [self.expense_add_btn, self.expense_save_btn, self.expense_del_btn, self.expense_clear_btn]: btns.addWidget(b)
        btns.addStretch(1); layout.addLayout(btns)
        self.expenses_table = QTableWidget(0,8); self.expenses_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.expenses_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.expenses_table.cellClicked.connect(self._load_expense_row)
        layout.addWidget(self.expenses_table)
        self.tabs.addTab(self.expenses_tab, "")

    def _build_material_tab(self) -> None:
        self.material_tab = QWidget(); layout = QVBoxLayout(self.material_tab)
        form_box = QGroupBox(); form = QGridLayout(form_box)
        self.mat_date = QDateEdit(); self.mat_date.setCalendarPopup(True); self.mat_date.setDate(date.today())
        self.mat_material = QComboBox(); self.mat_supplier = QLineEdit(); self.mat_qty = QDoubleSpinBox(); self.mat_qty.setRange(0, 999999); self.mat_qty.setDecimals(2)
        self.mat_unit_cost = QDoubleSpinBox(); self.mat_unit_cost.setRange(0, 999999999); self.mat_unit_cost.setDecimals(2)
        self.mat_total = QDoubleSpinBox(); self.mat_total.setRange(0, 999999999); self.mat_total.setDecimals(2)
        self.mat_payment = QLineEdit(); self.mat_add_stock = QCheckBox(); self.mat_notes = QLineEdit()
        self.material_labels = [QLabel() for _ in range(8)]
        form.addWidget(self.material_labels[0],0,0); form.addWidget(self.mat_date,0,1)
        form.addWidget(self.material_labels[1],0,2); form.addWidget(self.mat_material,0,3)
        form.addWidget(self.material_labels[2],1,0); form.addWidget(self.mat_supplier,1,1)
        form.addWidget(self.material_labels[3],1,2); form.addWidget(self.mat_qty,1,3)
        form.addWidget(self.material_labels[4],2,0); form.addWidget(self.mat_unit_cost,2,1)
        form.addWidget(self.material_labels[5],2,2); form.addWidget(self.mat_total,2,3)
        form.addWidget(self.material_labels[6],3,0); form.addWidget(self.mat_payment,3,1)
        form.addWidget(self.material_labels[7],3,2); form.addWidget(self.mat_add_stock,3,3)
        form.addWidget(QLabel(),4,0); form.addWidget(self.mat_notes,4,1,1,3)
        layout.addWidget(form_box)
        btns = QHBoxLayout()
        self.mat_add_btn = QPushButton(); self.mat_add_btn.clicked.connect(self._add_material_purchase)
        self.mat_save_btn = QPushButton(); self.mat_save_btn.clicked.connect(self._save_material_purchase)
        self.mat_del_btn = QPushButton(); self.mat_del_btn.clicked.connect(self._delete_material_purchase)
        self.mat_clear_btn = QPushButton(); self.mat_clear_btn.clicked.connect(self._clear_material)
        for b in [self.mat_add_btn, self.mat_save_btn, self.mat_del_btn, self.mat_clear_btn]: btns.addWidget(b)
        btns.addStretch(1); layout.addLayout(btns)
        self.material_table = QTableWidget(0,9); self.material_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.material_table.cellClicked.connect(self._load_material_row)
        layout.addWidget(self.material_table)
        self.tabs.addTab(self.material_tab, "")

    def _build_workers_tab(self) -> None:
        self.workers_tab = QWidget(); layout = QVBoxLayout(self.workers_tab)
        box = QGroupBox(); g = QGridLayout(box)
        self.worker_manage = QComboBox(); self.worker_manage.currentIndexChanged.connect(self._load_worker_form)
        self.worker_name = QLineEdit(); self.worker_phone = QLineEdit(); self.worker_role = QLineEdit(); self.worker_default_wage = QDoubleSpinBox(); self.worker_default_wage.setRange(0, 999999999); self.worker_default_wage.setDecimals(2)
        self.worker_wage_type = QComboBox()
        for key in ["daily", "weekly", "monthly", "custom"]: self.worker_wage_type.addItem(key, key)
        self.worker_notes = QLineEdit(); self.worker_labels = [QLabel() for _ in range(6)]
        g.addWidget(self.worker_labels[0],0,0); g.addWidget(self.worker_manage,0,1,1,3)
        g.addWidget(self.worker_labels[1],1,0); g.addWidget(self.worker_name,1,1)
        g.addWidget(self.worker_labels[2],1,2); g.addWidget(self.worker_phone,1,3)
        g.addWidget(self.worker_labels[3],2,0); g.addWidget(self.worker_role,2,1)
        g.addWidget(self.worker_labels[4],2,2); g.addWidget(self.worker_default_wage,2,3)
        g.addWidget(self.worker_labels[5],3,0); g.addWidget(self.worker_wage_type,3,1)
        g.addWidget(QLabel(),3,2); g.addWidget(self.worker_notes,3,3)
        actions = QHBoxLayout(); self.worker_add_btn = QPushButton(); self.worker_add_btn.clicked.connect(self._add_worker); self.worker_save_btn = QPushButton(); self.worker_save_btn.clicked.connect(self._update_worker); self.worker_del_btn = QPushButton(); self.worker_del_btn.clicked.connect(self._delete_worker)
        actions.addWidget(self.worker_add_btn); actions.addWidget(self.worker_save_btn); actions.addWidget(self.worker_del_btn); actions.addStretch(1); g.addLayout(actions,4,0,1,4)
        layout.addWidget(box)
        self.workers_table = QTableWidget(0,6); self.workers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); layout.addWidget(self.workers_table)
        pay_box = QGroupBox(); p = QGridLayout(pay_box)
        self.wp_worker = QComboBox(); self.wp_date = QDateEdit(); self.wp_date.setCalendarPopup(True); self.wp_date.setDate(date.today()); self.wp_amount = QDoubleSpinBox(); self.wp_amount.setRange(0, 999999999); self.wp_amount.setDecimals(2)
        self.wp_period = QComboBox();
        for key in ["daily", "weekly", "monthly", "custom"]: self.wp_period.addItem(key, key)
        self.wp_notes = QLineEdit(); self.wp_labels = [QLabel() for _ in range(5)]
        p.addWidget(self.wp_labels[0],0,0); p.addWidget(self.wp_worker,0,1)
        p.addWidget(self.wp_labels[1],0,2); p.addWidget(self.wp_date,0,3)
        p.addWidget(self.wp_labels[2],1,0); p.addWidget(self.wp_amount,1,1)
        p.addWidget(self.wp_labels[3],1,2); p.addWidget(self.wp_period,1,3)
        p.addWidget(self.wp_labels[4],2,0); p.addWidget(self.wp_notes,2,1,1,3)
        self.wp_add_btn = QPushButton(); self.wp_add_btn.clicked.connect(self._add_wage_payment); p.addWidget(self.wp_add_btn,3,0,1,2)
        layout.addWidget(pay_box)
        self.wage_table = QTableWidget(0,5); self.wage_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.wage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.wage_table.cellClicked.connect(self._load_wage_row)
        layout.addWidget(self.wage_table)
        self.tabs.addTab(self.workers_tab, "")

    def _reload_dropdowns(self):
        self._materials = list_materials(); self.mat_material.clear(); self.mat_material.addItem("", None)
        for m in self._materials: self.mat_material.addItem(choose_name(m.name_ar, m.name_en, language=self._language), m.id)
        workers = list_workers(); self._workers = [(w.id, w.name, w.wage_type, w.phone, w.role, w.default_wage) for w in workers]
        for combo in [self.worker_manage, self.wp_worker]:
            combo.blockSignals(True); combo.clear(); combo.addItem("", None)
            for w in workers: combo.addItem(w.name, w.id)
            combo.blockSignals(False)

    def _worker_payload(self):
        return {"name": self.worker_name.text().strip(), "phone": self.worker_phone.text().strip(), "role": self.worker_role.text().strip(), "default_wage": float(self.worker_default_wage.value()), "wage_type": self.worker_wage_type.currentData(), "notes": self.worker_notes.text().strip()}

    def _add_worker(self):
        try: add_worker(**self._worker_payload()); self._reload_dropdowns(); self.refresh_table()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))

    def _update_worker(self):
        wid = self.worker_manage.currentData()
        if not wid: return
        try: update_worker(wid, **self._worker_payload()); self._reload_dropdowns(); self.refresh_table()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))

    def _delete_worker(self):
        wid = self.worker_manage.currentData()
        if not wid: return
        delete_worker(wid); self._reload_dropdowns(); self.refresh_table()

    def _load_worker_form(self):
        wid = self.worker_manage.currentData(); w = next((x for x in list_workers() if x.id == wid), None)
        if not w:
            self.worker_name.clear(); self.worker_phone.clear(); self.worker_role.clear(); self.worker_default_wage.setValue(0); self.worker_wage_type.setCurrentIndex(0); self.worker_notes.clear(); return
        self.worker_name.setText(w.name); self.worker_phone.setText(w.phone); self.worker_role.setText(w.role); self.worker_default_wage.setValue(float(w.default_wage)); self.worker_notes.setText(w.notes)
        idx = self.worker_wage_type.findData(w.wage_type); self.worker_wage_type.setCurrentIndex(idx if idx >= 0 else 0)

    def _purchase_payload(self, *, category: str, vendor: str, amount: float, payment: str, notes: str, description: str = "", material_id=None, material_qty=None, worker_id=None, wage_period=""):
        return {"date": self.expense_date.date().toString("yyyy-MM-dd"), "category": category, "vendor": vendor, "amount": amount, "payment_method": payment, "description": description, "notes": notes, "linked_material_id": material_id, "material_qty": material_qty, "worker_id": worker_id, "wage_period": wage_period}

    def _add_expense(self):
        try: create_purchase(**self._purchase_payload(category=self.expense_category.currentData(), vendor=self.expense_vendor.text().strip(), amount=float(self.expense_amount.value()), payment=self.expense_payment.text().strip(), description=self.expense_description.text().strip(), notes=self.expense_notes.text().strip())); self.refresh_table(); self._clear_expense()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))
    def _save_expense(self):
        if not self._selected_expense_id: return self._add_expense()
        try: update_purchase(self._selected_expense_id, **self._purchase_payload(category=self.expense_category.currentData(), vendor=self.expense_vendor.text().strip(), amount=float(self.expense_amount.value()), payment=self.expense_payment.text().strip(), description=self.expense_description.text().strip(), notes=self.expense_notes.text().strip())); self.refresh_table(); self._clear_expense()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))
    def _delete_expense(self):
        if self._selected_expense_id: delete_purchase(self._selected_expense_id); self.refresh_table(); self._clear_expense()

    def _add_material_purchase(self):
        try:
            create_purchase(date=self.mat_date.date().toString("yyyy-MM-dd"), category="Material Purchase", vendor=self.mat_supplier.text().strip(), amount=float(self.mat_total.value()), payment_method=self.mat_payment.text().strip(), description="", notes=self.mat_notes.text().strip(), linked_material_id=self.mat_material.currentData() if self.mat_add_stock.isChecked() else None, material_qty=float(self.mat_qty.value()) if self.mat_add_stock.isChecked() else None)
            self.refresh_table(); self._clear_material()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))
    def _save_material_purchase(self):
        if not self._selected_material_purchase_id: return self._add_material_purchase()
        try:
            update_purchase(self._selected_material_purchase_id, date=self.mat_date.date().toString("yyyy-MM-dd"), category="Material Purchase", vendor=self.mat_supplier.text().strip(), amount=float(self.mat_total.value()), payment_method=self.mat_payment.text().strip(), description="", notes=self.mat_notes.text().strip(), linked_material_id=self.mat_material.currentData() if self.mat_add_stock.isChecked() else None, material_qty=float(self.mat_qty.value()) if self.mat_add_stock.isChecked() else None)
            self.refresh_table(); self._clear_material()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))
    def _delete_material_purchase(self):
        # Read the id from the table selection at click time.  The form's cached
        # id may outlive a cleared selection and must never cause a stale row to
        # be deleted.
        if self._material_delete_in_progress or not self.material_table.selectionModel().hasSelection():
            return
        row = self.material_table.currentRow()
        id_item = self.material_table.item(row, 0) if row >= 0 else None
        purchase_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
        if not purchase_id:
            return
        answer = QMessageBox.question(
            self,
            t("common.delete", language=self._language),
            t("common.confirm_delete", language=self._language),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._material_delete_in_progress = True
        self.mat_del_btn.setEnabled(False)
        try:
            # Material purchases are stocked as one saved purchase row.  Always
            # reverse its stock contribution in the same deletion operation.
            delete_purchase(int(purchase_id), reverse_stock=True)
            self.refresh_table()
            self._clear_material()
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))
        finally:
            self._material_delete_in_progress = False
            self.mat_del_btn.setEnabled(True)

    def _add_wage_payment(self):
        try:
            create_purchase(date=self.wp_date.date().toString("yyyy-MM-dd"), category="Worker Wage", vendor="", description="", amount=float(self.wp_amount.value()), payment_method="", notes=self.wp_notes.text().strip(), worker_id=self.wp_worker.currentData(), wage_period=self.wp_period.currentData())
            self.refresh_table()
        except Exception as exc: QMessageBox.warning(self, "Error", str(exc))

    def _clear_expense(self): self._selected_expense_id = None; self.expense_date.setDate(date.today()); self.expense_category.setCurrentIndex(0); self.expense_vendor.clear(); self.expense_amount.setValue(0); self.expense_payment.clear(); self.expense_description.clear(); self.expense_notes.clear()
    def _clear_material(self): self._selected_material_purchase_id = None; self.mat_date.setDate(date.today()); self.mat_material.setCurrentIndex(0); self.mat_supplier.clear(); self.mat_qty.setValue(0); self.mat_unit_cost.setValue(0); self.mat_total.setValue(0); self.mat_payment.clear(); self.mat_add_stock.setChecked(False); self.mat_notes.clear()

    def _load_expense_row(self, row, _):
        p = next((x for x in list_purchases() if x.id == self.expenses_table.item(row,0).data(Qt.ItemDataRole.UserRole)), None)
        if not p: return
        self._selected_expense_id = p.id; self.expense_date.setDate(date.fromisoformat(p.date)); self.expense_category.setCurrentIndex(max(0, self.expense_category.findData(p.category))); self.expense_vendor.setText(p.vendor); self.expense_amount.setValue(float(p.amount)); self.expense_payment.setText(p.payment_method); self.expense_description.setText(p.description); self.expense_notes.setText(p.notes)
    def _load_material_row(self, row, _):
        p = next((x for x in list_purchases() if x.id == self.material_table.item(row,0).data(Qt.ItemDataRole.UserRole)), None)
        if not p: return
        self._selected_material_purchase_id = p.id; self.mat_date.setDate(date.fromisoformat(p.date)); self.mat_supplier.setText(p.vendor); self.mat_qty.setValue(float(p.material_qty or 0)); self.mat_total.setValue(float(p.amount)); self.mat_payment.setText(p.payment_method); self.mat_notes.setText(p.notes); self.mat_add_stock.setChecked(bool(p.linked_material_id)); self.mat_material.setCurrentIndex(max(0, self.mat_material.findData(p.linked_material_id)))
    def _load_wage_row(self, row, _):
        pid = self.wage_table.item(row,0).data(Qt.ItemDataRole.UserRole); self._selected_wage_payment_id = pid

    def refresh_table(self):
        self._reload_dropdowns()
        purchases = list_purchases()
        exp = [p for p in purchases if p.category in self.EXPENSE_CATEGORIES]
        mat = [p for p in purchases if p.category == "Material Purchase"]
        wage = [p for p in purchases if p.category == "Worker Wage"]
        self.expenses_table.setRowCount(0)
        for p in exp:
            r = self.expenses_table.rowCount(); self.expenses_table.insertRow(r)
            vals = [p.date, p.category, p.vendor, p.description, f"{p.amount:.2f}", p.payment_method, p.notes, ""]
            for c,v in enumerate(vals): self.expenses_table.setItem(r,c,QTableWidgetItem(v))
            self.expenses_table.item(r,0).setData(Qt.ItemDataRole.UserRole, p.id)
        self.material_table.setRowCount(0)
        for p in mat:
            r = self.material_table.rowCount(); self.material_table.insertRow(r)
            mname = next((choose_name(m.name_ar,m.name_en,language=self._language) for m in self._materials if m.id == p.linked_material_id), "")
            vals = [p.date, mname, p.vendor, f"{float(p.material_qty or 0):.2f}", "", f"{p.amount:.2f}", p.payment_method, "✓" if p.linked_material_id else "", p.notes]
            for c,v in enumerate(vals): self.material_table.setItem(r,c,QTableWidgetItem(v))
            self.material_table.item(r,0).setData(Qt.ItemDataRole.UserRole, p.id)
        self.workers_table.setRowCount(0)
        for w in list_workers():
            r = self.workers_table.rowCount(); self.workers_table.insertRow(r)
            vals = [w.name, w.phone, w.role, f"{w.default_wage:.2f}", w.wage_type, w.notes]
            for c,v in enumerate(vals): self.workers_table.setItem(r,c,QTableWidgetItem(str(v)))
        self.wage_table.setRowCount(0)
        for p in wage:
            r = self.wage_table.rowCount(); self.wage_table.insertRow(r)
            wname = next((w[1] for w in self._workers if w[0] == p.worker_id), "")
            vals = [wname, p.date, f"{p.amount:.2f}", p.wage_period, p.notes]
            for c,v in enumerate(vals): self.wage_table.setItem(r,c,QTableWidgetItem(v))
            self.wage_table.item(r,0).setData(Qt.ItemDataRole.UserRole, p.id)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("purchases.header", language=language))
        self.tabs.setTabText(0, f"{t('purchases.expenses', language=language)} / {t('tab.purchases', language=language)}")
        self.tabs.setTabText(1, t("reports.material_purchases", language=language))
        self.tabs.setTabText(2, f"{t('purchases.worker', language=language)} / {t('reports.worker_wages', language=language)}")
        labels = [t("common.date", language=language), t("purchases.category", language=language), t("purchases.vendor", language=language), t("purchases.amount", language=language), t("common.payment_method", language=language), t("purchases.description", language=language), t("common.notes", language=language)]
        for i,txt in enumerate(labels): self.expense_labels[i].setText(txt)
        self.expenses_table.setHorizontalHeaderLabels([t("common.date",language=language), t("purchases.category",language=language), t("purchases.vendor",language=language), t("purchases.description",language=language), t("purchases.amount",language=language), t("common.payment_method",language=language), t("common.notes",language=language), ""])
        self.expense_add_btn.setText(t("common.add", language=language)); self.expense_save_btn.setText(t("common.save", language=language)); self.expense_del_btn.setText(t("common.delete", language=language)); self.expense_clear_btn.setText(t("common.clear", language=language))
        mat_labels = [t("common.date",language=language), t("purchases.material",language=language), t("purchases.supplier",language=language), t("common.qty",language=language), t("purchases.unit_cost",language=language), t("purchases.total_amount",language=language), t("common.payment_method",language=language), t("purchases.add_qty_to_material_stock",language=language)]
        for i,txt in enumerate(mat_labels): self.material_labels[i].setText(txt)
        self.material_table.setHorizontalHeaderLabels([t("common.date",language=language), t("purchases.material",language=language), t("purchases.supplier",language=language), t("common.qty",language=language), t("purchases.unit_cost",language=language), t("common.total",language=language), t("common.payment_method",language=language), t("purchases.stock_updated",language=language), t("common.notes",language=language)])
        self.mat_add_btn.setText(t("common.add", language=language)); self.mat_save_btn.setText(t("common.save", language=language)); self.mat_del_btn.setText(t("common.delete", language=language)); self.mat_clear_btn.setText(t("common.clear", language=language))
        self.worker_labels[0].setText(t("purchases.worker", language=language)); self.worker_labels[1].setText(t("purchases.name", language=language)); self.worker_labels[2].setText(t("purchases.phone", language=language)); self.worker_labels[3].setText(t("purchases.role", language=language)); self.worker_labels[4].setText(t("purchases.default_wage", language=language)); self.worker_labels[5].setText(t("purchases.wage_type", language=language))
        self.worker_add_btn.setText(t("purchases.add_worker", language=language)); self.worker_save_btn.setText(t("purchases.update_worker", language=language)); self.worker_del_btn.setText(t("purchases.delete_worker", language=language))
        self.workers_table.setHorizontalHeaderLabels([t("purchases.name",language=language), t("purchases.phone",language=language), t("purchases.role",language=language), t("purchases.default_wage",language=language), t("purchases.wage_type",language=language), t("common.notes",language=language)])
        self.wp_labels[0].setText(t("purchases.worker", language=language)); self.wp_labels[1].setText(t("common.date", language=language)); self.wp_labels[2].setText(t("purchases.amount", language=language)); self.wp_labels[3].setText(t("purchases.wage_period", language=language)); self.wp_labels[4].setText(t("common.notes", language=language)); self.wp_add_btn.setText(t("purchases.add_wage_payment", language=language))
        self.wage_table.setHorizontalHeaderLabels([t("purchases.worker",language=language), t("common.date",language=language), t("purchases.amount",language=language), t("purchases.wage_period",language=language), t("common.notes",language=language)])
        cat_map = {"Electricity Bill": t("purchases.electricity_bill", language=language), "Rent": t("purchases.rent", language=language), "Maintenance": t("purchases.maintenance", language=language), "Packaging": t("purchases.packaging", language=language), "Other": t("purchases.other", language=language), "Shop Bill": t("purchases.expenses", language=language)}
        for i,c in enumerate(self.EXPENSE_CATEGORIES): self.expense_category.setItemText(i, cat_map.get(c,c))
        period_map = {"daily": t("purchases.daily", language=language), "weekly": t("purchases.weekly", language=language), "monthly": t("purchases.monthly", language=language), "custom": t("purchases.custom", language=language)}
        for combo in [self.worker_wage_type, self.wp_period]:
            for i,key in enumerate(["daily","weekly","monthly","custom"]): combo.setItemText(i, period_map[key])
