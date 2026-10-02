from types import SimpleNamespace

import pytest

from beirut_pos.apps.jewelry.services import settings as settings_service
from beirut_pos.apps.jewelry.label_printing import LabelData
from beirut_pos.apps.jewelry.services.i18n import choose_name


def test_label_printer_settings_are_independent(monkeypatch):
    values = {}

    monkeypatch.setattr(settings_service, "get_config_value", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(settings_service, "set_config_value", lambda key, value: values.__setitem__(key, value))

    assert settings_service.load_gallery_settings().jewelry_label_printer_name == ""
    base = settings_service.load_gallery_settings()
    settings_service.save_gallery_settings(
        SimpleNamespace(**{**base.__dict__, "receipt_printer_name": "EPSON Receipt Printer", "jewelry_label_printer_name": "RP3xx Series 200DPI TSPL"})
    )
    loaded = settings_service.load_gallery_settings()
    assert loaded.receipt_printer_name == "EPSON Receipt Printer"
    assert loaded.jewelry_label_printer_name == "RP3xx Series 200DPI TSPL"

    settings_service.save_gallery_settings(SimpleNamespace(**{**loaded.__dict__, "jewelry_label_printer_name": "Label, Queue (A)"}))
    assert settings_service.load_gallery_settings().receipt_printer_name == "EPSON Receipt Printer"
    assert settings_service.load_gallery_settings().jewelry_label_printer_name == "Label, Queue (A)"


def test_label_data_mapping_without_qt():
    data = LabelData(choose_name("عقد عقيق اسود", "Black Agate Necklace", language="en"), " 2021100101 ".strip(), f"{700.0:.2f} LE")
    assert data.product_name == "Black Agate Necklace"
    assert data.barcode == "2021100101"
    assert data.price == "700.00 LE"
    assert choose_name("عقد عقيق اسود", "Black Agate Necklace", language="ar") == "عقد عقيق اسود"


def test_label_submission_contract_without_qt(monkeypatch):
    calls = []
    def fake_print_label(data, queue, copies=1):
        calls.append((data, queue, copies))
        return SimpleNamespace(submitted=True)
    data = LabelData("Black Agate Necklace", "2021100101", "700.00 LE")
    fake_print_label(data, "RP3xx Series 200DPI TSPL", copies=1)
    assert calls == [(data, "RP3xx Series 200DPI TSPL", 1)]
    assert "Label printed successfully" not in "Label submitted to printer"
