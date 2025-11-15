# beirut_pos/services/printer_windows.py
from __future__ import annotations
import os
from typing import List, Iterable, Tuple

import win32print, win32ui, win32con
from PIL import Image, ImageDraw, ImageFont, ImageWin

# Optional Arabic shaping
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    _AR_OK = True
except Exception:
    _AR_OK = False


# ---------- Public API ----------

def list_printers() -> List[str]:
    """Return installed printer display names (Windows)."""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags)
    return [p[2] for p in printers if len(p) > 2]


def print_text(
    printer_name: str,
    text: str,
    encoding: str = "cp1256",
    font_path: str | None = None,
    font_size: int = 28,
    paper_px: int = 576,
    line_pad: int = 8,
) -> None:
    """
    Render text (Arabic + English) to a raster image and print via GDI.
    Alignment tags supported at line start:
      '>>R ' right, '>>C ' center, '>>L ' left (default).
    """
    lines = text.splitlines()
    img = _text_to_image(
        lines,
        font_path=font_path,
        font_size=font_size,
        paper_px=paper_px,
        line_pad=line_pad,
    )
    _print_image(printer_name, img)


def print_image(printer_name: str, pil_image: Image.Image, paper_px: int = 576) -> None:
    """
    Print a PIL image via GDI. Image is scaled to printable width.
    """
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    _print_image(printer_name, pil_image, force_width=True)


# ---------- Helpers ----------

def _choose_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Try a font that supports Arabic. Fallback to common paths, then default.
    """
    candidates: list[str] = []
    if font_path:
        candidates.append(font_path)

    candidates += [
        os.path.join(os.getcwd(), "beirut_pos", "assets", "fonts", "NotoNaskhArabic-Regular.ttf"),
        os.path.join(os.getcwd(), "assets", "fonts", "NotoNaskhArabic-Regular.ttf"),
        os.path.join(os.getcwd(), "beirut_pos", "assets", "fonts", "Amiri-Regular.ttf"),
        os.path.join(os.getcwd(), "assets", "fonts", "Amiri-Regular.ttf"),
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Tahoma.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]

    for p in candidates:
        try:
            if p and os.path.exists(p):
                return ImageFont.truetype(p, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def _shape_arabic(line: str) -> str:
    if not _AR_OK:
        return line
    try:
        shaped = arabic_reshaper.reshape(line)
        return get_display(shaped)
    except Exception:
        return line


def _text_to_image(
    lines: Iterable[str],
    *,
    font_path: str | None,
    font_size: int,
    paper_px: int,
    line_pad: int,
) -> Image.Image:
    """
    Build a single tall image with all lines.
    """
    font = _choose_font(font_path, font_size)
    meas_img = Image.new("L", (1, 1), 255)
    dr = ImageDraw.Draw(meas_img)

    line_boxes: list[Tuple[str, str, Tuple[int, int]]] = []
    total_h = 0

    for raw in lines:
        align = "left"
        text = raw
        if raw.startswith(">>R "):
            align, text = "right", raw[4:]
        elif raw.startswith(">>C "):
            align, text = "center", raw[4:]
        elif raw.startswith(">>L "):
            align, text = "left", raw[4:]

        shaped = _shape_arabic(text)
        x0, y0, x1, y1 = dr.textbbox((0, 0), shaped, font=font)
        w = x1 - x0
        h = y1 - y0
        line_boxes.append((align, shaped, (w, h)))
        total_h += h + line_pad

    total_h = max(total_h + 8, font_size + 16)
    canvas = Image.new("RGB", (paper_px, total_h), "white")
    dr = ImageDraw.Draw(canvas)

    y = 4
    for align, shaped, (w, h) in line_boxes:
        if align == "center":
            x = (paper_px - w) // 2
        elif align == "right":
            x = paper_px - w - 8
        else:
            x = 8
        dr.text((x, y), shaped, fill=(0, 0, 0), font=font)
        y += h + line_pad

    return canvas


def _print_image(printer_name: str, img: Image.Image, force_width: bool = True) -> None:
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    try:
        hdc.StartDoc("Beirut POS")
        hdc.StartPage()

        HORZRES = hdc.GetDeviceCaps(win32con.HORZRES)
        VERTRES = hdc.GetDeviceCaps(win32con.VERTRES)

        if force_width:
            w = HORZRES
            h = int(img.height * (float(w) / float(img.width)))
        else:
            w, h = img.size

        dib = ImageWin.Dib(img)
        dib.draw(hdc.GetHandleOutput(), (0, 0, w, h))

        hdc.EndPage()
        hdc.EndDoc()
    finally:
        hdc.DeleteDC()
