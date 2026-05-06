"""Barcode label rendering/printing helpers for Jewelry app."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import importlib.util

from PIL import Image

if importlib.util.find_spec("reportlab") is None:
    raise RuntimeError("Barcode printing dependency missing")
if importlib.util.find_spec("reportlab.graphics") is None:
    raise RuntimeError("Barcode printing dependency missing")
if importlib.util.find_spec("reportlab.graphics.barcode") is None:
    raise RuntimeError("Barcode printing dependency missing")
if importlib.util.find_spec("reportlab.graphics.shapes") is None:
    raise RuntimeError("Barcode printing dependency missing")

from reportlab.graphics import renderPM
from reportlab.graphics.barcode import createBarcodeDrawing, qr
from reportlab.graphics.shapes import Drawing

from beirut_pos.services import printer as printer_service
from beirut_pos.services.arabic_bitmap import pil_image_to_escpos_raster


_LABEL_DPI = 203
_MM_PER_INCH = 25.4
_QR_LABEL_WIDTH_MM = 38.0
_QR_LABEL_HEIGHT_MM = 25.0


def _mm_to_px(mm: float, dpi: int = _LABEL_DPI) -> int:
    return max(1, int(round((mm / _MM_PER_INCH) * dpi)))


LABEL_WIDTH_PX = _mm_to_px(_QR_LABEL_WIDTH_MM)
LABEL_HEIGHT_PX = _mm_to_px(_QR_LABEL_HEIGHT_MM)
LABEL_MARGIN_PX = 8



def default_barcode_output_dir() -> Path:
    base_dir = Path.home() / ".beirut_pos" / "data"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata) / "BeirutPOS"
    output_dir = base_dir / "barcodes"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def suggest_barcode_pdf_path(sku: str) -> Path:
    safe_sku = (sku or "item").strip().replace("/", "-").replace("\\", "-")
    safe_sku = safe_sku or "item"
    return default_barcode_output_dir() / f"{safe_sku}_barcode_labels.pdf"


_SUPPORTED_BARCODE_TYPES = {
    "code128": "Code128",
    "code39": "Code39",
    "code93": "Code93",
    "qr": "QR",
}


def _normalize_barcode_type(barcode_type: str) -> str:
    normalized = barcode_type.strip().lower()
    normalized = normalized.replace(" ", "").replace("-", "")
    if normalized == "qrcode":
        normalized = "qr"
    return normalized


def _qr_drawing(value: str, size: int = 120) -> Drawing:
    widget = qr.QrCodeWidget(value)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    return drawing


def _barcode_drawing(barcode_value: str, barcode_type: str) -> Drawing:
    normalized = _normalize_barcode_type(barcode_type)
    if normalized == "code39":
        return createBarcodeDrawing(
            "Code39",
            value=barcode_value,
            barHeight=70,
            barWidth=1.2,
            humanReadable=False,
        )
    if normalized == "code93":
        return createBarcodeDrawing(
            "Code93",
            value=barcode_value,
            barHeight=70,
            barWidth=1.2,
            humanReadable=False,
        )
    if normalized == "qr":
        return _qr_drawing(barcode_value)
    return createBarcodeDrawing(
        "Code128",
        value=barcode_value,
        barHeight=70,
        barWidth=1.2,
        humanReadable=False,
    )


def _center_on_label(img: Image.Image, *, width: int, height: int, pad_y: int = 6) -> Image.Image:
    if img.mode != "1":
        img = img.convert("1")
    canvas = Image.new("1", (width, height), 1)
    x = max((width - img.width) // 2, 0)
    y = max((height - img.height) // 2, pad_y)
    canvas.paste(img, (x, y))
    return canvas


def _render_label_lines_at_width(lines: Sequence[str], width: int = LABEL_WIDTH_PX) -> tuple[Image.Image, str]:
    """Render tagged label lines (>>C/>>R/>>L) at label width, not receipt width."""
    width = max(1, int(width))

    if getattr(printer_service, "_BITMAP_OK", False):
        rows = []
        font = printer_service.load_font(size=28)
        for raw in lines:
            align, txt = "left", raw
            if raw.startswith(">>C "):
                align, txt = "center", raw[4:]
            elif raw.startswith(">>R "):
                align, txt = "right", raw[4:]
            elif raw.startswith(">>L "):
                align, txt = "left", raw[4:]

            shaped = printer_service._shape_for_bitmap(txt)
            rows.append(
                printer_service.render_line_bitmap(
                    shaped,
                    paper_px=width,
                    font=font,
                    align=align,
                )
            )

        total_h = sum(im.height for im in rows) or 1
        canvas = Image.new("1", (width, total_h), 1)
        y = 0
        for im in rows:
            canvas.paste(im, (0, y))
            y += im.height
        return canvas, "render_line_bitmap"

    return printer_service._render_lines_bitmap_fallback(lines, width=width), "fallback_bitmap"


def render_barcode_label_image(
    *,
    product_name: str,
    sku: str,
    barcode_value: str,
    barcode_type: str,
) -> Image.Image:
    title = product_name.strip() or "Item"
    sku_line = f"SKU: {sku}".strip()
    normalized_type = _normalize_barcode_type(barcode_type)
    type_label = _SUPPORTED_BARCODE_TYPES.get(normalized_type, barcode_type.strip() or "Barcode")
    barcode_line = f"{type_label}: {barcode_value}".strip()

    header_img, header_renderer = _render_label_lines_at_width([">>C " + title, ">>C " + sku_line, ">>C " + barcode_line], LABEL_WIDTH_PX)
    header_width_px = header_img.width
    header_height_px = header_img.height

    barcode_renderer = "reportlab"
    try:
        barcode_drawing = _barcode_drawing(barcode_value, barcode_type)
        barcode_img = renderPM.drawToPIL(barcode_drawing).convert("1")
    except Exception:
        barcode_renderer = "printer_service._render_lines_to_bitmap"
        barcode_img = printer_service._render_lines_to_bitmap([">>C [BARCODE]"])
    barcode_width_px = barcode_img.width
    barcode_height_px = barcode_img.height

    if header_img.width > LABEL_WIDTH_PX:
        header_img, header_renderer = _render_label_lines_at_width([">>C " + title, ">>C " + sku_line, ">>C " + barcode_line], LABEL_WIDTH_PX)
        if header_img.width > LABEL_WIDTH_PX:
            scale = LABEL_WIDTH_PX / max(header_img.width, 1)
            header_img = header_img.resize(
                (max(1, int(header_img.width * scale)), max(1, int(header_img.height * scale))),
                Image.NEAREST,
            )

    max_inner_w = LABEL_WIDTH_PX - (LABEL_MARGIN_PX * 2)
    max_inner_h = LABEL_HEIGHT_PX - (LABEL_MARGIN_PX * 2)
    if barcode_width_px > max_inner_w or barcode_height_px > max_inner_h:
        printer_service._log_struct(
            "barcode.label.compose.oversize_component",
            component="barcode",
            label_width_px=LABEL_WIDTH_PX,
            label_height_px=LABEL_HEIGHT_PX,
            header_width_px=header_width_px,
            header_height_px=header_height_px,
            barcode_width_px=barcode_width_px,
            barcode_height_px=barcode_height_px,
            max_component_width_px=max_inner_w,
            max_component_height_px=max_inner_h,
        )
    scale = min(max_inner_w / max(barcode_img.width, 1), max_inner_h / max(barcode_img.height, 1), 1.0)
    if scale < 1.0:
        new_size = (max(1, int(barcode_img.width * scale)), max(1, int(barcode_img.height * scale)))
        barcode_img = barcode_img.resize(new_size, Image.NEAREST)
    label = Image.new("1", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 1)
    header_h_target = min(int(LABEL_HEIGHT_PX * 0.4), max(32, LABEL_HEIGHT_PX - 70))
    if header_width_px > LABEL_WIDTH_PX or header_height_px > header_h_target:
        printer_service._log_struct(
            "barcode.label.compose.oversize_component",
            component="header",
            label_width_px=LABEL_WIDTH_PX,
            label_height_px=LABEL_HEIGHT_PX,
            header_width_px=header_width_px,
            header_height_px=header_height_px,
            barcode_width_px=barcode_width_px,
            barcode_height_px=barcode_height_px,
            max_component_width_px=LABEL_WIDTH_PX,
            max_component_height_px=header_h_target,
        )
    header_img = _center_on_label(header_img, width=LABEL_WIDTH_PX, height=header_h_target, pad_y=2)
    qr_h_target = LABEL_HEIGHT_PX - header_h_target
    barcode_block = _center_on_label(barcode_img, width=LABEL_WIDTH_PX, height=qr_h_target, pad_y=2)
    composed = Image.new("1", (LABEL_WIDTH_PX, header_img.height + barcode_block.height), 1)
    composed.paste(header_img, (0, 0))
    composed.paste(barcode_block, (0, header_img.height))
    label.paste(composed.crop((0, 0, LABEL_WIDTH_PX, min(composed.height, LABEL_HEIGHT_PX))), (0, 0))
    printer_service._log_struct(
        "barcode.label.compose.metrics",
        label_width_px=LABEL_WIDTH_PX,
        label_height_px=LABEL_HEIGHT_PX,
        header_width_px=header_width_px,
        header_height_px=header_height_px,
        barcode_width_px=barcode_width_px,
        barcode_height_px=barcode_height_px,
        composed_width_px=composed.width,
        composed_height_px=composed.height,
        final_canvas_width_px=label.width,
        final_canvas_height_px=label.height,
        header_renderer=header_renderer,
        barcode_renderer=barcode_renderer,
        compose_renderer="label_fixed_canvas",
    )
    return label




class BarcodePrinterError(RuntimeError):
    """Structured barcode printer error to help UI display actionable messages."""

    def __init__(self, message: str, *, code: str = "unknown") -> None:
        super().__init__(message)
        self.code = code


def _map_print_error(exc: BaseException) -> BarcodePrinterError:
    msg = str(exc)
    lowered = msg.lower()
    if "not found" in lowered or "no windows default printer" in lowered or "no esc/pos printer" in lowered:
        return BarcodePrinterError("Printer not found. Verify printer name or connect a printer.", code="printer_not_found")
    if "access is denied" in lowered or "permission" in lowered or "denied" in lowered:
        return BarcodePrinterError("Printer access denied. Check OS printer permissions.", code="access_denied")
    return BarcodePrinterError(f"Barcode printing failed: {msg}", code="unknown")


def try_print_barcode_label_image(img: Image.Image, *, printer_name: str, retries: int = 1) -> None:
    attempts = max(retries, 0) + 1
    last_error: BarcodePrinterError | None = None
    for _ in range(attempts):
        try:
            print_barcode_label_image(img, printer_name=printer_name)
            return
        except RuntimeError as exc:
            last_error = _map_print_error(exc)
    if last_error is not None:
        raise last_error


def print_barcode_label_image(
    img: Image.Image,
    *,
    printer_name: str,
) -> None:
    try:
        escpos_first_auto = os.environ.get("BEIRUT_POS_WINDOWS_AUTO_ESCPOS_FIRST", "1") == "1"
        if printer_name and printer_name != "auto" and printer_service._IS_WINDOWS:
            printer_service._log_struct(
                "barcode.label.print.payload",
                label_width_px=LABEL_WIDTH_PX,
                label_height_px=LABEL_HEIGHT_PX,
                header_width_px=0,
                header_height_px=0,
                barcode_width_px=0,
                barcode_height_px=0,
                composed_width_px=img.width,
                composed_height_px=img.height,
                final_canvas_width_px=img.width,
                final_canvas_height_px=img.height,
            )
            printer_service.win_print_image(printer_name, img.convert("RGB"))
            printer_service._log_struct(
                "barcode.print.selected",
                backend="windows-gdi",
                printer_name=printer_name,
                mode="explicit_printer",
            )
            return

        should_try_escpos = not printer_service._IS_WINDOWS or printer_name != "auto" or escpos_first_auto
        if should_try_escpos:
            escpos_printer = printer_service._find_thermal_printer()
            if escpos_printer:
                raster = pil_image_to_escpos_raster(img)
                printer_service._log_struct(
                    "barcode.label.print.payload",
                    label_width_px=LABEL_WIDTH_PX,
                    label_height_px=LABEL_HEIGHT_PX,
                    header_width_px=0,
                    header_height_px=0,
                    barcode_width_px=0,
                    barcode_height_px=0,
                    composed_width_px=img.width,
                    composed_height_px=img.height,
                    final_canvas_width_px=img.width,
                    final_canvas_height_px=img.height,
                    raster_bytes_len=len(raster),
                )
                if hasattr(escpos_printer, "_raw"):
                    escpos_printer._raw(raster)
                elif hasattr(escpos_printer, "image"):
                    escpos_printer.image(img)
                printer_service._post_feed_and_cut(escpos_printer)
                printer_service._log_struct(
                    "barcode.print.selected",
                    backend="escpos",
                    printer_name=printer_name,
                    mode="auto" if printer_name == "auto" else "fallback",
                )
                return
            printer_service._log_struct(
                "barcode.print.backend_failed",
                backend="escpos",
                reason="no_escpos_printer_detected",
                printer_name=printer_name,
                mode="auto" if printer_name == "auto" else "regular",
            )

        if printer_service._IS_WINDOWS and printer_name == "auto":
            default_printer = None
            try:
                import win32print  # type: ignore

                default_printer = win32print.GetDefaultPrinter()
            except Exception:
                pass
            if not default_printer:
                known = printer_service.win_list_printers()
                default_printer = known[0] if known else None
            if not default_printer:
                raise RuntimeError("No Windows default printer detected.")
            printer_service._log_struct(
                "barcode.label.print.payload",
                label_width_px=LABEL_WIDTH_PX,
                label_height_px=LABEL_HEIGHT_PX,
                header_width_px=0,
                header_height_px=0,
                barcode_width_px=0,
                barcode_height_px=0,
                composed_width_px=img.width,
                composed_height_px=img.height,
                final_canvas_width_px=img.width,
                final_canvas_height_px=img.height,
            )
            printer_service.win_print_image(default_printer, img.convert("RGB"))
            printer_service._log_struct(
                "barcode.print.selected",
                backend="windows-gdi",
                printer_name=default_printer,
                mode="auto_default_fallback",
            )
            return

        raise RuntimeError("No ESC/POS printer detected.")
    except BaseException as exc:
        printer_service._log_struct(
            "barcode.print.failed",
            backend="unknown",
            printer_name=printer_name,
            error=str(exc),
        )
        raise RuntimeError(f"Barcode printing failed: {exc}") from exc
