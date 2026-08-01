"""Inventory-only controls and diagnostics for barcode label printing."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QTextEdit, QVBoxLayout

from ...services import barcode_printer
from ...services.settings import load_gallery_settings
from ...services.windows_raw_printer import enumerate_printers


class BarcodePrintingPanel(QGroupBox):
    """Own barcode-printer actions so errors cannot leak into unrelated UI."""

    print_requested = pyqtSignal(int)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__("Barcode Printing", parent)
        self._configuration_signature: tuple[object, ...] | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.printer_combo = QComboBox()
        self.printer_combo.setEnabled(False)
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        form.addRow("Configured printer", self.printer_combo)
        form.addRow("Copies", self.copies_spin)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.print_button = QPushButton("Print Barcode")
        self.test_button = QPushButton("Test RP310")
        self.refresh_button = QPushButton("Refresh Printers")
        self.clear_button = QPushButton("Clear Status")
        for button in (self.print_button, self.test_button, self.refresh_button, self.clear_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status_label = QLabel("Ready")
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setPlaceholderText("Barcode printer diagnostics appear here.")
        self.diagnostics.setMinimumHeight(90)
        layout.addWidget(self.status_label)
        layout.addWidget(self.diagnostics)
        self.print_button.clicked.connect(self._request_print)
        self.test_button.clicked.connect(self._test_rp310)
        self.refresh_button.clicked.connect(self.refresh_printers)
        self.clear_button.clicked.connect(self.clear_status)
        self.refresh_configuration()

    def _settings_signature(self) -> tuple[object, ...]:
        settings = load_gallery_settings()
        value = settings.barcode_printer_settings
        return (
            value.enabled,
            value.exact_windows_name,
            value.model,
            value.command_language,
            value.width_mm,
            value.height_mm,
            value.gap_mm,
            value.dpi,
            value.density,
            value.speed,
            value.default_copies,
            settings.barcode_horizontal_offset_px,
            settings.barcode_vertical_offset_px,
        )

    def refresh_configuration(self) -> None:
        """Reload controls and clear stale failures only after configuration changes."""
        settings = load_gallery_settings().barcode_printer_settings
        signature = self._settings_signature()
        if self._configuration_signature is not None and signature != self._configuration_signature:
            self.clear_status()
        self._configuration_signature = signature
        self.copies_spin.setValue(max(1, int(settings.default_copies)))
        self.refresh_printers(show_status=False)

    def refresh_printers(self, _checked=False, *, show_status: bool = True) -> None:
        configured = load_gallery_settings().barcode_printer_settings.exact_windows_name
        try:
            names = enumerate_printers()
            self.printer_combo.clear()
            self.printer_combo.addItems(names)
            if configured and self.printer_combo.findText(configured) < 0:
                self.printer_combo.addItem(configured)
            self.printer_combo.setCurrentText(configured)
            if show_status:
                self.report_status(f"Found {len(names)} printer queue(s). Configured: {configured or 'none'}")
        except Exception as exc:
            self.report_failure("Refresh Printers", exc)

    def _begin_attempt(self, action: str) -> None:
        self.diagnostics.clear()  # A retry deliberately replaces the prior failure.
        self.report_status(f"{action} started…")

    def _request_print(self) -> None:
        self._begin_attempt("Print Barcode")
        self.print_requested.emit(self.copies_spin.value())

    def _test_rp310(self) -> None:
        self._begin_attempt("Test RP310")
        try:
            settings = load_gallery_settings().barcode_printer_settings
            barcode_printer.print_test_label(printer_name=settings.exact_windows_name or "auto", copies=self.copies_spin.value())
            self.report_success("Test RP310 RAW job accepted by the spooler.")
        except Exception as exc:
            self.report_failure("Test RP310", exc)

    def report_status(self, detail: str, *, failed: bool = False) -> None:
        self.status_label.setText("Failed" if failed else "Ready")
        self.diagnostics.append(f"[{datetime.now().strftime('%H:%M:%S')}] {detail}")
        self.status_changed.emit(detail, failed)

    def report_success(self, detail: str) -> None:
        self.report_status(detail)
        self.status_label.setText("Success")

    def report_failure(self, action: str, error: BaseException | str) -> None:
        self.report_status(f"{action} failed: {error}", failed=True)

    def clear_status(self) -> None:
        self.diagnostics.clear()
        self.status_label.setText("Ready")
        self.status_changed.emit("", False)
