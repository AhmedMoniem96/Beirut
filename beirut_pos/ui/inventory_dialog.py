# beirut_pos/ui/inventory_dialog.py
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .common.big_dialog import BigDialog
from ..services.orders import order_manager


class InventoryDialog(BigDialog):
    def __init__(self, actor: str, parent=None):
        super().__init__("المخزون", remember_key="inventory", parent=parent)
        self._actor = actor

        root = QVBoxLayout(self)

        intro = QLabel(
            "أضف كميات المخزون مباشرة من هنا ليكون كل التتبع في مكان واحد."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Filters row
        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(QLabel("بحث:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("ابحث باسم المنتج أو القسم…")
        self.search.textChanged.connect(self._apply_filter)
        filters.addWidget(self.search)
        filters.addStretch(1)
        root.addLayout(filters)

        self.table = QTableWidget(0, 4)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels([
            "المنتج",
            "القسم",
            "المتاح",
            "الحد الأدنى",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0, 1_000_000)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setSingleStep(0.5)
        self.qty_spin.setSuffix(" وحدة")
        controls.addWidget(QLabel("أضف للمخزون:"))
        controls.addWidget(self.qty_spin)

        self.btn_add = QPushButton("حفظ الكمية")
        self.btn_add.clicked.connect(self._on_add_stock)
        controls.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("تحديث")
        self.btn_refresh.clicked.connect(self._load_inventory)
        controls.addWidget(self.btn_refresh)

        controls.addStretch(1)
        root.addLayout(controls)

        self._inventory_rows: list[dict] = []
        self._load_inventory()

    # ------------------------------------------------------------------ data
    def _load_inventory(self) -> None:
        try:
            self._inventory_rows = order_manager.catalog.inventory_overview()
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر تحميل المخزون: {exc}")
            return

        self.table.setRowCount(0)
        for row_data in self._inventory_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(row_data["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, row_data["id"])
            name_item.setData(Qt.ItemDataRole.UserRole + 1, row_data["category"])
            self.table.setItem(row, 0, name_item)

            cat_item = QTableWidgetItem(row_data["category"])
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, cat_item)

            stock_item = QTableWidgetItem(self._format_qty(row_data["stock_qty"]))
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, stock_item)

            min_item = QTableWidgetItem(self._format_qty(row_data["min_stock"]))
            min_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, min_item)

        self._apply_filter()

    def _apply_filter(self) -> None:
        term = (self.search.text() or "").strip().lower()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            category = self.table.item(row, 1).text().lower()
            match = term in name or term in category
            self.table.setRowHidden(row, bool(term) and not match)

    # ----------------------------------------------------------------- actions
    def _on_add_stock(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "اختر منتجاً", "يرجى اختيار المنتج أولاً.")
            return

        qty = float(self.qty_spin.value())
        if qty <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "أدخل كمية أكبر من صفر.")
            return

        product_item = selected[0]
        pid = product_item.data(Qt.ItemDataRole.UserRole)
        name = product_item.text()

        try:
            order_manager.catalog.adjust_stock(pid, qty, actor=self._actor)
        except ValueError as exc:
            QMessageBox.warning(self, "غير مسموح", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر تحديث المخزون: {exc}")
            return

        QMessageBox.information(
            self,
            "تم الحفظ",
            f"تمت إضافة {qty:g} إلى مخزون {name} بنجاح.",
        )
        self.qty_spin.setValue(0)
        self._load_inventory()

    @staticmethod
    def _format_qty(value) -> str:
        if value is None:
            return "—"
        return f"{float(value):g}"

