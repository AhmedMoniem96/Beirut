from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QPushButton,
    QFrame,
)

from ...utils.currency import format_pounds


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

        summary_frame = QFrame()
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(4)

        self.items_total_label = QLabel("المجموع الفرعي: ج.م 0")
        self.subtotal_label = QLabel("الإجمالي قبل الخصم: ج.م 0")
        self.discount_label = QLabel("قيمة الخصم: ج.م 0")
        self.total_after_discount_label = QLabel("الإجمالي بعد الخصم: ج.م 0")
        self.final_cash_label = QLabel("إجمالي المستحق نقدًا: ج.م 0")

        for label in (
            self.items_total_label,
            self.subtotal_label,
            self.discount_label,
            self.total_after_discount_label,
            self.final_cash_label,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            summary_layout.addWidget(label)
        self.remove_btn = QPushButton("حذف المحدد")
        self.edit_btn = QPushButton("تعديل المحدد")
        v.addWidget(self.title)
        v.addWidget(self.list)
        v.addWidget(summary_frame)
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
            text = f"{it.qty}× {it.product} | {format_pounds(it.unit_price_cents)}"
            note = getattr(it, "note", "") or ""
            if note:
                text += f"\n    ملاحظة: {note}"
            self.list.addItem(text)

    def set_totals(self, subtotal_cents: int, discount_cents: int, total_cents: int) -> None:
        """Update the order summary labels with the latest totals."""

        subtotal_cents = int(subtotal_cents or 0)
        discount_cents = int(discount_cents or 0)
        total_cents = int(total_cents or 0)

        # The subtotal reflects the sum of all items before any adjustments.
        self.items_total_label.setText(
            f"المجموع الفرعي: {format_pounds(subtotal_cents)}"
        )
        self.subtotal_label.setText(
            f"الإجمالي قبل الخصم: {format_pounds(subtotal_cents)}"
        )
        self.discount_label.setText(
            f"قيمة الخصم: {format_pounds(discount_cents)}"
        )

        net_total = max(subtotal_cents - discount_cents, 0)
        if total_cents > 0:
            net_total = total_cents

        self.total_after_discount_label.setText(
            f"الإجمالي بعد الخصم: {format_pounds(net_total)}"
        )
        self.final_cash_label.setText(
            f"إجمالي المستحق نقدًا: {format_pounds(total_cents)}"
        )
