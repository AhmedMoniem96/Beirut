"""Barcode label rendering/printing helpers for Jewelry app."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Sequence

import importlib.util



from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
import logging
import string

try:
    import arabic_reshaper
except Exception:
    arabic_reshaper = None

try:
    from bidi.algorithm import get_display as bidi_get_display
except Exception:
    bidi_get_display = None


if importlib.util.find_spec("barcode") is None:
    raise RuntimeError("Barcode printing dependency missing")
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
from .settings import load_gallery_settings


_LABEL_DPI = 203
_MM_PER_INCH = 25.4
_QR_LABEL_WIDTH_MM = 38.0
_QR_LABEL_HEIGHT_MM = 25.0


def _mm_to_px(mm: float, dpi: int = _LABEL_DPI) -> int:
    return max(1, int(round((mm / _MM_PER_INCH) * dpi)))


LABEL_WIDTH_PX = _mm_to_px(_QR_LABEL_WIDTH_MM)
LABEL_HEIGHT_PX = _mm_to_px(_QR_LABEL_HEIGHT_MM)
LABEL_MARGIN_PX = 10


def get_label_calibration() -> dict[str, int | float]:
    settings = load_gallery_settings()
    width_mm = max(10.0, float(getattr(settings, "barcode_label_width_mm", _QR_LABEL_WIDTH_MM) or _QR_LABEL_WIDTH_MM))
    height_mm = max(10.0, float(getattr(settings, "barcode_label_height_mm", _QR_LABEL_HEIGHT_MM) or _QR_LABEL_HEIGHT_MM))
    return {
        "width_mm": width_mm,
        "height_mm": height_mm,
        "width_px": _mm_to_px(width_mm),
        "height_px": _mm_to_px(height_mm),
        "offset_x": int(getattr(settings, "barcode_horizontal_offset_px", 0) or 0),
        "offset_y": int(getattr(settings, "barcode_vertical_offset_px", 0) or 0),
    }



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
            barHeight=42,
            barWidth=0.75,
            humanReadable=False,
        )
    if normalized == "code93":
        return createBarcodeDrawing(
            "Code93",
            value=barcode_value,
            barHeight=42,
            barWidth=0.75,
            humanReadable=False,
        )
    if normalized == "qr":
        return _qr_drawing(barcode_value)
    return createBarcodeDrawing(
        "Code128",
        value=barcode_value,
        barHeight=42,
        barWidth=0.75,
        humanReadable=False,
    )




def _coerce_ascii_barcode_value(*candidates: str) -> str:
    allowed = set(string.printable) - {"\x0b", "\x0c", "\r", "\n", "\t"}
    for candidate in candidates:
        raw = (candidate or "").strip()
        if not raw:
            continue
        sanitized = "".join(ch for ch in raw if ch in allowed)
        sanitized = sanitized.encode("ascii", "ignore").decode("ascii").strip()
        if sanitized:
            return sanitized
    return ""


logger = logging.getLogger(__name__)


_ARABIC_LABEL_MODE_ENV = "BEIRUT_POS_LABEL_AR_MODE"
_VALID_ARABIC_MODES = {"raw", "reshape", "bidi"}


def _default_arabic_label_mode() -> str:
    platform_name = platform.system().lower()
    if platform_name.startswith("win"):
        return "reshape"
    return "raw"


def _selected_arabic_label_mode() -> str:
    default_mode = _default_arabic_label_mode()
    requested = (os.environ.get(_ARABIC_LABEL_MODE_ENV) or "").strip().lower()
    if requested in _VALID_ARABIC_MODES:
        return requested
    return default_mode


def _shape_label_text(text: str, *, mode: str) -> str:
    if mode == "reshape":
        if arabic_reshaper is None:
            return text
        return arabic_reshaper.reshape(text)
    if mode == "bidi":
        if arabic_reshaper is None or bidi_get_display is None:
            return text
        return bidi_get_display(arabic_reshaper.reshape(text))
    return text


def _render_code128_bitmap(value: str) -> Image.Image:
    buffer = BytesIO()
    Code128(value, writer=ImageWriter()).write(
        buffer,
        options={
            "module_width": 0.25,
            "module_height": 8.0,
            "quiet_zone": 1.0,
            "font_size": 0,
            "write_text": False,
        },
    )
    buffer.seek(0)
    return Image.open(buffer).convert("1")

def _fit_text_to_width(
    text: str,
    *,
    max_width: int,
    min_font_size: int = 14,
    max_font_size: int = 22,
) -> tuple[str, object]:
    base_text = (text or "").strip() or "-"
    ellipsis = "…"
    for size in range(max_font_size, min_font_size - 1, -1):
        font = _arabic_capable_font(size=size)
        bbox = font.getbbox(base_text)
        if (bbox[2] - bbox[0]) <= max_width:
            return base_text, font

        truncated = base_text
        while truncated:
            candidate = (truncated[:-1].rstrip() + ellipsis) if len(truncated) > 1 else ellipsis
            cb = font.getbbox(candidate)
            if (cb[2] - cb[0]) <= max_width:
                return candidate, font
            truncated = truncated[:-1]

    return ellipsis, _arabic_capable_font(size=min_font_size)


def _arabic_capable_font(size: int) -> ImageFont.ImageFont:
    platform_name = platform.system().lower()
    if platform_name.startswith("win"):
        candidates = [
            Path(r"C:\Windows\Fonts\tahoma.ttf"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path("beirut_pos/assets/fonts/NotoNaskhArabic-Regular.ttf"),
            Path("assets/fonts/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    else:
        candidates = [
            Path("beirut_pos/assets/fonts/NotoNaskhArabic-Regular.ttf"),
            Path("assets/fonts/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path(r"C:\Windows\Fonts\tahoma.ttf"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
        ]
    for path in candidates:
        try:
            if not path.exists():
                continue
            logger.info("barcode.label.font_path", extra={"font_path": str(path)})
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            continue
    raise BarcodeRenderError("No Arabic-capable font found for barcode label rendering")


def render_direct_arabic_experiment_png() -> Path:
    raw = "أقراط لؤلؤ"
    reshaped = arabic_reshaper.reshape(raw)
    bidi_shaped = bidi_get_display(reshaped)

    width = LABEL_WIDTH_PX
    font = _arabic_capable_font(size=18)
    canvas = Image.new("1", (width, LABEL_HEIGHT_PX), 1)
    draw = ImageDraw.Draw(canvas)
    y = 2
    for line in (raw, reshaped, bidi_shaped):
        bbox = font.getbbox(line)
        line_w = max(1, bbox[2] - bbox[0])
        x = max((width - line_w) // 2, LABEL_MARGIN_PX)
        draw.text((x, y - bbox[1]), line, font=font, fill=0)
        y += max(1, (bbox[3] - bbox[1])) + 2

    out_path = Path("tmp_arabic_test.png")
    canvas.save(out_path)
    return out_path


def _render_fitted_center_line(text: str, *, width: int, max_font_size: int, min_font_size: int) -> Image.Image:
    usable_width = max(1, width - (LABEL_MARGIN_PX * 2))
    raw_text = (text or "").strip() or "-"
    fitted_text, font = _fit_text_to_width(
        raw_text,
        max_width=usable_width,
        min_font_size=min_font_size,
        max_font_size=max_font_size,
    )
    bbox = font.getbbox(fitted_text)
    line_w = max(1, bbox[2] - bbox[0])
    line_h = max(1, bbox[3] - bbox[1])
    canvas_h = line_h + 4
    canvas = Image.new("1", (width, canvas_h), 1)
    draw = ImageDraw.Draw(canvas)
    x = max((width - line_w) // 2, LABEL_MARGIN_PX)
    y = 2 - bbox[1]
    platform_name = platform.system().lower()
    selected_mode = _selected_arabic_label_mode()
    shaped_text = _shape_label_text(fitted_text, mode=selected_mode)
    logger.info(
        "barcode.label.text_pipeline",
        extra={
            "platform": platform_name,
            "arabic_label_mode": selected_mode,
            "raw_label_name": fitted_text,
            "shaped_label_name": shaped_text,
            "raw_text_codepoints": [f"U+{ord(ch):04X}" for ch in fitted_text],
            "shaped_text_codepoints": [f"U+{ord(ch):04X}" for ch in shaped_text],
            "arabic_reshaper_available": bool(arabic_reshaper),
            "bidi_available": bool(bidi_get_display),
        },
    )
    draw.text((x, y), shaped_text, font=font, fill=0)
    return canvas


def _center_on_label(img: Image.Image, *, width: int, height: int, pad_y: int = 6) -> Image.Image:
    if img.mode != "1":
        img = img.convert("1")
    canvas = Image.new("1", (width, height), 1)
    x = max((width - img.width) // 2, 0)
    y = max((height - img.height) // 2, pad_y)
    canvas.paste(img, (x, y))
    return canvas


def _fit_barcode_image(
    barcode_img: Image.Image,
    *,
    max_width: int,
    max_height: int,
) -> Image.Image:
    target_w = max(1, int(max_width))
    target_h = max(1, int(max_height))
    scale = min(
        target_w / max(barcode_img.width, 1),
        target_h / max(barcode_img.height, 1),
        1.0,
    )
    if scale >= 1.0:
        return barcode_img
    new_size = (
        max(1, int(barcode_img.width * scale)),
        max(1, int(barcode_img.height * scale)),
    )
    return barcode_img.resize(new_size, Image.NEAREST)


def _render_label_lines_at_width(lines: Sequence[str], width: int = LABEL_WIDTH_PX) -> tuple[Image.Image, str]:
    """Render compact centered lines for narrow barcode labels."""
    width = max(1, int(width))

    rows = []
    for idx, raw in enumerate(lines):
        txt = raw[4:] if raw.startswith((">>C ", ">>R ", ">>L ")) else raw
        max_font = 18 if idx == 0 else 16
        min_font = 10 if idx == 0 else 9
        rows.append(_render_fitted_center_line(txt, width=width, max_font_size=max_font, min_font_size=min_font))

    total_h = sum(im.height for im in rows) or 1
    canvas = Image.new("1", (width, total_h), 1)
    y = 0
    for im in rows:
        canvas.paste(im, (0, y))
        y += im.height
    return canvas, "fitted_center_text"


def render_barcode_label_image(
    *,
    product_name: str,
    sku: str,
    barcode_value: str,
    barcode_type: str,
) -> Image.Image:
    calib = get_label_calibration()
    label_width_px = int(calib["width_px"])
    label_height_px = int(calib["height_px"])
    offset_x = int(calib["offset_x"])
    offset_y = int(calib["offset_y"])
    title = product_name.strip() or "Item"
    raw_sku = (sku or "").strip()
    encoded_value = _coerce_ascii_barcode_value(barcode_value, raw_sku)
    if not encoded_value:
        encoded_value = "UNKNOWN"
    sku_line = encoded_value
    normalized_type = "code128"
    type_label = "Code128"
    header_img, header_renderer = _render_label_lines_at_width([">>C " + title, ">>C " + sku_line], label_width_px)
    header_width_px = header_img.width
    header_height_px = header_img.height

    barcode_renderer = "python_barcode_code128"
    try:
        barcode_img = _render_code128_bitmap(encoded_value)
    except Exception as exc:
        logger.exception("Failed to generate barcode image", extra={"barcode_value": encoded_value})
        raise BarcodeRenderError(f"Failed to generate barcode image: {exc}") from exc
    barcode_width_px = barcode_img.width
    barcode_height_px = barcode_img.height

    if header_img.width > label_width_px:
        scale = label_width_px / max(header_img.width, 1)
        header_img = header_img.resize(
            (max(1, int(header_img.width * scale)), max(1, int(header_img.height * scale))),
            Image.NEAREST,
        )

    label = Image.new("1", (label_width_px, label_height_px), 1)
    barcode_w_target = max(1, label_width_px - (LABEL_MARGIN_PX * 2))
    barcode_h_target = max(1, label_height_px - (LABEL_MARGIN_PX * 2))
    if barcode_width_px > barcode_w_target or barcode_height_px > barcode_h_target:
        printer_service._log_struct(
            "barcode.label.compose.oversize_component",
            component="barcode",
            label_width_px=LABEL_WIDTH_PX,
            label_height_px=LABEL_HEIGHT_PX,
            header_width_px=header_width_px,
            header_height_px=header_height_px,
            barcode_width_px=barcode_width_px,
            barcode_height_px=barcode_height_px,
            max_component_width_px=barcode_w_target,
            max_component_height_px=barcode_h_target,
        )
    barcode_img = _fit_barcode_image(
        barcode_img,
        max_width=barcode_w_target,
        max_height=barcode_h_target,
    )
    if header_width_px > label_width_px:
        printer_service._log_struct(
            "barcode.label.compose.oversize_component",
            component="header",
            label_width_px=LABEL_WIDTH_PX,
            label_height_px=LABEL_HEIGHT_PX,
            header_width_px=header_width_px,
            header_height_px=header_height_px,
            barcode_width_px=barcode_width_px,
            barcode_height_px=barcode_height_px,
            max_component_width_px=label_width_px,
            max_component_height_px=label_height_px,
        )
    gap_px = 3
    content_h = header_img.height + gap_px + barcode_img.height

    if content_h > label_height_px:
        available_for_barcode_h = max(1, label_height_px - header_img.height - gap_px)
        barcode_img = _fit_barcode_image(
            barcode_img,
            max_width=barcode_w_target,
            max_height=available_for_barcode_h,
        )
        content_h = header_img.height + gap_px + barcode_img.height

    if content_h > label_height_px:
        available_for_header_h = max(1, label_height_px - barcode_img.height - gap_px)
        if header_img.height > available_for_header_h:
            scale = available_for_header_h / max(header_img.height, 1)
            header_img = header_img.resize(
                (max(1, int(header_img.width * scale)), max(1, int(header_img.height * scale))),
                Image.NEAREST,
            )
            content_h = header_img.height + gap_px + barcode_img.height

    top_y = max(1, (label_height_px - content_h) // 2)
    header_x = max(0, (label_width_px - header_img.width) // 2) + offset_x
    barcode_x = max(0, (label_width_px - barcode_img.width) // 2) + offset_x
    barcode_y = top_y + header_img.height + gap_px + offset_y
    if barcode_y + barcode_img.height > label_height_px:
        barcode_y = max(top_y + header_img.height, label_height_px - barcode_img.height)

    label.paste(header_img, (header_x, top_y))
    label.paste(barcode_img, (barcode_x, barcode_y))
    printer_service._log_struct(
        "barcode.label.compose.metrics",
        label_width_px=LABEL_WIDTH_PX,
        label_height_px=LABEL_HEIGHT_PX,
        text_width_px=header_img.width,
        text_height_px=header_img.height,
        barcode_width_px=barcode_img.width,
        barcode_height_px=barcode_img.height,
        final_content_height_px=content_h,
        content_top_y_px=top_y,
        barcode_y_px=barcode_y,
        final_canvas_width_px=label.width,
        final_canvas_height_px=label.height,
        header_renderer=header_renderer,
        barcode_renderer=barcode_renderer,
        compose_renderer="label_fixed_canvas",
        barcode_value=encoded_value,
        barcode_type=type_label,
    )
    return label




class BarcodeRenderError(RuntimeError):
    """Raised when barcode image rendering fails."""


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



def render_label_bitmap(lines: Sequence[str]) -> Image.Image:
    """Render narrow label text bitmap on a fixed 38x25mm canvas."""
    calib = get_label_calibration()
    width_px = int(calib["width_px"])
    height_px = int(calib["height_px"])
    label_text_img, renderer = _render_label_lines_at_width(lines, width_px)
    label_canvas = _center_on_label(label_text_img, width=width_px, height=height_px, pad_y=2)
    printer_service._log_struct(
        "printer.render.selected",
        printer_mode="label",
        renderer="render_label_bitmap",
        text_renderer=renderer,
        canvas_width_px=LABEL_WIDTH_PX,
        canvas_height_px=LABEL_HEIGHT_PX,
        bitmap_width_px=label_canvas.width,
        bitmap_height_px=label_canvas.height,
    )
    return label_canvas


def render_test_label_image() -> Image.Image:
    calib = get_label_calibration()
    width_px = int(calib["width_px"])
    height_px = int(calib["height_px"])
    offset_x = int(calib["offset_x"])
    offset_y = int(calib["offset_y"])
    img = Image.new("1", (width_px, height_px), 1)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width_px - 1, height_px - 1), outline=0, width=1)
    cx = max(0, min(width_px - 1, (width_px // 2) + offset_x))
    cy = max(0, min(height_px - 1, (height_px // 2) + offset_y))
    draw.line((max(0, cx - 12), cy, min(width_px - 1, cx + 12), cy), fill=0, width=1)
    draw.line((cx, max(0, cy - 12), cx, min(height_px - 1, cy + 12)), fill=0, width=1)
    sku_line = _render_fitted_center_line("SKU: TEST-123", width=width_px, max_font_size=14, min_font_size=10)
    img.paste(sku_line, (0, 3))
    sample = render_barcode_label_image(
        product_name="Sample",
        sku="TEST-123",
        barcode_value="TEST-123",
        barcode_type="qr",
    )
    sample_cropped = sample.crop((0, max(0, sample.height // 3), sample.width, sample.height))
    qr_x = max(0, min(width_px - sample_cropped.width, (width_px - sample_cropped.width) // 2 + offset_x))
    qr_y = max(10, min(height_px - sample_cropped.height, height_px - sample_cropped.height - 2 + offset_y))
    img.paste(sample_cropped, (qr_x, qr_y))
    return img


def print_test_label(*, printer_name: str) -> None:
    print_barcode_label_image(render_test_label_image(), printer_name=printer_name)


def print_barcode_label(
    *,
    product_name: str,
    sku: str,
    barcode_value: str,
    barcode_type: str,
    printer_name: str,
) -> None:
    """Public barcode/QR label printing entrypoint (label-only pipeline)."""
    img = render_barcode_label_image(
        product_name=product_name,
        sku=sku,
        barcode_value=barcode_value,
        barcode_type=barcode_type,
    )
    printer_service._log_struct(
        "printer.mode.active",
        printer_mode="label",
        renderer="render_label_bitmap",
        canvas_width_px=LABEL_WIDTH_PX,
        canvas_height_px=LABEL_HEIGHT_PX,
        bitmap_width_px=img.width,
        bitmap_height_px=img.height,
        printer_name=printer_name,
    )
    print_barcode_label_image(img, printer_name=printer_name)


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
