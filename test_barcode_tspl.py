from types import SimpleNamespace

import pytest
from PIL import Image

from beirut_pos.apps.jewelry.services import barcode_printer
from beirut_pos.apps.jewelry.services.settings import BarcodePrinterSettings
from beirut_pos.apps.jewelry.services.tspl_label import (
    TsplLabel,
    TsplValidationError,
    build_native_tspl,
    validate_native_tspl,
)


def settings(**overrides):
    values = dict(enabled=True, exact_windows_name="RP3xx Series 200DPI TSPL", width_mm=38,
                  height_mm=25, gap_mm=3, dpi=203, density=8, speed=4,
                  command_language="TSPL", native_font="0")
    values.update(overrides)
    return BarcodePrinterSettings(**values)


def test_english_name_keeps_native_tspl_text_path():
    name = "Black Agate Necklace"
    payload = build_native_tspl(TsplLabel(name, "2021100101", "700.00 LE"), settings())
    validate_native_tspl(payload)
    assert name.encode("ascii") in payload
    assert b'BARCODE ' in payload and b'"128"' in payload
    assert b"BITMAP" not in payload


@pytest.mark.parametrize("name", ["عقد عقيق اسود", "عقد عقيق Black Agate", "منتج ١٢٣، تجريبي"])
def test_arabic_name_uses_existing_shaped_bitmap_without_question_marks(name):
    name_row = barcode_printer._render_fitted_center_line(
        name, width=304, max_font_size=22, min_font_size=14, mode="bidi"
    )
    payload = build_native_tspl(
        TsplLabel(name, "2021100101", "700.00 LE"),
        settings(),
        shaped_name_bitmap=name_row,
    )
    validate_native_tspl(payload)
    assert b"BITMAP " in payload
    assert b"????" not in payload
    assert b'BARCODE ' in payload and b'"128"' in payload
    assert b"700.00 LE" in payload


def test_native_tspl_structure_layout_and_different_barcode():
    payload = build_native_tspl(TsplLabel("Ring", "ABC-987654", "700.00 LE"), settings())
    assert payload.startswith(b"SIZE 38 mm,25 mm\r\nGAP 3 mm,0 mm\r\n")
    for command in (b"DIRECTION 1", b"REFERENCE 0,0", b"CODEPAGE 1256", b"CLS", b"TEXT", b"BARCODE", b"PRINT 1,1"):
        assert command in payload
    for zpl in (b"^XA", b"^XZ", b"^FO", b"^FD", b"^BC", b"^BY", b"^CI"):
        assert zpl not in payload


def test_multiple_copies_are_in_one_tspl_job():
    payload = build_native_tspl(TsplLabel("Ring", "2021100101", "700.00 LE", copies=3), settings())
    assert payload.endswith(b"PRINT 1,3\r\n")
    assert payload.count(b"PRINT ") == 1


@pytest.mark.parametrize("label,field", [
    (TsplLabel("", "2021100101", "700.00 LE"), "product_name"),
    (TsplLabel("Ring", "", "700.00 LE"), "barcode"),
    (TsplLabel("Ring", "٢٠٢١", "700.00 LE"), "barcode"),
    (TsplLabel("Ring", "2021100101", ""), "price_text"),
])
def test_invalid_label_data_is_rejected(label, field):
    with pytest.raises(TsplValidationError) as raised:
        build_native_tspl(label, settings())
    assert raised.value.field == field


def test_unsupported_unicode_fails_instead_of_printing_question_marks():
    with pytest.raises(TsplValidationError, match="U\\+1F48D"):
        build_native_tspl(TsplLabel("Ring 💍", "2021100101", "700.00 LE"), settings())


def test_only_tspl_setting_is_accepted():
    with pytest.raises(barcode_printer.BarcodeValidationError, match="native TSPL"):
        barcode_printer.validate_barcode_printer_settings(settings(command_language="ZPL"))
    with pytest.raises(barcode_printer.BarcodeValidationError, match="native TSPL"):
        barcode_printer.validate_barcode_printer_settings(settings(command_language="ESC/POS"))


def test_windows_success_uses_exact_queue_once_and_saves_payload(monkeypatch, tmp_path):
    configured = settings()
    image = Image.new("1", (304, 200), 1)
    image.info.update(beirut_product_name="عقد عقيق اسود", beirut_barcode_value="2021100101",
                      beirut_price_text="700.00 LE", beirut_width_mm=38.0, beirut_height_mm=25.0)
    submitted = []
    monkeypatch.setattr(barcode_printer, "load_gallery_settings", lambda: SimpleNamespace(
        barcode_printer_settings=configured, barcode_horizontal_offset_px=0, barcode_vertical_offset_px=0))
    monkeypatch.setattr(barcode_printer.printer_service, "_IS_WINDOWS", True)
    monkeypatch.setattr(barcode_printer, "get_printer_port", lambda name: "USB001")
    monkeypatch.setattr(barcode_printer, "default_barcode_output_dir", lambda: tmp_path)
    monkeypatch.setattr(barcode_printer, "submit_raw_print_job", lambda name, payload: submitted.append((name, payload)))
    barcode_printer.print_barcode_label_image(image, printer_name=configured.exact_windows_name, copies=2)
    assert len(submitted) == 1
    assert submitted[0][0] == configured.exact_windows_name
    assert submitted[0][1].endswith(b"PRINT 1,2\r\n")
    assert list((tmp_path / "debug").glob("*.tspl"))


def test_printer_unavailable_is_diagnostic_and_does_not_retry(monkeypatch, tmp_path):
    configured = settings()
    image = Image.new("1", (304, 200), 1)
    image.info.update(beirut_product_name="Ring", beirut_barcode_value="2021100101",
                      beirut_price_text="700.00 LE", beirut_width_mm=38.0, beirut_height_mm=25.0)
    monkeypatch.setattr(barcode_printer, "load_gallery_settings", lambda: SimpleNamespace(
        barcode_printer_settings=configured, barcode_horizontal_offset_px=0, barcode_vertical_offset_px=0))
    monkeypatch.setattr(barcode_printer.printer_service, "_IS_WINDOWS", True)
    monkeypatch.setattr(barcode_printer, "default_barcode_output_dir", lambda: tmp_path)
    monkeypatch.setattr(barcode_printer, "get_printer_port", lambda name: "USB001")
    attempts = []
    def unavailable(*args):
        attempts.append(args)
        raise RuntimeError("Configured barcode printer not found")
    monkeypatch.setattr(barcode_printer, "submit_raw_print_job", unavailable)
    monkeypatch.setattr(barcode_printer.error_handling, "log_exception", lambda *a, **k: None)
    with pytest.raises(barcode_printer.BarcodePrintDiagnosticError, match="not found"):
        barcode_printer.print_barcode_label_image(image, printer_name=configured.exact_windows_name)
    assert len(attempts) == 1


def test_windows_raw_transport_uses_raw_datatype_and_full_payload(monkeypatch):
    from beirut_pos.apps.jewelry.services import windows_raw_printer
    calls = []
    class FakeWin32:
        PRINTER_ENUM_LOCAL = 1
        PRINTER_ENUM_CONNECTIONS = 2
        def EnumPrinters(self, flags): return [(None, None, "RP3xx")]
        def OpenPrinter(self, name): calls.append(("open", name)); return "handle"
        def GetPrinter(self, handle, level): return {"Status": 0, "pPortName": "USB001"}
        def StartDocPrinter(self, handle, level, doc): calls.append(("doc", doc)); return 7
        def StartPagePrinter(self, handle): calls.append(("page", handle))
        def WritePrinter(self, handle, payload): calls.append(("write", payload)); return len(payload)
        def EndPagePrinter(self, handle): calls.append(("endpage", handle))
        def EndDocPrinter(self, handle): calls.append(("enddoc", handle))
        def ClosePrinter(self, handle): calls.append(("close", handle))
    fake = FakeWin32()
    monkeypatch.setattr(windows_raw_printer, "_load_win32print", lambda: fake)
    payload = build_native_tspl(TsplLabel("Ring", "2021100101", "700.00 LE"), settings())
    assert windows_raw_printer.get_printer_port("RP3xx") == "USB001"
    windows_raw_printer.submit_raw_print_job("RP3xx", payload)
    assert ("doc", ("Beirut POS Jewelry Barcode", None, "RAW")) in calls
    assert ("write", payload) in calls


def test_windows_raw_transport_rejects_missing_queue(monkeypatch):
    from beirut_pos.apps.jewelry.services import windows_raw_printer
    fake = SimpleNamespace(PRINTER_ENUM_LOCAL=1, PRINTER_ENUM_CONNECTIONS=2, EnumPrinters=lambda flags: [])
    monkeypatch.setattr(windows_raw_printer, "_load_win32print", lambda: fake)
    with pytest.raises(RuntimeError, match="not found"):
        windows_raw_printer.submit_raw_print_job("Missing", b"SIZE 1 mm,1 mm\r\n")
