from __future__ import annotations
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QColorDialog,
    QFormLayout,
    QFrame,
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


def _avatar_palette(seed: str) -> tuple[str, str]:
    palettes = [
        ("#2f80ed", "#e9f2ff"),
        ("#9b51e0", "#f3e9ff"),
        ("#f2994a", "#fff1e0"),
        ("#56ccf2", "#e8f9ff"),
        ("#27ae60", "#e8f7ef"),
        ("#eb5757", "#ffecec"),
    ]
    idx = abs(hash(seed or "")) % len(palettes)
    return palettes[idx]


@dataclass(slots=True)
class _ProductValues:
    name: str
    price_cents: int
    customizable: bool
    track_stock: bool
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

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        self.setMinimumWidth(520)

        preview = self._build_preview()
        root.addWidget(preview)

        self.name_edit = QLineEdit()
        self.price_edit = QSpinBox()
        self.price_edit.setRange(0, 2_000_000)
        self.price_edit.setSingleStep(1)
        self.price_edit.setSuffix(" ج.م")
        self.custom_box = QCheckBox("يدعم خيارات مخصصة")
        self.track_box = QCheckBox("تتبع المخزون")
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0, 1_000_000)
        self.min_spin.setDecimals(2)
        self.package_size_spin = QDoubleSpinBox()
        self.package_size_spin.setRange(0, 100_000)
        self.package_size_spin.setDecimals(2)
        self.package_size_spin.setMinimum(1.0)
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

        basics = QGroupBox("التعريف والتسعير")
        basics_form = QFormLayout(basics)
        basics_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        basics_form.addRow("اسم المنتج:", self.name_edit)
        basics_form.addRow("نوع المنتج:", self.type_edit)
        basics_form.addRow("السعر (ج.م):", self.price_edit)
        basics_form.addRow("مستويات السكر:", sugar_widget)

        toggles = QGroupBox("خيارات الطلب")
        toggle_layout = QVBoxLayout(toggles)
        toggle_layout.setSpacing(4)
        toggle_layout.addWidget(self.custom_box)
        toggle_layout.addWidget(self.track_box)

        stock = QGroupBox("المخزون والتعبئة")
        stock_form = QFormLayout(stock)
        stock_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.package_size_spin.setSuffix(" وحدة")
        stock_form.addRow("حجم العبوة (وحدات):", self.package_size_spin)
        stock_form.addRow("حد أدنى للتنبيه:", self.min_spin)

        sections = QHBoxLayout()
        sections.setSpacing(12)
        sections.addWidget(basics, 2)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        sidebar.addWidget(toggles)
        sidebar.addWidget(stock)
        sections.addLayout(sidebar, 1)
        root.addLayout(sections)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        if values:
            self.name_edit.setText(values.name)
            self.price_edit.setValue(values.price_cents)
            self.custom_box.setChecked(values.customizable)
            self.track_box.setChecked(values.track_stock)
            self.min_spin.setValue(values.min_stock)
            self.package_size_spin.setValue(max(1.0, values.package_size))
            self.type_edit.setText(values.product_type)
            self._populate_sugar_levels(values.sugar_levels)
        else:
            self.track_box.setChecked(True)
            self.package_size_spin.setValue(1.0)

        self._toggle_stock(self.track_box.isChecked())
        self.track_box.toggled.connect(self._toggle_stock)
        self.btn_sugar_add.clicked.connect(self._add_sugar_level)
        self.btn_sugar_edit.clicked.connect(self._edit_sugar_level)
        self.btn_sugar_delete.clicked.connect(self._delete_sugar_level)
        self.name_edit.textChanged.connect(self._refresh_preview)
        self.price_edit.valueChanged.connect(self._refresh_preview)
        self.type_edit.textChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _toggle_stock(self, checked: bool) -> None:
        self.min_spin.setEnabled(checked)
        self.package_size_spin.setEnabled(checked)

    def _build_preview(self) -> QWidget:
        card = QFrame()
        card.setObjectName("productPreviewCard")
        card.setStyleSheet(
            "#productPreviewCard {"
            "  border: 1px solid #dcdde3;"
            "  border-radius: 10px;"
            "  background: #f9fafc;"
            "  padding: 12px;"
            "}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(56, 56)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet(
            "border-radius: 12px; color: white; font-weight: 800; font-size: 18px;"
        )

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.preview_name_label = QLabel("—")
        self.preview_name_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.preview_meta_label = QLabel("")
        self.preview_meta_label.setStyleSheet(
            "color: #4a5060; background-color: #eef1f7; padding: 2px 8px; border-radius: 8px;"
        )
        text_box.addWidget(self.preview_name_label)
        text_box.addWidget(self.preview_meta_label)

        self.preview_price_label = QLabel("0 ج.م")
        self.preview_price_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.preview_price_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #2f3b52;")

        layout.addWidget(self.avatar_label)
        layout.addLayout(text_box, 1)
        layout.addWidget(self.preview_price_label, 0, Qt.AlignmentFlag.AlignRight)
        return card

    def _populate_sugar_levels(self, levels: list[str]) -> None:
        self.sugar_list.clear()
        for level in levels:
            cleaned = level.strip()
            if cleaned:
                self.sugar_list.addItem(cleaned)

    def _refresh_preview(self) -> None:
        name = self.name_edit.text().strip() or "المنتج الجديد"
        product_type = self.type_edit.text().strip()
        price = int(self.price_edit.value())

        fg, bg = _avatar_palette(name)
        initials = (name[:2] if len(name) >= 2 else name or "? ").strip()
        self.avatar_label.setText(initials)
        self.avatar_label.setStyleSheet(
            f"border-radius: 12px; color: white; font-weight: 800; font-size: 18px;"
            f" background-color: {fg};"
        )

        self.preview_name_label.setText(name)
        meta = product_type if product_type else "بدون نوع محدد"
        self.preview_meta_label.setText(meta)
        self.preview_meta_label.setStyleSheet(
            f"color: #4a5060; background-color: {bg}; padding: 2px 8px; border-radius: 8px;"
        )
        self.preview_price_label.setText(f"{price:,} ج.م")

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


class _CategoryEditor(QDialog):
    def __init__(self, parent=None, *, name: str = "", color: str = ""):
        super().__init__(parent)
        self.setWindowTitle("القسم")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._color_value = color or ""
        self._result: tuple[str, str] | None = None

        form = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        form.addRow("اسم القسم:", self.name_edit)

        color_row = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setMinimumWidth(80)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.color_preview.setStyleSheet("border: 1px solid #ccc; padding: 6px; border-radius: 4px;")
        self._apply_color_preview()
        color_btn = QPushButton("اختيار اللون…")
        color_btn.clicked.connect(self._choose_color)
        color_row.addWidget(color_btn)
        color_row.addWidget(self.color_preview, 1)
        color_row.addStretch(1)
        color_widget = QWidget()
        color_widget.setLayout(color_row)
        form.addRow("لون القسم:", color_widget)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        form.addRow(btn_row)

    def _choose_color(self) -> None:
        initial = QColor(self._color_value) if self._color_value else QColor("#f6f7fb")
        chosen = QColorDialog.getColor(initial, self, "اختر لون القسم")
        if chosen.isValid():
            self._color_value = chosen.name()
            self._apply_color_preview()

    def _apply_color_preview(self) -> None:
        label = self._color_value or "بدون لون مخصّص"
        self.color_preview.setText(label)
        bg = self._color_value or "#f6f7fb"
        self.color_preview.setStyleSheet(
            f"background-color: {bg}; border: 1px solid #ccc; padding: 6px; border-radius: 4px;"
        )

    def accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "اسم القسم مطلوب.")
            return
        self._result = (name, self._color_value)
        super().accept()

    def get_values(self) -> tuple[str, str] | None:
        return self._result


class CatalogManagerDialog(BigDialog):
    def __init__(self, actor: str = "admin", parent=None):
        super().__init__("إدارة الكتالوج", remember_key="catalog_admin", parent=parent)
        self._actor = actor
        self._catalog = order_manager.catalog
        self._categories: list[dict] = []
        self._products: list[dict] = []
        self._options: list[dict] = []

        # Make the dialog generous so both tables are clearly visible even with many rows.
        self.setMinimumSize(1100, 750)

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
        self.btn_cat_color = QPushButton("لون…")
        self.btn_cat_delete = QPushButton("حذف")
        cat_header.addWidget(self.btn_cat_add)
        cat_header.addWidget(self.btn_cat_edit)
        cat_header.addWidget(self.btn_cat_color)
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

        self.product_table = QTableWidget(0, 6)
        self.product_table.setHorizontalHeaderLabels([
            "المنتج",
            "السعر (ج.م)",
            "تفاصيل الطلب",
            "الخيارات",
            "المخزون",
            "التعبئة",
        ])
        self.product_table.horizontalHeader().setStretchLastSection(False)
        self.product_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for idx in range(1, 6):
            self.product_table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.ResizeMode.Interactive)
        self.product_table.setColumnWidth(1, 90)
        self.product_table.setColumnWidth(2, 110)
        self.product_table.setColumnWidth(3, 100)
        self.product_table.setColumnWidth(4, 80)
        self.product_table.setColumnWidth(5, 80)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_table.setAlternatingRowColors(True)
        self.product_table.verticalHeader().setVisible(False)
        row_height = 82
        header_height = self.product_table.horizontalHeader().sizeHint().height()
        self.product_table.setMinimumHeight(row_height * 10 + header_height)

        prod_actions = QHBoxLayout()
        self.btn_prod_up = QPushButton("⬆ أعلى")
        self.btn_prod_down = QPushButton("⬇ أسفل")
        prod_actions.addWidget(self.btn_prod_up)
        prod_actions.addWidget(self.btn_prod_down)

        prod_table_container = QWidget()
        prod_table_layout = QVBoxLayout(prod_table_container)
        prod_table_layout.setContentsMargins(0, 0, 0, 0)
        prod_table_layout.setSpacing(6)
        prod_table_layout.addWidget(self.product_table, 1)
        prod_table_layout.addLayout(prod_actions)
        prod_panel.addWidget(prod_table_container, 3)

        self.options_group = QGroupBox("خيارات المنتج")
        opt_layout = QVBoxLayout(self.options_group)
        self.options_table = QTableWidget(0, 2)
        self.options_table.setHorizontalHeaderLabels(["الخيار", "فرق السعر (ج.م)"])
        self.options_table.horizontalHeader().setStretchLastSection(True)
        self.options_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.options_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.options_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.options_table.setMinimumHeight(220)
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
        prod_panel.addWidget(self.options_group, 2)
        self.options_group.setEnabled(False)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer.addWidget(self.options_group, 1)
        footer.addStretch(1)
        footer.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        root.addLayout(footer)

        # Signal wiring
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.btn_cat_add.clicked.connect(self._add_category)
        self.btn_cat_edit.clicked.connect(self._edit_category)
        self.btn_cat_color.clicked.connect(self._change_category_color)
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
    def _category_color(self, category_id: int) -> str:
        for cat in self._categories:
            if cat["id"] == category_id:
                return cat.get("color") or ""
        return ""

    def _build_pill(self, text: str, *, bg: str = "#eef1f7", fg: str = "#1f2937") -> QLabel:
        pill = QLabel(text)
        pill.setStyleSheet(
            f"padding: 4px 10px; border-radius: 10px; background-color: {bg}; color: {fg}; font-size: 11px;"
        )
        return pill

    def _sugar_text(self, product: dict) -> str:
        sugar_levels = product.get("sugar_levels") or []
        return "، ".join(sugar_levels) if sugar_levels else "بدون مستويات سكر"

    def _render_product_card(self, product: dict, category_color: str) -> QWidget:
        card = QFrame()
        card.setObjectName("productCard")
        bg = category_color or "#f9fafc"
        card.setStyleSheet(
            f"#productCard {{ background-color: {bg}; border: 1px solid #e5e7eb; border-radius: 12px; }}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        meta = QVBoxLayout()
        meta.setSpacing(4)
        name_label = QLabel(product.get("name") or "—")
        name_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        meta.addWidget(name_label)

        sugar_text = self._sugar_text(product)
        product_type = product.get("product_type") or "بدون نوع محدد"
        detail = QLabel(f"{product_type} • {sugar_text}")
        detail.setStyleSheet("color: #475467; font-size: 12px;")
        meta.addWidget(detail)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(6)
        if product.get("customizable"):
            pill_row.addWidget(self._build_pill("خيارات مخصصة", bg="#e8f5e9", fg="#166534"))
        if product.get("track_stock"):
            stock_qty = product.get("stock_qty")
            if stock_qty is None:
                stock_label = ("مخزون يدوي", "#fff7ed", "#c2410c")
            elif stock_qty <= 0:
                stock_label = ("غير متوفر", "#fef2f2", "#b42318")
            elif stock_qty <= 3:
                stock_label = ("كمية محدودة", "#fff7ed", "#c2410c")
            else:
                stock_label = ("متوفر", "#ecfdf3", "#027a48")
            pill_row.addWidget(self._build_pill(stock_label[0], bg=stock_label[1], fg=stock_label[2]))
        pill_row.addStretch(1)
        pill_widget = QWidget()
        pill_widget.setLayout(pill_row)
        meta.addWidget(pill_widget)

        layout.addLayout(meta, 1)
        layout.addStretch(1)

        return card

    def _options_text(self, product: dict) -> str:
        customizable = "✅" if product.get("customizable") else "—"
        sugar_text = self._sugar_text(product)
        return f"سعر إضافي: {customizable} | سكر: {sugar_text}"

    def _stock_text(self, product: dict) -> str:
        if not product.get("track_stock"):
            return "لا يتم تتبعه"
        stock_qty = product.get("stock_qty")
        min_stock = product.get("min_stock")
        stock_display = "—" if stock_qty is None else f"{float(stock_qty):g}"
        min_display = "—" if min_stock is None else f"{float(min_stock):g}"
        return f"كمية: {stock_display} | حد أدنى: {min_display}"

    def _packaging_text(self, product: dict) -> str:
        pkg_value = product.get("package_size")
        if not pkg_value:
            return "—"
        return f"{float(pkg_value):g} وحدة"

    def _load_categories(self, *, select_id: int | None = None) -> None:
        self._categories = self._catalog.list_categories()
        self.category_list.clear()
        selected_row = 0
        for idx, cat in enumerate(self._categories):
            item = QListWidgetItem(cat["name"])
            item.setData(Qt.ItemDataRole.UserRole, cat["id"])
            color_value = cat.get("color") or ""
            if color_value:
                item.setBackground(QColor(color_value))
                item.setToolTip(f"{cat['name']} — {color_value}")
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
        category_color = self._category_color(category_id)
        for row_idx, prod in enumerate(self._products):
            card = self._render_product_card(prod, category_color)
            self.product_table.setCellWidget(row_idx, 0, card)

            price_item = QTableWidgetItem(f"{prod['price_cents']:,}")
            details_item = QTableWidgetItem(
                f"{prod.get('product_type') or '—'} • {self._sugar_text(prod)}"
            )
            options_item = QTableWidgetItem(self._options_text(prod))
            stock_item = QTableWidgetItem(self._stock_text(prod))
            package_item = QTableWidgetItem(self._packaging_text(prod))

            cells = [price_item, details_item, options_item, stock_item, package_item]
            for col_idx, cell in enumerate(cells, start=1):
                self.product_table.setItem(row_idx, col_idx, cell)
                cell.setData(Qt.ItemDataRole.UserRole, prod["id"])

            self.product_table.setRowHeight(row_idx, 82)
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
        editor = _CategoryEditor(self)
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        name, color = values
        try:
            created = self._catalog.create_category(name, username=self._actor, color=color)
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self._load_categories(select_id=created["id"])

    def _edit_category(self) -> None:
        row, cat = self._current_category()
        if cat is None:
            return
        editor = _CategoryEditor(self, name=cat["name"], color=cat.get("color") or "")
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        name, color = values
        try:
            self._catalog.rename_category(cat["id"], name, username=self._actor, color=color)
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

    def _change_category_color(self) -> None:
        row, cat = self._current_category()
        if cat is None:
            return

        current_color = cat.get("color") or ""
        initial = QColor(current_color) if current_color else QColor("#f6f7fb")
        chosen = QColorDialog.getColor(initial, self, "اختر لون القسم")
        if not chosen.isValid():
            return

        try:
            self._catalog.rename_category(
                cat["id"],
                cat["name"],
                username=self._actor,
                color=chosen.name(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "تعذر التعديل", str(exc))
            return
        self._load_categories(select_id=cat["id"])
        if row >= 0:
            self.category_list.setCurrentRow(row)

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
                stock_qty=0,
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
                stock_qty=None,
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
