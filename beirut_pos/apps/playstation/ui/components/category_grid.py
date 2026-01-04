# beirut_pos/ui/components/category_grid.py
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QGroupBox, QVBoxLayout,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import QSize, Qt

from ....utils.currency import format_pounds
from ..common import branding

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
        self._button_height = branding.get_menu_button_height()
        self._button_font_size = branding.get_menu_button_font_size()
        self._button_padding = branding.get_menu_button_padding()
        self._columns = branding.get_menu_columns()
        self._thumb_size = 56
        self._palette_cycle = [
            "#e0f2fe",
            "#fee2e2",
            "#f5f3ff",
            "#ecfdf3",
            "#fff7ed",
            "#fef3c7",
        ]
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
                style_parts: list[str] = [
                    f"padding: {self._button_padding}px;",
                    f"font-size: {self._button_font_size}px;",
                ]
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

                button = self._make_product_button(
                    label,
                    price_cents,
                    status_prefix,
                    track_stock,
                    stock_qty,
                    tooltip_lines,
                    style_parts,
                    bg_color,
                    i,
                )
                grid.addWidget(button, i // self._columns, i % self._columns)

            self.v.addWidget(box)
            self._boxes.append(box)

        # NO MORE addStretch here! The alignment handles it

    # ----------------- helpers -----------------
    def _make_product_button(
        self,
        label: str,
        price_cents: int,
        status_prefix: str,
        track_stock: int,
        stock_qty: int | None,
        tooltip_lines: list[str],
        style_parts: list[str],
        category_color: str,
        row_index: int,
    ) -> QPushButton:
        button = QPushButton()
        button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        button.setMinimumHeight(max(self._button_height, self._thumb_size + 26))

        thumb_color = self._resolve_thumb_color(category_color, row_index)
        pixmap = self._render_thumbnail(label, thumb_color)
        button.setIcon(QIcon(pixmap))
        button.setIconSize(QSize(self._thumb_size, self._thumb_size))

        price_line = format_pounds(price_cents)
        stock_suffix = "" if track_stock == 0 else (" — غير متوفر" if stock_qty is None or stock_qty <= 0 else "")
        button.setText(f"{status_prefix}{label}\n{price_line}{stock_suffix}")

        base_style = (
            f"""
            QPushButton {{
                text-align: left;
                padding: {self._button_padding}px;
                padding-left: {self._button_padding + self._thumb_size + 10}px;
                font-size: {self._button_font_size}px;
                border: 1px solid #dfe3eb;
                border-radius: 12px;
                background: #ffffff;
                color: #0f172a;
            }}
            QPushButton:hover {{
                background: #f5f7fb;
            }}
            QPushButton:disabled {{
                color: #888;
                background: #f7f7f7;
                border-color: #e5e7eb;
            }}
            """
        )
        button.setStyleSheet(base_style + " ".join(style_parts))
        button.setToolTip("\n".join(tooltip_lines))
        button.clicked.connect(lambda _=False, L=label, P=price_cents: self.on_pick(L, P))

        if track_stock == 1 and (stock_qty is None or stock_qty <= 0):
            button.setEnabled(False)

        return button

    def _render_thumbnail(self, label: str, color: str) -> QPixmap:
        pix = QPixmap(self._thumb_size, self._thumb_size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(0, 0, self._thumb_size - 1, self._thumb_size - 1)

        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont()
        font.setBold(True)
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, (label or "?").strip()[:2] or "?")
        painter.end()
        return pix

    def _resolve_thumb_color(self, category_color: str, row_index: int) -> str:
        if category_color:
            return category_color
        return self._palette_cycle[row_index % len(self._palette_cycle)]
