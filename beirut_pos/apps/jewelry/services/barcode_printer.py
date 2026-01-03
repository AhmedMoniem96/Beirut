"""Barcode label rendering/printing helpers for Jewelry app."""

from __future__ import annotations

from typing import Sequence

from PIL import Image
from reportlab.graphics import renderPM
from reportlab.graphics.barcode import createBarcodeDrawing

from beirut_pos.services import printer as printer_service
from beirut_pos.services.arabic_bitmap import pil_image_to_escpos_raster


_LABEL_WIDTH_PX = printer_service.PAPER_PX


def _center_on_label(img: Image.Image, *, width: int, pad_y: int = 6) -> Image.Image:
    if img.mode != "1":
        img = img.convert("1")
    canvas = Image.new("1", (width, img.height + pad_y * 2), 1)
    x = max((width - img.width) // 2, 0)
    canvas.paste(img, (x, pad_y))
    return canvas


def _render_label_lines(lines: Sequence[str]) -> Image.Image:
    return printer_service._render_lines_to_bitmap(list(lines))


def render_barcode_label_image(
    *,
    product_name: str,
    sku: str,
    barcode_value: str,
    barcode_type: str,
) -> Image.Image:
    title = product_name.strip() or "Item"
    sku_line = f"SKU: {sku}".strip()
    type_label = barcode_type.strip() or "Barcode"
    barcode_line = f"{type_label}: {barcode_value}".strip()

    header_img = _render_label_lines([">>C " + title, ">>L " + sku_line, ">>L " + barcode_line])

    try:
        barcode_drawing = createBarcodeDrawing(
            "Code128",
            value=barcode_value,
            barHeight=70,
            barWidth=1.2,
            humanReadable=False,
        )
        barcode_img = renderPM.drawToPIL(barcode_drawing).convert("1")
    except Exception:
        barcode_img = printer_service._render_lines_to_bitmap([">>C [BARCODE]"])

    if barcode_img.width > _LABEL_WIDTH_PX - 24:
        scale = (_LABEL_WIDTH_PX - 24) / barcode_img.width
        new_size = (int(barcode_img.width * scale), int(barcode_img.height * scale))
        barcode_img = barcode_img.resize(new_size, Image.NEAREST)

    barcode_block = _center_on_label(barcode_img, width=_LABEL_WIDTH_PX, pad_y=8)
    return printer_service._stack_bitmaps([header_img, barcode_block])


def print_barcode_label_image(
    img: Image.Image,
    *,
    printer_name: str,
) -> None:
    if printer_name and printer_name != "auto" and printer_service._IS_WINDOWS:
        printer_service.win_print_image(printer_name, img.convert("RGB"))
        return

    escpos_printer = printer_service._find_thermal_printer()
    if not escpos_printer:
        raise RuntimeError("No ESC/POS printer detected.")

    raster = pil_image_to_escpos_raster(img)
    if hasattr(escpos_printer, "_raw"):
        escpos_printer._raw(raster)
    elif hasattr(escpos_printer, "image"):
        escpos_printer.image(img)
    printer_service._post_feed_and_cut(escpos_printer)
