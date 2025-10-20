"""Receipt/ticket PDF renderer for 80mm thermal printers (XP-80C) with Arabic shaping.
ULTIMATE FIX: Uses ESC/POS direct commands - bypasses PDF completely for thermal printers.
"""

from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional

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

def _shape_arabic(text: str) -> str:
    """Shape Arabic text for proper display on thermal printers"""
    if not text:
        return ""
    if not _AR_OK:
        return text

    # Reshape connects Arabic letters properly
    reshaped = arabic_reshaper.reshape(text)
    # get_display handles RTL ordering
    return get_display(reshaped)

def _format_currency_cents(cents: int | float, currency: str) -> str:
    try:
        return format_pounds(int(round(float(cents))), currency)
    except Exception:
        return f"{cents} {currency}"

# ---------------- ESC/POS Thermal Printer (THE REAL FIX) ----------------
def _get_escpos_printer(printer_name: str):
    """Get ESC/POS printer instance based on platform and printer name"""
    if not _ESCPOS_OK:
        return None

    try:
        if sys.platform.startswith("win"):
            # Windows: Use Win32Raw with printer name
            return Win32Raw(printer_name)
        else:
            # Linux: Try USB first, then network
            # Common thermal printer USB IDs (XP-80C and similar)
            usb_ids = [
                (0x04b8, 0x0e15),  # Epson TM-T20
                (0x0416, 0x5011),  # XP-80C common ID
                (0x0519, 0x0003),  # Generic thermal
                (0x28e9, 0x0289),  # Common POS printer
            ]

            for vid, pid in usb_ids:
                try:
                    return Usb(vid, pid)
                except (USBNotFoundError, Exception):
                    continue

            # Fallback to file-based printing
            return File(f"/dev/usb/lp0")
    except Exception as e:
        print(f"Error initializing ESC/POS printer: {e}")
        return None

def _print_escpos_bar_ticket(table_code: str, items: List[dict], printer_name: str) -> bool:
    """Print bar ticket using ESC/POS commands (DIRECT TO PRINTER)"""
    p = _get_escpos_printer(printer_name)
    if not p:
        return False

    try:
        currency = setting_get("currency", "EGP") or "EGP"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Set Arabic codepage
        p.charcode(code='ARABIC')

        # Header - centered and bold
        p.set(align='center', text_type='B', width=2, height=2)
        p.text(_shape_arabic("تذكرة البار") + "\n")

        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text(_shape_arabic(f"الطاولة: {table_code}") + "\n")
        p.text(_shape_arabic(f"وقت: {ts}") + "\n")
        p.text("=" * 32 + "\n")

        # Table header
        p.set(align='right', text_type='NORMAL')
        p.text(_shape_arabic("الإجمالي    الكمية    الصنف") + "\n")
        p.text("-" * 32 + "\n")

        # Items
        for it in items:
            name = _shape_arabic(str(it["name"])[:20])  # Limit name length
            qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.1f}"
            total = _format_currency_cents(it["total_cents"], currency)

            # Right-aligned for RTL
            p.set(align='right')
            line = f"{total}  {qty}  {name}"
            p.text(line + "\n")

            note = (it.get("note") or "").strip()
            if note:
                p.text("  " + _shape_arabic(f"ملاحظة: {note}") + "\n")

        p.text("=" * 32 + "\n")
        p.text("\n\n")

        # Cut paper
        p.cut()

        return True

    except Exception as e:
        print(f"ESC/POS print error: {e}")
        return False
    finally:
        try:
            p.close()
        except:
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

    try:
        currency = setting_get("currency", "EGP") or "EGP"
        company = setting_get("company_name", "Beirut") or "Beirut"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Set Arabic codepage
        p.charcode(code='ARABIC')

        # Logo (if available)
        logo_path = Path((setting_get("logo_path", "") or "").strip())
        if logo_path.exists():
            try:
                p.set(align='center')
                p.image(str(logo_path), impl='bitImageColumn', center=True)
                p.text("\n")
            except:
                pass

        # Header
        p.set(align='center', text_type='B', width=2, height=2)
        p.text(_shape_arabic(company) + "\n")

        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text(_shape_arabic(f"الطاولة: {table_code}") + "\n")
        p.text(_shape_arabic(f"الكاشير: {cashier}") + "\n")
        p.text(_shape_arabic(f"وقت: {ts}") + "\n")
        p.text(_shape_arabic(f"طريقة الدفع: {method}") + "\n")
        p.text("=" * 32 + "\n")

        # Table header
        p.set(align='right')
        p.text(_shape_arabic("الإجمالي  السعر  الكمية  الصنف") + "\n")
        p.text("-" * 32 + "\n")

        # Items
        for it in items:
            name = _shape_arabic(str(it["name"])[:15])
            qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.1f}"
            unit = _format_currency_cents(it["unit_price"], currency)[:8]
            item_total = _format_currency_cents(it["total_cents"], currency)[:10]

            p.set(align='right')
            line = f"{item_total} {unit} {qty} {name}"
            p.text(line + "\n")

            note = (it.get("note") or "").strip()
            if note:
                p.text("  " + _shape_arabic(f"ملاحظة: {note}") + "\n")

        p.text("-" * 32 + "\n")

        # Totals
        p.set(align='right', text_type='NORMAL')
        p.text(_shape_arabic(f"الإجمالي قبل الخصم: {_format_currency_cents(subtotal, currency)}") + "\n")

        if discount:
            p.text(_shape_arabic(f"الخصم: {_format_currency_cents(discount, currency)}") + "\n")
        if service:
            p.text(_shape_arabic(f"الخدمة: {_format_currency_cents(service, currency)}") + "\n")
        if tax:
            p.text(_shape_arabic(f"الضريبة: {_format_currency_cents(tax, currency)}") + "\n")

        p.text("=" * 32 + "\n")

        # Final total - bold
        p.set(align='right', text_type='B', width=2, height=2)
        p.text(_shape_arabic(f"الصافي: {_format_currency_cents(total, currency)}") + "\n")

        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text("=" * 32 + "\n")
        p.text(_shape_arabic("شكراً لزيارتكم") + " 💛\n")
        p.text("\n\n\n")

        # Cut paper
        p.cut()

        return True

    except Exception as e:
        print(f"ESC/POS receipt print error: {e}")
        return False
    finally:
        try:
            p.close()
        except:
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
    """Save receipt as text file with proper Arabic encoding"""
    _ensure_dirs()

    currency = setting_get("currency", "EGP") or "EGP"
    company = setting_get("company_name", "Beirut") or "Beirut"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    if is_bar:
        lines.append("=" * 40)
        lines.append(_shape_arabic("تذكرة البار").center(40))
        lines.append("=" * 40)
        lines.append(_shape_arabic(f"الطاولة: {table_code}"))
        lines.append(_shape_arabic(f"وقت الإصدار: {ts}"))
    else:
        lines.append("=" * 40)
        lines.append(_shape_arabic(company).center(40))
        lines.append("=" * 40)
        lines.append(_shape_arabic(f"الطاولة: {table_code}"))
        lines.append(_shape_arabic(f"الكاشير: {cashier}"))
        lines.append(_shape_arabic(f"وقت الإصدار: {ts}"))
        lines.append(_shape_arabic(f"طريقة الدفع: {method}"))

    lines.append("-" * 40)

    for it in items:
        name = _shape_arabic(str(it["name"]))
        qty = int(it["qty"]) if abs(it["qty"] - round(it["qty"])) < 1e-6 else f"{it['qty']:.2f}"
        item_total = _format_currency_cents(it["total_cents"], currency)

        lines.append(f"{name}")
        lines.append(f"  الكمية: {qty}  |  الإجمالي: {item_total}")

        note = (it.get("note") or "").strip()
        if note:
            lines.append(f"  ملاحظة: {_shape_arabic(note)}")

    lines.append("-" * 40)

    if not is_bar:
        lines.append(_shape_arabic(f"الإجمالي قبل الخصم: {_format_currency_cents(subtotal, currency)}"))
        if discount:
            lines.append(_shape_arabic(f"الخصم: {_format_currency_cents(discount, currency)}"))
        if service:
            lines.append(_shape_arabic(f"الخدمة: {_format_currency_cents(service, currency)}"))
        if tax:
            lines.append(_shape_arabic(f"الضريبة: {_format_currency_cents(tax, currency)}"))
        lines.append("=" * 40)
        lines.append(_shape_arabic(f"الصافي: {_format_currency_cents(total, currency)}"))
        lines.append("=" * 40)
        lines.append(_shape_arabic("شكراً لزيارتكم 💛").center(40))

    lines.append("\n" * 3)

    content = "\n".join(lines)

    folder = _BAR_DIR if is_bar else _RECEIPTS_DIR
    filename = f"{datetime.now():%Y%m%d-%H%M%S}-{'bar' if is_bar else 'cashier'}-{table_code}.txt"
    target = folder / filename

    target.write_text(content, encoding='utf-8')
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
        if _ESCPOS_OK:
            success = _print_escpos_bar_ticket(table_code, data, self.bar_printer)
            if success:
                # Still save text file for records
                return _save_receipt_as_text(table_code, data, 0, 0, 0, 0, 0, "", "", is_bar=True)

        # Fallback: save as text file
        txt = _save_receipt_as_text(table_code, data, 0, 0, 0, 0, 0, "", "", is_bar=True)

        # Try to print text file
        if sys.platform.startswith("win"):
            try:
                os.startfile(str(txt), "print")  # type: ignore
            except:
                pass
        else:
            try:
                subprocess.Popen(["lp", "-d", self.bar_printer, str(txt)])
            except:
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
        if _ESCPOS_OK:
            success = _print_escpos_cashier_receipt(
                table_code, data, subtotal, discount, svc, tx, total, method, cashier,
                self.cashier_printer
            )
            if success:
                # Still save text file for records
                return _save_receipt_as_text(
                    table_code, data, subtotal, discount, svc, tx, total, method, cashier, is_bar=False
                )

        # Fallback: save as text file
        txt = _save_receipt_as_text(
            table_code, data, subtotal, discount, svc, tx, total, method, cashier, is_bar=False
        )

        # Try to print text file
        if sys.platform.startswith("win"):
            try:
                os.startfile(str(txt), "print")  # type: ignore
            except:
                pass
        else:
            try:
                subprocess.Popen(["lp", "-d", self.cashier_printer, str(txt)])
            except:
                pass

        return txt

printer = PrinterService()

def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)

bus.subscribe("printers_changed", _apply_printer_settings)

# ---------------- Data shaping ----------------
def _collapse_items(items: Iterable) -> List[dict]:
    out: List[dict] = []
    for it in items:
        out.append({
            "name": getattr(it, "product", str(it)),
            "qty": float(getattr(it, "qty", 1.0) or 1.0),
            "unit_price": int(getattr(it, "unit_price_cents", 0) or 0),
            "total_cents": int(getattr(it, "total_cents", 0) or 0),
            "note": (getattr(it, "note", "") or "").strip(),
        })
    return out