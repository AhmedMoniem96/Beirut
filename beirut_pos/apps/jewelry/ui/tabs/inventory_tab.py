"""Inventory tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import QElapsedTimer, QEvent, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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
    QWidget,
)

from ...services.db import barcode_exists, delete_product, list_products, save_product
from ...services.barcode_printer import render_barcode_label_image, print_barcode_label_image
from ...services.pdf_exports import export_barcode_labels_pdf
from ...services.settings import load_gallery_settings
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
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("")
        self.search_input.textChanged.connect(self.refresh)
        self.search_label = QLabel()
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        content_layout.addLayout(search_layout)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.form_box = form_box
        form_layout = QFormLayout(form_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
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
        form_layout.addRow(self.name_ar_label, self.name_ar_input)
        form_layout.addRow(self.name_en_label, self.name_en_input)
        form_layout.addRow(self.sku_label, self.sku_input)
        form_layout.addRow(self.barcode_label, self.barcode_input)
        form_layout.addRow(self.barcode_type_label, self.barcode_type_input)
        form_layout.addRow(self.price_label, self.price_input)
        form_layout.addRow(self.qty_label, self.qty_input)
        form_layout.addRow(self.min_qty_label, self.min_qty_input)
        form_layout.addRow(self.category_label, self.category_input)
        form_layout.addRow("", self.handmade_check)
        form_layout.addRow(self.stone_type_label, self.stone_type_input)
        form_layout.addRow(self.color_label, self.color_input)

        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self._save_product)
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(self._delete_product)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_form)
        self.print_barcode_btn = QPushButton()
        self.print_barcode_btn.clicked.connect(self._print_barcode_label)

        content_layout.addWidget(form_box)
        self.footer_layout.addWidget(self.save_btn)
        self.footer_layout.addWidget(self.delete_btn)
        self.footer_layout.addWidget(self.clear_btn)
        self.footer_layout.addWidget(self.print_barcode_btn)

        self.table = QTableWidget(0, 12)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellClicked.connect(self._load_selected_product)
        content_layout.addWidget(self.table)

        self.alerts_box = QGroupBox()
        alerts_layout = QVBoxLayout(self.alerts_box)
        self.alerts_table = QTableWidget(0, 5)
        self.alerts_table.setAlternatingRowColors(True)
        self.alerts_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        alerts_layout.addWidget(self.alerts_table)
        content_layout.addWidget(self.alerts_box)

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

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("inventory.header", language=language))
        self.search_label.setText(f"{t('common.search', language=language)}:")
        self.search_input.setPlaceholderText(t("inventory.search_placeholder", language=language))
        self.form_box.setTitle(t("inventory.details_box", language=language))
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

    def _print_barcode_label(self) -> None:
        if not self._selected_product_id:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("inventory.select_product", language=self._language),
            )
            return
        product = next((p for p in self._products if p.id == self._selected_product_id), None)
        if not product:
            return
        if not product.barcode:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("inventory.barcode_missing", language=self._language),
            )
            return
        barcode_type_value = self._validated_barcode_type(product.barcode_type)
        if barcode_type_value is None:
            return
        settings = load_gallery_settings()
        if settings.barcode_print_mode == "direct":
            try:
                label_img = render_barcode_label_image(
                    product_name=choose_name(product.name_ar, product.name_en, language=self._language),
                    sku=product.sku,
                    barcode_value=product.barcode,
                    barcode_type=barcode_type_value,
                )
                print_barcode_label_image(
                    label_img,
                    printer_name=settings.barcode_printer_name,
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    t("inventory.print_failed", language=self._language),
                    t("inventory.direct_print_failed", language=self._language, error=exc),
                )
                return
            QMessageBox.information(
                self,
                t("common.print", language=self._language),
                t("inventory.printed", language=self._language),
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("inventory.export_labels", language=self._language),
            f"{product.sku}_barcode_labels.pdf",
            f"{t('common.file_filter_pdf', language=self._language)} (*.pdf)",
        )
        if not path:
            return
        export_barcode_labels_pdf(
            path,
            choose_name(product.name_ar, product.name_en, language=self._language),
            product.sku,
            product.barcode,
            barcode_type_value,
        )
        QMessageBox.information(
            self,
            t("common.export", language=self._language),
            t("inventory.exported_labels", language=self._language),
        )

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
