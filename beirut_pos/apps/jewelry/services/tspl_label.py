"""Native TSPL label generation for the Jewelry barcode printer.

The RP3xx queue is a command-language printer, not a Windows text/GDI
printer.  This module therefore produces the complete TSPL job and deliberately
contains no transport code.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .settings import BarcodePrinterSettings

if TYPE_CHECKING:
    from PIL import Image


class TsplValidationError(ValueError):
    """Raised before dispatch when a value cannot be represented safely."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


@dataclass(frozen=True)
class TsplLabel:
    product_name: str
    barcode: str
    price_text: str
    copies: int = 1


_FORBIDDEN_ZPL = (b"^XA", b"^XZ", b"^FO", b"^FD", b"^BC", b"^BY", b"^CI")
_ARABIC_NUMERIC_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹،٫", "01234567890123456789,.")


def _text(value: object, field: str, *, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise TsplValidationError(field, f"{field.replace('_', ' ').title()} is required.")
    if "\r" in result or "\n" in result:
        raise TsplValidationError(field, f"{field.replace('_', ' ').title()} must be one line.")
    # TSPL has no portable in-string quote escaping. A typographic apostrophe
    # preserves the visible content without permitting command injection.
    return result.replace('"', "'")


def _encode_cp1256(value: str, field: str) -> bytes:
    # Windows-1256 omits Arabic-Indic digits even though RP firmware exposes it
    # as the Arabic code page. Normalize only numeric glyphs/punctuation; names
    # and identifiers otherwise remain unchanged and are encoded strictly.
    value = value.translate(_ARABIC_NUMERIC_TRANSLATION)
    try:
        return value.encode("cp1256", errors="strict")
    except UnicodeEncodeError as exc:
        unsupported = value[exc.start : exc.end]
        points = " ".join(f"U+{ord(char):04X}" for char in unsupported)
        raise TsplValidationError(
            field,
            f"{field.replace('_', ' ').title()} contains characters unsupported "
            f"by the configured native TSPL Arabic code page 1256 ({points}).",
        ) from exc


def _command_with_text(prefix: str, value: str, field: str) -> bytes:
    return prefix.encode("ascii") + _encode_cp1256(value, field) + b'"\r\n'


def _bitmap_bytes(image: "Image.Image") -> tuple[int, bytes]:
    monochrome = image.convert("1")
    width_bytes = (monochrome.width + 7) // 8
    data = bytearray(width_bytes * monochrome.height)
    pixels = monochrome.load()
    for y in range(monochrome.height):
        for x in range(monochrome.width):
            if pixels[x, y] == 0:
                data[(y * width_bytes) + (x // 8)] |= 0x80 >> (x % 8)
    return width_bytes, bytes(data)


def build_native_tspl(
    label: TsplLabel,
    settings: BarcodePrinterSettings,
    *,
    shaped_name_bitmap: "Image.Image | None" = None,
) -> bytes:
    """Return one complete TSPL command stream.

    English uses the printer's native ``TEXT`` command. RP3xx font ``0`` does
    not reliably contain or shape Arabic, so callers may provide the already
    shaped product-name row used by the existing preview renderer. Only that
    row is emitted as a TSPL ``BITMAP``; barcode and price remain native.
    """
    name = _text(label.product_name, "product_name")
    barcode = _text(label.barcode, "barcode")
    price = _text(label.price_text, "price_text")
    price_match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s+[A-Za-z]{2,4})?", price)
    if not price_match or not math.isfinite(float(price_match.group(1))):
        raise TsplValidationError("price_text", "Price must be a finite decimal with an optional currency code.")
    if any(ord(char) < 32 or ord(char) > 126 for char in barcode):
        raise TsplValidationError("barcode", "Code 128 barcode must contain printable ASCII only.")
    if isinstance(label.copies, bool) or not isinstance(label.copies, int) or label.copies < 1:
        raise TsplValidationError("copies", "Copies must be a positive integer.")
    for field in ("width_mm", "height_mm", "gap_mm"):
        value = getattr(settings, field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise TsplValidationError(field, f"{field} must be a finite number.")
    if settings.width_mm < 10 or settings.height_mm < 10 or settings.gap_mm < 0:
        raise TsplValidationError("dimensions", "Label dimensions must be at least 10 mm and gap cannot be negative.")

    dpi = settings.dpi
    width = round(settings.width_mm * dpi / 25.4)
    height = round(settings.height_mm * dpi / 25.4)
    x = max(8, round(width * 0.06))
    text_y = max(6, round(height * 0.06))
    barcode_y = max(text_y + 28, round(height * 0.30))
    barcode_height = max(32, min(round(height * 0.42), height - barcode_y - 34))
    price_y = min(height - 25, barcode_y + barcode_height + 7)
    font = _text(settings.native_font, "native_font")
    if any(ord(char) > 127 for char in font) or ',' in font:
        raise TsplValidationError("native_font", "TSPL native font name must be ASCII and cannot contain commas.")

    payload = bytearray(
        (
            f"SIZE {settings.width_mm:g} mm,{settings.height_mm:g} mm\r\n"
            f"GAP {settings.gap_mm:g} mm,0 mm\r\n"
            f"SPEED {settings.speed}\r\n"
            f"DENSITY {settings.density}\r\n"
            "DIRECTION 1\r\n"
            "REFERENCE 0,0\r\n"
            "CODEPAGE 1256\r\n"
            "CLS\r\n"
        ).encode("ascii")
    )
    if shaped_name_bitmap is None:
        payload += _command_with_text(f'TEXT {x},{text_y},"{font}",0,1,1,"', name, "product_name")
    else:
        width_bytes, bitmap = _bitmap_bytes(shaped_name_bitmap)
        bitmap_x = max(0, (width - shaped_name_bitmap.width) // 2)
        payload += f"BITMAP {bitmap_x},{text_y},{width_bytes},{shaped_name_bitmap.height},0,".encode("ascii")
        payload += bitmap + b"\r\n"
    payload += _command_with_text(
        f'BARCODE {x},{barcode_y},"128",{barcode_height},1,0,2,2,"', barcode, "barcode"
    )
    payload += _command_with_text(f'TEXT {x},{price_y},"{font}",0,1,1,"', price, "price_text")
    payload += f"PRINT 1,{label.copies}\r\n".encode("ascii")
    validate_native_tspl(bytes(payload))
    return bytes(payload)


def validate_native_tspl(payload: bytes) -> None:
    """Reject incomplete, bitmap, legacy, or injected printer payloads."""
    if not payload.startswith(b"SIZE ") or not payload.endswith(b"\r\n"):
        raise TsplValidationError("payload", "TSPL payload must start with SIZE and end with CRLF.")
    required = (b"\r\nGAP ", b"\r\nDIRECTION ", b"\r\nREFERENCE ", b"\r\nCLS\r\n", b"TEXT ", b"BARCODE ", b"PRINT 1,")
    if any(command not in payload for command in required):
        raise TsplValidationError("payload", "TSPL payload is missing a required label command.")
    if any(command in payload for command in _FORBIDDEN_ZPL):
        raise TsplValidationError("payload", "ZPL commands are not allowed in a TSPL label payload.")
    if payload.count(b"\r\nPRINT ") != 1:
        raise TsplValidationError("payload", "TSPL payload must contain exactly one PRINT command.")
