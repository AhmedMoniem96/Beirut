"""Settings tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import Qt
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...services.db import add_payment_method
from ...services.settings import GallerySettings, load_gallery_settings, save_gallery_settings
from ...services.demo_seed import seed_demo_data
from ...services.i18n import get_ui_language, set_ui_language, t
from ..dialogs.delivery_companies_dialog import DeliveryCompaniesDialog
from ..dialogs.loyalty_settings_dialog import LoyaltySettingsDialog
from ..dialogs.statuses_dialog import StatusesDialog
from beirut_pos.services import printer as printer_service


class SettingsTab(QWidget):
    def __init__(self, on_settings_changed=None, on_payment_methods_changed=None, on_language_changed=None) -> None:
        super().__init__()
        self._on_settings_changed = on_settings_changed
        self._on_payment_methods_changed = on_payment_methods_changed
        self._on_language_changed = on_language_changed
        self._language = get_ui_language()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        header = QLabel()
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        self.header_label = header

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
        layout.addWidget(gallery_box)
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
        layout.addWidget(website_box)
        self.website_box = website_box

        printer_box = QGroupBox()
        printer_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        printer_layout = QFormLayout(printer_box)
        printer_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._form_layouts.append(printer_layout)
        self.barcode_mode = QComboBox()
        self.barcode_mode.addItem("", "pdf")
        self.barcode_mode.addItem("", "direct")

        self.barcode_printer = QComboBox()
        self.barcode_printer.addItem("", "auto")
        for name in printer_service.win_list_printers():
            self.barcode_printer.addItem(name, name)

        self.printer_mode_label = QLabel()
        self.printer_label = QLabel()
        printer_layout.addRow(self.printer_mode_label, self.barcode_mode)
        printer_layout.addRow(self.printer_label, self.barcode_printer)
        layout.addWidget(printer_box)
        self.printer_box = printer_box

        save_btn = QPushButton()
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        self.save_btn = save_btn

        loyalty_btn = QPushButton()
        loyalty_btn.clicked.connect(self._open_loyalty_settings)
        layout.addWidget(loyalty_btn)
        self.loyalty_btn = loyalty_btn

        delivery_companies_btn = QPushButton()
        delivery_companies_btn.clicked.connect(self._open_delivery_companies)
        layout.addWidget(delivery_companies_btn)
        self.delivery_companies_btn = delivery_companies_btn

        statuses_btn = QPushButton()
        statuses_btn.clicked.connect(self._open_statuses)
        layout.addWidget(statuses_btn)
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
        layout.addWidget(payment_box)
        self.payment_box = payment_box
        self.add_payment_btn = add_payment_btn

        demo_box = QGroupBox()
        demo_layout = QVBoxLayout(demo_box)
        demo_btn = QPushButton()
        demo_btn.clicked.connect(self._seed_demo)
        demo_layout.addWidget(demo_btn)
        layout.addWidget(demo_box)
        self.demo_box = demo_box
        self.demo_btn = demo_btn
        layout.addStretch()

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
        self.name_en_input.setText(settings.name_en)
        self.name_ar_input.setText(settings.name_ar)
        self.address_input.setText(settings.address)
        self.phone_input.setText(settings.phone)
        self.logo_input.setText(settings.logo_path)
        self.font_input.setText(settings.font_path)
        self.rtl_check.setChecked(settings.rtl_enabled)
        self._set_combo_value(self.barcode_mode, settings.barcode_print_mode)
        self._set_combo_value(self.barcode_printer, settings.barcode_printer_name)
        self.website_name_input.setText(settings.website_name)
        self.website_url_input.setText(settings.website_url)
        self.website_orders_check.setChecked(settings.website_orders_enabled)
        self._set_language_combo(get_ui_language())

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
            website_name=self.website_name_input.text().strip(),
            website_url=self.website_url_input.text().strip(),
            website_orders_enabled=self.website_orders_check.isChecked(),
        )
        save_gallery_settings(settings)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("settings.saved_message", language=self._language),
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
        self.gallery_box.setTitle(t("settings.gallery_info", language=language))
        self.website_box.setTitle(t("settings.website_info", language=language))
        self.printer_box.setTitle(t("settings.barcode_printing", language=language))
        self.payment_box.setTitle(t("settings.payment_methods", language=language))
        self.demo_box.setTitle(t("settings.demo_seed", language=language))
        self.name_en_label.setText(t("settings.name_en", language=language))
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
        self.printer_label.setText(t("settings.printer", language=language))
        self.barcode_mode.setItemText(0, t("settings.barcode_mode_pdf", language=language))
        self.barcode_mode.setItemText(1, t("settings.barcode_mode_direct", language=language))
        self.barcode_printer.setItemText(0, t("settings.printer_auto", language=language))
        self.save_btn.setText(t("settings.save", language=language))
        self.payment_ar_label.setText(t("settings.name_ar", language=language))
        self.payment_en_label.setText(t("settings.name_en", language=language))
        self.add_payment_btn.setText(t("settings.add_method", language=language))
        self.demo_btn.setText(t("settings.seed_demo", language=language))
        self.loyalty_btn.setText(t("loyalty.settings.button", language=language))
        self.delivery_companies_btn.setText(t("delivery_companies.button", language=language))
        self.statuses_btn.setText(t("statuses.button", language=language))
        self._set_language_combo(language)

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
