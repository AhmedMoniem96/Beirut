# services/printer.py
from __future__ import annotations
import glob, os, sys, re, math, io, platform
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

try:
    from escpos.printer import File, Usb
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:
    _ESCPOS_OK = False
    class USBNotFoundError(Exception): ...
    Usb = None; File = None

# ---------- Optional Windows GDI backend (normal Printer driver) ----------
_IS_WINDOWS = platform.system().lower().startswith("win")
if _IS_WINDOWS:
    try:
        import win32print, win32ui, win32con
        from PIL import Image, ImageWin  # Pillow already in your deps
        _WIN_GDI_OK = True
    except Exception:
        _WIN_GDI_OK = False
else:
    _WIN_GDI_OK = False

from ..core.paths import DATA_DIR
from .arabic_codec import sanitize_line, shape_bidi_arabic, encode_for_printer

try:
    from .raw_usb_escpos import RawUsbEscpos
    _RAW_USB_OK = True
except ImportError:
    RawUsbEscpos = None  # type: ignore
    _RAW_USB_OK = False

try:
    # bitmap helpers from your arabic_bitmap module
    from .arabic_bitmap import (
        render_line_bitmap,
        render_table_bitmap,
        pil_image_to_escpos_raster,
        load_font,
    )
    _BITMAP_OK = True
except Exception:
    _BITMAP_OK = False

from ..core.bus import bus

_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_LOG_PATH = _OUTPUT_ROOT / "printer.log"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

USB_PRINTER_IDS = [(0x0483,0x5743),(0x0416,0x5011),(0x04B8,0x0202),(0x04B8,0x0E15),(0x067B,0x2305)]

# === layout constants (keep in sync with RawUsbEscpos.render_table_bitmap) ===
PAPER_PX = 576  # 80mm @ 203dpi usable width
COLS_RECEIPT = [348, 60, 84, 84]   # Item, Qty, Price, Total (sum=576)
COLS_BAR     = [456, 120]          # Item, Qty for bar ticket
CELL_PAD_X, CELL_PAD_Y = 8, 4      # table cell padding

# ====================================================================== utils
def _ensure_dirs() -> None:
    for p in (_OUTPUT_ROOT,_RECEIPTS_DIR,_BAR_DIR): p.mkdir(parents=True, exist_ok=True)
    try: _LOG_PATH.touch(exist_ok=True)
    except Exception: pass

def _log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    print(msg)
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as h: h.write(f"[{ts}] {msg}\n")
    except Exception: pass

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
    if not note: return []
    cleaned = note.replace("\n", " ")
    raw = [p.strip(" ؛;,-•") for p in re.split(r"[؛;]", cleaned) if p.strip()]
    out: list[str] = []
    for seg in raw:
        low = seg.lower()
        if "سكر" in seg or "sugar" in low:
            if include_sugar:
                val = seg.replace("سكر:", "").replace("sugar:", "").strip()
                # keep ONLY the value unless tag_sugar=True
                out.append(val if not tag_sugar else f"سكر: {val}")
        else:
            out.append(seg)
    return out

def _draw_line(char: str = "─", width_chars: int = 48) -> str:
    return char * width_chars

# --- text fit helpers (prevent spill into Qty/next cell) ----------------
def _max_chars_for_px(col_px: int) -> int:
    """
    Conservative px→char map to keep text inside its cell.
    Tunable via BEIRUT_POS_PX_PER_CHAR (default 16).
    """
    px_per_char = os.getenv("BEIRUT_POS_PX_PER_CHAR", "16")
    try:
        v = float(px_per_char)
        px_per_char_f = max(9.0, v)
    except Exception:
        px_per_char_f = 16.0
    return max(6, int(col_px / px_per_char_f))

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

# ================================================= header/meta (receipt)
def _build_receipt_header_meta(table_code: str, cashier: str) -> List[str]:
    ts = datetime.now().strftime("%Y/%m/%d %H:%M")
    lines: List[str] = []
    lines.append(">>C " + ("╔" + "═" * 30 + "╗"))
    lines.append(">>C " + "║  كافيه بيروت  ║")
    lines.append(">>C " + "║    Cafe Beirut    ║")
    lines.append(">>C " + ("╚" + "═" * 30 + "╝"))
    lines.append(">>R " + f"التاريخ: {ts}")
    lines.append(">>R " + f"الطاولة: {table_code}")
    lines.append(">>R " + f"الكاشير: {cashier}")
    lines.append(_draw_line("═"))
    return lines

# ========================================== items tables (receipt / bar)
def _build_items_table(items: Sequence[dict]) -> tuple[list[str], list[list[str]], float, float]:
    headers = ["الصنف", "الكمية", "السعر", "الإجمالي"]
    rows: list[list[str]] = []
    subtotal_calc = 0.0
    total_qty = 0.0
    item_px, qty_px, price_px, total_px = COLS_RECEIPT

    for it in items:
        name = str(it["name"])
        qty  = float(it.get("qty", 0) or 0)
        total = float(it.get("total_cents", 0) or 0)
        unit = float(it.get("unit_price", 0) or (total / qty if qty else 0.0))
        notes = _note_segments(it.get("note", ""), include_sugar=False)
        name_disp = f"{name} ({'؛ '.join(notes)})" if notes else name
        name_disp = _fit_line_for_col(name_disp, item_px)  # prevent overflow
        rows.append([
            name_disp,
            _format_qty(qty),
            _format_currency_simple(unit),
            _format_currency_simple(total),
        ])
        subtotal_calc += total
        total_qty += qty
    return headers, rows, subtotal_calc, total_qty

def _build_bar_table(items: Sequence[dict]) -> tuple[list[str], list[list[str]]]:
    headers = ["الصنف", "الكمية"]
    rows: list[list[str]] = []
    item_px, qty_px = COLS_BAR
    for it in items:
        name = str(it["name"])
        qty  = _format_qty(float(it.get("qty", 0) or 0))
        notes = _note_segments(it.get("note", ""), include_sugar=True, tag_sugar=False)
        name_disp = f"{name} ({'؛ '.join(notes)})" if notes else name
        name_disp = _fit_line_for_col(name_disp, item_px)
        rows.append([name_disp, qty])
    return headers, rows

# ================================================= backends / plumbing ==
class MockPrinter:
    def __init__(self, name: str="MockPrinter") -> None:
        self.name=name; self.buffer: list[str]=[]
    def text(self, d: str) -> None: self.buffer.append(d)
    def set(self, **kw) -> None: ...
    def cut(self) -> None: self.buffer.append("<CUT>")
    def _raw(self, b: bytes) -> None: self.buffer.append(f"<RAW {b.hex()}>")
    def close(self) -> None: self.buffer.append("<CLOSE>")
    # bitmap helpers for fallback
    def print_lines(self, lines: Sequence[str]) -> None:
        for ln in lines: self.text(ln + "\n")
    def print_table(self, headers, rows, **kw) -> None:
        self.text("[TABLE]\n" + " | ".join(headers) + "\n")
        for r in rows: self.text(" | ".join(map(str, r)) + "\n")

def _log_printer_error(prefix: str, err: Exception) -> None: _log(f"❌ {prefix}: {err}")
def _usblp_device_paths() -> list[str]: return sorted(glob.glob("/dev/usb/lp*"))

def _try_usb_printer(*, allow_when_blocked: bool=False):
    if not _ESCPOS_OK or Usb is None: return None
    lp = _usblp_device_paths()
    if lp and not allow_when_blocked:
        _log(f"ℹ️  Kernel usblp driver detected ({', '.join(lp)}); skipping ESC/POS USB backend")
        return None
    for vendor, product in USB_PRINTER_IDS:
        try:
            prn = Usb(vendor, product, interface=0, in_ep=0x82, out_ep=0x01)
            return prn
        except Exception as e:
            _log_printer_error("Printer connection error", e)
    return None

def _try_file_printer():
    if File is None: return None
    for p in _usblp_device_paths():
        try:
            prn = File(p); prn.open(raise_not_found=False); return prn
        except Exception: continue
    return None

def _setup_printer_arabic(printer) -> bool:
    try: printer._raw(b"\x1B@"); printer._raw(b"\x1B\x61\x00"); return True
    except Exception as e: _log_printer_error("Failed to reset printer", e); return False

def _post_feed_and_cut(printer) -> None:
    try:
        if hasattr(printer, "_raw"):
            printer._raw(b"\n")
            printer._raw(b"\x1B\x64\x02")   # feed 2 lines
            printer._raw(b"\x1B\x4A\x30")   # feed 48 dots (~6mm)
        import time as _t; _t.sleep(0.15)
        if hasattr(printer, "cut"): printer.cut()
    except Exception as e:
        _log_printer_error("Post-feed/cut failed", e)

def _emit_lines_to_printer(printer, lines: Sequence[str]) -> None:
    if hasattr(printer, "print_lines"): printer.print_lines(list(lines)); return
    for ln in lines: printer.text(ln + "\n")

def _print_escpos_lines(printer, lines: Sequence[str]) -> None:
    try: _setup_printer_arabic(printer)
    except Exception as e: _log_printer_error("Init wrapper failed", e)
    _emit_lines_to_printer(printer, lines)
    _post_feed_and_cut(printer)

# ------------------------------ Windows GDI backend ----------------------
class WindowsGDIPrinter:
    """
    Renders lines/tables to a single PIL image (width=576 px), then sends to the
    selected Windows printer using GDI. Requires a normal Windows printer driver.
    """
    def __init__(self, printer_name: str) -> None:
        if not _WIN_GDI_OK:
            raise RuntimeError("pywin32 not available for Windows GDI printing")
        self.printer_name = printer_name

    # --- helpers to render into a single image ---
    def _lines_to_image(self, lines: Sequence[str]) -> Image.Image:
        if not _BITMAP_OK:
            # very minimal fallback if arabic_bitmap is unavailable
            from PIL import Image, ImageDraw, ImageFont
            font = ImageFont.load_default()
            heights = []
            tmp = Image.new("L", (1,1), 255); dr = ImageDraw.Draw(tmp)
            for raw in lines:
                txt = raw
                if txt.startswith(">>"):  # strip tags for fallback
                    txt = txt.split(" ",1)[1] if " " in txt else ""
                _,_,w,h = dr.multiline_textbbox((0,0), txt, font=font)
                heights.append(h+6)
            total_h = max(1, sum(heights))
            img = Image.new("L", (PAPER_PX, total_h), 255); dr = ImageDraw.Draw(img)
            y=0
            for i, raw in enumerate(lines):
                txt = raw
                align = "left"
                if raw.startswith(">>C "): align, txt = "center", raw[4:]
                elif raw.startswith(">>R "): align, txt = "right",  raw[4:]
                elif raw.startswith(">>L "): align, txt = "left",   raw[4:]
                _,_,w,h = dr.multiline_textbbox((0,0), txt, font=font)
                if align == "center": x = (PAPER_PX - w)//2
                elif align == "right": x = PAPER_PX - w - 8
                else: x = 8
                dr.text((x,y), txt, 0, font=font)
                y += heights[i]
            return img.convert("1")

        # Bitmap path (preferred)
        from PIL import Image
        rows: list[Image.Image] = []
        for raw in lines:
            align = "left"; txt = raw
            if raw.startswith(">>C "): align, txt = "center", raw[4:]
            elif raw.startswith(">>R "): align, txt = "right",  raw[4:]
            elif raw.startswith(">>L "): align, txt = "left",   raw[4:]
            # Render each line as a raster (tight vertical spacing)
            font = load_font(size=28)
            line_img = render_line_bitmap(txt, paper_px=PAPER_PX, font=font, align=align)
            rows.append(line_img)
        total_h = sum(im.height for im in rows)
        canvas = Image.new("1", (PAPER_PX, total_h), 1)
        y=0
        for im in rows:
            canvas.paste(im, (0,y))
            y += im.height
        return canvas

    def _table_to_image(self, headers, rows, *, footer_rows=None,
                        font_size: int = 30,
                        col_widths_px=None,
                        col_align=("left","center","right","right"),
                        cell_pad=(8,4),
                        draw_borders=True) -> Image.Image:
        if not _BITMAP_OK:
            # fallback simple text table
            from PIL import Image, ImageDraw, ImageFont
            font = ImageFont.load_default()
            text_lines = [" | ".join(headers)] + [" | ".join(map(str,r)) for r in rows]
            if footer_rows: text_lines += [" | ".join(map(str,r)) for r in footer_rows]
            tmp = Image.new("L",(1,1),255); dr = ImageDraw.Draw(tmp)
            heights = []
            for t in text_lines:
                _,_,w,h = dr.textbbox((0,0), t, font=font)
                heights.append(h+6)
            canvas = Image.new("L",(PAPER_PX,sum(heights)),255); dr = ImageDraw.Draw(canvas)
            y=0
            for i,t in enumerate(text_lines):
                dr.text((8,y), t, 0, font=font)
                y += heights[i]
            return canvas.convert("1")

        font_body = load_font(size=font_size)
        font_header = load_font(size=font_size, bold=True)
        font_footer = load_font(size=font_size, bold=True)
        return render_table_bitmap(
            headers, rows,
            footer_rows=footer_rows,
            paper_px=PAPER_PX,
            col_widths_px=col_widths_px,
            font_body=font_body, font_header=font_header, font_footer=font_footer,
            cell_pad=cell_pad, draw_borders=draw_borders,
            col_align=col_align,
        )

    # --- public API used by our flow ---
    def print_lines(self, lines: Sequence[str]) -> None:
        img = self._lines_to_image(lines)
        self._print_image(img)

    def print_table(self, headers, rows, *, footer_rows=None, font_size=30,
                    col_widths_px=None, col_align=("left","center","right","right"),
                    cell_pad=(8,4), draw_borders=True) -> None:
        img = self._table_to_image(headers, rows, footer_rows=footer_rows,
                                   font_size=font_size, col_widths_px=col_widths_px,
                                   col_align=col_align, cell_pad=cell_pad, draw_borders=draw_borders)
        self._print_image(img)

    def cut(self):  # no direct cutter via GDI; many drivers auto-cut at page end
        pass

    # --- GDI actual print ---
    def _print_image(self, img) -> None:
        # Convert 1-bit to RGB for stable GDI blit
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Start print job
        hprinter = win32print.OpenPrinter(self.printer_name)
        try:
            # Set to portrait, no scaling margins (driver decides)
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(self.printer_name)
            hdc.StartDoc("BeirutPOS Ticket")
            hdc.StartPage()

            # Query printable area
            HORZRES = hdc.GetDeviceCaps(win32con.HORZRES)
            VERTRES = hdc.GetDeviceCaps(win32con.VERTRES)

            # Scale image to full printable width; calc height proportionally
            w = HORZRES
            h = int(img.height * (w / img.width))
            # If too long, we still blit; driver will paginate / cut as per length
            dib = ImageWin.Dib(img)
            dib.draw(hdc.GetHandleOutput(), (0, 0, w, h))

            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
        finally:
            win32print.ClosePrinter(hprinter)

# ------------------------- choose backend(s) -----------------------------
def _find_thermal_printer():
    """Legacy single backend (kept for fallback paths)."""
    if _DISABLE_ESCPOS: return None
    if RawUsbEscpos is not None and _RAW_USB_OK:
        try: return RawUsbEscpos(vid=0x0483, pid=0x5743, interface=0)
        except Exception as e: _log_printer_error("RawUsbEscpos failed", e)
    if not _ESCPOS_OK or Usb is None: return None
    try: return Usb(0x0416, 0x5011, interface=0, in_ep=0x82, out_ep=0x01)
    except Exception: pass
    return _try_usb_printer() or _try_file_printer()

def _make_backend_windows(printer_name: Optional[str]):
    if not _IS_WINDOWS or not _WIN_GDI_OK: return None
    if not printer_name: return None
    try:
        return WindowsGDIPrinter(printer_name)
    except Exception as e:
        _log_printer_error(f"Windows GDI backend init failed for '{printer_name}'", e)
        return None

# ================================================= printing flows ========
def _print_escpos_receipt(
    printer,
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    total: int,
    method: str,
    cashier: str,
) -> None:
    head = _build_receipt_header_meta(table_code, cashier)
    _emit_lines_to_printer(printer, head)

    headers, rows, calc_sub, total_qty = _build_items_table(items)

    foot: list[list[str]] = []
    if discount and float(discount) > 0:
        foot.append(["الخصم", "", "", f"-{_format_currency_simple(discount)}"])
    foot.append(["الإجمالي", "", "", _format_currency_simple(total)])

    if hasattr(printer, "print_table"):
        printer.print_table(
            headers, rows,
            footer_rows=foot,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT","28")),  # slightly smaller headers
            col_widths_px=COLS_RECEIPT,
            col_align=("left", "center", "right", "right"),
            cell_pad=(CELL_PAD_X, CELL_PAD_Y),
            draw_borders=True,
        )
    else:
        _emit_lines_to_printer(printer,
            [" | ".join(headers)] +
            [" | ".join(map(str, r)) for r in rows] +
            [" | ".join(map(str, r)) for r in foot]
        )

    # polite footer
    _print_escpos_lines(printer, [">>C شكراً لزيارتكم", ">>C Thank you for visiting!"])

def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]) -> None:
    now = datetime.now().strftime("%H:%M")
    _emit_lines_to_printer(printer, [
        ">>C " + f"{now}  |  {table_code}",
        _draw_line("═"),
    ])
    headers, rows = _build_bar_table(items)
    if hasattr(printer, "print_table"):
        printer.print_table(
            headers, rows,
            footer_rows=None,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT","28")),
            col_widths_px=COLS_BAR,
            col_align=("left", "center"),
            cell_pad=(CELL_PAD_X, CELL_PAD_Y),
            draw_borders=True,
        )
    else:
        _emit_lines_to_printer(printer, [" | ".join(headers)] + [" | ".join(map(str, r)) for r in rows])
    _print_escpos_lines(printer, [_draw_line("═")])

# ============================================= collapse & service ========
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
            grouped[key] = {"name": name, "qty": qty, "unit_price": unit_price, "total_cents": total_cents, "note": note}
    return list(grouped.values())

class PrinterService:
    """
    Dual-printer support:
      - On Windows: set env BEIRUT_WIN_PRINTER_BAR / BEIRUT_WIN_PRINTER_CASHIER to printer names.
      - Else: falls back to ESC/POS single backend (legacy).
    """
    def __init__(self) -> None:
        _ensure_dirs()
        self._bar_backend = None
        self._cash_backend = None
        self._escpos_printer = None
        self._init_backends()

    def _init_backends(self) -> None:
        # Windows dual-printer path
        bar_name = os.getenv("BEIRUT_WIN_PRINTER_BAR", "").strip()
        cash_name = os.getenv("BEIRUT_WIN_PRINTER_CASHIER", "").strip()
        if _IS_WINDOWS and _WIN_GDI_OK and (bar_name or cash_name):
            if bar_name:
                self._bar_backend = _make_backend_windows(bar_name)
            if cash_name:
                self._cash_backend = _make_backend_windows(cash_name)
            _log(f"Windows GDI printers -> BAR: {bar_name or '-'} | CASHIER: {cash_name or '-'}")
        else:
            # legacy single backend
            self._escpos_printer = _find_thermal_printer()
            _log("Using ESC/POS backend")

    def update_printers(self, bar: Optional[str], cash: Optional[str]) -> None:
        """
        If you expose UI to save printer names, set env and re-init.
        """
        try:
            if hasattr(self._escpos_printer, "close"): self._escpos_printer.close()  # type: ignore
        except Exception: ...
        # Allow override names from args
        if bar: os.environ["BEIRUT_WIN_PRINTER_BAR"] = bar
        if cash: os.environ["BEIRUT_WIN_PRINTER_CASHIER"] = cash
        self._bar_backend = None; self._cash_backend = None; self._escpos_printer = None
        self._init_backends()

    def _current_printer_cashier(self):
        return self._cash_backend or self._escpos_printer

    def _current_printer_bar(self):
        return self._bar_backend or self._escpos_printer

    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        data = _collapse_items(items)
        prn = self._current_printer_bar()
        if prn: _print_escpos_bar_ticket(prn, table_code, data)
        return True

    def print_cashier_receipt(self, table_code: str, items: Iterable, subtotal: int, discount: int, total: int, method: str, cashier: str, service: int | None = None, tax: int | None = None, *, discount_label: str | None = None) -> bool:
        data = _collapse_items(items)
        prn = self._current_printer_cashier()
        if prn: _print_escpos_receipt(prn, table_code, data, subtotal, discount, total, method, cashier)
        return True

printer = PrinterService()

def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)

bus.subscribe("printers_changed", _apply_printer_settings)
