# beirut_pos/ui/admin_products_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QMessageBox, QCheckBox, QDoubleSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from .common.big_dialog import BigDialog
from ..services.orders import order_manager

class AdminProductsDialog(BigDialog):
    def __init__(self, categories: list[str], on_add_category, on_add_product, current_admin="admin"):
        super().__init__("إدارة الأصناف والمنتجات", remember_key="admin_products")
        self.current_admin = current_admin
        self.on_add_category = on_add_category
        self.on_add_product = on_add_product
        self._categories = categories

        tabs = QTabWidget()

        # --- Tab 1: Add Product ---
        t_add = QWidget(); v1 = QVBoxLayout(t_add)

        row1 = QHBoxLayout()
        self.cat_combo = QComboBox(); self.cat_combo.addItems(categories); self.cat_combo.setEditable(True)
        row1.addWidget(QLabel("القسم:")); row1.addWidget(self.cat_combo)
        v1.addLayout(row1)

        row2 = QHBoxLayout()
        self.prod_name = QLineEdit(); self.prod_name.setPlaceholderText("اسم المنتج")
        self.price = QSpinBox(); self.price.setRange(0, 10_000_000); self.price.setSingleStep(500); self.price.setValue(10000)
        row2.addWidget(QLabel("المنتج:")); row2.addWidget(self.prod_name, 2)
        row2.addWidget(QLabel("السعر (قرش):")); row2.addWidget(self.price)
        v1.addLayout(row2)

        row3 = QHBoxLayout()
        self.track_cb = QCheckBox("تتبع المخزون"); self.track_cb.setChecked(True)
        self.stock = QDoubleSpinBox(); self.stock.setDecimals(2); self.stock.setRange(0, 1_000_000); self.stock.setValue(0)
        self.min_stock = QDoubleSpinBox(); self.min_stock.setDecimals(2); self.min_stock.setRange(0, 1_000_000); self.min_stock.setValue(0)
        row3.addWidget(self.track_cb)
        row3.addWidget(QLabel("المخزون:")); row3.addWidget(self.stock)
        row3.addWidget(QLabel("حد أدنى:")); row3.addWidget(self.min_stock)
        v1.addLayout(row3)

        def _toggle_stock(chk):
            self.stock.setEnabled(chk); self.min_stock.setEnabled(chk)
        _toggle_stock(True); self.track_cb.toggled.connect(_toggle_stock)

        add_btn = QPushButton("إضافة المنتج"); add_btn.setDefault(True)
        add_btn.clicked.connect(self._add_product)
        v1.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(t_add, "إضافة منتج")

        # --- Tab 2: Update Price ---
        t_upd = QWidget(); v2 = QVBoxLayout(t_upd)
        row4 = QHBoxLayout()
        self.cat_u = QComboBox(); self.cat_u.addItems(categories); self.cat_u.setEditable(True)
        self.name_u = QLineEdit(); self.name_u.setPlaceholderText("اسم المنتج")
        self.new_price = QSpinBox(); self.new_price.setRange(0, 10_000_000); self.new_price.setSingleStep(500)
        row4.addWidget(QLabel("القسم:")); row4.addWidget(self.cat_u)
        row4.addWidget(QLabel("المنتج:")); row4.addWidget(self.name_u, 1)
        row4.addWidget(QLabel("سعر جديد (قرش):")); row4.addWidget(self.new_price)
        v2.addLayout(row4)
        upd = QPushButton("تحديث السعر"); upd.clicked.connect(self._update_price)
        v2.addWidget(upd, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(t_upd, "تعديل السعر")

        # --- Tab 3: Categories ---
        t_cat = QWidget(); v3 = QVBoxLayout(t_cat)
        self.new_cat = QLineEdit(); self.new_cat.setPlaceholderText("اسم القسم")
        add_cat = QPushButton("إضافة القسم"); add_cat.clicked.connect(self._add_category)
        rowc = QHBoxLayout(); rowc.addWidget(self.new_cat, 1); rowc.addWidget(add_cat, 0)
        v3.addLayout(rowc)
        v3.addWidget(QLabel("الأقسام الحالية:"))
        self.cat_table = QTableWidget(0, 1); self.cat_table.setHorizontalHeaderLabels(["القسم"])
        self.cat_table.horizontalHeader().setStretchLastSection(True)
        self._reload_categories_table()
        v3.addWidget(self.cat_table, 1)
        tabs.addTab(t_cat, "الأقسام")

        # --- Tab 4: Low stock ---
        t_low = QWidget(); v4 = QVBoxLayout(t_low)
        self.low_table = QTableWidget(0, 3)
        self.low_table.setHorizontalHeaderLabels(["المنتج", "المخزون", "الحد الأدنى"])
        self.low_table.horizontalHeader().setStretchLastSection(True)
        self._reload_low_stock()
        v4.addWidget(self.low_table, 1)
        refresh = QPushButton("تحديث"); refresh.clicked.connect(self._reload_low_stock)
        v4.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(t_low, "مخزون منخفض")

        root = QVBoxLayout(self)
        root.addWidget(tabs, 1)

    def _reload_categories_table(self):
        self.cat_table.setRowCount(0)
        for cat in self._categories:
            r = self.cat_table.rowCount(); self.cat_table.insertRow(r)
            self.cat_table.setItem(r, 0, QTableWidgetItem(cat))

    def _add_category(self):
        name = self.new_cat.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "أدخل اسم القسم."); return
        self.on_add_category(name)
        if name not in self._categories:
            self._categories.append(name)
        self._reload_categories_table()
        self.cat_combo.addItem(name); self.cat_u.addItem(name)
        self.new_cat.clear()

    def _add_product(self):
        cat = self.cat_combo.currentText().strip()
        name = self.prod_name.text().strip()
        price = int(self.price.value())
        track = 1 if self.track_cb.isChecked() else 0
        stock_val = float(self.stock.value()) if track else None
        min_val = float(self.min_stock.value()) if track else 0.0

        if not cat or not name or price <= 0:
            QMessageBox.warning(self, "خطأ", "أدخل القسم، المنتج، والسعر."); return

        order_manager.catalog.add_product(
            cat, name, price, username=self.current_admin,
            track_stock=track, stock_qty=stock_val, min_stock=min_val
        )
        QMessageBox.information(self, "تم", "تمت إضافة المنتج.")
        self.prod_name.clear()

    def _update_price(self):
        cat = self.cat_u.currentText().strip()
        name = self.name_u.text().strip()
        price = int(self.new_price.value())
        if not cat or not name or price <= 0:
            QMessageBox.warning(self, "خطأ", "أدخل القسم، المنتج، والسعر الجديد."); return
        ok = order_manager.catalog.update_product_price(cat, name, price, username=self.current_admin)
        if ok:
            QMessageBox.information(self, "تم", "تم تحديث السعر وتسجيله في السجل.")
            self.name_u.clear(); self.new_price.setValue(0)
        else:
            QMessageBox.warning(self, "فشل", "لم يتم العثور على المنتج.")

    def _reload_low_stock(self):
        rows = order_manager.catalog.get_low_stock()
        self.low_table.setRowCount(0)
        for name, stock, min_s in rows:
            r = self.low_table.rowCount(); self.low_table.insertRow(r)
            self.low_table.setItem(r, 0, QTableWidgetItem(str(name)))
            self.low_table.setItem(r, 1, QTableWidgetItem(str(stock)))
            self.low_table.setItem(r, 2, QTableWidgetItem(str(min_s)))
