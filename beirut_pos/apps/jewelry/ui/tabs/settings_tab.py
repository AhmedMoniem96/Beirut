"""Settings tab for Jewelry app."""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QEventLoop, QSignalBlocker, QTimer, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...services.db import add_payment_method
from ...services.settings import (
    BarcodePrinterSettings,
    load_gallery_settings,
    normalize_scanner_payload,
    save_gallery_settings,
)
from ...services.demo_seed import seed_demo_data
from ...services.i18n import get_ui_language, set_ui_language, t
from ...services import device_health
from ...services import barcode_printer
from ...services.windows_raw_printer import enumerate_printers
from ..dialogs.delivery_companies_dialog import DeliveryCompaniesDialog
from ..dialogs.loyalty_settings_dialog import LoyaltySettingsDialog
from ..dialogs.statuses_dialog import StatusesDialog
from .base_tab import BaseTabContainer
from beirut_pos.services import printer as printer_service


class SettingsTab(BaseTabContainer):
    def __init__(self, on_settings_changed=None, on_payment_methods_changed=None, on_language_changed=None) -> None:
        super().__init__()
        self._on_settings_changed = on_settings_changed
        self._on_payment_methods_changed = on_payment_methods_changed
        self._on_language_changed = on_language_changed
        self._language = get_ui_language()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        gallery_box = QGroupBox()
        gallery_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        gallery_layout = QFormLayout(gallery_box)
        gallery_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form_layouts = [gallery_layout]
        self.name_en_input = QLineEdit()
        self.name_ar_input = QLineEdit()
        self.address_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.logo_input = QLineEdit()
        self.font_input = QLineEdit()
        self.rtl_check = QCheckBox()
        self.website_name_input = QLineEdit()
        self.website_url_input = QLineEdit()
        self.website_orders_check = QCheckBox()
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self._handle_language_change)
        logo_btn = QPushButton()
        logo_btn.clicked.connect(self._pick_logo)
        font_btn = QPushButton()
        font_btn.clicked.connect(self._pick_font)

        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_input)
        logo_row.addWidget(logo_btn)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_input)
        font_row.addWidget(font_btn)

        self.name_en_label = QLabel()
        self.name_ar_label = QLabel()
        self.address_label = QLabel()
        self.phone_label = QLabel()
        self.logo_label = QLabel()
        self.font_label = QLabel()
        self.language_label = QLabel()
        gallery_layout.addRow(self.name_en_label, self.name_en_input)
        gallery_layout.addRow(self.name_ar_label, self.name_ar_input)
        gallery_layout.addRow(self.address_label, self.address_input)
        gallery_layout.addRow(self.phone_label, self.phone_input)
        gallery_layout.addRow(self.logo_label, logo_row)
        gallery_layout.addRow(self.font_label, font_row)
        gallery_layout.addRow("", self.rtl_check)
        gallery_layout.addRow(self.language_label, self.language_combo)
        content_layout.addWidget(gallery_box)
        self.gallery_box = gallery_box
        self.logo_btn = logo_btn
        self.font_btn = font_btn

        website_box = QGroupBox()
        website_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        website_layout = QFormLayout(website_box)
        website_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form_layouts.append(website_layout)
        self.website_name_label = QLabel()
        self.website_url_label = QLabel()
        website_layout.addRow(self.website_name_label, self.website_name_input)
        website_layout.addRow(self.website_url_label, self.website_url_input)
        website_layout.addRow("", self.website_orders_check)
        content_layout.addWidget(website_box)
        self.website_box = website_box

        printer_box = QGroupBox()
        printer_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        printer_layout = QFormLayout(printer_box)
        printer_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form_layouts.append(printer_layout)
        self.barcode_mode = QComboBox()
        self.barcode_mode.addItem("", "pdf")
        self.barcode_mode.addItem("", "direct")

        windows_printers = self._windows_printer_names()
        self.barcode_enabled_check = QCheckBox()
        self.barcode_printer = QComboBox()
        self.barcode_printer.setEditable(True)
        self.barcode_printer.addItem("")
        for name in windows_printers:
            if self.barcode_printer.findText(name) < 0:
                self.barcode_printer.addItem(name)

        self.barcode_model = QComboBox()
        self.barcode_model.addItem("Generic", "")
        self.barcode_model.addItem("Rongta RP310", "Rongta RP310")
        self.barcode_command_language = QComboBox()
        for language in ("ESC/POS", "TSPL", "ZPL", "CPCL"):
            self.barcode_command_language.addItem(language, language)

        self.barcode_label_width = self._make_mm_spin_box(0.1, 300.0)
        self.barcode_label_height = self._make_mm_spin_box(0.1, 300.0)
        self.barcode_label_gap = self._make_mm_spin_box(0.0, 50.0)
        self.barcode_dpi = QSpinBox()
        self.barcode_dpi.setRange(72, 1200)
        self.barcode_dpi.setSuffix(" DPI")
        self.barcode_density = QSpinBox()
        self.barcode_density.setRange(0, 15)
        self.barcode_speed = QSpinBox()
        self.barcode_speed.setRange(1, 12)
        self.barcode_copies = QSpinBox()
        self.barcode_copies.setRange(1, 999)

        self.receipt_mode = QComboBox()
        self.receipt_mode.addItem("", "auto")
        self.receipt_mode.addItem("", "windows")
        self.receipt_printer = QComboBox()
        self.receipt_printer.setEditable(True)
        self.receipt_printer.addItem("", "auto")
        for name in windows_printers:
            self.receipt_printer.addItem(name, name)

        self.refresh_printers_btn = QPushButton("Refresh Printers")
        self.refresh_printers_btn.clicked.connect(self._refresh_printers)

        self.printer_mode_label = QLabel()
        self.printer_label = QLabel()
        self.receipt_mode_label = QLabel()
        self.receipt_printer_label = QLabel()
        self.active_printer_mode_label = QLabel()
        self.invoice_auto_print_after_save_check = QCheckBox()
        self.invoice_print_preview_check = QCheckBox()

        self.printer_vendor_id = QLineEdit()
        self.printer_product_id = QLineEdit()
        self.printer_interface = QLineEdit()
        self.printer_out_ep = QLineEdit()
        self.printer_in_ep = QLineEdit()
        self.printer_backend_priority = QLineEdit()
        self.receipt_paper_preset = QLineEdit("80mm")
        self.qr_label_preset = QLineEdit("38×25mm")
        self.barcode_offset_x = QSpinBox()
        self.barcode_offset_x.setRange(-1000, 1000)
        self.barcode_offset_x.setSuffix(" px")
        self.barcode_offset_y = QSpinBox()
        self.barcode_offset_y.setRange(-1000, 1000)
        self.barcode_offset_y.setSuffix(" px")
        self.print_test_label_btn = QPushButton()
        self.print_test_receipt_btn = QPushButton()
        self.preview_sample_receipt_btn = QPushButton()
        self.receipt_paper_preset.setReadOnly(True)
        self.qr_label_preset.setReadOnly(True)
        self.print_test_label_btn.clicked.connect(self._print_test_label)
        self.print_test_receipt_btn.clicked.connect(self._print_test_receipt)
        self.preview_sample_receipt_btn.clicked.connect(self._preview_sample_receipt)
        self.printer_vendor_label = QLabel("Vendor ID")
        self.printer_product_label = QLabel("Product ID")
        self.printer_interface_label = QLabel("USB Interface")
        self.printer_out_ep_label = QLabel("OUT Endpoint")
        self.printer_in_ep_label = QLabel("IN Endpoint")
        self.printer_backend_priority_label = QLabel("Backend priority")
        self.receipt_paper_preset_label = QLabel("Receipt paper")
        self.qr_label_preset_label = QLabel("QR label size")
        printer_layout.addRow("Barcode printer enabled", self.barcode_enabled_check)
        printer_layout.addRow(self.printer_mode_label, self.barcode_mode)
        printer_layout.addRow(self.printer_label, self.barcode_printer)
        printer_layout.addRow("Barcode printer model", self.barcode_model)
        printer_layout.addRow("Command language", self.barcode_command_language)
        printer_layout.addRow(self.receipt_mode_label, self.receipt_mode)
        printer_layout.addRow(self.receipt_printer_label, self.receipt_printer)
        printer_layout.addRow("", self.refresh_printers_btn)
        printer_layout.addRow(self.receipt_paper_preset_label, self.receipt_paper_preset)
        printer_layout.addRow(self.qr_label_preset_label, self.qr_label_preset)
        printer_layout.addRow("Label Width (mm)", self.barcode_label_width)
        printer_layout.addRow("Label Height (mm)", self.barcode_label_height)
        printer_layout.addRow("Label Gap (mm)", self.barcode_label_gap)
        printer_layout.addRow("Printer DPI", self.barcode_dpi)
        printer_layout.addRow("Print density", self.barcode_density)
        printer_layout.addRow("Print speed", self.barcode_speed)
        printer_layout.addRow("Default copies", self.barcode_copies)
        printer_layout.addRow("Horizontal Offset (px)", self.barcode_offset_x)
        printer_layout.addRow("Vertical Offset (px)", self.barcode_offset_y)
        printer_layout.addRow("", self.print_test_receipt_btn)
        printer_layout.addRow("", self.preview_sample_receipt_btn)
        printer_layout.addRow("", self.print_test_label_btn)
        printer_layout.addRow("", self.invoice_auto_print_after_save_check)
        printer_layout.addRow("", self.invoice_print_preview_check)
        printer_layout.addRow(self.printer_vendor_label, self.printer_vendor_id)
        printer_layout.addRow(self.printer_product_label, self.printer_product_id)
        printer_layout.addRow(self.printer_interface_label, self.printer_interface)
        printer_layout.addRow(self.printer_out_ep_label, self.printer_out_ep)
        printer_layout.addRow(self.printer_in_ep_label, self.printer_in_ep)
        printer_layout.addRow(self.printer_backend_priority_label, self.printer_backend_priority)
        content_layout.addWidget(printer_box)
        self.printer_box = printer_box

        device_status_box = QGroupBox("Device Status")
        device_status_layout = QFormLayout(device_status_box)
        self.receipt_status = QLabel("Unknown")
        self.barcode_status = QLabel("Unknown")
        self.scanner_status = QLabel("Unknown")
        device_status_layout.addRow("Receipt printer status", self.receipt_status)
        device_status_layout.addRow("Barcode printer status", self.barcode_status)
        device_status_layout.addRow("Barcode scanner status", self.scanner_status)

        tests_row = QHBoxLayout()
        self.test_printer_btn = QPushButton("Test Printer")
        self.test_scanner_btn = QPushButton("Test Scanner")
        self.test_printer_btn.clicked.connect(self._test_printers)
        self.test_scanner_btn.clicked.connect(self._test_scanner)
        tests_row.addWidget(self.test_printer_btn)
        tests_row.addWidget(self.test_scanner_btn)
        device_status_layout.addRow("", tests_row)

        content_layout.addWidget(device_status_box)
        self.device_status_box = device_status_box

        save_btn = QPushButton()
        save_btn.clicked.connect(self._save_settings)
        self.footer_layout.addWidget(save_btn)
        self.save_btn = save_btn

        loyalty_btn = QPushButton()
        loyalty_btn.clicked.connect(self._open_loyalty_settings)
        self.footer_layout.addWidget(loyalty_btn)
        self.loyalty_btn = loyalty_btn

        delivery_companies_btn = QPushButton()
        delivery_companies_btn.clicked.connect(self._open_delivery_companies)
        self.footer_layout.addWidget(delivery_companies_btn)
        self.delivery_companies_btn = delivery_companies_btn

        statuses_btn = QPushButton()
        statuses_btn.clicked.connect(self._open_statuses)
        self.footer_layout.addWidget(statuses_btn)
        self.statuses_btn = statuses_btn

        payment_box = QGroupBox()
        payment_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        payment_layout = QFormLayout(payment_box)
        payment_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form_layouts.append(payment_layout)
        self.payment_ar_input = QLineEdit()
        self.payment_en_input = QLineEdit()
        add_payment_btn = QPushButton()
        add_payment_btn.clicked.connect(self._add_payment_method)
        self.payment_ar_label = QLabel()
        self.payment_en_label = QLabel()
        payment_layout.addRow(self.payment_ar_label, self.payment_ar_input)
        payment_layout.addRow(self.payment_en_label, self.payment_en_input)
        payment_layout.addRow("", add_payment_btn)
        content_layout.addWidget(payment_box)
        self.payment_box = payment_box
        self.add_payment_btn = add_payment_btn

        demo_box = QGroupBox()
        demo_layout = QVBoxLayout(demo_box)
        demo_btn = QPushButton()
        demo_btn.clicked.connect(self._seed_demo)
        demo_layout.addWidget(demo_btn)
        content_layout.addWidget(demo_box)
        self.demo_box = demo_box
        self.demo_btn = demo_btn

        self.set_page_content_widget(content)
        self._load_settings()
        self.apply_language(self._language)
        self._apply_rtl_layout()

    def apply_rtl_layout(self, rtl_enabled: bool) -> None:
        for form_layout in self._form_layouts:
            form_layout.setLabelAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                if rtl_enabled
                else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def _apply_rtl_layout(self) -> None:
        settings = load_gallery_settings()
        self.apply_rtl_layout(settings.rtl_enabled)

    def _load_settings(self) -> None:
        settings = load_gallery_settings()
        barcode_settings = settings.barcode_printer_settings
        self.name_en_input.setText(settings.name_en)
        self.name_ar_input.setText(settings.name_ar)
        self.address_input.setText(settings.address)
        self.phone_input.setText(settings.phone)
        self.logo_input.setText(settings.logo_path)
        self.font_input.setText(settings.font_path)
        self.rtl_check.setChecked(settings.rtl_enabled)
        self._set_combo_value(self.barcode_mode, settings.barcode_print_mode)
        self.barcode_enabled_check.setChecked(barcode_settings.enabled)
        self.barcode_printer.setCurrentText(barcode_settings.exact_windows_name)
        self._set_combo_value(self.barcode_model, barcode_settings.model)
        self._set_combo_value(self.barcode_command_language, barcode_settings.command_language)
        self._set_combo_value(self.receipt_mode, settings.receipt_print_mode or "auto")
        self._set_combo_value(self.receipt_printer, settings.receipt_printer_name)
        self.website_name_input.setText(settings.website_name)
        self.website_url_input.setText(settings.website_url)
        self.website_orders_check.setChecked(settings.website_orders_enabled)
        self.printer_vendor_id.setText(settings.printer_vendor_id)
        self.printer_product_id.setText(settings.printer_product_id)
        self.printer_interface.setText(settings.printer_interface)
        self.printer_out_ep.setText(settings.printer_out_ep)
        self.printer_in_ep.setText(settings.printer_in_ep)
        self.printer_backend_priority.setText(settings.printer_backend_priority)
        self.invoice_auto_print_after_save_check.setChecked(settings.invoice_auto_print_after_save)
        self.invoice_print_preview_check.setChecked(settings.invoice_print_preview)
        self.barcode_label_width.setValue(barcode_settings.width_mm)
        self.barcode_label_height.setValue(barcode_settings.height_mm)
        self.barcode_label_gap.setValue(barcode_settings.gap_mm)
        self.barcode_dpi.setValue(barcode_settings.dpi)
        self.barcode_density.setValue(barcode_settings.density)
        self.barcode_speed.setValue(barcode_settings.speed)
        self.barcode_copies.setValue(barcode_settings.default_copies)
        self.barcode_offset_x.setValue(settings.barcode_horizontal_offset_px)
        self.barcode_offset_y.setValue(settings.barcode_vertical_offset_px)
        self._set_language_combo(get_ui_language())
        self._refresh_device_status()

    def _save_settings(self) -> None:
        current_settings = load_gallery_settings()
        barcode_settings = self._barcode_settings_from_controls()
        app_settings = replace(
            current_settings,
            name_en=self.name_en_input.text().strip(),
            name_ar=self.name_ar_input.text().strip(),
            address=self.address_input.text().strip(),
            phone=self.phone_input.text().strip(),
            logo_path=self.logo_input.text().strip(),
            font_path=self.font_input.text().strip(),
            rtl_enabled=self.rtl_check.isChecked(),
            barcode_print_mode=self.barcode_mode.currentData() or "pdf",
            barcode_printer_name=barcode_settings.exact_windows_name or "auto",
            receipt_print_mode=self.receipt_mode.currentData() or "auto",
            receipt_printer_name=self.receipt_printer.currentData() or "auto",
            website_name=self.website_name_input.text().strip(),
            website_url=self.website_url_input.text().strip(),
            website_orders_enabled=self.website_orders_check.isChecked(),
            printer_vendor_id=self.printer_vendor_id.text().strip() or "0x0FE6",
            printer_product_id=self.printer_product_id.text().strip() or "0x811E",
            printer_interface=self.printer_interface.text().strip() or "0",
            printer_out_ep=self.printer_out_ep.text().strip() or "0x01",
            printer_in_ep=self.printer_in_ep.text().strip() or "0x81",
            printer_backend_priority=self.printer_backend_priority.text().strip() or "raw-usb-escpos,escpos-usb,file,windows",
            invoice_auto_print_after_save=self.invoice_auto_print_after_save_check.isChecked(),
            invoice_print_preview=self.invoice_print_preview_check.isChecked(),
            barcode_label_width_mm=barcode_settings.width_mm,
            barcode_label_height_mm=barcode_settings.height_mm,
            barcode_horizontal_offset_px=self.barcode_offset_x.value(),
            barcode_vertical_offset_px=self.barcode_offset_y.value(),
            barcode_printer_settings=barcode_settings,
        )
        save_gallery_settings(app_settings)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("settings.saved_successfully", language=self._language),
        )
        if self._on_settings_changed:
            self._on_settings_changed()

    def _add_payment_method(self) -> None:
        name_ar = self.payment_ar_input.text().strip()
        name_en = self.payment_en_input.text().strip()
        if not name_ar or not name_en:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("settings.payment_missing", language=self._language),
            )
            return
        add_payment_method(name_ar, name_en)
        self.payment_ar_input.clear()
        self.payment_en_input.clear()
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("settings.payment_added", language=self._language),
        )
        if self._on_payment_methods_changed:
            self._on_payment_methods_changed()

    def _pick_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.logo_dialog", language=self._language),
            "",
            f"{t('settings.images_filter', language=self._language)} (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            self.logo_input.setText(path)

    def _pick_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.font_dialog", language=self._language),
            "",
            f"{t('settings.fonts_filter', language=self._language)} (*.ttf *.otf)",
        )
        if path:
            self.font_input.setText(path)

    def _seed_demo(self) -> None:
        seed_demo_data()
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("settings.demo_seeded", language=self._language),
        )
        if self._on_payment_methods_changed:
            self._on_payment_methods_changed()

    def _set_language_combo(self, language: str) -> None:
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(t("language.option.ar", language=language), "ar")
        self.language_combo.addItem(t("language.option.en", language=language), "en")
        idx = self.language_combo.findData(language)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)
        self.language_combo.blockSignals(False)

    def _handle_language_change(self) -> None:
        language = self.language_combo.currentData() or "ar"
        if language == self._language:
            return
        set_ui_language(language)
        self.apply_language(language)
        if self._on_language_changed:
            self._on_language_changed(language)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("settings.header", language=language))
        self.gallery_box.setTitle(t("settings.company_info", language=language))
        self.website_box.setTitle(t("settings.website_info", language=language))
        self.printer_box.setTitle(t("settings.printing", language=language))
        self.payment_box.setTitle(t("settings.payment_methods", language=language))
        self.demo_box.setTitle(t("settings.demo_seed", language=language))
        self.name_en_label.setText(t("settings.store_name", language=language))
        self.name_ar_label.setText(t("settings.name_ar", language=language))
        self.address_label.setText(t("settings.address", language=language))
        self.phone_label.setText(t("settings.phone", language=language))
        self.logo_label.setText(t("settings.logo_path", language=language))
        self.font_label.setText(t("settings.font_path", language=language))
        self.language_label.setText(t("language.label", language=language))
        self.website_name_label.setText(t("settings.website_name", language=language))
        self.website_url_label.setText(t("settings.website_url", language=language))
        self.rtl_check.setText(t("settings.rtl_toggle", language=language))
        self.website_orders_check.setText(t("settings.website_orders_toggle", language=language))
        self.logo_btn.setText(t("settings.browse_logo", language=language))
        self.font_btn.setText(t("settings.browse_font", language=language))
        self.printer_mode_label.setText(t("settings.default_mode", language=language))
        self.printer_label.setText(t("settings.barcode_label_printer", language=language))
        self.receipt_mode_label.setText(t("settings.receipt_mode", language=language))
        self.receipt_printer_label.setText(t("settings.receipt_printer", language=language))
        self.refresh_printers_btn.setText(
            "تحديث الطابعات" if language == "ar" else "Refresh Printers"
        )
        self.receipt_paper_preset_label.setText("ورق الإيصال" if language == "ar" else "Receipt paper")
        self.qr_label_preset_label.setText("مقاس ملصق QR" if language == "ar" else "QR label size")
        self.receipt_paper_preset.setText("80mm (افتراضي)" if language == "ar" else "80mm (default)")
        self.qr_label_preset.setText("38×25mm (افتراضي)" if language == "ar" else "38×25mm (default)")
        self.barcode_mode.setItemText(0, t("settings.barcode_mode_pdf", language=language))
        self.barcode_mode.setItemText(1, t("settings.barcode_mode_direct", language=language))
        self.receipt_mode.setItemText(0, t("settings.receipt_mode_auto", language=language))
        self.receipt_mode.setItemText(1, t("settings.receipt_mode_windows", language=language))
        self.receipt_printer.setItemText(0, t("settings.printer_auto", language=language))
        self.print_test_receipt_btn.setText(t("settings.print_test_receipt", language=language))
        self.preview_sample_receipt_btn.setText(t("settings.preview_sample_receipt", language=language))
        self.print_test_label_btn.setText(t("settings.print_test_barcode_label", language=language))
        self.invoice_auto_print_after_save_check.setText("طباعة تلقائية بعد الحفظ" if language == "ar" else "Auto print after save")
        self.invoice_print_preview_check.setText("معاينة سريعة قبل الطباعة" if language == "ar" else "Quick preview before print")
        self.save_btn.setText(t("settings.save", language=language))
        self.payment_ar_label.setText(t("settings.name_ar", language=language))
        self.payment_en_label.setText(t("settings.name_en", language=language))
        self.add_payment_btn.setText(t("settings.add_method", language=language))
        self.demo_btn.setText(t("settings.seed_demo", language=language))
        self.loyalty_btn.setText(t("loyalty.settings.button", language=language))
        self.delivery_companies_btn.setText(t("delivery_companies.button", language=language))
        self.statuses_btn.setText(t("statuses.button", language=language))
        self._set_language_combo(language)


    def _refresh_device_status(self) -> None:
        receipt = device_health.check_receipt_printer(self.receipt_printer.currentData() or "auto", self.receipt_mode.currentData() or "auto")
        barcode_name = self.barcode_printer.currentText().strip() or "auto"
        barcode = device_health.check_barcode_printer(barcode_name, self.barcode_mode.currentData() or "pdf")
        scanner = device_health.check_barcode_scanner()
        self.receipt_status.setText(f"{receipt['status']}: {receipt['detail']}")
        self.barcode_status.setText(f"{barcode['status']}: {barcode['detail']}")
        self.scanner_status.setText(f"{scanner['status']}: {scanner['detail']}")

    @staticmethod
    def _windows_printer_names() -> list[str]:
        try:
            return enumerate_printers()
        except RuntimeError:
            return []

    def _refresh_printers(self) -> None:
        """Repopulate printer queues while preserving explicit user choices."""
        barcode_name = self.barcode_printer.currentText()
        receipt_name = self.receipt_printer.currentText()
        names = self._windows_printer_names()

        barcode_blocker = QSignalBlocker(self.barcode_printer)
        receipt_blocker = QSignalBlocker(self.receipt_printer)
        try:
            self.barcode_printer.clear()
            self.barcode_printer.addItem("")
            for name in names:
                if self.barcode_printer.findText(name) < 0:
                    self.barcode_printer.addItem(name)
            if barcode_name and self.barcode_printer.findText(barcode_name) < 0:
                self.barcode_printer.addItem(barcode_name)
            self.barcode_printer.setCurrentText(barcode_name)

            self.receipt_printer.clear()
            self.receipt_printer.addItem(
                t("settings.printer_auto", language=self._language), "auto"
            )
            for name in names:
                if self.receipt_printer.findText(name) < 0:
                    self.receipt_printer.addItem(name, name)
            if receipt_name and self.receipt_printer.findText(receipt_name) < 0:
                self.receipt_printer.addItem(receipt_name, receipt_name)
            self.receipt_printer.setCurrentText(receipt_name)
        finally:
            del barcode_blocker, receipt_blocker

    def _test_printers(self) -> None:
        receipt_name = self.receipt_printer.currentData() or "auto"
        receipt_mode = self.receipt_mode.currentData() or "auto"
        device_health.test_receipt_bitmap_route(str(receipt_name), str(receipt_mode))
        device_health.test_receipt_raw_text_route(str(receipt_name), str(receipt_mode))
        self._refresh_device_status()
        QMessageBox.information(self, "Device Test", "Printer diagnostics sent (bitmap + raw text). Review Device Status details.")

    def _test_scanner(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Scanner Test")
        dialog.setText("Scan a barcode within 10 seconds.")
        editor = QLineEdit()
        dialog.layout().addWidget(editor, 1, 1)
        editor.setFocus()
        loop = QEventLoop()
        parsed = {"value": ""}

        def finish_timeout() -> None:
            if not parsed["value"]:
                loop.quit()

        def on_return() -> None:
            parsed["value"] = normalize_scanner_payload(editor.text())
            loop.quit()

        editor.returnPressed.connect(on_return)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(finish_timeout)
        timer.start(10000)
        dialog.show()
        loop.exec()
        dialog.close()
        if parsed["value"]:
            QMessageBox.information(self, "Scanner Test", f"Scanner payload valid: {parsed['value']}")
        else:
            QMessageBox.warning(self, "Scanner Test", "No scanner payload received before timeout.")
        self._refresh_device_status()

    def _print_test_label(self) -> None:
        try:
            current_settings = load_gallery_settings()
            barcode_settings = self._barcode_settings_from_controls()
            settings = replace(
                current_settings,
                barcode_print_mode=self.barcode_mode.currentData() or "pdf",
                barcode_printer_name=barcode_settings.exact_windows_name or "auto",
                barcode_label_width_mm=barcode_settings.width_mm,
                barcode_label_height_mm=barcode_settings.height_mm,
                barcode_horizontal_offset_px=self.barcode_offset_x.value(),
                barcode_vertical_offset_px=self.barcode_offset_y.value(),
                barcode_printer_settings=barcode_settings,
            )
            save_gallery_settings(settings)
            barcode_printer.print_test_label(
                printer_name=barcode_settings.exact_windows_name or "auto"
            )
            QMessageBox.information(self, "Barcode Calibration", t("inventory.printed", language=self._language))
        except Exception as exc:
            QMessageBox.warning(self, "Barcode Calibration", f"{t('common.failed_to_print', language=self._language)}: {exc}")

    def _print_test_receipt(self) -> None:
        receipt_printer = self.receipt_printer.currentData() or "auto"
        receipt_mode = self.receipt_mode.currentData() or "auto"
        try:
            did_print = printer_service.printer.print_text_receipt(
                ["*** TEST RECEIPT ***", "Jewelry POS", "Thank you"],
                printer_name=receipt_printer,
                print_mode=receipt_mode,
            )
            if did_print is False:
                raise RuntimeError(f"Printer unavailable/offline ({receipt_printer})")
            QMessageBox.information(self, "Receipt Test", t("settings.receipt_sent_to_printer", language=self._language))
        except Exception as exc:
            QMessageBox.warning(self, "Receipt Test", f"{t('common.failed_to_print', language=self._language)}: {exc}")

    def _preview_sample_receipt(self) -> None:
        try:
            path = printer_service.render_sample_arabic_receipt_preview()
            QMessageBox.information(self, "Receipt Preview", f"Sample Arabic receipt preview saved to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Receipt Preview", f"Failed to render sample preview: {exc}")

    def _open_loyalty_settings(self) -> None:
        dialog = LoyaltySettingsDialog(self)
        dialog.exec()

    def _open_delivery_companies(self) -> None:
        dialog = DeliveryCompaniesDialog(self)
        dialog.exec()

    def _open_statuses(self) -> None:
        dialog = StatusesDialog(self)
        dialog.exec()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        for idx in range(combo.count()):
            if combo.itemData(idx) == value or combo.itemText(idx) == value:
                combo.setCurrentIndex(idx)
                return

    @staticmethod
    def _make_mm_spin_box(minimum: float, maximum: float) -> QDoubleSpinBox:
        spin_box = QDoubleSpinBox()
        spin_box.setRange(minimum, maximum)
        spin_box.setDecimals(1)
        spin_box.setSingleStep(0.1)
        spin_box.setSuffix(" mm")
        return spin_box

    def _barcode_settings_from_controls(self) -> BarcodePrinterSettings:
        return BarcodePrinterSettings(
            enabled=self.barcode_enabled_check.isChecked(),
            model=str(self.barcode_model.currentData() or ""),
            exact_windows_name=self.barcode_printer.currentText().strip(),
            width_mm=self.barcode_label_width.value(),
            height_mm=self.barcode_label_height.value(),
            gap_mm=self.barcode_label_gap.value(),
            dpi=self.barcode_dpi.value(),
            density=self.barcode_density.value(),
            speed=self.barcode_speed.value(),
            default_copies=self.barcode_copies.value(),
            command_language=str(self.barcode_command_language.currentData() or "ESC/POS"),
        )
