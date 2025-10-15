# beirut_pos/ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QPushButton,
    QComboBox, QFileDialog, QTabWidget, QHBoxLayout, QLabel,
    QColorDialog, QListWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from ..core.db import setting_get, setting_set
from ..core.bus import bus
from .common.big_dialog import BigDialog
from .common import branding
import sys

def _list_printers():
    if not sys.platform.startswith("win"):
        return []
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []

class SettingsDialog(BigDialog):
    def __init__(self, parent=None):
        super().__init__("الإعدادات", remember_key="settings", parent=parent)

        self._default_palette = branding.default_palette()

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        # --- General tab ---
        gen = QWidget(); gen_v = QVBoxLayout(gen); gen_f = QFormLayout(); gen_v.addLayout(gen_f)
        self.company = QLineEdit(setting_get("company_name","Beirut Coffee"))
        self.currency = QLineEdit(setting_get("currency","EGP"))
        self.service  = QSpinBox(); self.service.setRange(0,50); self.service.setValue(int(setting_get("service_pct","0")))
        gen_f.addRow("الاسم التجاري:", self.company)
        gen_f.addRow("العملة:", self.currency)
        gen_f.addRow("نسبة الخدمة %:", self.service)
        tabs.addTab(gen, "عام")

        # --- Printers tab ---
        prn = QWidget(); prn_v = QVBoxLayout(prn); prn_f = QFormLayout(); prn_v.addLayout(prn_f)
        names = _list_printers()
        self.bar_prn  = QComboBox(); self.bar_prn.setEditable(True); self.bar_prn.addItems(names)
        self.cash_prn = QComboBox(); self.cash_prn.setEditable(True); self.cash_prn.addItems(names)
        self.bar_prn.setCurrentText(setting_get("bar_printer",""))
        self.cash_prn.setCurrentText(setting_get("cashier_printer",""))
        prn_f.addRow("طابعة البار:", self.bar_prn)
        prn_f.addRow("طابعة الكاشير:", self.cash_prn)
        # small hint
        hint = QLabel("ملاحظة: على ويندوز، تأكد أن أسماء الطابعات هنا مطابقة تماماً لاسم الجهاز في \"Devices and Printers\".")
        hint.setWordWrap(True); prn_v.addWidget(hint)
        tabs.addTab(prn, "الطابعات")

        # --- PlayStation tab ---
        ps = QWidget(); ps_v = QVBoxLayout(ps); ps_f = QFormLayout(); ps_v.addLayout(ps_f)
        self.ps_p2 = QSpinBox(); self.ps_p2.setRange(0,1_000_000); self.ps_p2.setValue(int(setting_get("ps_rate_p2","5000")))
        self.ps_p4 = QSpinBox(); self.ps_p4.setRange(0,1_000_000); self.ps_p4.setValue(int(setting_get("ps_rate_p4","8000")))
        ps_f.addRow("سعر PS لاعبين/ساعة (قرش):", self.ps_p2)
        ps_f.addRow("سعر PS أربعة/ساعة (قرش):", self.ps_p4)
        tabs.addTab(ps, "البلايستيشن")

        # --- Branding tab ---
        br = QWidget(); br_v = QVBoxLayout(br); br_f = QFormLayout(); br_v.addLayout(br_f)
        self.logo_path = QLineEdit(setting_get("logo_path",""))
        btn_browse = QPushButton("اختيار…")
        def pick_logo():
            p, _ = QFileDialog.getOpenFileName(self, "اختيار الشعار", "", "Images (*.png *.jpg *.jpeg)")
            if p: self.logo_path.setText(p)
        btn_browse.clicked.connect(pick_logo)
        row = QHBoxLayout(); row.addWidget(self.logo_path, 1); row.addWidget(btn_browse, 0)
        row_w = QWidget(); row_w.setLayout(row)
        br_f.addRow("الشعار:", row_w)

        self.background_path = QLineEdit(setting_get("background_path", ""))
        btn_bg = QPushButton("اختيار…")
        def pick_bg():
            p, _ = QFileDialog.getOpenFileName(self, "اختيار الخلفية", "", "Images (*.png *.jpg *.jpeg)")
            if p: self.background_path.setText(p)
        btn_bg.clicked.connect(pick_bg)
        bg_row = QHBoxLayout(); bg_row.addWidget(self.background_path, 1); bg_row.addWidget(btn_bg, 0)
        bg_widget = QWidget(); bg_widget.setLayout(bg_row)
        br_f.addRow("الخلفية:", bg_widget)

        palette = self._default_palette

        def make_color_row(key: str, label: str, dialog_title: str):
            field = QLineEdit(setting_get(key, palette[key]))
            field.setMaxLength(7)
            button = QPushButton("لون…")

            def pick():
                current = QColor(field.text() or palette[key])
                col = QColorDialog.getColor(current, self, dialog_title)
                if col.isValid():
                    field.setText(col.name())

            button.clicked.connect(pick)
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(button, 0)
            wrapper = QWidget()
            wrapper.setLayout(row)
            br_f.addRow(label, wrapper)
            return field

        self.accent_color = make_color_row("accent_color", "اللون الرئيسي:", "اختر اللون الرئيسي")
        self.surface_color = make_color_row("surface_color", "لون خلفية الواجهة:", "اختر لون لوحة التحكم")
        self.text_color = make_color_row("text_color", "لون النص:", "اختر لون النص")
        self.muted_text_color = make_color_row("muted_text_color", "لون النص الثانوي:", "اختر لون النص الثانوي")
        self.menu_card_color = make_color_row("menu_card_color", "لون بطاقات الأقسام:", "اختر لون بطاقات الأقسام")
        self.menu_header_color = make_color_row("menu_header_color", "لون عناوين الأقسام:", "اختر لون عنوان القسم")
        self.menu_button_color = make_color_row("menu_button_color", "لون أزرار المنتجات:", "اختر لون زر المنتج")
        self.menu_button_text_color = make_color_row("menu_button_text_color", "لون خط أزرار المنتجات:", "اختر لون خط زر المنتج")
        self.menu_button_hover_color = make_color_row("menu_button_hover_color", "لون الزر عند التحويم:", "اختر لون الزر عند التحويم")

        reset_colors = QPushButton("استعادة الألوان الافتراضية")
        reset_colors.clicked.connect(self._reset_palette_fields)
        br_v.addWidget(reset_colors, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(br, "الهوية")

        # --- Category order tab ---
        cat_tab = QWidget(); cat_v = QVBoxLayout(cat_tab)
        cat_hint = QLabel("رتّب الأقسام بالسحب والإفلات لتظهر بالترتيب نفسه في شاشة الطلبات.")
        cat_hint.setWordWrap(True)
        cat_v.addWidget(cat_hint)

        self.category_list = QListWidget()
        self.category_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.category_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.category_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.category_list.setAlternatingRowColors(True)
        cat_v.addWidget(self.category_list, 1)

        ordered = get_category_order()
        existing = [cat for cat, _ in order_manager.categories]
        seen = set()
        for name in ordered + [n for n in existing if n not in ordered]:
            if name in seen:
                continue
            seen.add(name)
            self.category_list.addItem(name)

        tabs.addTab(cat_tab, "ترتيب الأقسام")

        # --- Footer buttons ---
        save = QPushButton("حفظ")
        save.setDefault(True)
        save.clicked.connect(self._save)

        root = QVBoxLayout(self)
        root.addWidget(tabs, 1)
        root.addWidget(save, 0, alignment=Qt.AlignmentFlag.AlignLeft)

    def _save(self):
        setting_set("company_name", self.company.text().strip())
        setting_set("currency", self.currency.text().strip())
        setting_set("service_pct", str(self.service.value()))
        setting_set("ps_rate_p2", str(self.ps_p2.value()))
        setting_set("ps_rate_p4", str(self.ps_p4.value()))
        bar = self.bar_prn.currentText().strip()
        cash = self.cash_prn.currentText().strip()
        logo = self.logo_path.text().strip()
        setting_set("bar_printer", bar)
        setting_set("cashier_printer", cash)
        setting_set("logo_path", logo)
        branding.clear_logo_cache()
        bus.emit("branding_changed", logo)
        bus.emit("printers_changed", bar, cash)
        QMessageBox.information(self, "تم", "تم حفظ الإعدادات.")
        self.accept()

    def _reset_palette_fields(self):
        palette = self._default_palette
        self.accent_color.setText(palette["accent_color"])
        self.surface_color.setText(palette["surface_color"])
        self.text_color.setText(palette["text_color"])
        self.muted_text_color.setText(palette["muted_text_color"])
        self.menu_card_color.setText(palette["menu_card_color"])
        self.menu_header_color.setText(palette["menu_header_color"])
        self.menu_button_color.setText(palette["menu_button_color"])
        self.menu_button_text_color.setText(palette["menu_button_text_color"])
        self.menu_button_hover_color.setText(palette["menu_button_hover_color"])
