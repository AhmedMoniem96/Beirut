from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QLabel, QPushButton


class OrderList(QWidget):
    def __init__(self, on_remove):
        super().__init__()
        self.on_remove = on_remove
        v = QVBoxLayout(self)
        self.title = QLabel("طلب:")
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.setObjectName("OrderItems")
        self.total = QLabel("الإجمالي: ج.م 0.00")
        self.remove_btn = QPushButton("حذف المحدد")
        v.addWidget(self.title)
        v.addWidget(self.list)
        v.addWidget(self.total)
        v.addWidget(self.remove_btn)
        self.remove_btn.clicked.connect(self._remove)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.on_remove(row)

    def set_table(self, code):
        self.title.setText(f"طلب: {code}")

    def set_items(self, items):
        self.list.clear()
        for it in items:
            text = f"{it.qty}× {it.product} | ج.م {it.unit_price_cents/100:.2f}"
            note = getattr(it, "note", "") or ""
            if note:
                text += f"\n    ملاحظة: {note}"
            self.list.addItem(text)

    def set_total(self, cents):
        self.total.setText(f"الإجمالي: ج.م {cents/100:.2f}")
