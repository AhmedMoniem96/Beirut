"""Settings tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services.db import add_payment_method
from ...services.settings import GallerySettings, load_gallery_settings, save_gallery_settings
from ...services.demo_seed import seed_demo_data
from beirut_pos.services import printer as printer_service


class SettingsTab(QWidget):
    def __init__(self, on_settings_changed=None, on_payment_methods_changed=None) -> None:
        super().__init__()
        self._on_settings_changed = on_settings_changed
        self._on_payment_methods_changed = on_payment_methods_changed

        layout = QVBoxLayout(self)
        header = QLabel("Settings (الإعدادات)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        gallery_box = QGroupBox("Gallery Info (بيانات المعرض)")
        gallery_layout = QFormLayout(gallery_box)
        self.name_en_input = QLineEdit()
        self.name_ar_input = QLineEdit()
        self.address_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.logo_input = QLineEdit()
        self.font_input = QLineEdit()
        self.rtl_check = QCheckBox("Enable RTL Layout (تفعيل الاتجاه العربي)")
        logo_btn = QPushButton("Browse Logo (اختيار شعار)")
        logo_btn.clicked.connect(self._pick_logo)
        font_btn = QPushButton("Browse Arabic Font (خط عربي)")
        font_btn.clicked.connect(self._pick_font)

        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_input)
        logo_row.addWidget(logo_btn)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_input)
        font_row.addWidget(font_btn)

        gallery_layout.addRow("Name EN:", self.name_en_input)
        gallery_layout.addRow("Name AR:", self.name_ar_input)
        gallery_layout.addRow("Address:", self.address_input)
        gallery_layout.addRow("Phone:", self.phone_input)
        gallery_layout.addRow("Logo Path:", logo_row)
        gallery_layout.addRow("Arabic Font Path:", font_row)
        gallery_layout.addRow("", self.rtl_check)
        layout.addWidget(gallery_box)

        printer_box = QGroupBox("Barcode Printing (طباعة الباركود)")
        printer_layout = QFormLayout(printer_box)
        self.barcode_mode = QComboBox()
        self.barcode_mode.addItem("Export PDF (تصدير PDF)", "pdf")
        self.barcode_mode.addItem("Direct Print (طباعة مباشرة)", "direct")

        self.barcode_printer = QComboBox()
        self.barcode_printer.addItem("Auto (USB/ESC/POS)", "auto")
        for name in printer_service.win_list_printers():
            self.barcode_printer.addItem(name, name)

        printer_layout.addRow("Default Mode:", self.barcode_mode)
        printer_layout.addRow("Printer:", self.barcode_printer)
        layout.addWidget(printer_box)

        save_btn = QPushButton("Save Settings (حفظ)")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        payment_box = QGroupBox("Payment Methods (طرق الدفع)")
        payment_layout = QFormLayout(payment_box)
        self.payment_ar_input = QLineEdit()
        self.payment_en_input = QLineEdit()
        add_payment_btn = QPushButton("Add Method (إضافة)")
        add_payment_btn.clicked.connect(self._add_payment_method)
        payment_layout.addRow("Name AR:", self.payment_ar_input)
        payment_layout.addRow("Name EN:", self.payment_en_input)
        payment_layout.addRow("", add_payment_btn)
        layout.addWidget(payment_box)

        demo_box = QGroupBox("Demo Seed (بيانات تجريبية)")
        demo_layout = QVBoxLayout(demo_box)
        demo_btn = QPushButton("Seed Demo Data (إضافة بيانات)")
        demo_btn.clicked.connect(self._seed_demo)
        demo_layout.addWidget(demo_btn)
        layout.addWidget(demo_box)

        self._load_settings()

    def _load_settings(self) -> None:
        settings = load_gallery_settings()
        self.name_en_input.setText(settings.name_en)
        self.name_ar_input.setText(settings.name_ar)
        self.address_input.setText(settings.address)
        self.phone_input.setText(settings.phone)
        self.logo_input.setText(settings.logo_path)
        self.font_input.setText(settings.font_path)
        self.rtl_check.setChecked(settings.rtl_enabled)
        self._set_combo_value(self.barcode_mode, settings.barcode_print_mode)
        self._set_combo_value(self.barcode_printer, settings.barcode_printer_name)

    def _save_settings(self) -> None:
        settings = GallerySettings(
            name_en=self.name_en_input.text().strip(),
            name_ar=self.name_ar_input.text().strip(),
            address=self.address_input.text().strip(),
            phone=self.phone_input.text().strip(),
            logo_path=self.logo_input.text().strip(),
            font_path=self.font_input.text().strip(),
            rtl_enabled=self.rtl_check.isChecked(),
            barcode_print_mode=self.barcode_mode.currentData() or "pdf",
            barcode_printer_name=self.barcode_printer.currentData() or "auto",
        )
        save_gallery_settings(settings)
        QMessageBox.information(self, "Saved", "Settings saved.")
        if self._on_settings_changed:
            self._on_settings_changed()

    def _add_payment_method(self) -> None:
        name_ar = self.payment_ar_input.text().strip()
        name_en = self.payment_en_input.text().strip()
        if not name_ar or not name_en:
            QMessageBox.warning(self, "Missing", "Provide Arabic and English names.")
            return
        add_payment_method(name_ar, name_en)
        self.payment_ar_input.clear()
        self.payment_en_input.clear()
        QMessageBox.information(self, "Saved", "Payment method added.")
        if self._on_payment_methods_changed:
            self._on_payment_methods_changed()

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Logo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            self.logo_input.setText(path)

    def _pick_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Arabic Font",
            "",
            "Font Files (*.ttf *.otf)",
        )
        if path:
            self.font_input.setText(path)

    def _seed_demo(self) -> None:
        seed_demo_data()
        QMessageBox.information(self, "Seeded", "Demo data created.")
        if self._on_payment_methods_changed:
            self._on_payment_methods_changed()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value or combo.itemText(idx) == value:
                combo.setCurrentIndex(idx)
                return
