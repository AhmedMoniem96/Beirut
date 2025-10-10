from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QHBoxLayout


class PaymentPanel(QWidget):
    def __init__(self, on_pay, on_discount):
        super().__init__()
        v = QVBoxLayout(self)
        self.sub = QLabel("المجموع قبل الخصم: ج.م 0.00")
        self.disc = QLabel("الخصم: ج.م 0.00")
        self.total = QLabel("المجموع النهائي: ج.م 0.00")

        self.method = QComboBox(); self.method.addItems(["نقدي", "فيزا"])

        row_btns = QHBoxLayout()
        self.discount_btn = QPushButton("تطبيق خصم (مدير)")
        self.pay_btn = QPushButton("تحصيل / دفع")
        row_btns.addWidget(self.discount_btn)
        row_btns.addWidget(self.pay_btn)

        v.addWidget(self.sub)
        v.addWidget(self.disc)
        v.addWidget(self.total)
        v.addWidget(self.method)
        v.addLayout(row_btns)

        self.discount_btn.clicked.connect(on_discount)
        self.pay_btn.clicked.connect(lambda: on_pay(self.method.currentText()))

    def set_totals(self, subtotal_cents, discount_cents, total_cents):
        self.sub.setText(f"المجموع قبل الخصم: ج.م {subtotal_cents/100:.2f}")
        self.disc.setText(f"الخصم: ج.م {discount_cents/100:.2f}")
        self.total.setText(f"المجموع النهائي: ج.م {total_cents/100:.2f}")
