"""Inventory tab for Jewelry app."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PyQt6.QtCore import QElapsedTimer, QEvent, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)

from ...services.db import barcode_exists, delete_product, list_products, save_product
from ...services.product_import import generate_import_template, import_products_from_excel
from ...services.settings import (
    PRINTER_MODE_LABEL,
    PRINTER_MODE_RECEIPT,
    load_gallery_settings,
    set_printer_mode,
)
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


class InventoryTab(BaseTabContainer):
    _SUPPORTED_BARCODE_TYPES = {
        "code128": "Code128",
        "code39": "Code39",
        "qr": "QR",
    }

    def __init__(self, on_products_changed=None) -> None:
        super().__init__()
        print("LOADED INVENTORY TAB FILE:", __file__)
        self._on_products_changed = on_products_changed
        self._selected_product_id = None
        self._products = []
        self._allow_edit = True
        self._scan_buffer = ""
        self._scan_timer = QElapsedTimer()
        self._scan_timer.start()
        self._language = get_ui_language()
        QApplication.instance().installEventFilter(self)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(12)
        self.set_content_layout(self.content_layout)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("")
        self.search_input.textChanged.connect(self.refresh)
        self.search_label = QLabel()
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        self.add_content_layout(search_layout)

        self.inventory_tabs = QTabWidget()
        self.products_tab = QWidget()
        self.alerts_tab = QWidget()
        self.inventory_tabs.addTab(self.products_tab, "")
        self.inventory_tabs.addTab(self.alerts_tab, "")

        products_layout = QVBoxLayout(self.products_tab)
        products_layout.setSpacing(10)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.form_box = form_box
        form_layout = QGridLayout(form_box)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(6)
        self.name_ar_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.sku_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.barcode_type_input = QLineEdit()
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setDecimals(2)
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0, 999999)
        self.qty_input.setDecimals(2)
        self.min_qty_input = QDoubleSpinBox()
        self.min_qty_input.setRange(0, 999999)
        self.min_qty_input.setDecimals(2)
        self.category_input = QLineEdit()
        self.handmade_check = QCheckBox()
        self.stone_type_input = QLineEdit()
        self.color_input = QLineEdit()

        self.name_ar_label = QLabel()
        self.name_en_label = QLabel()
        self.sku_label = QLabel()
        self.barcode_label = QLabel()
        self.barcode_type_label = QLabel()
        self.price_label = QLabel()
        self.qty_label = QLabel()
        self.min_qty_label = QLabel()
        self.category_label = QLabel()
        self.stone_type_label = QLabel()
        self.color_label = QLabel()

        info_box = QGroupBox()
        self.info_box = info_box
        info_layout = QGridLayout(info_box)
        info_layout.addWidget(self.name_ar_label, 0, 0)
        info_layout.addWidget(self.name_ar_input, 1, 0)
        info_layout.addWidget(self.name_en_label, 0, 1)
        info_layout.addWidget(self.name_en_input, 1, 1)
        info_layout.addWidget(self.sku_label, 0, 2)
        info_layout.addWidget(self.sku_input, 1, 2)
        info_layout.addWidget(self.barcode_label, 2, 0)
        info_layout.addWidget(self.barcode_input, 3, 0)
        info_layout.addWidget(self.barcode_type_label, 2, 1)
        info_layout.addWidget(self.barcode_type_input, 3, 1)

        pricing_box = QGroupBox()
        self.pricing_box = pricing_box
        pricing_layout = QGridLayout(pricing_box)
        pricing_layout.addWidget(self.price_label, 0, 0)
        pricing_layout.addWidget(self.price_input, 1, 0)
        pricing_layout.addWidget(self.qty_label, 0, 1)
        pricing_layout.addWidget(self.qty_input, 1, 1)
        pricing_layout.addWidget(self.min_qty_label, 0, 2)
        pricing_layout.addWidget(self.min_qty_input, 1, 2)

        attrs_box = QGroupBox()
        self.attrs_box = attrs_box
        attrs_layout = QGridLayout(attrs_box)
        attrs_layout.addWidget(self.category_label, 0, 0)
        attrs_layout.addWidget(self.category_input, 1, 0)
        attrs_layout.addWidget(self.stone_type_label, 0, 1)
        attrs_layout.addWidget(self.stone_type_input, 1, 1)
        attrs_layout.addWidget(self.color_label, 0, 2)
        attrs_layout.addWidget(self.color_input, 1, 2)
        attrs_layout.addWidget(self.handmade_check, 1, 3)

        form_layout.addWidget(info_box, 0, 0)
        form_layout.addWidget(pricing_box, 0, 1)
        form_layout.addWidget(attrs_box, 1, 0, 1, 2)
        form_layout.setColumnStretch(0, 2)
        form_layout.setColumnStretch(1, 1)

        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self._save_product)
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self._delete_product)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_form)
        self.print_barcode_btn = QPushButton()
        self.print_barcode_btn.clicked.connect(self._print_barcode_label)
        self.import_excel_btn = QPushButton()
        self.import_excel_btn.clicked.connect(self._import_excel)
        self.download_template_btn = QPushButton()
        self.download_template_btn.clicked.connect(self._download_import_template)
        self.auto_save_barcode_check = QCheckBox()
        self.auto_print_barcode_check = QCheckBox()

        products_layout.addWidget(form_box)
        for btn in [self.download_template_btn, self.import_excel_btn, self.print_barcode_btn, self.clear_btn, self.delete_btn, self.save_btn]:
            btn.setMinimumWidth(150)

        self.footer_layout.addWidget(self.download_template_btn)
        self.footer_layout.addWidget(self.import_excel_btn)
        self.footer_layout.addSpacing(12)
        self.footer_layout.addWidget(self.print_barcode_btn)
        self.footer_layout.addWidget(self.auto_print_barcode_check)
        self.footer_layout.addSpacing(12)
        self.footer_layout.addWidget(self.clear_btn)
        self.footer_layout.addWidget(self.delete_btn)
        self.footer_layout.addWidget(self.save_btn)
        self.footer_layout.addWidget(self.auto_save_barcode_check)

        self.table = QTableWidget(0, 12)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setMinimumHeight(320)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._load_selected_product)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 140)
        products_layout.addWidget(self.table, 1)

        alerts_layout_root = QVBoxLayout(self.alerts_tab)
        self.alerts_box = QGroupBox()
        alerts_layout = QVBoxLayout(self.alerts_box)
        self.alerts_table = QTableWidget(0, 5)
        self.alerts_table.setAlternatingRowColors(True)
        self.alerts_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.alerts_table.horizontalHeader().setStretchLastSection(True)
        self.alerts_table.setMinimumHeight(300)
        alerts_layout.addWidget(self.alerts_table)
        self.no_alerts_label = QLabel()
        alerts_layout.addWidget(self.no_alerts_label)
        alerts_layout_root.addWidget(self.alerts_box)

        self.add_content_widget(self.inventory_tabs)

        self.set_page_content_widget(content)
        self.apply_language(self._language)
        self.refresh()

    def _normalize_barcode_type(self, barcode_type: str) -> str:
        normalized = barcode_type.strip().lower()
        normalized = normalized.replace(" ", "").replace("-", "")
        if normalized == "qrcode":
            normalized = "qr"
        return normalized

    def _validated_barcode_type(self, barcode_type: str) -> str | None:
        if not barcode_type:
            return ""
        normalized = self._normalize_barcode_type(barcode_type)
        if normalized not in self._SUPPORTED_BARCODE_TYPES:
            supported = ", ".join(self._SUPPORTED_BARCODE_TYPES.values())
            QMessageBox.warning(
                self,
                t("inventory.invalid_barcode", language=self._language),
                t("inventory.supported_barcode", language=self._language, types=supported),
            )
            return None
        return self._SUPPORTED_BARCODE_TYPES[normalized]

    def set_edit_permissions(self, allow_edit: bool) -> None:
        self._allow_edit = allow_edit
        form_widgets = [
            self.name_ar_input,
            self.name_en_input,
            self.sku_input,
            self.barcode_input,
            self.barcode_type_input,
            self.category_input,
            self.stone_type_input,
            self.color_input,
        ]
        for widget in form_widgets:
            widget.setReadOnly(not allow_edit)
        for widget in [
            self.price_input,
            self.qty_input,
            self.min_qty_input,
            self.handmade_check,
        ]:
            widget.setEnabled(allow_edit)
        for button in [self.save_btn, self.delete_btn, self.clear_btn]:
            button.setEnabled(True)

    def refresh(self, _text: str | None = None) -> None:
        search = self.search_input.text().strip()
        products = list_products(search=search if search else None)
        self._products = products
        self.table.setRowCount(0)
        self.alerts_table.setRowCount(0)
        alert_count = 0
        for product in products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(product.name_ar))
            self.table.setItem(row, 1, QTableWidgetItem(product.name_en))
            self.table.setItem(row, 2, QTableWidgetItem(product.sku))
            self.table.setItem(row, 3, QTableWidgetItem(product.barcode))
            self.table.setItem(row, 4, QTableWidgetItem(product.barcode_type))
            self.table.setItem(row, 5, QTableWidgetItem(f"{product.price:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{product.min_qty:.2f}"))
            self.table.setItem(row, 8, QTableWidgetItem(product.category))
            self.table.setItem(
                row,
                9,
                QTableWidgetItem(
                    t("common.yes", language=self._language)
                    if product.handmade_flag
                    else t("common.no", language=self._language)
                ),
            )
            self.table.setItem(row, 10, QTableWidgetItem(product.stone_type))
            self.table.setItem(row, 11, QTableWidgetItem(product.color))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, product.id)

            if product.qty_on_hand <= 0 or product.qty_on_hand <= product.min_qty:
                alert_row = self.alerts_table.rowCount()
                self.alerts_table.insertRow(alert_row)
                self.alerts_table.setItem(
                    alert_row,
                    0,
                    QTableWidgetItem(choose_name(product.name_ar, product.name_en, language=self._language)),
                )
                self.alerts_table.setItem(alert_row, 1, QTableWidgetItem(product.sku))
                self.alerts_table.setItem(
                    alert_row, 2, QTableWidgetItem(f"{product.qty_on_hand:.2f}")
                )
                self.alerts_table.setItem(
                    alert_row, 3, QTableWidgetItem(f"{product.min_qty:.2f}")
                )
                status = (
                    t("inventory.status_out", language=self._language)
                    if product.qty_on_hand <= 0
                    else t("inventory.status_near", language=self._language)
                )
                self.alerts_table.setItem(alert_row, 4, QTableWidgetItem(status))
                alert_count += 1

        self.no_alerts_label.setVisible(alert_count == 0)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("inventory.header", language=language))
        self.search_label.setText(f"{t('common.search', language=language)}:")
        self.search_input.setPlaceholderText(t("inventory.search_placeholder", language=language))
        self.inventory_tabs.setTabText(0, t("inventory.products_tab", language=language))
        self.inventory_tabs.setTabText(1, t("inventory.alerts_box", language=language))
        self.form_box.setTitle("")
        self.info_box.setTitle(t("inventory.product_info", language=language))
        self.pricing_box.setTitle(t("inventory.pricing_stock", language=language))
        self.attrs_box.setTitle(t("inventory.attributes", language=language))
        self.name_ar_label.setText(t("inventory.name_ar", language=language))
        self.name_en_label.setText(t("inventory.name_en", language=language))
        self.sku_label.setText(t("inventory.sku", language=language))
        self.barcode_label.setText(t("inventory.barcode", language=language))
        self.barcode_type_label.setText(t("inventory.barcode_type", language=language))
        self.price_label.setText(t("common.price", language=language))
        self.qty_label.setText(t("inventory.qty_on_hand", language=language))
        self.min_qty_label.setText(t("inventory.min_qty", language=language))
        self.category_label.setText(t("inventory.category", language=language))
        self.handmade_check.setText(t("inventory.handmade", language=language))
        self.stone_type_label.setText(t("inventory.stone_type", language=language))
        self.color_label.setText(t("inventory.color", language=language))
        self.save_btn.setText(t("inventory.save_product", language=language))
        self.delete_btn.setText(t("inventory.delete", language=language))
        self.clear_btn.setText(t("inventory.clear", language=language))
        self.print_barcode_btn.setText(t("inventory.print_barcode", language=language))
        self.auto_save_barcode_check.setText(t("inventory.auto_save_copy", language=language))
        self.auto_print_barcode_check.setText(t("inventory.auto_print", language=language))
        self.import_excel_btn.setText(t("inventory.import_excel", language=language))
        self.download_template_btn.setText(t("inventory.download_template", language=language))
        self.table.setHorizontalHeaderLabels(
            [
                t("inventory.table_arabic", language=language),
                t("inventory.table_english", language=language),
                t("common.code", language=language),
                t("inventory.table_barcode", language=language),
                t("inventory.table_type", language=language),
                t("common.price", language=language),
                t("inventory.table_qty", language=language),
                t("inventory.table_min", language=language),
                t("inventory.table_category", language=language),
                t("inventory.table_handmade", language=language),
                t("inventory.stone_type", language=language),
                t("inventory.color", language=language),
            ]
        )
        self.alerts_box.setTitle(t("inventory.alerts_box", language=language))
        self.no_alerts_label.setText(t("common.no_data", language=language))
        self.alerts_table.setHorizontalHeaderLabels(
            [
                t("invoice.products_header_name", language=language),
                t("common.code", language=language),
                t("inventory.table_qty", language=language),
                t("inventory.table_min", language=language),
                t("inventory.alerts_status", language=language),
            ]
        )

    def _load_selected_product(self, row: int) -> None:
        self._selected_product_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.name_ar_input.setText(self.table.item(row, 0).text())
        self.name_en_input.setText(self.table.item(row, 1).text())
        self.sku_input.setText(self.table.item(row, 2).text())
        self.barcode_input.setText(self.table.item(row, 3).text())
        self.barcode_type_input.setText(self.table.item(row, 4).text())
        self.price_input.setValue(float(self.table.item(row, 5).text()))
        self.qty_input.setValue(float(self.table.item(row, 6).text()))
        self.min_qty_input.setValue(float(self.table.item(row, 7).text()))
        self.category_input.setText(self.table.item(row, 8).text())
        self.handmade_check.setChecked(
            self.table.item(row, 9).text() == t("common.yes", language=self._language)
        )
        self.stone_type_input.setText(self.table.item(row, 10).text())
        self.color_input.setText(self.table.item(row, 11).text())

    def _save_product(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(
                self,
                t("common.access_restricted_title", language=self._language),
                t("inventory.admin_only", language=self._language),
            )
            return
        if not self.name_ar_input.text().strip() or not self.name_en_input.text().strip():
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("inventory.name_required", language=self._language),
            )
            return
        if not self.sku_input.text().strip():
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("inventory.sku_required", language=self._language),
            )
            return
        barcode_value = self.barcode_input.text().strip()
        if barcode_value and barcode_exists(barcode_value, exclude_product_id=self._selected_product_id):
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("inventory.duplicate_barcode", language=self._language),
            )
            return
        barcode_type_value = self._validated_barcode_type(self.barcode_type_input.text().strip())
        if barcode_type_value is None:
            return
        save_product(
            self._selected_product_id,
            self.name_ar_input.text().strip(),
            self.name_en_input.text().strip(),
            self.sku_input.text().strip(),
            barcode_value,
            barcode_type_value,
            float(self.price_input.value()),
            float(self.qty_input.value()),
            float(self.min_qty_input.value()),
            self.category_input.text().strip(),
            self.handmade_check.isChecked(),
            self.stone_type_input.text().strip(),
            self.color_input.text().strip(),
        )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("inventory.saved_message", language=self._language),
        )
        self.refresh()
        if self._on_products_changed:
            self._on_products_changed()

    def _delete_product(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(
                self,
                t("common.access_restricted_title", language=self._language),
                t("inventory.admin_only", language=self._language),
            )
            return
        if not self._selected_product_id:
            return
        confirm = QMessageBox.question(
            self,
            t("common.delete", language=self._language),
            t("common.confirm_delete", language=self._language),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_product(self._selected_product_id)
        self._clear_form()
        self.refresh()
        if self._on_products_changed:
            self._on_products_changed()

    def _clear_form(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(
                self,
                t("common.access_restricted_title", language=self._language),
                t("inventory.admin_only", language=self._language),
            )
            return
        self._selected_product_id = None
        self.name_ar_input.clear()
        self.name_en_input.clear()
        self.sku_input.clear()
        self.barcode_input.clear()
        self.barcode_type_input.clear()
        self.price_input.setValue(0)
        self.qty_input.setValue(0)
        self.min_qty_input.setValue(0)
        self.category_input.clear()
        self.handmade_check.setChecked(False)
        self.stone_type_input.clear()
        self.color_input.clear()


    def _download_import_template(self) -> None:
        desktop_path = Path.home() / "Desktop"
        if not desktop_path.exists():
            desktop_path = Path("C:/Users/Public/Desktop")
        target_path = desktop_path / "inventory_import_template.xlsx"

        try:
            desktop_path.mkdir(parents=True, exist_ok=True)
            generate_import_template(str(target_path))
        except Exception:
            path, _ = QFileDialog.getSaveFileName(
                self,
                t("inventory.download_template", language=self._language),
                "inventory_import_template.xlsx",
                f"{t('common.file_filter_excel', language=self._language)} (*.xlsx)",
            )
            if not path:
                return
            generate_import_template(path)
            target_path = Path(path)

        QMessageBox.information(
            self,
            t("common.export", language=self._language),
            f"{t('inventory.template_saved', language=self._language)}\n{target_path}",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_path.parent)))

    def _import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("inventory.import_excel", language=self._language),
            "",
            f"{t('common.file_filter_excel', language=self._language)} (*.xlsx)",
        )
        if not path:
            return
        try:
            report = import_products_from_excel(path)
        except ValueError as exc:
            QMessageBox.warning(self, t("inventory.import_excel", language=self._language), str(exc))
            return
        details = "\n".join(
            f"Row {row.row_number} [{row.sku or '-'}]: {row.status}{' - ' + row.message if row.message else ''}"
            for row in report.rows[:20]
        )
        if len(report.rows) > 20:
            details += "\n..."
        QMessageBox.information(
            self,
            t("inventory.import_excel", language=self._language),
            t("inventory.import_summary", language=self._language, created=report.created, updated=report.updated, skipped=report.skipped, errors=report.errors)
            + (f"\n\n{details}" if details else ""),
        )
        self.refresh()
        if self._on_products_changed:
            self._on_products_changed()

    def _print_barcode_label(self) -> None:
        if not self._selected_product_id:
            QMessageBox.warning(self, t("common.select", language=self._language), t("inventory.select_product", language=self._language))
            return
        product = next((p for p in self._products if p.id == self._selected_product_id), None)
        if not product:
            return
        if not product.barcode:
            QMessageBox.warning(self, t("common.select", language=self._language), t("inventory.barcode_missing", language=self._language))
            return
        barcode_type_value = self._validated_barcode_type(product.barcode_type)
        if barcode_type_value is None:
            return
        label_img = self._build_barcode_label_image(product, barcode_type_value)
        if label_img is None:
            return
        preview_action = self._show_label_preview_dialog(product, label_img)
        if preview_action == "cancel":
            return
        if preview_action == "switch_mode":
            if not self._ensure_printer_mode_for_labels():
                return
        elif not self._ensure_printer_mode_for_labels():
            return

        if not self._dispatch_barcode_print(product, barcode_type_value, label_img):
            QMessageBox.critical(
                self,
                t("inventory.print_failed", language=self._language),
                t("inventory.direct_print_failed", language=self._language, error="Dispatch failed."),
            )

    def _export_barcode_pdf(self, path: str, product, barcode_type_value: str) -> None:
        try:
            from ...services.pdf_exports import export_barcode_labels_pdf
        except RuntimeError:
            QMessageBox.critical(self, t("common.export", language=self._language), "PDF export is unavailable. Please install or rebuild with the missing dependency.")
            return
        export_barcode_labels_pdf(path, choose_name(product.name_ar, product.name_en, language=self._language), product.sku, product.barcode, barcode_type_value)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(t("common.export", language=self._language))
        msg.setText(t("inventory.exported_labels_path", language=self._language, path=path))
        open_btn = msg.addButton(t("inventory.open_folder", language=self._language), QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        msg.exec()
        if msg.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _dispatch_barcode_print(self, product, barcode_type_value: str, label_img) -> bool:
        settings = load_gallery_settings()
        mode = (settings.barcode_print_mode or "pdf").strip().lower() or "pdf"
        if mode == "pdf":
            return self._print_barcode_via_pdf_dispatch(label_img)
        return self._print_barcode_direct(label_img)

    def _build_barcode_label_image(self, product, barcode_type_value: str):
        try:
            from ...services.barcode_printer import render_barcode_label_image
        except RuntimeError:
            QMessageBox.critical(self, t("inventory.print_failed", language=self._language), "Barcode printing is unavailable because required dependencies are missing.")
            return None
        return render_barcode_label_image(
            product_name=choose_name(product.name_ar, product.name_en, language=self._language),
            sku=product.sku,
            barcode_value=product.barcode,
            barcode_type=barcode_type_value,
        )

    def _show_label_preview_dialog(self, product, label_img) -> str:
        dialog = QDialog(self)
        dialog.setWindowTitle("Label Preview")
        layout = QVBoxLayout(dialog)
        name = choose_name(product.name_ar, product.name_en, language=self._language) or "-"
        layout.addWidget(QLabel(f"Product: {name}"))
        layout.addWidget(QLabel(f"SKU/Barcode: {product.sku or '-'} / {product.barcode or '-'}"))
        layout.addWidget(QLabel(f"Dimensions: {label_img.width} x {label_img.height} px"))

        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        png_data = BytesIO()
        label_img.convert("L").save(png_data, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(png_data.getvalue(), "PNG")
        preview.setPixmap(pixmap.scaled(520, 340, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(preview)

        buttons = QDialogButtonBox(dialog)
        print_btn = buttons.addButton("Print", QDialogButtonBox.ButtonRole.AcceptRole)
        switch_btn = buttons.addButton("Switch Printer Mode", QDialogButtonBox.ButtonRole.ActionRole)
        cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        dialog.exec()
        clicked = buttons.clickedButton()
        if clicked is print_btn:
            return "print"
        if clicked is switch_btn:
            return "switch_mode"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

    def _ensure_printer_mode_for_labels(self) -> bool:
        active_mode = load_gallery_settings().printer_mode or PRINTER_MODE_RECEIPT
        if active_mode == PRINTER_MODE_LABEL:
            return True
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Printer Mode")
        dialog.setText("Printer is in Receipt Mode. Switch to Label Mode to print labels.")
        switch_btn = dialog.addButton("Switch Mode", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is not switch_btn:
            return False
        confirm = QMessageBox.question(
            self,
            t("settings.printer_mode_confirm_title", language=self._language),
            t("settings.printer_mode_confirm_label", language=self._language),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return False
        set_printer_mode(PRINTER_MODE_LABEL)
        return True

    def _print_barcode_via_pdf_dispatch(self, label_img) -> bool:
        try:
            from ...services.barcode_printer import try_print_barcode_label_image, BarcodePrinterError
        except RuntimeError:
            QMessageBox.critical(self, t("inventory.print_failed", language=self._language), "Barcode printing is unavailable because required dependencies are missing.")
            return False
        try:
            try_print_barcode_label_image(label_img, printer_name=load_gallery_settings().barcode_printer_name, retries=0)
            QMessageBox.information(self, t("common.print", language=self._language), t("inventory.printed", language=self._language))
            return True
        except BarcodePrinterError as exc:
            QMessageBox.critical(self, t("inventory.print_failed", language=self._language), t("inventory.direct_print_failed", language=self._language, error=exc))
            return False

    def _print_barcode_direct(self, label_img) -> bool:
        settings = load_gallery_settings()
        try:
            from ...services.barcode_printer import try_print_barcode_label_image, BarcodePrinterError
        except RuntimeError:
            QMessageBox.critical(self, t("inventory.print_failed", language=self._language), "Barcode printing is unavailable because required dependencies are missing.")
            return False
        for attempt in range(2):
            try:
                try_print_barcode_label_image(label_img, printer_name=settings.barcode_printer_name, retries=0)
                QMessageBox.information(self, t("common.print", language=self._language), t("inventory.printed", language=self._language))
                return True
            except BarcodePrinterError as exc:
                if attempt == 0:
                    retry = QMessageBox.question(
                        self,
                        t("inventory.print_failed", language=self._language),
                        t("inventory.retry_print_error", language=self._language, error=str(exc)),
                        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Retry,
                    )
                    if retry == QMessageBox.StandardButton.Retry:
                        continue
                QMessageBox.critical(self, t("inventory.print_failed", language=self._language), t("inventory.direct_print_failed", language=self._language, error=exc))
                return False


    def handle_scan(self, code: str) -> str:
        normalized_code = self._normalize_scan_text(code)
        self.search_input.setText(normalized_code)
        self.refresh()
        return t("inventory.search_status", language=self._language, code=normalized_code)

    def _normalize_scan_text(self, code: str) -> str:
        return code.rstrip("\r\n")

    def _dispatch_scan(self, code: str) -> None:
        message = self.handle_scan(code)
        if message and hasattr(self.window(), "statusBar"):
            status_bar = self.window().statusBar()
            if status_bar:
                status_bar.showMessage(message, 3000)

    def eventFilter(self, source, event):  # noqa: N802 - Qt naming convention
        if not self.isVisible():
            return super().eventFilter(source, event)
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._scan_timer.elapsed() < 500 and len(self._scan_buffer) >= 2:
                    self._dispatch_scan(self._scan_buffer)
                    self._scan_buffer = ""
                    return True
                self._scan_buffer = ""
            else:
                if self._scan_timer.elapsed() > 400:
                    self._scan_buffer = ""
                text = event.text()
                if text:
                    self._scan_buffer += text
                    self._scan_timer.restart()
        return super().eventFilter(source, event)
