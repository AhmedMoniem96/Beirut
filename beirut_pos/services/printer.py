"""Receipt/ticket PDF renderer for 80mm thermal printers (XP-80C) with Arabic shaping.
ULTIMATE FIX: Uses ESC/POS direct commands - bypasses PDF completely for thermal printers.
"""

from __future__ import annotations
import os, sys, subprocess, shutil
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional

# ---------------- ESC/POS availability ----------------
try:
    from escpos.printer import Usb, Network, File, Win32Raw
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:
    _ESCPOS_OK = False

from ..core.db import setting_get
from ..core.paths import DATA_DIR
from ..utils.currency import format_pounds
from ..core.bus import bus

# ---------------- Paths & constants ----------------
_OUTPUT_ROOT  = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR      = _OUTPUT_ROOT / "bar_tickets"
# Set this to "1" in env (or PyCharm Run Config) to force text fallback on dev machines
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

def _ensure_dirs():
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)

# ---------------- Arabic shaping ----------------
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR_OK = True
except Exception:
    _AR_OK = False

def _set_ar_codepage(p) -> None:
    """Select an Arabic-capable codepage for python-escpos 3.x."""
    for cp in ("CP864", "CP720", "CP1256"):
        try:
            fn = getattr(p, "charcode", None)
            if callable(fn):
                fn(cp)  # type: ignore[misc]
                print(f"[DEBUG] ESC/POS codepage set to {cp}")
                return
        except Exception as e:
            print(f"[DEBUG] Failed to set codepage {cp}: {e}")
    # If none worked, printing may be garbled; still continue.

def _shape_ar_escpos(text: str) -> str:
    """Arabic shaping for ESC/POS printers (DO NOT reverse again)."""
    if not text:
        return ""
    if not _AR_OK:
        return text
    reshaped = arabic_reshaper.reshape(text)
    return reshaped  # FIXED: Remove get_display() for ESC/POS

def _shape_ar_textfile(text: str) -> str:
    """Arabic shaping for saving readable text files (optional)."""
    if not text:
        return ""
    if not _AR_OK:
        return text[::-1]
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)  # usually fine for viewing in editors

# ✅ Backward compatibility alias for any old calls
_shape_arabic = _shape_ar_textfile

def _format_currency_cents(cents: int | float, currency: str) -> str:
    try:
        return format_pounds(int(round(float(cents))), currency)
    except Exception:
        return f"{cents} {currency}"

# ---------------- Helpers ----------------
def _can_system_print(printer_name: str) -> bool:
    """Check if CUPS can print to a given printer on Linux."""
    if not printer_name or not shutil.which("lp"):
        return False
    try:
        out = subprocess.check_output(["lpstat", "-a"], text=True)
        return printer_name in out
    except Exception:
        return False

# ---------------- ESC/POS Thermal Printer (THE REAL FIX) ----------------
def _get_escpos_printer(printer_name: str):
    """Get ESC/POS printer instance based on platform and printer name."""
    if not _ESCPOS_OK or _DISABLE_ESCPOS:
        return None
    try:
        if sys.platform.startswith("win"):
            # Windows: Use Win32Raw with printer name (no pyusb needed)
            return Win32Raw(printer_name)

        # Linux: Prefer direct device file (no pyusb needed)
        if os.path.exists("/dev/usb/lp0"):
            return File("/dev/usb/lp0")

        # If no device file, optionally try raw USB VID/PID pairs
        try:
            # Only present if python-escpos USB backend installed
            Usb  # type: ignore  # reference to ensure import exists
        except Exception:
            return None

        usb_ids = [
            (0x04b8, 0x0e15),  # Epson TM-T20
            (0x0416, 0x5011),  # XP-80C common ID
            (0x0519, 0x0003),  # Generic thermal
            (0x28e9, 0x0289),  # Common POS printer
        ]
        for vid, pid in usb_ids:
            try:
                return Usb(vid, pid)
            except Exception:
                continue

        return None
    except Exception as e:
        print(f"[DEBUG] Error initializing ESC/POS printer: {e}")
        return None

def _print_escpos_bar_ticket(table_code: str, items: List[dict], printer_name: str) -> bool:
    """Print bar ticket using ESC/POS commands (DIRECT TO PRINTER)"""
    print(f"[DEBUG] _print_escpos_bar_ticket called for table {table_code}")

    p = _get_escpos_printer(printer_name)
    if not p:
        print("[DEBUG] ESC/POS printer not available, returning False")
        return False

    # Try to open device early to avoid internal assertions
    try:
        fn = getattr(p, "open", None)
        if callable(fn):
            fn()
    except Exception as e:
        print(f"[DEBUG] Cannot open ESC/POS device: {e}")
        return False

    try:
        currency = setting_get("currency", "EGP") or "EGP"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        print(f"[DEBUG] Starting ESC/POS print...")

        # Initialize printer + Arabic codepage
        _set_ar_codepage(p)
        p.set(align='right')  # alignment only

        # Header
        p.set(align='center', text_type='B', width=2, height=2)
        p.text(_shape_ar_escpos("تذكرة البار") + "\n")

        # Info
        p.set(align='right', text_type='NORMAL', width=1, height=1)
        p.text(_shape_ar_escpos(f"الطاولة: {table_code}") + "\n")
        p.text(_shape_ar_escpos(f"وقت الإصدار: {ts}") + "\n")

        p.set(align='center')
        p.text("=" * 32 + "\n")

        # Table header
        p.set(align='right', text_type='NORMAL')
        p.text(_shape_ar_escpos("الصنف               الكمية    الإجمالي") + "\n")
        p.set(align='center')
        p.text("-" * 32 + "\n")

        # Items
        for it in items:
            name = _shape_ar_escpos(str(it["name"]))
            qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.1f}"
            total = _format_currency_cents(it["total_cents"], currency)

            p.set(align='left')
            p.text(name)
            spaces_needed = 32 - len(name) - len(str(qty)) - len(total) - 4
            if spaces_needed < 1:
                spaces_needed = 1
            p.text(" " * spaces_needed + f"{qty}    {total}\n")

            note = (it.get("note") or "").strip()
            if note:
                p.set(align='right')
                p.text(_shape_ar_escpos(f"ملاحظة: {note}") + "\n")

        p.set(align='center')
        p.text("=" * 32 + "\n")
        p.text("\n\n")

        # Cut
        p.cut()

        print("[DEBUG] ESC/POS print completed successfully")
        return True

    except Exception as e:
        print(f"[DEBUG] ESC/POS print error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            p.close()
        except Exception:
            pass

def _print_escpos_cashier_receipt(
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    service: int,
    tax: int,
    total: int,
    method: str,
    cashier: str,
    printer_name: str
) -> bool:
    """Print cashier receipt using ESC/POS commands"""
    p = _get_escpos_printer(printer_name)
    if not p:
        return False

    # Try to open device early to avoid internal assertions
    try:
        fn = getattr(p, "open", None)
        if callable(fn):
            fn()
    except Exception as e:
        print(f"[DEBUG] Cannot open ESC/POS device: {e}")
        return False

    try:
        currency = setting_get("currency", "EGP") or "EGP"
        company = setting_get("company_name", "Beirut") or "Beirut"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Initialize printer and Arabic codepage
        _set_ar_codepage(p)
        p.set(align='right')

        # Header
        p.set(align='center', text_type='B', width=2, height=2)
        p.text(_shape_ar_escpos(company) + "\n")

        # Info
        p.set(align='right', text_type='NORMAL', width=1, height=1)
        p.text(_shape_ar_escpos(f"الطاولة: {table_code} — الكاشير: {cashier}") + "\n")
        p.text(_shape_ar_escpos(f"وقت الإصدار: {ts}") + "\n")
        p.text(_shape_ar_escpos(f"طريقة الدفع: {method}") + "\n")

        p.set(align='center')
        p.text("=" * 32 + "\n")

        # Table header
        p.set(align='right')
        p.text(_shape_ar_escpos("الصنف           الكمية  السعر  الإجمالي") + "\n")
        p.set(align='center')
        p.text("-" * 32 + "\n")

        # Items
        for it in items:
            name = _shape_ar_escpos(str(it["name"]))
            qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.1f}"
            unit = _format_currency_cents(it["unit_price"], currency)
            item_total = _format_currency_cents(it["total_cents"], currency)

            p.set(align='left')
            p.text(name)
            numbers_str = f"{qty}  {unit}  {item_total}"
            spaces_needed = 32 - len(name) - len(numbers_str) - 2
            if spaces_needed < 1:
                spaces_needed = 1
            p.text(" " * spaces_needed + numbers_str + "\n")

            note = (it.get("note") or "").strip()
            if note:
                p.set(align='right')
                p.text(_shape_ar_escpos(f"ملاحظة: {note}") + "\n")

        p.set(align='center')
        p.text("-" * 32 + "\n")

        # Totals
        p.set(align='right', text_type='NORMAL')
        p.text(_shape_ar_escpos(f"الإجمالي قبل الخصم: {_format_currency_cents(subtotal, currency)}") + "\n")
        if discount:
            p.text(_shape_ar_escpos(f"الخصم: {_format_currency_cents(discount, currency)}") + "\n")
        if service:
            p.text(_shape_ar_escpos(f"الخدمة: {_format_currency_cents(service, currency)}") + "\n")
        if tax:
            p.text(_shape_ar_escpos(f"الضريبة: {_format_currency_cents(tax, currency)}") + "\n")

        p.set(align='center')
        p.text("=" * 32 + "\n")

        # Final total
        p.set(align='right', text_type='B')
        p.text(_shape_ar_escpos(f"الصافي: {_format_currency_cents(total, currency)}") + "\n")

        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text("=" * 32 + "\n")
        p.text(_shape_ar_escpos("شكراً لزيارتكم") + " 💛\n")
        p.text("\n\n\n")

        # Cut
        p.cut()

        return True

    except Exception as e:
        print(f"ESC/POS receipt print error: {e}")
        return False
    finally:
        try:
            p.close()
        except Exception:
            pass

# ---------------- Fallback: Save as text file if ESC/POS fails ----------------
def _save_receipt_as_text(
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    service: int,
    tax: int,
    total: int,
    method: str,
    cashier: str,
    is_bar: bool = False
) -> Path:
    """Save receipt as text file with proper Arabic shaping for viewing."""
    _ensure_dirs()

    currency = setting_get("currency", "EGP") or "EGP"
    company = setting_get("company_name", "Beirut") or "Beirut"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []

    if is_bar:
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile("تذكرة البار").center(40))
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile(f"الطاولة: {table_code}"))
        lines.append(_shape_ar_textfile(f"وقت الإصدار: {ts}"))
    else:
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile(company).center(40))
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile(f"الطاولة: {table_code}"))
        lines.append(_shape_ar_textfile(f"الكاشير: {cashier}"))
        lines.append(_shape_ar_textfile(f"وقت الإصدار: {ts}"))
        lines.append(_shape_ar_textfile(f"طريقة الدفع: {method}"))

    lines.append("-" * 40)

    for it in items:
        name = _shape_ar_textfile(str(it["name"]))
        qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.2f}"
        item_total = _format_currency_cents(it["total_cents"], currency)

        lines.append(f"{name}")
        lines.append(_shape_ar_textfile(f"  الكمية: {qty}  |  الإجمالي: {item_total}"))

        note = (it.get("note") or "").strip()
        if note:
            lines.append(_shape_ar_textfile(f"  ملاحظة: {note}"))

    lines.append("-" * 40)

    if not is_bar:
        lines.append(_shape_ar_textfile(f"الإجمالي قبل الخصم: {_format_currency_cents(subtotal, currency)}"))
        if discount:
            lines.append(_shape_ar_textfile(f"الخصم: {_format_currency_cents(discount, currency)}"))
        if service:
            lines.append(_shape_ar_textfile(f"الخدمة: {_format_currency_cents(service, currency)}"))
        if tax:
            lines.append(_shape_ar_textfile(f"الضريبة: {_format_currency_cents(tax, currency)}"))
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile(f"الصافي: {_format_currency_cents(total, currency)}"))
        lines.append("=" * 40)
        lines.append(_shape_ar_textfile("شكراً لزيارتكم 💛").center(40))

    lines.append("\n" * 3)

    folder = _BAR_DIR if is_bar else _RECEIPTS_DIR
    filename = f"{datetime.now():%Y%m%d-%H%M%S}-{'bar' if is_bar else 'cashier'}-{table_code}.txt"
    target = folder / filename

    target.write_text("\n".join(lines), encoding='utf-8')
    return target

# ---------------- Public API ----------------
BAR_PRINTER_NAME     = "XP-80C"  # Change to your actual printer name
CASHIER_PRINTER_NAME = "XP-80C"  # Change to your actual printer name

class PrinterService:
    __slots__ = ("bar_printer", "cashier_printer")

    def __init__(self):
        _ensure_dirs()
        self.bar_printer = BAR_PRINTER_NAME
        self.cashier_printer = CASHIER_PRINTER_NAME
        self.reload_from_settings()

    def reload_from_settings(self):
        bar  = (setting_get("bar_printer","") or "").strip()
        cash = (setting_get("cashier_printer","") or "").strip()
        if bar:  self.bar_printer = bar
        if cash: self.cashier_printer = cash

    def update_printers(self, bar: Optional[str], cashier: Optional[str]):
        if bar is not None:
            self.bar_printer = bar.strip() or BAR_PRINTER_NAME
        if cashier is not None:
            self.cashier_printer = cashier.strip() or CASHIER_PRINTER_NAME

    def print_bar_ticket(self, table_code: str, items: Iterable) -> Path:
        data = _collapse_items(items)

        # Try ESC/POS first
        if _ESCPOS_OK and not _DISABLE_ESCPOS:
            success = _print_escpos_bar_ticket(table_code, data, self.bar_printer)
            if success:
                # Save text file for records, DON'T send to printer again
                return _save_receipt_as_text(table_code, data, 0, 0, 0, 0, 0, "", "", is_bar=True)

        # Fallback ONLY if ESC/POS failed: save and (optionally) CUPS-print text file
        txt = _save_receipt_as_text(table_code, data, 0, 0, 0, 0, 0, "", "", is_bar=True)

        if sys.platform.startswith("win"):
            try:
                os.startfile(str(txt), "print")  # type: ignore
            except Exception:
                pass
        else:
            try:
                if _can_system_print(self.bar_printer):
                    subprocess.Popen(["lp", "-d", self.bar_printer, str(txt)])
            except Exception:
                pass

        return txt

    def print_cashier_receipt(
        self, table_code: str, items: Iterable,
        subtotal: int, discount: int, total: int,
        method: str, cashier: str, service: int | None = None, tax: int | None = None,
    ) -> Path:
        data = _collapse_items(items)
        svc = service or 0
        tx = tax or 0

        # Try ESC/POS first
        if _ESCPOS_OK and not _DISABLE_ESCPOS:
            success = _print_escpos_cashier_receipt(
                table_code, data, subtotal, discount, svc, tx, total, method, cashier,
                self.cashier_printer
            )
            if success:
                # Save text file for records, DON'T send to printer again
                return _save_receipt_as_text(
                    table_code, data, subtotal, discount, svc, tx, total, method, cashier, is_bar=False
                )

        # Fallback ONLY if ESC/POS failed: save and (optionally) CUPS-print text file
        txt = _save_receipt_as_text(
            table_code, data, subtotal, discount, svc, tx, total, method, cashier, is_bar=False
        )

        if sys.platform.startswith("win"):
            try:
                os.startfile(str(txt), "print")  # type: ignore
            except Exception:
                pass
        else:
            try:
                if _can_system_print(self.cashier_printer):
                    subprocess.Popen(["lp", "-d", self.cashier_printer, str(txt)])
            except Exception:
                pass

        return txt

printer = PrinterService()

def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)

bus.subscribe("printers_changed", _apply_printer_settings)

# ---------------- Data shaping with quantity grouping ----------------
def _collapse_items(items: Iterable) -> List[dict]:
    """Collapse items and GROUP identical products together (e.g., 2x same item)"""
    grouped: dict[tuple, dict] = {}

    for it in items:
        name = getattr(it, "product", str(it))
        unit_price = int(getattr(it, "unit_price_cents", 0) or 0)
        note = (getattr(it, "note", "") or "").strip()

        # Create unique key: name + unit_price + note
        key = (name, unit_price, note)

        if key in grouped:
            # Add quantity to existing item
            grouped[key]["qty"] += float(getattr(it, "qty", 1.0) or 1.0)
            grouped[key]["total_cents"] += int(getattr(it, "total_cents", 0) or 0)
        else:
            # New item
            grouped[key] = {
                "name": name,
                "qty": float(getattr(it, "qty", 1.0) or 1.0),
                "unit_price": unit_price,
                "total_cents": int(getattr(it, "total_cents", 0) or 0),
                "note": note,
            }

    return list(grouped.values())