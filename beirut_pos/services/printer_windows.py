# beirut_pos/services/printer_windows.py
from __future__ import annotations
import os
import platform

# Hard dependency only on Windows
_IS_WINDOWS = platform.system().lower().startswith("win")

if _IS_WINDOWS:
    import win32print
    import win32ui
    import win32con
from PIL import Image, ImageDraw, ImageFont, ImageWin

# Optional Arabic shaping (for when text-to-image pass is used without your arabic_bitmap)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _ARABIC_OK = True
except Exception:
    _ARABIC_OK = False


def list_printers() -> list[str]:
    """Return local + connected printers (Windows only)."""
    if not _IS_WINDOWS:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def _ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def print_image(printer_name: str, pil_image: Image.Image) -> None:
    """
    Send a PIL image to a Windows printer via GDI. Uses full printable width.
    This avoids RTL/ligature issues by rasterizing the receipt.
    """
    if not _IS_WINDOWS:
        raise RuntimeError("Windows printing is only available on Windows")
    pil_image = _ensure_rgb(pil_image)

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        # Start document
        hdc.StartDoc("BeirutPOS")
        hdc.StartPage()

        # Printable resolution
        HORZRES = hdc.GetDeviceCaps(win32con.HORZRES)
        # Keep width = printable width, scale height proportionally
        w = HORZRES
        h = int(pil_image.height * (w / pil_image.width))

        dib = ImageWin.Dib(pil_image)
        dib.draw(hdc.GetHandleOutput(), (0, 0, w, h))

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
    finally:
        win32print.ClosePrinter(hprinter)


def print_text(printer_name: str, text: str, *, width_px: int = 576, font_size: int = 28) -> None:
    """
    Text -> raster -> print_image. Safer for Arabic than RAW text.
    If you really want RAW bytes, add another function. This one is robust.
    """
    # Build a simple raster (fallback if you don't use your own arabic_bitmap pipeline here).
    # Shape Arabic if libs present:
    if _ARABIC_OK:
        text = get_display(arabic_reshaper.reshape(text))

    # Render simple multiline: left-aligned
    font = None
    try:
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except Exception:
        font = ImageFont.load_default()

    # Size pass
    tmp = Image.new("L", (1, 1), 255)
    dr = ImageDraw.Draw(tmp)
    lines = text.split("\n")
    heights = []
    max_w = 0
    for ln in lines:
        x0, y0, x1, y1 = dr.textbbox((0, 0), ln, font=font)
        heights.append((y1 - y0) + 6)
        max_w = max(max_w, x1 - x0)
    total_h = max(1, sum(heights))

    img = Image.new("L", (width_px, total_h), 255)
    dr = ImageDraw.Draw(img)
    y = 0
    for i, ln in enumerate(lines):
        x0, y0, x1, y1 = dr.textbbox((0, 0), ln, font=font)
        dr.text((8, y), ln, 0, font=font)
        y += heights[i]

    print_image(printer_name, img.convert("RGB"))
