from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QPushButton

from ...core.money import cents_to_le, fmt_le


class OrderList(QWidget):
    def __init__(self, on_remove, on_edit):
        super().__init__()
        self.on_remove = on_remove
        self.on_edit = on_edit
        v = QVBoxLayout(self)
        self.title = QLabel("طلب:")
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.setObjectName("OrderItems")
        self.list.setSpacing(4)
        self.list.setStyleSheet("QListWidget#OrderItems::item { padding: 6px 8px; }")
        self.total = QLabel("الإجمالي: LE 0.00")
        self.remove_btn = QPushButton("حذف المحدد")
        self.edit_btn = QPushButton("تعديل المحدد")
        v.addWidget(self.title)
        v.addWidget(self.list)
        v.addWidget(self.total)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.remove_btn)
        v.addLayout(btn_row)
        self.remove_btn.clicked.connect(self._remove)
        self.edit_btn.clicked.connect(self._edit)
        self.list.itemDoubleClicked.connect(lambda _: self._edit())

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.on_remove(row)

    def _edit(self):
        row = self.list.currentRow()
        if row >= 0:
            self.on_edit(row)

    def set_table(self, code):
        self.title.setText(f"طلب: {code}")

    def set_items(self, items):
        self.list.clear()
        for it in items:
            amount = fmt_le(cents_to_le(getattr(it, "unit_price_cents", 0)))
            text = f"{it.qty}× {it.product} | {amount}"
            note = getattr(it, "note", "") or ""
            if note:
                text += f"\n    ملاحظة: {note}"
            self.list.addItem(text)

    def set_total(self, cents):
        self.total.setText(f"الإجمالي: {fmt_le(cents_to_le(cents))}")
