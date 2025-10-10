# beirut_pos/ui/admin_products_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QMessageBox, QCheckBox, QDoubleSpinBox
)
from ..services.orders import order_manager

class AdminProductsDialog(QDialog):
    def __init__(self, categories: list[str], on_add_category, on_add_product, current_admin="admin"):
        super().__init__()
        self.setWindowTitle("إدارة الأصناف والمنتجات")
        self.current_admin = current_admin
        self.on_add_category = on_add_category
        self.on_add_product = on_add_product

        v = QVBoxLayout(self)

        # Add Category
        v.addWidget(QLabel("إضافة قسم جديد"))
        row_cat = QHBoxLayout()
        self.new_cat = QLineEdit(); self.new_cat.setPlaceholderText("اسم القسم")
        btn_add_cat = QPushButton("إضافة القسم")
        btn_add_cat.clicked.connect(self._add_category)
        row_cat.addWidget(self.new_cat); row_cat.addWidget(btn_add_cat)
        v.addLayout(row_cat)

        # Add Product
        v.addWidget(QLabel("إضافة منتج"))
        row1 = QHBoxLayout()
        self.cat_combo = QComboBox(); self.cat_combo.addItems(categories); self.cat_combo.setEditable(True)
        row1.addWidget(QLabel("القسم:")); row1.addWidget(self.cat_combo)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        self.prod_name = QLineEdit(); self.prod_name.setPlaceholderText("اسم المنتج")
        self.price = QSpinBox(); self.price.setRange(0, 10_000_000); self.price.setSingleStep(500); self.price.setValue(10000)
        row2.addWidget(QLabel("المنتج:")); row2.addWidget(self.prod_name, 2)
        row2.addWidget(QLabel("السعر (قرش):")); row2.addWidget(self.price)
        v.addLayout(row2)

        # Track stock?
        row_track = QHBoxLayout()
        self.track_cb = QCheckBox("تتبع المخزون")
        self.track_cb.setChecked(True)
        row_track.addWidget(self.track_cb)
        v.addLayout(row_track)

        # Stock + min stock
        row_stock = QHBoxLayout()
        self.stock = QDoubleSpinBox(); self.stock.setDecimals(2); self.stock.setRange(0, 1_000_000); self.stock.setValue(0)
        self.min_stock = QDoubleSpinBox(); self.min_stock.setDecimals(2); self.min_stock.setRange(0, 1_000_000); self.min_stock.setValue(0)
        row_stock.addWidget(QLabel("المخزون:")); row_stock.addWidget(self.stock)
        row_stock.addWidget(QLabel("حد أدنى:")); row_stock.addWidget(self.min_stock)
        v.addLayout(row_stock)

        def _toggle_stock(chk):
            self.stock.setEnabled(chk)
            self.min_stock.setEnabled(chk)
        _toggle_stock(True)
        self.track_cb.toggled.connect(_toggle_stock)

        row3 = QHBoxLayout()
        add_btn = QPushButton("إضافة المنتج")
        add_btn.clicked.connect(self._add_product)
        row3.addWidget(add_btn)
        v.addLayout(row3)

        # Update price
        v.addWidget(QLabel("تعديل سعر منتج"))
        row4 = QHBoxLayout()
        self.cat_u = QComboBox(); self.cat_u.addItems(categories); self.cat_u.setEditable(True)
        self.name_u = QLineEdit(); self.name_u.setPlaceholderText("اسم المنتج")
        self.new_price = QSpinBox(); self.new_price.setRange(0, 10_000_000); self.new_price.setSingleStep(500)
        row4.addWidget(QLabel("القسم:")); row4.addWidget(self.cat_u)
        row4.addWidget(QLabel("المنتج:")); row4.addWidget(self.name_u)
        row4.addWidget(QLabel("سعر جديد (قرش):")); row4.addWidget(self.new_price)
        v.addLayout(row4)

        row5 = QHBoxLayout()
        upd = QPushButton("تحديث السعر")
        upd.clicked.connect(self._update_price)
        row5.addWidget(upd)
        v.addLayout(row5)

        close_btn = QPushButton("إغلاق")
        v.addWidget(close_btn)
        close_btn.clicked.connect(self.accept)

    def _add_category(self):
        name = self.new_cat.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "أدخل اسم القسم.")
            return
        self.on_add_category(name)
        if self.cat_combo.findText(name) < 0:
            self.cat_combo.addItem(name)
            self.cat_u.addItem(name)
        self.new_cat.clear()

    def _add_product(self):
        cat = self.cat_combo.currentText().strip()
        name = self.prod_name.text().strip()
        price = int(self.price.value())
        track = 1 if self.track_cb.isChecked() else 0
        stock_val = float(self.stock.value()) if track else None
        min_val = float(self.min_stock.value()) if track else 0.0

        if not cat or not name or price <= 0:
            QMessageBox.warning(self, "خطأ", "أدخل القسم، المنتج، والسعر.")
            return

        order_manager.catalog.add_product(
            cat, name, price, username=self.current_admin,
            track_stock=track, stock_qty=stock_val, min_stock=min_val
        )
        self.prod_name.clear()

    def _update_price(self):
        cat = self.cat_u.currentText().strip()
        name = self.name_u.text().strip()
        price = int(self.new_price.value())
        if not cat or not name or price <= 0:
            QMessageBox.warning(self, "خطأ", "أدخل القسم، المنتج، والسعر الجديد.")
            return
        ok = order_manager.catalog.update_product_price(cat, name, price, username=self.current_admin)
        if ok:
            QMessageBox.information(self, "تم", "تم تحديث السعر وتسجيله في السجل.")
        else:
            QMessageBox.warning(self, "فشل", "لم يتم العثور على المنتج.")
