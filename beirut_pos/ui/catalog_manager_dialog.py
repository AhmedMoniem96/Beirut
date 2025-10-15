from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.orders import order_manager
from .common.big_dialog import BigDialog


@dataclass(slots=True)
class _ProductValues:
    name: str
    price_cents: int
    track_stock: bool
    stock_qty: float
    min_stock: float


class _ProductEditor(QDialog):
    def __init__(self, parent=None, *, values: _ProductValues | None = None):
        super().__init__(parent)
        self.setWindowTitle("بيانات المنتج")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._result: _ProductValues | None = None

        form = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.price_edit = QSpinBox()
        self.price_edit.setRange(0, 2_000_000)
        self.price_edit.setSingleStep(500)
        self.track_box = QCheckBox("تتبع المخزون")
        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setRange(0, 1_000_000)
        self.stock_spin.setDecimals(2)
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0, 1_000_000)
        self.min_spin.setDecimals(2)

        form.addRow("اسم المنتج:", self.name_edit)
        form.addRow("السعر (قرش):", self.price_edit)
        form.addRow("", self.track_box)
        form.addRow("المخزون الحالي:", self.stock_spin)
        form.addRow("حد أدنى للتنبيه:", self.min_spin)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        form.addRow(btn_row)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        if values:
            self.name_edit.setText(values.name)
            self.price_edit.setValue(values.price_cents)
            self.track_box.setChecked(values.track_stock)
            self.stock_spin.setValue(values.stock_qty)
            self.min_spin.setValue(values.min_stock)
        else:
            self.track_box.setChecked(True)

        self._toggle_stock(self.track_box.isChecked())
        self.track_box.toggled.connect(self._toggle_stock)

    def _toggle_stock(self, checked: bool) -> None:
        self.stock_spin.setEnabled(checked)
        self.min_spin.setEnabled(checked)

    def _collect_values(self) -> _ProductValues | None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "اسم المنتج مطلوب.")
            return None
        price = int(self.price_edit.value())
        if price <= 0:
            QMessageBox.warning(self, "خطأ", "السعر يجب أن يكون أكبر من صفر.")
            return None
        return _ProductValues(
            name=name,
            price_cents=price,
            track_stock=self.track_box.isChecked(),
            stock_qty=float(self.stock_spin.value()),
            min_stock=float(self.min_spin.value()),
        )

    def accept(self) -> None:
        values = self._collect_values()
        if not values:
            return
        self._result = values
        super().accept()

    def get_values(self) -> _ProductValues | None:
        return self._result


class CatalogManagerDialog(BigDialog):
    def __init__(self, actor: str = "admin", parent=None):
        super().__init__("إدارة الكتالوج", remember_key="catalog_admin", parent=parent)
        self._actor = actor
        self._catalog = order_manager.catalog
        self._categories: list[dict] = []
        self._products: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QLabel("قم بإدارة الأقسام والمنتجات، مع إمكانية ترتيبها.")
        header.setWordWrap(True)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # Categories panel
        cat_panel = QVBoxLayout()
        cat_panel.setSpacing(8)
        body.addLayout(cat_panel, 1)

        cat_header = QHBoxLayout()
        cat_header.addWidget(QLabel("الأقسام"))
        self.btn_cat_add = QPushButton("إضافة…")
        self.btn_cat_edit = QPushButton("تعديل…")
        self.btn_cat_delete = QPushButton("حذف")
        cat_header.addWidget(self.btn_cat_add)
        cat_header.addWidget(self.btn_cat_edit)
        cat_header.addWidget(self.btn_cat_delete)
        cat_panel.addLayout(cat_header)

        self.category_list = QListWidget()
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        cat_panel.addWidget(self.category_list, 1)

        cat_actions = QHBoxLayout()
        self.btn_cat_up = QPushButton("⬆ أعلى")
        self.btn_cat_down = QPushButton("⬇ أسفل")
        cat_actions.addWidget(self.btn_cat_up)
        cat_actions.addWidget(self.btn_cat_down)
        cat_panel.addLayout(cat_actions)

        # Products panel
        prod_panel = QVBoxLayout()
        prod_panel.setSpacing(8)
        body.addLayout(prod_panel, 2)

        prod_header = QHBoxLayout()
        prod_header.addWidget(QLabel("المنتجات"))
        self.btn_prod_add = QPushButton("إضافة…")
        self.btn_prod_edit = QPushButton("تعديل…")
        self.btn_prod_delete = QPushButton("حذف")
        prod_header.addWidget(self.btn_prod_add)
        prod_header.addWidget(self.btn_prod_edit)
        prod_header.addWidget(self.btn_prod_delete)
        prod_panel.addLayout(prod_header)

        self.product_table = QTableWidget(0, 5)
        self.product_table.setHorizontalHeaderLabels([
            "المنتج",
            "السعر (قرش)",
            "تتبع",
            "المخزون",
            "حد أدنى",
        ])
        self.product_table.horizontalHeader().setStretchLastSection(True)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        prod_panel.addWidget(self.product_table, 1)

        prod_actions = QHBoxLayout()
        self.btn_prod_up = QPushButton("⬆ أعلى")
        self.btn_prod_down = QPushButton("⬇ أسفل")
        prod_actions.addWidget(self.btn_prod_up)
        prod_actions.addWidget(self.btn_prod_down)
        prod_panel.addLayout(prod_actions)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Signal wiring
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.btn_cat_add.clicked.connect(self._add_category)
        self.btn_cat_edit.clicked.connect(self._edit_category)
        self.btn_cat_delete.clicked.connect(self._delete_category)
        self.btn_cat_up.clicked.connect(lambda: self._move_category(-1))
        self.btn_cat_down.clicked.connect(lambda: self._move_category(1))

        self.btn_prod_add.clicked.connect(self._add_product)
        self.btn_prod_edit.clicked.connect(self._edit_product)
        self.btn_prod_delete.clicked.connect(self._delete_product)
        self.btn_prod_up.clicked.connect(lambda: self._move_product(-1))
        self.btn_prod_down.clicked.connect(lambda: self._move_product(1))
        self.product_table.doubleClicked.connect(lambda _: self._edit_product())

        self._load_categories()

    # ----------------- loading helpers -----------------
    def _load_categories(self, *, select_id: int | None = None) -> None:
        self._categories = self._catalog.list_categories()
        self.category_list.clear()
        selected_row = 0
        for idx, cat in enumerate(self._categories):
            item = QListWidgetItem(cat["name"])
            item.setData(Qt.ItemDataRole.UserRole, cat["id"])
            self.category_list.addItem(item)
            if select_id is not None and cat["id"] == select_id:
                selected_row = idx
        if self._categories:
            self.category_list.setCurrentRow(selected_row)
        else:
            self._products = []
            self.product_table.setRowCount(0)

    def _load_products(self, category_id: int) -> None:
        self._products = self._catalog.list_products(category_id)
        self.product_table.setRowCount(len(self._products))
        for row_idx, prod in enumerate(self._products):
            self.product_table.setItem(row_idx, 0, QTableWidgetItem(prod["name"]))
            self.product_table.setItem(row_idx, 1, QTableWidgetItem(str(prod["price_cents"])))
            self.product_table.setItem(row_idx, 2, QTableWidgetItem("✅" if prod["track_stock"] else "—"))
            stock_text = "" if prod["stock_qty"] is None else f"{prod['stock_qty']:.2f}"
            min_text = "" if prod["min_stock"] is None else f"{prod['min_stock']:.2f}"
            self.product_table.setItem(row_idx, 3, QTableWidgetItem(stock_text))
            self.product_table.setItem(row_idx, 4, QTableWidgetItem(min_text))
            for col in range(5):
                item = self.product_table.item(row_idx, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, prod["id"])

    def _current_category(self) -> tuple[int, dict] | tuple[None, None]:
        row = self.category_list.currentRow()
        if row < 0 or row >= len(self._categories):
            return None, None
        return row, self._categories[row]

    def _current_product(self) -> tuple[int, dict] | tuple[None, None]:
        row = self.product_table.currentRow()
        if row < 0 or row >= len(self._products):
            return None, None
        return row, self._products[row]

    # ----------------- category handlers -----------------
    def _on_category_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._categories):
            self.product_table.setRowCount(0)
            self._products = []
            return
        category_id = self._categories[row]["id"]
        self._load_products(category_id)

    def _add_category(self) -> None:
        name, ok = QInputDialog.getText(self, "إضافة قسم", "اسم القسم:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "اسم القسم مطلوب.")
            return
        try:
            created = self._catalog.create_category(name, username=self._actor)
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self._load_categories(select_id=created["id"])

    def _edit_category(self) -> None:
        row, cat = self._current_category()
        if cat is None:
            return
        name, ok = QInputDialog.getText(self, "تعديل القسم", "اسم القسم:", text=cat["name"])
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "اسم القسم مطلوب.")
            return
        try:
            self._catalog.rename_category(cat["id"], name, username=self._actor)
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر التعديل", str(exc))
            return
        self._load_categories(select_id=cat["id"])
        self.category_list.setCurrentRow(row)

    def _delete_category(self) -> None:
        _, cat = self._current_category()
        if cat is None:
            return
        confirm = QMessageBox.question(
            self,
            "حذف القسم",
            f"سيتم حذف القسم '{cat['name']}' وجميع المنتجات المرتبطة به. هل أنت متأكد؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._catalog.delete_category(cat["id"], username=self._actor)
        self._load_categories()

    def _move_category(self, delta: int) -> None:
        row, cat = self._current_category()
        if cat is None:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= len(self._categories):
            return
        order = [c["id"] for c in self._categories]
        order[row], order[new_row] = order[new_row], order[row]
        self._catalog.reorder_categories(order)
        self._load_categories(select_id=cat["id"])
        self.category_list.setCurrentRow(new_row)

    # ----------------- product handlers -----------------
    def _add_product(self) -> None:
        _, cat = self._current_category()
        if cat is None:
            QMessageBox.warning(self, "تنبيه", "اختر قسمًا أولاً.")
            return
        editor = _ProductEditor(self)
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        try:
            self._catalog.create_product(
                cat["id"],
                values.name,
                values.price_cents,
                username=self._actor,
                track_stock=1 if values.track_stock else 0,
                stock_qty=values.stock_qty,
                min_stock=values.min_stock,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self._load_products(cat["id"])

    def _edit_product(self) -> None:
        _, cat = self._current_category()
        row, prod = self._current_product()
        if cat is None or prod is None:
            return
        editor = _ProductEditor(
            self,
            values=_ProductValues(
                name=prod["name"],
                price_cents=prod["price_cents"],
                track_stock=bool(prod["track_stock"]),
                stock_qty=float(prod["stock_qty"] or 0.0),
                min_stock=float(prod["min_stock"] or 0.0),
            ),
        )
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        try:
            self._catalog.update_product(
                prod["id"],
                name=values.name,
                price_cents=values.price_cents,
                track_stock=1 if values.track_stock else 0,
                stock_qty=values.stock_qty,
                min_stock=values.min_stock,
                username=self._actor,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر التعديل", str(exc))
            return
        self._load_products(cat["id"])
        self.product_table.setCurrentCell(row, 0)

    def _delete_product(self) -> None:
        _, cat = self._current_category()
        _, prod = self._current_product()
        if cat is None or prod is None:
            return
        confirm = QMessageBox.question(
            self,
            "حذف المنتج",
            f"سيتم حذف المنتج '{prod['name']}'. هل أنت متأكد؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._catalog.delete_product(prod["id"], username=self._actor)
        self._load_products(cat["id"])

    def _move_product(self, delta: int) -> None:
        _, cat = self._current_category()
        row, prod = self._current_product()
        if cat is None or prod is None:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= len(self._products):
            return
        order = [p["id"] for p in self._products]
        order[row], order[new_row] = order[new_row], order[row]
        self._catalog.reorder_products(cat["id"], order)
        self._load_products(cat["id"])
        self.product_table.setCurrentCell(new_row, 0)
