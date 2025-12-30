from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QHBoxLayout

from ...utils.currency import format_pounds
from ...texts import texts


class PaymentPanel(QWidget):
    def __init__(self, on_pay, on_discount):
        super().__init__()
        v = QVBoxLayout(self)
        self.sub = QLabel(f"{texts.get('orders.total_before_discount')}: {format_pounds(0)}")
        self.disc = QLabel(f"{texts.get('orders.discount_summary_label')}: {format_pounds(0)}")
        self.total = QLabel(f"{texts.get('orders.total_after_discount')}: {format_pounds(0)}")

        self.method = QComboBox()
        self.method.addItems(
            [
                texts.get("orders.payment_method_cash"),
                texts.get("orders.payment_method_card"),
            ]
        )

        row_btns = QHBoxLayout()
        self.discount_btn = QPushButton(texts.get("orders.discount_button"))
        self.pay_btn = QPushButton(texts.get("orders.pay_button"))
        row_btns.addWidget(self.discount_btn)
        row_btns.addWidget(self.pay_btn)

        v.addWidget(self.sub)
        v.addWidget(self.disc)
        v.addWidget(self.total)
        v.addWidget(self.method)
        v.addLayout(row_btns)

        self.discount_btn.clicked.connect(on_discount)
        self.pay_btn.clicked.connect(lambda: on_pay(self.method.currentText()))

    def set_totals(self, subtotal_cents, discount_cents, total_cents, discount_label: str | None = None):
        discount_text = discount_label or texts.get("orders.discount_summary_label")
        self.sub.setText(f"{texts.get('orders.total_before_discount')}: {format_pounds(subtotal_cents)}")
        self.disc.setText(f"{discount_text}: {format_pounds(discount_cents)}")
        self.total.setText(f"{texts.get('orders.total_after_discount')}: {format_pounds(total_cents)}")
