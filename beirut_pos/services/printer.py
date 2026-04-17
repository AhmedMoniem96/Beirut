# beirut_pos/services/printer.py
from __future__ import annotations
import glob, os, re, platform, json
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

# -------- ESC/POS raw USB (fallback) -------------------------------------
try:
    from escpos.printer import File, Usb
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:
    _ESCPOS_OK = False

    class USBNotFoundError(Exception):
        ...

    Usb = None
    File = None

# -------- OS / PIL -------------------------------------------------------
_IS_WINDOWS = platform.system().lower().startswith("win")

from PIL import Image, ImageDraw, ImageFont

from ..core.paths import DATA_DIR
from . import settings as settings_service
from . import texts as texts_service
from .arabic_codec import sanitize_line, shape_bidi_arabic, encode_for_printer  # keep import for other modules

# Optional: your raw USB optimized class
try:
    from .raw_usb_escpos import RawUsbEscpos
    _RAW_USB_OK = True
except ImportError:
    RawUsbEscpos = None  # type: ignore
    _RAW_USB_OK = False

# Preferred high-quality renderers (if present)
try:
    from .arabic_bitmap import (
        render_line_bitmap,
        render_table_bitmap,
        pil_image_to_escpos_raster,
        load_font,
    )
    _BITMAP_OK = True
except Exception:
    _BITMAP_OK = False

# ---------- Windows driver backend (only on Windows) ----------
_WIN_PRINT_OK = False
if _IS_WINDOWS:
    try:
        from .printer_windows import (
            list_printers as win_list_printers,
            print_image as win_print_image,
        )
        _WIN_PRINT_OK = True
    except Exception:
        _WIN_PRINT_OK = False

        def win_list_printers() -> list[str]:
            return []

        def win_print_image(*args, **kwargs):
            raise RuntimeError("Windows printing backend not available")
else:
    def win_list_printers() -> list[str]:
        return []

    def win_print_image(*args, **kwargs):
        raise RuntimeError("Windows printing not supported on this OS")

# ---------- Arabic shaping for bitmap (Windows image path) ----------
try:
    import arabic_reshaper
    from bidi.algorithm import get_display as _bidi_get_display
    _ARABIC_VISUAL_OK = True
except Exception:
    _ARABIC_VISUAL_OK = False


def _shape_for_bitmap(text: str) -> str:
    """
    Visual shaping for bitmap (PIL) rendering:
      - use arabic_reshaper + bidi.get_display if available
      - do NOT use arabic_codec.shape_bidi_arabic here to avoid ESC/POS-specific quirks.
    """
    if not text:
        return text
    if not _ARABIC_VISUAL_OK:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return _bidi_get_display(reshaped)
    except Exception:
        return text


from ..core.bus import bus

# =================================================================== CONSTS
_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_LOG_PATH = _OUTPUT_ROOT / "printer.log"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

USB_PRINTER_IDS = [
    (0x0483, 0x5743),
    (0x0416, 0x5011),
    (0x04B8, 0x0202),
    (0x04B8, 0x0E15),
    (0x067B, 0x2305),
    (0x0FE6, 0x811E),  # Rongta RP310
]

USB_PROBE_CANDIDATES: list[dict[str, int | None]] = [
    {"interface": 0, "out_ep": 0x01, "in_ep": 0x81},
    {"interface": 0, "out_ep": 0x02, "in_ep": 0x82},
    {"interface": 1, "out_ep": 0x01, "in_ep": 0x81},
    {"interface": 1, "out_ep": 0x02, "in_ep": 0x82},
    {"interface": 2, "out_ep": 0x01, "in_ep": 0x81},
    {"interface": 2, "out_ep": 0x02, "in_ep": 0x82},
    {"interface": None, "out_ep": None, "in_ep": None},  # let python-escpos auto-pick
]

_ALLOW_USB_WITH_USBLP = os.environ.get("BEIRUT_POS_USB_TRY_BOTH", "0") == "1"

# Keep in sync with bitmap renderer
PAPER_PX = 576  # 80mm at 203 dpi usable width
COLS_RECEIPT = [348, 60, 84, 84]  # Item, Qty, Price, Total (sum=576)
COLS_BAR = [456, 120]  # Item, Qty
CELL_PAD_X, CELL_PAD_Y = 8, 4

# =================================================================== UTILS
def _ensure_dirs() -> None:
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)
    try:
        _LOG_PATH.touch(exist_ok=True)
    except Exception:
        pass


def _log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(msg)
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as h:
            h.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _log_struct(event: str, **fields) -> None:
    payload = {"event": event, **fields}
    try:
        _log("STRUCT " + json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    except Exception:
        _log(f"STRUCT {event} {fields}")


def _format_qty(qty: float) -> str:
    r = round(qty)
    if abs(qty - r) < 1e-6:
        return str(int(r))
    return f"{qty:.2f}".rstrip("0").rstrip(".")


def _format_currency_simple(amount: int | float | str) -> str:
    try:
        v = float(amount)
        if abs(v - round(v)) < 1e-6:
            return str(int(round(v)))
        return f"{v:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(amount)


def _note_segments(note: str, *, include_sugar: bool = False, tag_sugar: bool = False) -> list[str]:
    if not note:
        return []
    cleaned = note.replace("\n", " ")
    raw = [p.strip(" ؛;,-•") for p in re.split(r"[؛;]", cleaned) if p.strip()]
    out: list[str] = []
    for seg in raw:
        low = seg.lower()
        if "سكر" in seg or "sugar" in low:
            if include_sugar:
                val = seg.replace("سكر:", "").replace("sugar:", "").strip()
                out.append(val if not tag_sugar else f"سكر: {val}")
        else:
            out.append(seg)
    return out


def _draw_line(char: str = "─", width_chars: int = 48) -> str:
    return char * width_chars


# ---------- text fit (avoid spilling into Qty col / next cell) ----------
def _max_chars_for_px(col_px: int) -> int:
    px_per_char = os.getenv("BEIRUT_POS_PX_PER_CHAR", "16")
    try:
        v = float(px_per_char)
        v = max(9.0, v)
    except Exception:
        v = 16.0
    return max(6, int(col_px / v))


def _halve_long_words(text: str, threshold: int = 12) -> str:
    out_tokens: list[str] = []
    for tok in text.split():
        if len(tok) > threshold:
            cut = (len(tok) + 1) // 2
            out_tokens.append(tok[:cut])
        else:
            out_tokens.append(tok)
    return " ".join(out_tokens)


def _fit_line_for_col(text: str, col_px: int) -> str:
    safety = 12
    effective_px = max(24, col_px - (2 * CELL_PAD_X) - safety)
    text = _halve_long_words(text, threshold=12)
    max_chars = _max_chars_for_px(effective_px)
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"


# ===================================================== header/meta (receipt)
def _build_receipt_header_meta(
    table_code: str,
    cashier: str,
    method: str | None = None,
    *,
    customer_name: str | None = None,
    loyalty_balance: int | None = None,
    loyalty_delta: int | None = None,
) -> List[str]:
    ts = datetime.now().strftime("%Y/%m/%d %I:%M %p")
    client_name = settings_service.get_client_name()
    box_width = 30
    brand_lines = [
        texts_service.get("receipt.cashier.header", client_name=client_name),
        texts_service.get("receipt.cashier.subtitle", client_name=client_name),
        texts_service.get("receipt.cashier.address"),
        texts_service.get("receipt.cashier.phone"),
    ]
    brand_lines = [ln.strip() for ln in brand_lines if ln and ln.strip()]
    if not brand_lines:
        brand_lines = [client_name]

    def _box_line(text: str) -> str:
        trimmed = text[:box_width]
        return ">>C " + f"║{trimmed.center(box_width)}║"

    lines: List[str] = []
    lines.append(">>C " + ("╔" + "═" * box_width + "╗"))
    for segment in brand_lines:
        lines.append(_box_line(segment))
    lines.append(">>C " + ("╚" + "═" * box_width + "╝"))

    date_line = texts_service.get(
        "receipt.cashier.date",
        default="التاريخ: {timestamp}",
        timestamp=ts,
    ).strip()
    if date_line:
        lines.append(">>R " + date_line)

    meta_line = texts_service.get(
        "receipt.cashier.meta",
        default="{table_code} : {cashier}",
        table_code=table_code,
        cashier=cashier,
    ).strip()
    if meta_line:
        lines.append(">>R " + meta_line)

    method_clean = (method or "").strip()
    if method_clean:
        method_line = texts_service.get("receipt.cashier.method", method=method_clean).strip()
        if method_line:
            lines.append(">>R " + method_line)

    customer_clean = (customer_name or "").strip()
    if customer_clean:
        lines.append(f">>R العميل: {customer_clean}")
    if loyalty_balance is not None:
        delta_segment = ""
        if loyalty_delta not in (None, 0):
            sign = "+" if loyalty_delta > 0 else ""
            delta_segment = f" ({sign}{int(loyalty_delta)})"
        lines.append(f">>R نقاط الولاء: {int(loyalty_balance)}{delta_segment}")

    lines.append(_draw_line("═"))
    return lines


def _build_receipt_footer_lines(
    subtotal: int | float | None,
    discount: int | float | None,
    total: int | float,
    *,
    service: int | float | None = None,
    tax: int | float | None = None,
    discount_label: str | None = None,
) -> List[str]:
    lines: List[str] = [_draw_line("═")]
    if subtotal is not None:
        lines.append(
            ">>R "
            + texts_service.get(
                "receipt.cashier.subtotal",
                amount=_format_currency_simple(subtotal),
            )
        )
    if discount and float(discount) > 0:
        discount_amount = _format_currency_simple(-abs(float(discount)))
        lines.append(
            ">>R "
            + texts_service.get(
                "receipt.cashier.discount",
                amount=discount_amount,
                label=discount_label or "الخصم",
            )
        )
    if service and float(service) > 0:
        lines.append(
            ">>R "
            + texts_service.get(
                "receipt.cashier.service",
                amount=_format_currency_simple(service),
            )
        )
    if tax and float(tax) > 0:
        lines.append(
            ">>R "
            + texts_service.get(
                "receipt.cashier.tax",
                amount=_format_currency_simple(tax),
            )
        )
    lines.append(
        ">>R "
        + texts_service.get(
            "receipt.cashier.total",
            amount=_format_currency_simple(total),
        )
    )
    footer_text = texts_service.get("receipt.footer", default="شكراً").strip()
    if footer_text:
        lines.append(">>C " + footer_text)
    return lines


# ======================================= items tables (receipt / bar)
def _build_items_table(items: Sequence[dict]) -> tuple[list[str], list[list[str]], float, float]:
    headers = ["الصنف", "الكمية", "السعر", "الإجمالي"]
    rows: list[list[str]] = []
    subtotal_calc = 0.0
    total_qty = 0.0
    item_px, qty_px, price_px, total_px = COLS_RECEIPT

    for it in items:
        name = str(it["name"])
        qty = float(it.get("qty", 0) or 0)
        total = float(it.get("total_cents", 0) or 0)
        unit = float(it.get("unit_price", 0) or (total / qty if qty else 0.0))
        notes = _note_segments(it.get("note", ""), include_sugar=False)
        name_disp = f"{name} ({'؛ '.join(notes)})" if notes else name
        name_disp = _fit_line_for_col(name_disp, item_px)
        rows.append(
            [
                name_disp,
                _format_qty(qty),
                _format_currency_simple(unit),
                _format_currency_simple(total),
            ]
        )
        subtotal_calc += total
        total_qty += qty
    return headers, rows, subtotal_calc, total_qty


def _build_bar_table(items: Sequence[dict]) -> tuple[list[str], list[list[str]]]:
    headers = ["الصنف", "الكمية"]
    rows: list[list[str]] = []
    item_px, qty_px = COLS_BAR
    for it in items:
        name = str(it["name"])
        qty = _format_qty(float(it.get("qty", 0) or 0))
        notes = _note_segments(it.get("note", ""), include_sugar=True, tag_sugar=False)
        name_disp = f"{name} ({'؛ '.join(notes)})" if notes else name
        name_disp = _fit_line_for_col(name_disp, item_px)
        rows.append([name_disp, qty])
    return headers, rows


# ================================================== ESC/POS PLUMBING
class MockPrinter:
    def __init__(self, name: str = "MockPrinter") -> None:
        self.name = name
        self.buffer: list[str] = []

    def text(self, d: str) -> None:
        self.buffer.append(d)

    def set(self, **kw) -> None:
        ...

    def cut(self) -> None:
        self.buffer.append("<CUT>")

    def _raw(self, b: bytes) -> None:
        self.buffer.append(f"<RAW {b.hex()}>")

    def close(self) -> None:
        self.buffer.append("<CLOSE>")

    def print_lines(self, lines: Sequence[str]) -> None:
        for ln in lines:
            self.text(ln + "\n")

    def print_table(self, headers, rows, **kw) -> None:
        self.text("[TABLE]\n" + " | ".join(headers) + "\n")
        for r in rows:
            self.text(" | ".join(map(str, r)) + "\n")


def _log_printer_error(prefix: str, err: Exception) -> None:
    _log(f"❌ {prefix}: {err}")


def _usblp_device_paths() -> list[str]:
    return sorted(glob.glob("/dev/usb/lp*"))


def _try_usb_printer(*, allow_when_blocked: bool = False, usb_ids: Sequence[tuple[int, int]] | None = None):
    if not _ESCPOS_OK or Usb is None:
        _log_struct("printer.usb.skip", reason="escpos_not_available")
        return None
    lp = _usblp_device_paths()
    should_skip_for_usblp = lp and not allow_when_blocked and not _ALLOW_USB_WITH_USBLP
    if should_skip_for_usblp:
        _log(f"ℹ️  Kernel usblp driver detected ({', '.join(lp)}); skipping ESC/POS USB backend")
        _log_struct(
            "printer.usb.skip",
            reason="kernel_usblp_present",
            usblp_paths=lp,
            allow_when_blocked=allow_when_blocked,
            allow_try_both=_ALLOW_USB_WITH_USBLP,
        )
        return None
    init_probe = b"\x1B@"
    usb_id_list = list(usb_ids or USB_PRINTER_IDS)
    for vendor, product in usb_id_list:
        for candidate in USB_PROBE_CANDIDATES:
            interface = candidate.get("interface")
            out_ep = candidate.get("out_ep")
            in_ep = candidate.get("in_ep")
            try:
                kwargs = {}
                if interface is not None:
                    kwargs["interface"] = int(interface)
                if out_ep is not None:
                    kwargs["out_ep"] = int(out_ep)
                if in_ep is not None:
                    kwargs["in_ep"] = int(in_ep)
                _log_struct(
                    "printer.usb.candidate",
                    vid=f"0x{vendor:04X}",
                    pid=f"0x{product:04X}",
                    interface=interface,
                    out_ep=None if out_ep is None else f"0x{int(out_ep):02X}",
                    in_ep=None if in_ep is None else f"0x{int(in_ep):02X}",
                )
                prn = Usb(vendor, product, **kwargs)
                if hasattr(prn, "_raw"):
                    prn._raw(init_probe)
                _log_struct(
                    "printer.usb.selected",
                    backend="escpos-usb",
                    vid=f"0x{vendor:04X}",
                    pid=f"0x{product:04X}",
                    interface=interface,
                    out_ep=None if out_ep is None else f"0x{int(out_ep):02X}",
                    in_ep=None if in_ep is None else f"0x{int(in_ep):02X}",
                    usblp_paths=lp,
                )
                return prn
            except Exception as e:
                _log_struct(
                    "printer.usb.candidate_failed",
                    vid=f"0x{vendor:04X}",
                    pid=f"0x{product:04X}",
                    interface=interface,
                    out_ep=None if out_ep is None else f"0x{int(out_ep):02X}",
                    in_ep=None if in_ep is None else f"0x{int(in_ep):02X}",
                    error=str(e),
                )
                _log_printer_error("Printer connection error", e)
    return None


def _try_file_printer():
    if File is None:
        _log_struct("printer.file.skip", reason="file_backend_not_available")
        return None
    for p in _usblp_device_paths():
        try:
            prn = File(p)
            prn.open(raise_not_found=False)
            _log_struct("printer.file.selected", backend="file", path=p)
            return prn
        except Exception as exc:
            _log_struct("printer.file.failed", backend="file", path=p, error=str(exc))
            continue
    return None


def _setup_printer_arabic(printer) -> bool:
    try:
        printer._raw(b"\x1B@")
        printer._raw(b"\x1B\x61\x00")
        return True
    except Exception as e:
        _log_printer_error("Failed to reset printer", e)
        return False


def _post_feed_and_cut(printer) -> None:
    try:
        if hasattr(printer, "_raw"):
            printer._raw(b"\n")
            printer._raw(b"\x1B\x64\x02")  # feed 2 lines
            printer._raw(b"\x1B\x4A\x30")  # feed 48 dots (~6mm)
        import time as _t

        _t.sleep(0.15)
        if hasattr(printer, "cut"):
            printer.cut()
    except Exception as e:
        _log_printer_error("Post-feed/cut failed", e)


def _emit_lines_to_printer(printer, lines: Sequence[str]) -> bool:
    try:
        if hasattr(printer, "print_lines"):
            printer.print_lines(list(lines))
            return True
        for ln in lines:
            printer.text(ln + "\n")
        return True
    except Exception as exc:
        _log_printer_error("Print failed", exc)
        return False


def _print_escpos_lines(printer, lines: Sequence[str]) -> bool:
    ok = True
    try:
        _setup_printer_arabic(printer)
    except Exception as e:
        _log_printer_error("Init wrapper failed", e)
        ok = False
    if not _emit_lines_to_printer(printer, lines):
        ok = False
    if ok:
        _post_feed_and_cut(printer)
    return ok


# =================================== RENDER HELPERS (Windows raster path)
def _font_default(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _render_lines_bitmap_fallback(lines: Sequence[str], width: int = PAPER_PX) -> Image.Image:
    """
    Fallback when arabic_bitmap is missing: draw using PIL, shaping Arabic
    via _shape_for_bitmap so it appears correctly (not reversed) on Windows.
    """
    font = _font_default(28)
    tmp = Image.new("L", (1, 1), 255)
    dr = ImageDraw.Draw(tmp)
    heights: list[int] = []
    eff_lines: list[tuple[str, str]] = []

    for raw in lines:
        align, txt = "left", raw
        if raw.startswith(">>C "):
            align, txt = "center", raw[4:]
        elif raw.startswith(">>R "):
            align, txt = "right", raw[4:]
        elif raw.startswith(">>L "):
            align, txt = "left", raw[4:]

        shaped = _shape_for_bitmap(txt)
        eff_lines.append((align, shaped))
        _, _, x1, y1 = dr.textbbox((0, 0), shaped, font=font)
        h = y1 + 6
        heights.append(h)

    total_h = max(1, sum(heights))
    img = Image.new("L", (width, total_h), 255)
    dr = ImageDraw.Draw(img)
    y = 0
    for i, (align, shaped) in enumerate(eff_lines):
        x0, y0, x1, y1 = dr.textbbox((0, 0), shaped, font=font)
        text_w = x1 - x0
        if align == "center":
            x = (width - text_w) // 2
        elif align == "right":
            x = width - text_w - 8
        else:
            x = 8
        dr.text((x, y), shaped, 0, font=font)
        y += heights[i]
    return img.convert("1")


def _render_lines_to_bitmap(lines: Sequence[str]) -> Image.Image:
    """
    Convert tagged lines (>>C, >>R, >>L) into a single bitmap.
    Uses _shape_for_bitmap so Arabic is visually correct on Windows.
    """
    if _BITMAP_OK:
        rows = []
        for raw in lines:
            align, txt = "left", raw
            if raw.startswith(">>C "):
                align, txt = "center", raw[4:]
            elif raw.startswith(">>R "):
                align, txt = "right", raw[4:]
            elif raw.startswith(">>L "):
                align, txt = "left", raw[4:]

            shaped = _shape_for_bitmap(txt)
            font = load_font(size=28)
            rows.append(
                render_line_bitmap(
                    shaped,
                    paper_px=PAPER_PX,
                    font=font,
                    align=align,
                )
            )
        h = sum(im.height for im in rows)
        canvas = Image.new("1", (PAPER_PX, h), 1)
        y = 0
        for im in rows:
            canvas.paste(im, (0, y))
            y += im.height
        return canvas
    return _render_lines_bitmap_fallback(lines, width=PAPER_PX)


def _render_table_to_bitmap(
    headers,
    rows,
    *,
    footer_rows=None,
    font_size=28,
    col_widths_px=None,
    col_align=("left", "center", "right", "right"),
    cell_pad=(CELL_PAD_X, CELL_PAD_Y),
    draw_borders=True,
) -> Image.Image:
    """
    Render a full table as bitmap. All cells (headers/body/footer) are passed
    through _shape_for_bitmap so Arabic text is not reversed under Windows.
    """

    def _shape_row(row):
        return [_shape_for_bitmap(str(c)) for c in row]

    shaped_headers = _shape_row(headers)
    shaped_rows = [_shape_row(r) for r in rows]
    shaped_footer = [_shape_row(r) for r in (footer_rows or [])] if footer_rows else None

    if _BITMAP_OK:
        return render_table_bitmap(
            shaped_headers,
            shaped_rows,
            footer_rows=shaped_footer,
            paper_px=PAPER_PX,
            col_widths_px=col_widths_px,
            font_body=load_font(size=font_size),
            font_header=load_font(size=font_size, bold=True),
            font_footer=load_font(size=font_size, bold=True),
            cell_pad=cell_pad,
            draw_borders=draw_borders,
            col_align=col_align,
        )

    font = _font_default(font_size)
    text_lines: list[str] = []
    text_lines.append(" | ".join(shaped_headers))
    text_lines += [" | ".join(map(str, r)) for r in shaped_rows]
    if shaped_footer:
        text_lines += [" | ".join(map(str, r)) for r in shaped_footer]

    tmp = Image.new("L", (1, 1), 255)
    dr = ImageDraw.Draw(tmp)
    heights = []
    for t in text_lines:
        _, _, _, h = dr.textbbox((0, 0), t, font=font)
        heights.append(h + 6)
    canvas = Image.new("L", (PAPER_PX, sum(heights)), 255)
    dr = ImageDraw.Draw(canvas)
    y = 0
    for i, t in enumerate(text_lines):
        dr.text((8, y), t, 0, font=font)
        y += heights[i]
    return canvas.convert("1")


def _stack_bitmaps(bitmaps: list[Image.Image]) -> Image.Image:
    if not bitmaps:
        return Image.new("1", (PAPER_PX, 1), 1)
    w = PAPER_PX
    h = sum(im.height for im in bitmaps)
    canvas = Image.new("1", (w, h), 1)
    y = 0
    for im in bitmaps:
        if im.mode != "1":
            im = im.convert("1")
        canvas.paste(im, (0, y))
        y += im.height
    return canvas


# =========================================== SINGLE BACKEND (ESC/POS)
def _find_thermal_printer():
    if _DISABLE_ESCPOS:
        _log_struct("printer.discovery.skip", reason="escpos_disabled")
        return None
    # first-class order: RP310 first, then other known USB IDs
    probe_order = [(0x0FE6, 0x811E)] + [pair for pair in USB_PRINTER_IDS if pair != (0x0FE6, 0x811E)]

    if RawUsbEscpos is not None and _RAW_USB_OK:
        for vendor, product in probe_order:
            try:
                prn = RawUsbEscpos(vid=vendor, pid=product, interface=0)
                _log_struct(
                    "printer.discovery.selected",
                    backend="raw-usb-escpos",
                    vid=f"0x{vendor:04X}",
                    pid=f"0x{product:04X}",
                )
                return prn
            except Exception as e:
                _log_struct(
                    "printer.discovery.backend_failed",
                    backend="raw-usb-escpos",
                    vid=f"0x{vendor:04X}",
                    pid=f"0x{product:04X}",
                    error=str(e),
                )
                _log_printer_error("RawUsbEscpos failed", e)

    usb_printer = _try_usb_printer(usb_ids=probe_order)
    if usb_printer:
        _log_struct("printer.discovery.selected", backend="escpos-usb")
        return usb_printer

    file_printer = _try_file_printer()
    if file_printer:
        _log_struct("printer.discovery.selected", backend="usblp-file")
        return file_printer

    if _ALLOW_USB_WITH_USBLP and _usblp_device_paths():
        usb_after_file = _try_usb_printer(allow_when_blocked=True, usb_ids=probe_order)
        if usb_after_file:
            _log_struct(
                "printer.discovery.selected",
                backend="escpos-usb",
                mode="fallback_after_usblp_file",
            )
            return usb_after_file

    _log_struct("printer.discovery.failed", reason="all_backends_failed")
    return None


# =============================================== FLOWS (ESC/POS objects)
def _print_escpos_receipt(
    printer,
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    total: int,
    method: str,
    cashier: str,
    *,
    service: int | float | None = None,
    tax: int | float | None = None,
    discount_label: str | None = None,
    customer_name: str | None = None,
    loyalty_balance: int | None = None,
    loyalty_delta: int | None = None,
) -> None:
    head = _build_receipt_header_meta(
        table_code,
        cashier,
        method,
        customer_name=customer_name,
        loyalty_balance=loyalty_balance,
        loyalty_delta=loyalty_delta,
    )
    _emit_lines_to_printer(printer, head)

    headers, rows, calc_sub, total_qty = _build_items_table(items)

    if hasattr(printer, "print_table"):
        printer.print_table(
            headers,
            rows,
            footer_rows=None,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT", "28")),
            col_widths_px=COLS_RECEIPT,
            col_align=("left", "center", "right", "right"),
            cell_pad=(CELL_PAD_X, CELL_PAD_Y),
            draw_borders=True,
        )
    else:
        _emit_lines_to_printer(
            printer,
            [" | ".join(headers)] + [" | ".join(map(str, r)) for r in rows],
        )
    footer_lines = _build_receipt_footer_lines(
        subtotal,
        discount,
        total,
        service=service,
        tax=tax,
        discount_label=discount_label,
    )
    _print_escpos_lines(printer, footer_lines)


def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]) -> None:
    now = datetime.now().strftime("%I:%M %p")
    _emit_lines_to_printer(
        printer,
        [
            ">>C " + f"{now}  |  {table_code}",
            _draw_line("═"),
        ],
    )
    headers, rows = _build_bar_table(items)
    if hasattr(printer, "print_table"):
        printer.print_table(
            headers,
            rows,
            footer_rows=None,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT", "28")),
            col_widths_px=COLS_BAR,
            col_align=("left", "center"),
            cell_pad=(CELL_PAD_X, CELL_PAD_Y),
            draw_borders=True,
        )
    else:
        _emit_lines_to_printer(
            printer,
            [" | ".join(headers)] + [" | ".join(map(str, r)) for r in rows],
        )
    _print_escpos_lines(printer, [_draw_line("═")])


# ============================================= COLLAPSE & SERVICE
def _collapse_items(items: Iterable) -> List[dict]:
    grouped: dict[tuple[str, int, str], dict[str, object]] = {}
    for it in items:
        name = getattr(it, "product", str(it))
        unit_price = float(getattr(it, "unit_price_cents", 0) or 0)
        note = (getattr(it, "note", "") or "").strip()
        key = (name, int(unit_price), note)
        qty = float(getattr(it, "qty", 1.0) or 1.0)
        total_cents = float(getattr(it, "total_cents", 0) or (unit_price * qty))
        if key in grouped:
            grouped[key]["qty"] = float(grouped[key]["qty"]) + qty
            grouped[key]["total_cents"] = float(grouped[key]["total_cents"]) + total_cents
        else:
            grouped[key] = {
                "name": name,
                "qty": qty,
                "unit_price": unit_price,
                "total_cents": total_cents,
                "note": note,
            }
    return list(grouped.values())


class PrinterService:
    """
    Windows driver path:
      - Set env:
          BEIRUT_WIN_PRINTER_BAR="Exact Printer Name"
          BEIRUT_WIN_PRINTER_CASHIER="Exact Printer Name"
    Else: ESC/POS fallback (raw USB or /dev/usb/lp*).
    """

    def __init__(self) -> None:
        _ensure_dirs()
        self._bar_win = os.getenv("BEIRUT_WIN_PRINTER_BAR", "").strip()
        self._cash_win = os.getenv("BEIRUT_WIN_PRINTER_CASHIER", "").strip()
        self._escpos_printer = None
        if not (_IS_WINDOWS and _WIN_PRINT_OK and (self._bar_win or self._cash_win)):
            self._escpos_printer = _find_thermal_printer()

    def _refresh_escpos_printer(self) -> bool:
        """
        Ensure there is an active ESC/POS printer handle.

        This is useful after a printer power cycle so the user does not need to
        re-open the settings dialog to trigger a reload.
        """

        if self._escpos_printer is not None:
            return True
        new_printer = _find_thermal_printer()
        if new_printer:
            self._escpos_printer = new_printer
            _log("✅ Thermal printer handle refreshed")
            return True
        _log("ℹ️  No thermal printer available after refresh")
        return False

    def ensure_printer_ready(self) -> bool:
        """Return True when any configured printer is reachable/ready."""

        if self._use_windows_bar() or self._use_windows_cash():
            return True
        return self._refresh_escpos_printer()

    def update_printers(self, bar: Optional[str], cash: Optional[str]) -> None:
        self._bar_win = (bar or "").strip()
        self._cash_win = (cash or "").strip()
        try:
            if hasattr(self._escpos_printer, "close"):
                self._escpos_printer.close()  # type: ignore
        except Exception:
            ...
        self._escpos_printer = None
        if not (_IS_WINDOWS and _WIN_PRINT_OK and (self._bar_win or self._cash_win)):
            self._escpos_printer = _find_thermal_printer()
        _log(
            f"Windows printers -> BAR: {self._bar_win or '-'} | CASHIER: {self._cash_win or '-'}"
        )

    def _current_printer(self):
        """Backwards-compatible accessor used by older maintenance scripts."""
        return self._escpos_printer

    def test_print(self) -> bool:
        """
        Emit a tiny diagnostic receipt.  When no physical printer is connected
        we fall back to the in-memory MockPrinter to keep automated tests happy.
        """
        _log("🧪 Starting printer self-test...")
        now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        lines = [
            ">>C Beirut POS",
            _draw_line(),
            f">>L Self-test @ {now}",
            ">>L الاتصال ناجح",  # "Connection OK"
            _draw_line(),
        ]
        printer = self._current_printer()
        target = printer
        if target is None:
            _log("ℹ️  No ESC/POS printer detected – capturing output via MockPrinter")
            target = MockPrinter("SelfTest")
        try:
            _print_escpos_lines(target, lines)
            return True
        except Exception as exc:
            _log_printer_error("Test print failed", exc)
            return False

    def _use_windows_bar(self) -> bool:
        return _IS_WINDOWS and _WIN_PRINT_OK and bool(self._bar_win)

    def _use_windows_cash(self) -> bool:
        return _IS_WINDOWS and _WIN_PRINT_OK and bool(self._cash_win)

    # ---------------------------- BAR
    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        data = _collapse_items(items)

        now = datetime.now().strftime("%I:%M %p")
        head_lines = [">>C " + f"{now}  |  {table_code}", _draw_line("═")]
        headers, rows = _build_bar_table(data)

        if self._use_windows_bar():
            bmp_head = _render_lines_to_bitmap(head_lines)
            bmp_tbl = _render_table_to_bitmap(
                headers,
                rows,
                footer_rows=None,
                font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT", "28")),
                col_widths_px=COLS_BAR,
                col_align=("left", "center"),
                cell_pad=(CELL_PAD_X, CELL_PAD_Y),
                draw_borders=True,
            )
            bmp_footer = _render_lines_to_bitmap([_draw_line("═")])
            img = _stack_bitmaps([bmp_head, bmp_tbl, bmp_footer]).convert("RGB")
            win_print_image(self._bar_win, img)
            return True

        self._refresh_escpos_printer()
        prn = self._escpos_printer
        if prn:
            _print_escpos_bar_ticket(prn, table_code, data)
        return True

    # ---------------------------- CASHIER
    def print_cashier_receipt(
        self,
        table_code: str,
        items: Iterable,
        subtotal: int,
        discount: int,
        total: int,
        method: str,
        cashier: str,
        service: int | None = None,
        tax: int | None = None,
        *,
        discount_label: str | None = None,
        customer_name: str | None = None,
        loyalty_balance: int | None = None,
        loyalty_delta: int | None = None,
    ) -> bool:
        data = _collapse_items(items)
        head = _build_receipt_header_meta(
            table_code,
            cashier,
            method,
            customer_name=customer_name,
            loyalty_balance=loyalty_balance,
            loyalty_delta=loyalty_delta,
        )
        headers, rows, calc_sub, total_qty = _build_items_table(data)
        tail_lines = _build_receipt_footer_lines(
            subtotal,
            discount,
            total,
            service=service,
            tax=tax,
            discount_label=discount_label,
        )

        if self._use_windows_cash():
            bmp_head = _render_lines_to_bitmap(head)
            bmp_tbl = _render_table_to_bitmap(
                headers,
                rows,
                footer_rows=None,
                font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT", "28")),
                col_widths_px=COLS_RECEIPT,
                col_align=("left", "center", "right", "right"),
                cell_pad=(CELL_PAD_X, CELL_PAD_Y),
                draw_borders=True,
            )
            bmp_tail = _render_lines_to_bitmap(tail_lines)
            img = _stack_bitmaps([bmp_head, bmp_tbl, bmp_tail]).convert("RGB")
            win_print_image(self._cash_win, img)
            return True

        self._refresh_escpos_printer()
        prn = self._escpos_printer
        if prn:
            _print_escpos_receipt(
                prn,
                table_code,
                data,
                subtotal,
                discount,
                total,
                method,
                cashier,
                service=service,
                tax=tax,
                discount_label=discount_label,
                customer_name=customer_name,
                loyalty_balance=loyalty_balance,
                loyalty_delta=loyalty_delta,
            )
        return True

    def print_text_receipt(
        self,
        lines: Sequence[str],
        *,
        printer_name: str | None = None,
        print_mode: str | None = None,
    ) -> bool:
        """Print tagged text lines as a receipt."""
        selected_name = (printer_name or "").strip()
        selected_mode = (print_mode or "auto").strip().lower()

        target_windows_printer = ""
        if selected_mode != "escpos":
            if selected_name and selected_name.lower() != "auto":
                target_windows_printer = selected_name
            elif selected_mode == "auto" and self._use_windows_cash():
                target_windows_printer = self._cash_win
            elif selected_mode == "windows" and self._cash_win:
                target_windows_printer = self._cash_win

        if _IS_WINDOWS and _WIN_PRINT_OK and target_windows_printer:
            bmp = _render_lines_to_bitmap(lines)
            win_print_image(target_windows_printer, bmp.convert("RGB"))
            return True

        self._refresh_escpos_printer()
        prn = self._escpos_printer
        if prn:
            _print_escpos_lines(prn, lines)
        return True


# singleton
printer = PrinterService()


def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)


bus.subscribe("printers_changed", _apply_printer_settings)
