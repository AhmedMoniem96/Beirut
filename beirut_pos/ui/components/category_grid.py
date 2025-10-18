# beirut_pos/ui/components/category_grid.py
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QGroupBox, QVBoxLayout,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt

from ...core.money import cents_to_le, fmt_le

# English->Arabic display map (DB can stay English internally)
AR_DISPLAY = {
    "Food": "أطباق الطعام",
    "Fresh Drinks": "عصائر طازجة",
    "Smoothies": "سموذي",
    "Coffee Corner": "ركن القهوة",
    "Hot Drinks": "مشروبات ساخنة",
    "Desserts": "حلويات",
    "Soda Drinks": "مشروبات غازية",
    "PlayStation 2 Players": "بلايستيشن لاعبَين",
    "PlayStation 4 Players": "بلايستيشن أربعة لاعبين",
    "Sheshaaaa": "شيشة",
    "Cocktails": "كوكتيلات",
    "Ice Cream": "آيس كريم",
    "Mixes": "ميكسات",
    "Shakes / Milk": "شيكس / حليب",
}


class CategoryGrid(QWidget):
    """
    Scrollable Arabic category grid.
    Now auto-disables out-of-stock buttons for tracked items.
    """
    def __init__(self, categories, on_pick):
        super().__init__()
        self.on_pick = on_pick
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)

        self.container = QWidget()
        self.scroll.setWidget(self.container)

        self.v = QVBoxLayout(self.container)
        self.v.setContentsMargins(6, 6, 6, 6)
        self.v.setSpacing(8)

        self._boxes: list[QGroupBox] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.set_categories(categories)

    def clear(self):
        for b in self._boxes:
            self.v.removeWidget(b)
            b.setParent(None)
        self._boxes.clear()

    def set_categories(self, categories):
        """
        Accepts either:
          items = [(label, price_cents)]  OR
          items = [(label, price_cents, track_stock, stock_qty)]
        """
        self.clear()
        source = categories() if callable(categories) else categories
        for cat_name, items in source:
            title = AR_DISPLAY.get(cat_name, cat_name)
            box = QGroupBox(title)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)

            for i, tup in enumerate(items):
                # Unpack flexibly
                if len(tup) >= 4:
                    label, price_cents, track_stock, stock_qty = tup[0], tup[1], int(tup[2]), tup[3]
                else:
                    label, price_cents = tup[0], tup[1]
                    track_stock, stock_qty = 0, None

                text = f"{label}\n{fmt_le(cents_to_le(price_cents))}"
                b = QPushButton(text)
                b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                b.clicked.connect(lambda _=False, L=label, P=price_cents: self.on_pick(L, P))

                # Disable if tracked & out of stock
                if track_stock == 1 and (stock_qty is None or stock_qty <= 0):
                    b.setEnabled(False)
                    b.setText(f"{label}\n(غير متوفر) {fmt_le(cents_to_le(price_cents))}")
                    b.setStyleSheet("color: gray;")

                grid.addWidget(b, i // 3, i % 3)

            self.v.addWidget(box)
            self._boxes.append(box)
        self.v.addStretch(1)
