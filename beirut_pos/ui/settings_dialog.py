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
from ..services.orders import order_manager, get_category_order, set_category_order
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

        self.accent_color = QLineEdit(setting_get("accent_color", "#C89A5B"))
        self.accent_color.setMaxLength(7)
        btn_color = QPushButton("لون…")

        def pick_color():
            current = QColor(self.accent_color.text() or "#C89A5B")
            col = QColorDialog.getColor(current, self, "اختر اللون الرئيسي")
            if col.isValid():
                self.accent_color.setText(col.name())

        btn_color.clicked.connect(pick_color)
        color_row = QHBoxLayout(); color_row.addWidget(self.accent_color, 1); color_row.addWidget(btn_color, 0)
        color_widget = QWidget(); color_widget.setLayout(color_row)
        br_f.addRow("اللون الرئيسي:", color_widget)

        self.surface_color = QLineEdit(setting_get("surface_color", "#23140C"))
        self.surface_color.setMaxLength(7)
        btn_surface = QPushButton("لون…")

        def pick_surface():
            current = QColor(self.surface_color.text() or "#23140C")
            col = QColorDialog.getColor(current, self, "اختر لون لوحة التحكم")
            if col.isValid():
                self.surface_color.setText(col.name())

        btn_surface.clicked.connect(pick_surface)
        surface_row = QHBoxLayout(); surface_row.addWidget(self.surface_color, 1); surface_row.addWidget(btn_surface, 0)
        surface_widget = QWidget(); surface_widget.setLayout(surface_row)
        br_f.addRow("لون خلفية الواجهة:", surface_widget)

        self.text_color = QLineEdit(setting_get("text_color", "#F8EFE4"))
        self.text_color.setMaxLength(7)
        btn_text = QPushButton("لون…")

        def pick_text():
            current = QColor(self.text_color.text() or "#F8EFE4")
            col = QColorDialog.getColor(current, self, "اختر لون النص")
            if col.isValid():
                self.text_color.setText(col.name())

        btn_text.clicked.connect(pick_text)
        text_row = QHBoxLayout(); text_row.addWidget(self.text_color, 1); text_row.addWidget(btn_text, 0)
        text_widget = QWidget(); text_widget.setLayout(text_row)
        br_f.addRow("لون النص:", text_widget)
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
        background = self.background_path.text().strip()
        accent = self.accent_color.text().strip()
        surface_color = self.surface_color.text().strip()
        text_color = self.text_color.text().strip()
        setting_set("bar_printer", bar)
        setting_set("cashier_printer", cash)
        setting_set("logo_path", logo)
        setting_set("background_path", background)
        setting_set("accent_color", accent)
        setting_set("surface_color", surface_color)
        setting_set("text_color", text_color)

        order = [self.category_list.item(i).text() for i in range(self.category_list.count())]
        set_category_order(order)

        branding.clear_branding_cache()
        bus.emit("branding_changed", {"logo": logo, "background": background, "accent": accent})
        bus.emit("catalog_changed")
        bus.emit("printers_changed", bar, cash)
        bus.emit("settings_saved")
        self.accept()
