# beirut_pos/ui/components/category_grid.py
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QGroupBox, QVBoxLayout,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt

from ...utils.currency import format_pounds

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

    LOW_STOCK_THRESHOLD = 3

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
        self.v.setAlignment(Qt.AlignmentFlag.AlignTop)  # FORCE items to top!

        self._boxes: list[QGroupBox] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.set_categories(categories)

    def clear(self):
        """Clear all category boxes."""
        for b in self._boxes:
            self.v.removeWidget(b)
            b.setParent(None)
            b.deleteLater()
        self._boxes.clear()

    def set_categories(self, categories):
        """
        Accepts either:
          items = [(label, price_cents)]  OR
          items = [(label, price_cents, track_stock, stock_qty)]
        """
        self.clear()
        source = categories() if callable(categories) else categories

        for idx, cat in enumerate(source):
            if len(cat) >= 3:
                cat_name, items, color = cat[0], cat[1], cat[2]
            else:
                cat_name, items = cat[0], cat[1]
                color = ""
            title = AR_DISPLAY.get(cat_name, cat_name)
            box = QGroupBox(title)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)

            # Alternate subtle backgrounds per category to improve scanning
            bg_color = color or ("#f6f7fb" if idx % 2 == 0 else "#eef5ff")
            box.setStyleSheet(
                f"""
                QGroupBox {{
                    background-color: {bg_color};
                    border: 1px solid #dfe3eb;
                    border-radius: 10px;
                    color: #0f172a;
                    margin-top: 8px;
                    font-weight: 600;
                    padding-top: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    color: #0f172a;
                    left: 12px;
                    padding: 4px 8px;
                }}
                """
            )

            for i, tup in enumerate(items):
                # Unpack flexibly
                if len(tup) >= 4:
                    label, price_cents, track_stock, stock_qty = tup[0], tup[1], int(tup[2]), tup[3]
                else:
                    label, price_cents = tup[0], tup[1]
                    track_stock, stock_qty = 0, None

                status_prefix = ""
                style_parts: list[str] = ["padding: 12px; font-size: 16px;"]
                tooltip_lines = [label, format_pounds(price_cents), f"الفئة: {title}"]

                if track_stock == 1:
                    stock_display = "غير متوفر" if stock_qty is None else str(stock_qty)
                    tooltip_lines.append(f"المخزون: {stock_display}")
                    if stock_qty is None:
                        status_prefix = "🟠 "
                        style_parts.append("color: #c47a00;")
                    elif stock_qty <= 0:
                        status_prefix = "🔴 "
                    elif stock_qty <= self.LOW_STOCK_THRESHOLD:
                        status_prefix = "🟠 "
                        style_parts.append("color: #c47a00;")
                    else:
                        status_prefix = "🟢 "
                        style_parts.append("color: #1b7a1b;")

                text = f"{status_prefix}{label}\n{format_pounds(price_cents)}"
                b = QPushButton(text)
                b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                b.setMinimumHeight(76)
                b.setStyleSheet(" ".join(style_parts))
                b.setToolTip("\n".join(tooltip_lines))
                b.clicked.connect(lambda _=False, L=label, P=price_cents: self.on_pick(L, P))

                # Disable if tracked & out of stock
                if track_stock == 1 and (stock_qty is None or stock_qty <= 0):
                    b.setEnabled(False)
                    b.setText(f"{status_prefix}{label}\n(غير متوفر) {format_pounds(price_cents)}")
                    b.setStyleSheet("padding: 12px; font-size: 16px; color: gray;")

                grid.addWidget(b, i // 3, i % 3)

            self.v.addWidget(box)
            self._boxes.append(box)

        # NO MORE addStretch here! The alignment handles it