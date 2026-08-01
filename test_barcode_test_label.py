from datetime import datetime, timezone
from types import SimpleNamespace

from beirut_pos.apps.jewelry.services import barcode_printer
from beirut_pos.apps.jewelry.services.settings import BarcodePrinterSettings


def test_test_label_data_has_operational_values_without_product(monkeypatch):
    configured = BarcodePrinterSettings(
        model="Rongta RP310",
        exact_windows_name="Jewelry Labels",
        default_copies=2,
    )
    monkeypatch.setattr(
        barcode_printer,
        "load_gallery_settings",
        lambda: SimpleNamespace(barcode_printer_settings=configured),
    )
    generated_at = datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc)

    data = barcode_printer.create_test_barcode_label_data(generated_at=generated_at)

    assert data.product_name is None
    assert data.model_name == "Rongta RP310"
    assert data.printer_queue == "Jewelry Labels"
    assert data.generated_at == generated_at
    assert data.barcode_value == barcode_printer.TEST_BARCODE_VALUE == "123456789012"
    assert data.copies == 2


def test_test_and_product_labels_share_label_data_orchestration(monkeypatch):
    test_data = barcode_printer.BarcodeLabelData(None, "123456789012")
    product_data = barcode_printer.BarcodeLabelData("Ring", "RING-1")
    calls = []
    monkeypatch.setattr(barcode_printer, "create_test_barcode_label_data", lambda **_: test_data)
    monkeypatch.setattr(barcode_printer, "prepare_barcode_label_data", lambda **_: product_data)
    monkeypatch.setattr(
        barcode_printer,
        "print_barcode_label_data",
        lambda data, **kwargs: calls.append((data, kwargs)),
    )

    barcode_printer.print_test_label(printer_name="Jewelry Labels")
    barcode_printer.print_barcode_label(
        product_name="Ring",
        sku="RING-1",
        barcode_value="RING-1",
        barcode_type="code128",
        printer_name="Jewelry Labels",
    )

    assert calls[0] == (test_data, {"printer_name": "Jewelry Labels", "test": True})
    assert calls[1] == (
        product_data,
        {"printer_name": "Jewelry Labels", "sku": "RING-1", "barcode_type": "code128"},
    )


def test_test_renderer_includes_operational_header(monkeypatch):
    captured = {}
    data = barcode_printer.BarcodeLabelData(
        None,
        "123456789012",
        model_name="Rongta RP310",
        printer_queue="Jewelry Labels",
        generated_at=datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc),
    )
    sentinel = object()

    def fake_render(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(barcode_printer, "render_barcode_label_image", fake_render)

    assert barcode_printer.render_test_label_image(data) is sentinel
    assert captured["header_lines"] == (
        "Rongta RP310",
        "Jewelry Labels",
        "2026-08-01 12:30:00+00:00",
        "123456789012",
    )
    assert captured["print_stage"] == "Test RP310"
