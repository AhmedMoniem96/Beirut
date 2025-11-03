from __future__ import annotations
import glob, os, sys, re, math
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

try:
    from escpos.printer import File, Usb
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:
    _ESCPOS_OK = False
    class USBNotFoundError(Exception): ...
    Usb = None; File = None
    print("❌ python-escpos not installed")

from ..core.paths import DATA_DIR
from .arabic_codec import sanitize_line, shape_bidi_arabic, encode_for_printer
try:
    from .raw_usb_escpos import RawUsbEscpos
    _RAW_USB_OK = True
except ImportError:
    RawUsbEscpos = None  # type: ignore
    _RAW_USB_OK = False

from ..core.bus import bus

_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_LOG_PATH = _OUTPUT_ROOT / "printer.log"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

USB_PRINTER_IDS = [(0x0483,0x5743),(0x0416,0x5011),(0x04B8,0x0202),(0x04B8,0x0E15),(0x067B,0x2305)]
PAPER_WIDTH = 48

# === layout constants (keep in sync with RawUsbEscpos.render_table_bitmap) ===
COLS_RECEIPT = [348, 60, 84, 84]   # Item, Qty, Price, Total (sum=576)
COLS_BAR     = [456, 120]          # Item, Qty for bar ticket
CELL_PAD_X, CELL_PAD_Y = 8, 4      # table cell padding

# === util ===============================================================

def _ensure_dirs() -> None:
    for p in (_OUTPUT_ROOT,_RECEIPTS_DIR,_BAR_DIR): p.mkdir(parents=True, exist_ok=True)
    try: _LOG_PATH.touch(exist_ok=True)
    except Exception: pass

def _log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds"); print(msg)
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
                # keep ONLY the value unless tag_sugar=True
                out.append(val if not tag_sugar else f"سكر: {val}")
        else:
            out.append(seg)
    return out

def _draw_line(char: str = "─", width: int = PAPER_WIDTH) -> str:
    return char * width

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
    """
    Split by whitespace; for each long token, keep its first half.
    """
    out_tokens: list[str] = []
    for tok in text.split():
        if len(tok) > threshold:
            cut = (len(tok) + 1) // 2
            out_tokens.append(tok[:cut])
        else:
            out_tokens.append(tok)
    return " ".join(out_tokens)

def _fit_line_for_col(text: str, col_px: int) -> str:
    """
    1) Cut long tokens in half; 2) ellipsize to fit inside the *effective* pixel width:
       col_px - (2*CELL_PAD_X) - safety.
    """
    safety = 12
    effective_px = max(24, col_px - (2 * CELL_PAD_X) - safety)
    text = _halve_long_words(text, threshold=12)
    max_chars = _max_chars_for_px(effective_px)
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"

# === receipt header/meta (no 'order list' label) ========================

def _build_receipt_header_meta(table_code: str, cashier: str) -> List[str]:
    ts = datetime.now().strftime("%Y/%m/%d %H:%M")
    lines: List[str] = []
    # header
    lines.append(">>C " + ("╔" + "═" * 30 + "╗"))
    lines.append(">>C " + "║  كافيه بيروت  ║")
    lines.append(">>C " + "║    Cafe Beirut    ║")
    lines.append(">>C " + ("╚" + "═" * 30 + "╝"))
    # meta (right)
    lines.append(">>R " + f"التاريخ: {ts}")
    lines.append(">>R " + f"الطاولة: {table_code}")
    lines.append(">>R " + f"الكاشير: {cashier}")
    lines.append(_draw_line("═"))
    return lines

# === receipt items table (customizations only; NO sugar) =================

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
        # prevent overflow into qty col
        name_disp = _fit_line_for_col(name_disp, item_px)

        rows.append([
            name_disp,
            _format_qty(qty),
            _format_currency_simple(unit),
            _format_currency_simple(total),
        ])
        subtotal_calc += total
        total_qty += qty
    return headers, rows, subtotal_calc, total_qty

# === BAR: 2-col table (الصنف includes customizations + sugar VALUE ONLY) ===

def _build_bar_table(items: Sequence[dict]) -> tuple[list[str], list[list[str]]]:
    headers = ["الصنف", "الكمية"]
    rows: list[list[str]] = []

    item_px, qty_px = COLS_BAR

    for it in items:
        name = str(it["name"])
        qty  = _format_qty(float(it.get("qty", 0) or 0))
        # include sugar value only
        notes = _note_segments(it.get("note", ""), include_sugar=True, tag_sugar=False)
        name_disp = f"{name} ({'؛ '.join(notes)})" if notes else name
        name_disp = _fit_line_for_col(name_disp, item_px)
        rows.append([name_disp, qty])
    return headers, rows

# === printer plumbing ====================================================

class MockPrinter:
    def __init__(self, name: str="MockPrinter") -> None:
        self.name=name; self.buffer: list[str]=[]
    def text(self, d: str) -> None: self.buffer.append(d)
    def set(self, **kw) -> None: ...
    def cut(self) -> None: self.buffer.append("<CUT>")
    def _raw(self, b: bytes) -> None: self.buffer.append(f"<RAW {b.hex()}>")
    def close(self) -> None: self.buffer.append("<CLOSE>")

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

def _emit_lines_to_printer(printer, lines: Sequence[str]) -> None:
    if hasattr(printer, "print_lines"): printer.print_lines(list(lines)); return
    for ln in lines: printer.text(ln + "\n")

def _find_thermal_printer():
    if _DISABLE_ESCPOS: return None
    if RawUsbEscpos is not None and _RAW_USB_OK:
        try: return RawUsbEscpos(vid=0x0483, pid=0x5743, interface=0)
        except Exception as e: _log_printer_error("RawUsbEscpos failed", e)
    if not _ESCPOS_OK or Usb is None: return None
    try: return Usb(0x0416, 0x5011, interface=0, in_ep=0x82, out_ep=0x01)
    except Exception: pass
    return _try_usb_printer() or _try_file_printer()

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

def _print_escpos_lines(printer, lines: Sequence[str]) -> None:
    try: _setup_printer_arabic(printer)
    except Exception as e: _log_printer_error("Init wrapper failed", e)
    _emit_lines_to_printer(printer, lines)
    _post_feed_and_cut(printer)

# === printing flows ======================================================

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
    # header/meta (right-aligned)
    head = _build_receipt_header_meta(table_code, cashier)
    _emit_lines_to_printer(printer, head)

    # items table inside (customizations only; NO sugar)
    headers, rows, calc_sub, total_qty = _build_items_table(items)

    # footer rows INSIDE the table (no 'الإجمالي الفرعي')
    foot: list[list[str]] = []
    if discount and float(discount) > 0:
        foot.append(["الخصم", "", "", f"-{_format_currency_simple(discount)}"])
    foot.append(["الإجمالي", "", "", _format_currency_simple(total)])

    # full width table (match pixel widths with our fitters)
    if hasattr(printer, "print_table"):
        printer.print_table(
            headers, rows,
            footer_rows=foot,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT","30")),
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
    # centered time | table number (no labels)
    now = datetime.now().strftime("%H:%M")
    _emit_lines_to_printer(printer, [
        ">>C " + f"{now}  |  {table_code}",
        _draw_line("═"),
    ])

    # BAR table: الصنف (product + customizations + sugar VALUE) + الكمية
    headers, rows = _build_bar_table(items)

    if hasattr(printer, "print_table"):
        printer.print_table(
            headers, rows,
            footer_rows=None,
            font_size=int(os.getenv("BEIRUT_POS_TABLE_FONT","30")),
            col_widths_px=COLS_BAR,          # keep in sync with fitter
            col_align=("left", "center"),
            cell_pad=(CELL_PAD_X, CELL_PAD_Y),
            draw_borders=True,
        )
    else:
        _emit_lines_to_printer(printer, [" | ".join(headers)] + [" | ".join(map(str, r)) for r in rows])

    _print_escpos_lines(printer, [_draw_line("═")])

# === collapse, service ===================================================

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
    def __init__(self) -> None:
        _ensure_dirs(); self._escpos_printer = _find_thermal_printer()
    def update_printers(self, bar: Optional[str], cash: Optional[str]) -> None:
        try:
            if hasattr(self._escpos_printer, "close"): self._escpos_printer.close()  # type: ignore
        except Exception: ...
        self._escpos_printer = _find_thermal_printer()
    def _current_printer(self): return self._escpos_printer
    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        data = _collapse_items(items)
        prn = self._current_printer()
        if prn: _print_escpos_bar_ticket(prn, table_code, data)
        return True
    def print_cashier_receipt(self, table_code: str, items: Iterable, subtotal: int, discount: int, total: int, method: str, cashier: str, service: int | None = None, tax: int | None = None, *, discount_label: str | None = None) -> bool:
        data = _collapse_items(items)
        prn = self._current_printer()
        if prn: _print_escpos_receipt(prn, table_code, data, subtotal, discount, total, method, cashier)
        return True

printer = PrinterService()
def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None: printer.update_printers(bar, cash)
bus.subscribe("printers_changed", _apply_printer_settings)
