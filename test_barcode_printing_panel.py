from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from beirut_pos.apps.jewelry.ui.widgets import barcode_printing_panel


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def panel(monkeypatch, application):
    printer = SimpleNamespace(
        enabled=True,
        exact_windows_name="RP310",
        model="RP310",
        command_language="escpos",
        width_mm=38,
        height_mm=25,
        gap_mm=2,
        dpi=203,
        density=8,
        speed=4,
        default_copies=1,
    )
    settings = SimpleNamespace(
        barcode_printer_settings=printer,
        barcode_horizontal_offset_px=0,
        barcode_vertical_offset_px=0,
    )
    monkeypatch.setattr(barcode_printing_panel, "load_gallery_settings", lambda: settings)
    monkeypatch.setattr(barcode_printing_panel, "enumerate_printers", lambda: ["RP310"])
    return barcode_printing_panel.BarcodePrintingPanel()


def test_print_claims_busy_before_signal_and_ignores_nested_activation(panel):
    observed = []

    def submit(copies):
        observed.append((copies, panel._submission_busy, panel.print_button.isEnabled(), panel.test_button.isEnabled()))
        panel._request_print()

    panel.print_requested.connect(submit)
    panel._request_print()

    assert observed == [(1, True, False, False)]
    assert panel._submission_busy is False
    assert panel.print_button.isEnabled()
    assert panel.test_button.isEnabled()


def test_test_button_restored_after_submission_failure(panel, monkeypatch):
    monkeypatch.setattr(
        barcode_printing_panel.barcode_printer,
        "print_test_label",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    panel._test_rp310()

    assert panel._submission_busy is False
    assert panel.print_button.isEnabled()
    assert panel.test_button.isEnabled()
    assert "offline" in panel.diagnostics.toPlainText()
