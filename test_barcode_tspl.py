from types import SimpleNamespace

from PIL import Image

from beirut_pos.apps.jewelry.services import barcode_printer
from beirut_pos.apps.jewelry.services.settings import BarcodePrinterSettings


def test_tspl_bitmap_packs_black_dots_and_pads_rows_white():
    image = Image.new("1", (9, 1), 1)
    image.putpixel((0, 0), 0)
    image.putpixel((8, 0), 0)

    width_bytes, payload = barcode_printer._tspl_bitmap_bytes(image)

    assert width_bytes == 2
    assert payload == b"\x80\x80"


def test_tspl_commands_include_media_setup_bitmap_and_print():
    image = Image.new("1", (9, 2), 1)
    image.putpixel((0, 0), 0)
    settings = BarcodePrinterSettings(
        width_mm=38,
        height_mm=25,
        gap_mm=3,
        density=8,
        speed=4,
        command_language="TSPL",
    )

    commands = barcode_printer.build_tspl_commands(image, settings)

    header, remainder = commands.split(b"BITMAP 0,0,2,2,0,", 1)
    assert header == (
        b"SIZE 38 mm,25 mm\r\n"
        b"GAP 3 mm,0 mm\r\n"
        b"SPEED 4\r\n"
        b"DENSITY 8\r\n"
        b"DIRECTION 1\r\n"
        b"CLS\r\n"
    )
    assert remainder == b"\x80\x00\x00\x00\r\nPRINT 1,1\r\n"
    assert b"^XA" not in commands


def test_windows_dispatch_uses_selected_tspl_language(monkeypatch):
    settings = BarcodePrinterSettings(
        enabled=True,
        exact_windows_name="RP3xx Series 200DPI TSPL",
        command_language="TSPL",
    )
    image = Image.new("1", (303, 200), 1)
    image.info.update(
        beirut_product_name="Ring",
        beirut_barcode_value="2021100101",
        beirut_width_mm=38.0,
        beirut_height_mm=25.0,
    )
    submitted = []
    monkeypatch.setattr(
        barcode_printer,
        "load_gallery_settings",
        lambda: SimpleNamespace(
            barcode_printer_settings=settings,
            barcode_horizontal_offset_px=0,
            barcode_vertical_offset_px=0,
        ),
    )
    monkeypatch.setattr(barcode_printer.printer_service, "_IS_WINDOWS", True)
    monkeypatch.setattr(
        barcode_printer,
        "submit_rp310_raw_commands",
        lambda printer_name, commands, *, copies: submitted.append(
            (printer_name, commands, copies)
        ),
    )

    barcode_printer.print_barcode_label_image(
        image, printer_name=settings.exact_windows_name, copies=1
    )

    assert submitted[0][0] == settings.exact_windows_name
    assert submitted[0][1].startswith(b"SIZE 38 mm,25 mm\r\n")
    assert b"BITMAP 0,0,38,200,0," in submitted[0][1]
    assert submitted[0][1].endswith(b"\r\nPRINT 1,1\r\n")
    assert submitted[0][2] == 1


def test_unsupported_zpl_setting_fails_before_dispatch():
    settings = BarcodePrinterSettings(command_language="ZPL")

    try:
        barcode_printer.validate_barcode_printer_settings(settings)
    except barcode_printer.BarcodeValidationError as error:
        assert error.field == "command_language"
        assert "ESC/POS or TSPL" in str(error)
    else:
        raise AssertionError("ZPL must not silently reach a TSPL printer")
