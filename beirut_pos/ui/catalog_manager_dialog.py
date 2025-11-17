from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
    customizable: bool
    track_stock: bool
    stock_qty: float
    min_stock: float
    package_size: float
    product_type: str
    sugar_levels: list[str]


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
        self.price_edit.setSingleStep(1)
        self.price_edit.setSuffix(" ج.م")
        self.custom_box = QCheckBox("يدعم خيارات مخصصة")
        self.track_box = QCheckBox("تتبع المخزون")
        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setRange(0, 1_000_000)
        self.stock_spin.setDecimals(2)
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0, 1_000_000)
        self.min_spin.setDecimals(2)
        self.package_size_spin = QDoubleSpinBox()
        self.package_size_spin.setRange(0, 100_000)
        self.package_size_spin.setDecimals(2)
        self.package_size_spin.setMinimum(1.0)
        self.package_add_spin = QDoubleSpinBox()
        self.package_add_spin.setRange(0, 100_000)
        self.package_add_spin.setDecimals(2)
        self.package_hint = QLabel("—")
        self.package_hint.setStyleSheet("color: #b9b9b9; font-size: 9.5pt;")
        self.package_apply = QPushButton("إضافة")
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("مثال: مشروب ساخن")
        self.sugar_list = QListWidget()
        self.sugar_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sugar_list.setMinimumHeight(90)
        self.sugar_list.setAlternatingRowColors(True)
        sugar_buttons = QHBoxLayout()
        self.btn_sugar_add = QPushButton("إضافة مستوى…")
        self.btn_sugar_edit = QPushButton("تعديل…")
        self.btn_sugar_delete = QPushButton("حذف")
        for btn in (self.btn_sugar_add, self.btn_sugar_edit, self.btn_sugar_delete):
            sugar_buttons.addWidget(btn)
        sugar_container = QVBoxLayout()
        sugar_container.setSpacing(6)
        sugar_container.addWidget(self.sugar_list)
        sugar_buttons_widget = QWidget()
        sugar_buttons_widget.setLayout(sugar_buttons)
        sugar_container.addWidget(sugar_buttons_widget)
        sugar_widget = QWidget()
        sugar_widget.setLayout(sugar_container)

        form.addRow("اسم المنتج:", self.name_edit)
        form.addRow("السعر (ج.م):", self.price_edit)
        form.addRow("نوع المنتج:", self.type_edit)
        form.addRow("مستويات السكر:", sugar_widget)
        form.addRow("", self.custom_box)
        form.addRow("", self.track_box)
        form.addRow("المخزون الحالي:", self.stock_spin)
        form.addRow("حد أدنى للتنبيه:", self.min_spin)
        form.addRow("حجم العبوة (وحدات):", self.package_size_spin)
        pkg_widget = QWidget()
        pkg_layout = QHBoxLayout(pkg_widget)
        pkg_layout.setContentsMargins(0, 0, 0, 0)
        pkg_layout.setSpacing(8)
        pkg_layout.addWidget(self.package_add_spin)
        pkg_layout.addWidget(self.package_apply)
        pkg_layout.addWidget(self.package_hint, 1)
        form.addRow("إضافة للمخزون (عبوات):", pkg_widget)

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
            self.custom_box.setChecked(values.customizable)
            self.track_box.setChecked(values.track_stock)
            self.stock_spin.setValue(values.stock_qty)
            self.min_spin.setValue(values.min_stock)
            self.package_size_spin.setValue(max(1.0, values.package_size))
            self.type_edit.setText(values.product_type)
            self._populate_sugar_levels(values.sugar_levels)
        else:
            self.track_box.setChecked(True)
            self.package_size_spin.setValue(1.0)

        self._toggle_stock(self.track_box.isChecked())
        self.package_add_spin.setValue(0)
        self._update_package_hint()
        self.track_box.toggled.connect(self._toggle_stock)
        self.package_add_spin.valueChanged.connect(self._update_package_hint)
        self.package_size_spin.valueChanged.connect(self._update_package_hint)
        self.package_apply.clicked.connect(self._apply_package_add)
        self.btn_sugar_add.clicked.connect(self._add_sugar_level)
        self.btn_sugar_edit.clicked.connect(self._edit_sugar_level)
        self.btn_sugar_delete.clicked.connect(self._delete_sugar_level)

    def _toggle_stock(self, checked: bool) -> None:
        self.stock_spin.setEnabled(checked)
        self.min_spin.setEnabled(checked)
        self.package_size_spin.setEnabled(checked)
        self.package_add_spin.setEnabled(checked)
        self.package_apply.setEnabled(checked)
        self.package_hint.setEnabled(checked)

    def _update_package_hint(self) -> None:
        size = max(0.0, float(self.package_size_spin.value()))
        packages = max(0.0, float(self.package_add_spin.value()))
        if packages <= 0 or size <= 0:
            self.package_hint.setText("أدخل عبوات لإضافتها للمخزون.")
            return
        units = packages * size
        self.package_hint.setText(f"{packages:g} عبوة = {units:g} وحدة")

    def _apply_package_add(self) -> None:
        if not self.track_box.isChecked():
            QMessageBox.warning(self, "المخزون معطل", "فعّل تتبع المخزون لتحديث الكمية.")
            return
        size = float(self.package_size_spin.value())
        packages = float(self.package_add_spin.value())
        if size <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "حدد حجم العبوة أولاً.")
            return
        if packages <= 0:
            QMessageBox.warning(self, "قيمة غير صالحة", "أدخل عدد العبوات المراد إضافتها.")
            return
        units = packages * size
        self.stock_spin.setValue(self.stock_spin.value() + units)
        self.package_add_spin.setValue(0)
        self._update_package_hint()

    def _populate_sugar_levels(self, levels: list[str]) -> None:
        self.sugar_list.clear()
        for level in levels:
            cleaned = level.strip()
            if cleaned:
                self.sugar_list.addItem(cleaned)

    def _add_sugar_level(self) -> None:
        text, ok = QInputDialog.getText(self, "إضافة مستوى سكر", "المستوى:")
        if not ok:
            return
        cleaned = text.strip()
        if not cleaned:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال مستوى صالح.")
            return
        self.sugar_list.addItem(cleaned)

    def _edit_sugar_level(self) -> None:
        current = self.sugar_list.currentItem()
        if current is None:
            return
        text, ok = QInputDialog.getText(self, "تعديل مستوى السكر", "المستوى:", text=current.text())
        if not ok:
            return
        cleaned = text.strip()
        if not cleaned:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال مستوى صالح.")
            return
        current.setText(cleaned)

    def _delete_sugar_level(self) -> None:
        row = self.sugar_list.currentRow()
        if row < 0:
            return
        item = self.sugar_list.takeItem(row)
        if item is not None:
            item = None

    def _collect_values(self) -> _ProductValues | None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "اسم المنتج مطلوب.")
            return None
        price = int(self.price_edit.value())
        if price <= 0:
            QMessageBox.warning(self, "خطأ", "السعر يجب أن يكون أكبر من صفر.")
            return None
        product_type = self.type_edit.text().strip()
        sugar_levels = [self.sugar_list.item(i).text().strip() for i in range(self.sugar_list.count())]
        sugar_levels = [lvl for lvl in sugar_levels if lvl]
        return _ProductValues(
            name=name,
            price_cents=price,
            customizable=self.custom_box.isChecked(),
            track_stock=self.track_box.isChecked(),
            stock_qty=float(self.stock_spin.value()),
            min_stock=float(self.min_spin.value()),
            package_size=float(max(1.0, self.package_size_spin.value())),
            product_type=product_type,
            sugar_levels=sugar_levels,
        )

    def accept(self) -> None:
        values = self._collect_values()
        if not values:
            return
        self._result = values
        super().accept()

    def get_values(self) -> _ProductValues | None:
        return self._result


class _OptionEditor(QDialog):
    def __init__(self, parent=None, *, label: str = "", delta: int = 0):
        super().__init__(parent)
        self.setWindowTitle("خيار المنتج")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._result: tuple[str, int] | None = None

        form = QFormLayout(self)
        self.label_edit = QLineEdit(label)
        self.delta_edit = QSpinBox()
        self.delta_edit.setRange(-1_000_000, 1_000_000)
        self.delta_edit.setSingleStep(1)
        self.delta_edit.setSuffix(" ج.م")
        self.delta_edit.setValue(delta)
        form.addRow("اسم الخيار:", self.label_edit)
        form.addRow("فرق السعر (ج.م):", self.delta_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        form.addRow(btn_row)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def accept(self) -> None:
        label = self.label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "خطأ", "اسم الخيار مطلوب.")
            return
        self._result = (label, int(self.delta_edit.value()))
        super().accept()

    def get_values(self) -> tuple[str, int] | None:
        return self._result


class CatalogManagerDialog(BigDialog):
    def __init__(self, actor: str = "admin", parent=None):
        super().__init__("إدارة الكتالوج", remember_key="catalog_admin", parent=parent)
        self._actor = actor
        self._catalog = order_manager.catalog
        self._categories: list[dict] = []
        self._products: list[dict] = []
        self._options: list[dict] = []

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

        self.product_table = QTableWidget(0, 9)
        self.product_table.setHorizontalHeaderLabels([
            "المنتج",
            "السعر (ج.م)",
            "نوع المنتج",
            "مستويات السكر",
            "مخصص",
            "تتبع",
            "المخزون",
            "حد أدنى",
            "العبوة",
        ])
        self.product_table.horizontalHeader().setStretchLastSection(True)
        self.product_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for idx in range(1, 9):
            self.product_table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeMode.ResizeToContents)
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

        self.options_group = QGroupBox("خيارات المنتج")
        opt_layout = QVBoxLayout(self.options_group)
        self.options_table = QTableWidget(0, 2)
        self.options_table.setHorizontalHeaderLabels(["الخيار", "فرق السعر (ج.م)"])
        self.options_table.horizontalHeader().setStretchLastSection(True)
        self.options_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.options_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.options_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        opt_layout.addWidget(self.options_table, 1)

        opt_buttons = QHBoxLayout()
        self.btn_opt_add = QPushButton("إضافة خيار…")
        self.btn_opt_edit = QPushButton("تعديل…")
        self.btn_opt_delete = QPushButton("حذف")
        self.btn_opt_up = QPushButton("⬆")
        self.btn_opt_down = QPushButton("⬇")
        for btn in (self.btn_opt_add, self.btn_opt_edit, self.btn_opt_delete, self.btn_opt_up, self.btn_opt_down):
            opt_buttons.addWidget(btn)
        opt_layout.addLayout(opt_buttons)
        prod_panel.addWidget(self.options_group, 1)
        self.options_group.setEnabled(False)

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
        self.product_table.currentCellChanged.connect(self._on_product_changed)

        self.btn_opt_add.clicked.connect(self._add_option)
        self.btn_opt_edit.clicked.connect(self._edit_option)
        self.btn_opt_delete.clicked.connect(self._delete_option)
        self.btn_opt_up.clicked.connect(lambda: self._move_option(-1))
        self.btn_opt_down.clicked.connect(lambda: self._move_option(1))
        self.options_table.doubleClicked.connect(lambda _: self._edit_option())

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
            self._options = []
            self.options_table.setRowCount(0)
            self.options_group.setEnabled(False)

    def _load_products(self, category_id: int) -> None:
        self._products = self._catalog.list_products(category_id)
        self.product_table.setRowCount(len(self._products))
        for row_idx, prod in enumerate(self._products):
            self.product_table.setItem(row_idx, 0, QTableWidgetItem(prod["name"]))
            self.product_table.setItem(row_idx, 1, QTableWidgetItem(str(prod["price_cents"])))
            self.product_table.setItem(row_idx, 2, QTableWidgetItem(prod.get("product_type") or ""))
            sugar_levels = prod.get("sugar_levels") or []
            sugar_text = "، ".join(sugar_levels) if sugar_levels else "—"
            self.product_table.setItem(row_idx, 3, QTableWidgetItem(sugar_text))
            self.product_table.setItem(row_idx, 4, QTableWidgetItem("✅" if prod["customizable"] else "—"))
            self.product_table.setItem(row_idx, 5, QTableWidgetItem("✅" if prod["track_stock"] else "—"))
            stock_text = "" if prod["stock_qty"] is None else f"{prod['stock_qty']:.2f}"
            min_text = "" if prod["min_stock"] is None else f"{prod['min_stock']:.2f}"
            self.product_table.setItem(row_idx, 6, QTableWidgetItem(stock_text))
            self.product_table.setItem(row_idx, 7, QTableWidgetItem(min_text))
            pkg_value = prod.get("package_size")
            if pkg_value:
                package_text = f"{float(pkg_value):g}"
            else:
                package_text = ""
            self.product_table.setItem(row_idx, 8, QTableWidgetItem(package_text))
            for col in range(9):
                item = self.product_table.item(row_idx, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, prod["id"])
        current = self.product_table.currentRow()
        if self._products and current < 0:
            self.product_table.setCurrentCell(0, 0)
            current = 0
        self._on_product_changed(current)

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

    def _current_option(self) -> tuple[int, dict] | tuple[None, None]:
        row = self.options_table.currentRow()
        if row < 0 or row >= len(self._options):
            return None, None
        return row, self._options[row]

    # ----------------- category handlers -----------------
    def _on_category_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._categories):
            self.product_table.setRowCount(0)
            self._products = []
            self._load_options(None)
            return
        category_id = self._categories[row]["id"]
        self._load_products(category_id)

    def _on_product_changed(self, row: int, *_) -> None:
        if row < 0 or row >= len(self._products):
            self._load_options(None)
            return
        self._load_options(self._products[row])

    def _load_options(self, product: dict | None) -> None:
        if not product or not product.get("customizable"):
            self._options = []
            self.options_table.setRowCount(0)
            self.options_group.setEnabled(False)
            return
        options = self._catalog.list_options(product["id"])
        self._options = options
        self.options_table.setRowCount(len(options))
        for idx, opt in enumerate(options):
            self.options_table.setItem(idx, 0, QTableWidgetItem(opt["label"]))
            self.options_table.setItem(idx, 1, QTableWidgetItem(str(opt["price_delta_cents"])))
            for col in range(2):
                item = self.options_table.item(idx, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, opt["id"])
        self.options_group.setEnabled(True)
        if options and self.options_table.currentRow() < 0:
            self.options_table.setCurrentCell(0, 0)

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
                customizable=1 if values.customizable else 0,
                track_stock=1 if values.track_stock else 0,
                stock_qty=values.stock_qty,
                min_stock=values.min_stock,
                package_size=values.package_size,
                product_type=values.product_type,
                sugar_levels=values.sugar_levels,
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
                customizable=bool(prod.get("customizable", 0)),
                track_stock=bool(prod["track_stock"]),
                stock_qty=float(prod["stock_qty"] or 0.0),
                min_stock=float(prod["min_stock"] or 0.0),
                package_size=float(prod.get("package_size") or 1.0),
                product_type=prod.get("product_type", ""),
                sugar_levels=list(prod.get("sugar_levels") or []),
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
                customizable=1 if values.customizable else 0,
                track_stock=1 if values.track_stock else 0,
                stock_qty=values.stock_qty,
                min_stock=values.min_stock,
                package_size=values.package_size,
                product_type=values.product_type,
                sugar_levels=values.sugar_levels,
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

    # ----------------- option handlers -----------------
    def _ensure_customizable(self, product: dict | None) -> bool:
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتجًا أولاً.")
            return False
        if not product.get("customizable"):
            QMessageBox.information(
                self,
                "التخصيص معطل",
                "فعّل خيار \"يدعم خيارات مخصصة\" للمنتج قبل إضافة الخيارات.",
            )
            return False
        return True

    def _add_option(self) -> None:
        _, product = self._current_product()
        if not self._ensure_customizable(product):
            return
        editor = _OptionEditor(self)
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        try:
            self._catalog.create_option(
                product["id"],
                values[0],
                values[1],
                username=self._actor,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self._load_options(product)

    def _edit_option(self) -> None:
        _, product = self._current_product()
        row, option = self._current_option()
        if not self._ensure_customizable(product) or option is None:
            return
        editor = _OptionEditor(self, label=option["label"], delta=option["price_delta_cents"])
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        try:
            self._catalog.update_option(
                option["id"],
                label=values[0],
                price_delta_cents=values[1],
                username=self._actor,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر التعديل", str(exc))
            return
        self._load_options(product)
        self.options_table.setCurrentCell(row, 0)

    def _delete_option(self) -> None:
        _, product = self._current_product()
        _, option = self._current_option()
        if not self._ensure_customizable(product) or option is None:
            return
        confirm = QMessageBox.question(
            self,
            "حذف الخيار",
            f"سيتم حذف الخيار '{option['label']}'. هل أنت متأكد؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._catalog.delete_option(option["id"], username=self._actor)
        self._load_options(product)

    def _move_option(self, delta: int) -> None:
        _, product = self._current_product()
        row, option = self._current_option()
        if not self._ensure_customizable(product) or option is None:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= len(self._options):
            return
        order = [opt["id"] for opt in self._options]
        order[row], order[new_row] = order[new_row], order[row]
        self._catalog.reorder_options(product["id"], order)
        self._load_options(product)
        self.options_table.setCurrentCell(new_row, 0)
