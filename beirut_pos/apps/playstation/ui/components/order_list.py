from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QPushButton, QFrame, QSizePolicy, QSpacerItem
)
from ....utils.currency import format_pounds
from ...texts import texts


class OrderList(QWidget):
    def __init__(self, on_remove, on_edit):
        super().__init__()
        self.on_remove = on_remove
        self.on_edit = on_edit

        # Force RTL across this panel
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        # Root layout - compact
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        # Title (right aligned) - compact
        self.title = QLabel("طلب:")
        self.title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff; padding: 2px;")
        v.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignRight)

        # Items list
        self.list = QListWidget()
        self.list.setObjectName("OrderItems")
        self.list.setAlternatingRowColors(True)
        self.list.setSpacing(3)
        self.list.setStyleSheet("QListWidget#OrderItems::item { padding: 4px 6px; }")
        self.list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v.addWidget(self.list)

        # Totals summary - COMPACT, right aligned
        self.summary_frame = QFrame()
        self.summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.summary_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        s = QVBoxLayout(self.summary_frame)
        s.setContentsMargins(10, 8, 10, 8)
        s.setSpacing(4)

        # Create labels - COMPACT
        self.subtotal_label = QLabel(f"{texts.get('orders.subtotal_label')}: {format_pounds(0)}")
        self.discount_label = QLabel(f"{texts.get('orders.discount_summary_label')}: {format_pounds(0)}")
        self.total_after_label = QLabel(f"{texts.get('orders.total_label')}: {format_pounds(0)}")

        # Ensure RTL and right alignment
        for lab in (self.subtotal_label, self.discount_label, self.total_after_label):
            lab.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lab.setMinimumHeight(22)
            lab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lab.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 12px; padding: 2px 6px; text-align: right;")
            s.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)

        # Make final total prominent
        self.total_after_label.setStyleSheet(
            "color: #4CAF50; font-weight: bold; font-size: 13px; padding: 3px 6px; "
            "background-color: rgba(76, 175, 80, 0.15); border-radius: 3px; text-align: right;"
        )

        v.addWidget(self.summary_frame)

        # Buttons row - COMPACT
        self.edit_btn = QPushButton("تعديل")
        self.remove_btn = QPushButton("حذف")

        # Make buttons smaller
        for btn in (self.edit_btn, self.remove_btn):
            btn.setMaximumWidth(80)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        btn_row.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.remove_btn)
        v.addLayout(btn_row)

        # Signals
        self.edit_btn.clicked.connect(self._edit)
        self.remove_btn.clicked.connect(self._remove)
        self.list.itemDoubleClicked.connect(lambda _: self._edit())

        # Render once
        self.set_totals(0, 0, 0)

    # Actions
    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.on_remove(row)

    def _edit(self):
        row = self.list.currentRow()
        if row >= 0:
            self.on_edit(row)

    # API
    def set_table(self, code: str, client_name: str | None = None):
        base = texts.get("main.order.header")
        label = (code or "").strip()
        extra = (client_name or "").strip()
        if label and extra:
            display = f"{label} — {extra}"
        elif extra:
            display = extra
        else:
            display = label
        if display:
            self.title.setText(f"{base} {display}".strip())
        else:
            self.title.setText(base)

    def set_items(self, items):
        self.list.clear()
        for it in items:
            text = f"{it.qty}× {it.product} | {format_pounds(it.unit_price_cents)}"
            note = getattr(it, "note", "") or ""
            if note:
                text += f"\n    ملاحظة: {note}"
            self.list.addItem(text)

    def set_totals(
        self,
        subtotal_cents: int,
        discount_cents: int,
        total_cents: int,
        discount_label: str | None = None,
    ) -> None:
        subtotal_cents = int(subtotal_cents or 0)
        discount_cents = int(discount_cents or 0)
        final_payable = int(total_cents or max(subtotal_cents - discount_cents, 0))

        # Update labels - shorter text
        subtotal_text = texts.get("orders.subtotal_label")
        total_text = texts.get("orders.total_label")
        discount_text = discount_label or texts.get("orders.discount_summary_label")

        self.subtotal_label.setText(f"{subtotal_text}: {format_pounds(subtotal_cents)}")
        self.discount_label.setText(f"{discount_text}: {format_pounds(discount_cents)}")
        self.total_after_label.setText(f"{total_text}: {format_pounds(final_payable)}")
