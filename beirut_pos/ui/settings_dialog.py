# beirut_pos/ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QTabWidget, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
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
        tabs.addTab(br, "الهوية")

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
