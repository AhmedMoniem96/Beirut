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
        self.table.itemSelectionChanged.connect(self._apply_selected_package_size)
        root.addWidget(self.table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0, 1_000_000)
        self.qty_spin.setDecimals(2)
        self.qty_spin.setSingleStep(0.5)
        self.qty_spin.setSuffix(" وحدة")
        controls.addWidget(QLabel("أضف وحدات:"))
        controls.addWidget(self.qty_spin)

        self.btn_add_units = QPushButton("حفظ الكمية")
        self.btn_add_units.clicked.connect(self._on_add_stock)
        controls.addWidget(self.btn_add_units)

        self.pkg_size_spin = QDoubleSpinBox()
        self.pkg_size_spin.setRange(0, 100_000)
        self.pkg_size_spin.setDecimals(2)
        self.pkg_size_spin.setMinimum(1.0)
        self.pkg_size_spin.setSuffix(" وحدة/عبوة")
        controls.addWidget(QLabel("حجم العبوة:"))
        controls.addWidget(self.pkg_size_spin)

        self.pkg_count_spin = QDoubleSpinBox()
        self.pkg_count_spin.setRange(0, 100_000)
        self.pkg_count_spin.setDecimals(2)
        self.pkg_count_spin.setSuffix(" عبوة")
        controls.addWidget(QLabel("عدد العبوات:"))
        controls.addWidget(self.pkg_count_spin)

        self.btn_add_packages = QPushButton("إضافة عبوات")
        self.btn_add_packages.clicked.connect(self._on_add_packages)
        controls.addWidget(self.btn_add_packages)

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
            name_item.setData(Qt.ItemDataRole.UserRole + 2, row_data.get("package_size") or 1.0)
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
        if self.table.rowCount() > 0 and not self.table.selectedItems():
            self.table.selectRow(0)
        self._apply_selected_package_size()

    def _apply_filter(self) -> None:
        term = (self.search.text() or "").strip().lower()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            category = self.table.item(row, 1).text().lower()
            match = term in name or term in category
            self.table.setRowHidden(row, bool(term) and not match)

    # ----------------------------------------------------------------- actions
    def _selected_row(self) -> QTableWidgetItem | None:
        selected = self.table.selectedItems()
        return selected[0] if selected else None

    def _apply_selected_package_size(self) -> None:
        item = self._selected_row()
        if not item:
            return
        pkg_size = item.data(Qt.ItemDataRole.UserRole + 2)
        try:
            pkg_size = float(pkg_size)
        except (TypeError, ValueError):
            pkg_size = 1.0
        if pkg_size <= 0:
            pkg_size = 1.0
        self.pkg_size_spin.setValue(pkg_size)

    def _on_add_stock(self) -> None:
        product_item = self._selected_row()
        if not product_item:
            QMessageBox.information(self, "اختر منتجاً", "يرجى اختيار المنتج أولاً.")
            return

        qty = float(self.qty_spin.value())
        if qty <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "أدخل كمية أكبر من صفر.")
            return

        pid = product_item.data(Qt.ItemDataRole.UserRole)
        name = product_item.text()

        self._apply_adjustment(pid, qty, name)

    def _on_add_packages(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "اختر منتجاً", "يرجى اختيار المنتج أولاً.")
            return

        size = float(self.pkg_size_spin.value())
        count = float(self.pkg_count_spin.value())
        if size <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "حدد حجم العبوة أولاً.")
            return
        if count <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "أدخل عدد العبوات المراد إضافتها.")
            return

        units = size * count
        product_item = selected[0]
        pid = product_item.data(Qt.ItemDataRole.UserRole)
        name = product_item.text()

        self._apply_adjustment(pid, units, name, hint=f"{count:g} × {size:g}")
        self.pkg_count_spin.setValue(0)

    def _apply_adjustment(self, product_id: int, qty: float, name: str, *, hint: str | None = None) -> None:
        try:
            order_manager.catalog.adjust_stock(product_id, qty, actor=self._actor)
        except ValueError as exc:
            QMessageBox.warning(self, "غير مسموح", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر تحديث المخزون: {exc}")
            return

        detail = f" ({hint})" if hint else ""
        QMessageBox.information(
            self,
            "تم الحفظ",
            f"تمت إضافة {qty:g} إلى مخزون {name}{detail} بنجاح.",
        )
        self.qty_spin.setValue(0)
        self._load_inventory()

    @staticmethod
    def _format_qty(value) -> str:
        if value is None:
            return "—"
        return f"{float(value):g}"

