"""Receipt/ticket renderer for XP-80C thermal printers with proper formatting."""
from __future__ import annotations
import os, sys, subprocess, shutil, re, json, tempfile
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional
try:
    from importlib import metadata
except ImportError:  # pragma: no cover - Python < 3.8 fallback
    import importlib_metadata as metadata  # type: ignore

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
from . import texts
from .settings import get_client_name

# ---------------- Paths & constants ----------------
_OUTPUT_ROOT  = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR      = _OUTPUT_ROOT / "bar_tickets"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

# ---------------- XP-80C USB Configuration ----------------
XP80C_VENDOR_ID = 0x0416   # Xprinter vendor ID
XP80C_PRODUCT_ID = 0x5011  # XP-80C product ID

def _ensure_dirs():
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)

# ---------------- Arabic shaping ----------------
_AR_OK = False
_AR_ERROR: Exception | None = None
_AR_WARNED = False

def _version_tuple(version_str: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", version_str)]
    return tuple(parts) if parts else (0,)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    try:
        _reshaper_version = metadata.version("arabic-reshaper")
    except Exception:
        _reshaper_version = getattr(arabic_reshaper, "__version__", "0")

    if _version_tuple(_reshaper_version) < (2, 0, 0):
        print(f"[WARN] arabic-reshaper {_reshaper_version} detected; some features may not work optimally")

    _AR_OK = True
    _AR_ERROR = None
except Exception as exc:  # pragma: no cover - import-time guard
    _AR_ERROR = exc

def _warn_arabic_missing() -> None:
    global _AR_WARNED
    if _AR_WARNED:
        return
    _AR_WARNED = True
    reason = f" ({_AR_ERROR})" if _AR_ERROR else ""
    print(
        "[WARN] Arabic shaping disabled - install arabic-reshaper and python-bidi"
        f"{reason}"
    )

def _shape_ar_textfile(text: str) -> str:
    """Arabic shaping for thermal printers - reshape ONLY."""
    if not text:
        return ""
    if not _AR_OK:
        _warn_arabic_missing()
        return text
    try:
        # CRITICAL FIX: Reshape Arabic but DON'T apply bidi reversal
        reshaped = arabic_reshaper.reshape(text)
        return reshaped  # ← NO get_display()!
    except Exception as e:
        print(f"[WARN] Arabic reshaping failed: {e}")
        return text
_shape_arabic = _shape_ar_textfile

def _format_currency_cents(cents: int | float, currency: str) -> str:
    try:
        return format_pounds(int(round(float(cents))), currency)
    except Exception:
        return f"{cents} {currency}"

def _format_qty(qty: float) -> str:
    """Return a friendly quantity string (trim trailing zeros)."""
    rounded = round(qty)
    if abs(qty - rounded) < 1e-6:
        return str(int(rounded))
    return f"{qty:.2f}".rstrip("0").rstrip(".")

def _note_segments(note: str) -> list[str]:
    """Split composite notes (sugar level, customisations) into bullet-friendly parts."""
    if not note:
        return []
    cleaned = note.replace("\n", " ")
    parts = [seg.strip(" ؛-•") for seg in cleaned.split("؛")]
    return [seg for seg in parts if seg]

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

def _convert_html_to_pdf(html_path: Path) -> Optional[Path]:
    """Convert HTML to PDF for better printing support"""
    try:
        import pdfkit
        pdf_path = html_path.with_suffix('.pdf')

        # Configuration for 80mm receipt
        options = {
            'page-size': 'Custom',
            'page-width': '80mm',
            'page-height': '297mm',  # A4 height for dynamic content
            'margin-top': '0mm',
            'margin-right': '0mm',
            'margin-bottom': '0mm',
            'margin-left': '0mm',
            'encoding': "UTF-8",
            'no-outline': None,
            'disable-smart-shrinking': None,
            'print-media-type': None,
        }

        pdfkit.from_file(str(html_path), str(pdf_path), options=options)
        return pdf_path
    except ImportError:
        print("[DEBUG] pdfkit not available, skipping PDF conversion")
        return None
    except Exception as e:
        print(f"[DEBUG] PDF conversion failed: {e}")
        return None

# ---------------- ESC/POS Thermal Printer Functions ----------------
def _find_xp80c_printer():
    """Find and initialize XP-80C thermal printer"""
    if not _ESCPOS_OK or _DISABLE_ESCPOS:
        return None

    try:
        # Method 1: Try specific XP-80C USB IDs
        printer = Usb(XP80C_VENDOR_ID, XP80C_PRODUCT_ID)
        print("[DEBUG] XP-80C found by specific USB IDs")
        return printer
    except USBNotFoundError:
        print("[DEBUG] XP-80C not found by specific IDs, trying auto-detect...")

        # Method 2: Try to find any thermal printer
        try:
            # Common thermal printer vendors: Xprinter, Epson, Star, Bixolon
            common_printers = [
                (0x0416, 0x5011),  # Xprinter XP-80C
                (0x04B8, 0x0202),  # Epson TM-series
                (0x0519, 0x0003),  # Star TSP100
                (0x0FE6, 0x811E),  # Bixolon series
            ]

            for vendor, product in common_printers:
                try:
                    printer = Usb(vendor, product)
                    print(f"[DEBUG] Found thermal printer: {vendor:04X}:{product:04X}")
                    return printer
                except USBNotFoundError:
                    continue

        except Exception as e:
            print(f"[DEBUG] Printer detection error: {e}")

    print("[WARN] No thermal printer found")
    return None

def _print_escpos_receipt(printer, table_code: str, items: List[dict], subtotal: int,
                         discount: int, total: int, method: str, cashier: str,
                         receipt_number: str = None):
    """Print receipt using ESC/POS commands with PROPER FORMATTING"""
    if not printer:
        raise ValueError("No printer available")

    currency = "EGP"
    client_name = "كافيه بيروت"
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    if not receipt_number:
        receipt_number = f"{datetime.now():%Y%m%d%H%M%S}"

    try:
        # Reset printer and set basic settings
        printer.set(align='center')

        # Header - CENTERED and BOLD
        printer.set(bold=True, double_height=True)
        printer.text(_shape_ar_textfile(client_name) + "\n")
        printer.set(bold=True, double_height=False)
        printer.text(_shape_ar_textfile("كافيه ومعلم") + "\n")
        printer.text("\n")

        # Receipt info - LEFT ALIGNED
        printer.set(align='left', bold=False)
        printer.text(f"{_shape_ar_textfile('التاريخ:')} {ts}\n")
        printer.text(f"{_shape_ar_textfile('رقم الفاتورة:')} {receipt_number}\n")
        printer.text(f"{_shape_ar_textfile('الطاولة:')} {table_code}\n")
        printer.text(f"{_shape_ar_textfile('الكاشير:')} {_shape_ar_textfile(cashier)}\n")

        printer.text("-" * 32 + "\n")  # Separator line

        # Items header - CENTERED
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_textfile("الطلبات") + "\n")
        printer.set(align='left', bold=False)
        printer.text("-" * 32 + "\n")

        # Column headers - FIXED WIDTH FORMATTING
        headers = f"{_shape_ar_textfile('الصنف'):<16} {_shape_ar_textfile('كم'):<3} {_shape_ar_textfile('السعر'):<6} {_shape_ar_textfile('المجموع'):<8}"
        printer.text(headers + "\n")
        printer.text("-" * 32 + "\n")

        # Items with PROPER COLUMN ALIGNMENT
        for it in items:
            name = _shape_ar_textfile(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))
            price = _format_currency_cents(it.get("unit_price", 0), currency)
            total_price = _format_currency_cents(it.get("total_cents", 0), currency)

            # TRUNCATE long names to fit thermal printer width
            if len(name) > 15:
                name = name[:12] + "..."

            # FIXED WIDTH columns to ensure numbers are visible
            item_line = f"{name:<15} {qty:>2} {price:>6} {total_price:>8}"
            printer.text(item_line + "\n")

            # Print notes if any (indented)
            notes = _note_segments(it.get("note", ""))
            for note in notes:
                shaped_note = _shape_ar_textfile(note)
                if len(shaped_note) > 28:
                    shaped_note = shaped_note[:25] + "..."
                printer.text(f"  • {shaped_note}\n")

        printer.text("=" * 32 + "\n")  # Total separator

        # Totals - RIGHT ALIGNED for clarity
        printer.set(align='right', bold=True)
        printer.text(f"{_shape_ar_textfile('المجموع الفرعي:')} {_format_currency_cents(subtotal, currency):>10}\n")
        printer.text(f"{_shape_ar_textfile('الخصم:')} {_format_currency_cents(discount, currency):>10}\n")
        printer.text(f"{_shape_ar_textfile('المجموع الكلي:')} {_format_currency_cents(total, currency):>10}\n")

        printer.text("\n")
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_textfile("شكراً لزيارتكم") + "\n")
        printer.text("\n")

        # Cut paper (partial cut)
        printer.cut()

    except Exception as e:
        print(f"[ERROR] ESC/POS printing failed: {e}")
        raise

def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]):
    """Print bar ticket using ESC/POS commands with PROPER FORMATTING"""
    if not printer:
        raise ValueError("No printer available")

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    try:
        # Header - CENTERED and BOLD
        printer.set(align='center', bold=True, double_height=True)
        printer.text(_shape_ar_textfile("بار كافيه بيروت") + "\n")
        printer.set(align='center', bold=True, double_height=False)
        printer.text(_shape_ar_textfile("تذكرة طلبات البار") + "\n")
        printer.text("\n")

        # Ticket info - LEFT ALIGNED
        printer.set(align='left', bold=False)
        printer.text(f"{_shape_ar_textfile('التاريخ:')} {ts}\n")
        printer.text(f"{_shape_ar_textfile('الطاولة:')} {table_code}\n")

        printer.text("-" * 32 + "\n")  # Separator line

        # Orders header - CENTERED
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_textfile("الطلبات الجديدة") + "\n")
        printer.set(align='left', bold=False)
        printer.text("-" * 32 + "\n")

        # Column headers - FIXED WIDTH
        headers = f"{_shape_ar_textfile('الصنف'):<22} {_shape_ar_textfile('الكمية'):<6}"
        printer.text(headers + "\n")
        printer.text("-" * 32 + "\n")

        # Items with PROPER COLUMN ALIGNMENT
        for it in items:
            name = _shape_ar_textfile(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))

            # TRUNCATE long names to fit thermal printer width
            if len(name) > 20:
                name = name[:17] + "..."

            # FIXED WIDTH columns
            item_line = f"{name:<20} {qty:>6}"
            printer.text(item_line + "\n")

            # Print notes if any (indented)
            notes = _note_segments(it.get("note", ""))
            for note in notes:
                shaped_note = _shape_ar_textfile(note)
                if len(shaped_note) > 28:
                    shaped_note = shaped_note[:25] + "..."
                printer.text(f"  • {shaped_note}\n")

        printer.text("=" * 32 + "\n")  # Footer separator
        printer.text("\n")

        printer.set(align='center', bold=True)
        printer.text(_shape_ar_textfile("يتم التحضير فوراً - شكراً لتفهمكم") + "\n")
        printer.text("\n")

        # Cut paper (partial cut)
        printer.cut()

    except Exception as e:
        print(f"[ERROR] ESC/POS bar ticket printing failed: {e}")
        raise

# ---------------- HTML Receipt Generation (Fallback) ----------------
def _generate_html_receipt(
        table_code: str,
        items: List[dict],
        subtotal: int,
        discount: int,
        total: int,
        method: str,
        cashier: str,
        receipt_number: str = None,
) -> Path:
    _ensure_dirs()

    currency = "EGP"
    client_name = "كافيه بيروت"
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    if not receipt_number:
        receipt_number = f"{datetime.now():%Y%m%d%H%M%S}"

    # Build items HTML
    items_html = ""
    for it in items:
        name = _shape_ar_textfile(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))
        price = _format_currency_cents(it.get("unit_price", 0), currency)
        total_price = _format_currency_cents(it.get("total_cents", 0), currency)

        items_html += f"""
        <tr>
            <td style="text-align: right; padding: 5px; border-bottom: 1px dotted #000;">{name}</td>
            <td style="text-align: center; padding: 5px; border-bottom: 1px dotted #000;">{qty}</td>
            <td style="text-align: center; padding: 5px; border-bottom: 1px dotted #000;">{price}</td>
            <td style="text-align: center; padding: 5px; border-bottom: 1px dotted #000;">{total_price}</td>
        </tr>"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Receipt</title>
    <style>
        body {{
            width: 80mm;
            margin: 0;
            padding: 10px;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }}
        .header {{ text-align: center; margin-bottom: 15px; }}
        .cafe-name {{ font-size: 20px; font-weight: bold; }}
        .info-row {{ display: flex; justify-content: space-between; margin: 5px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th {{ border-bottom: 2px solid #000; padding: 8px; text-align: right; }}
        td {{ padding: 5px; border-bottom: 1px dotted #000; }}
        .total-row {{ display: flex; justify-content: space-between; margin: 8px 0; font-weight: bold; }}
        .footer {{ text-align: center; margin-top: 15px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="cafe-name">{_shape_ar_textfile(client_name)}</div>
        <div>{_shape_ar_textfile("كافيه ومعلم")}</div>
    </div>

    <div class="info-row">
        <span>{_shape_ar_textfile("التاريخ:")}</span>
        <span>{ts}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_textfile("رقم الفاتورة:")}</span>
        <span>{receipt_number}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_textfile("الطاولة:")}</span>
        <span>{table_code}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_textfile("الكاشير:")}</span>
        <span>{_shape_ar_textfile(cashier)}</span>
    </div>

    <hr>
    <div style="text-align: center; font-weight: bold; margin: 10px 0;">{_shape_ar_textfile("الطلبات")}</div>

    <table>
        <thead>
            <tr>
                <th>{_shape_ar_textfile("الصنف")}</th>
                <th>{_shape_ar_textfile("الكمية")}</th>
                <th>{_shape_ar_textfile("السعر")}</th>
                <th>{_shape_ar_textfile("الإجمالي")}</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <hr>
    <div class="total-row">
        <span>{_shape_ar_textfile("المجموع الفرعي:")}</span>
        <span>{_format_currency_cents(subtotal, currency)}</span>
    </div>
    <div class="total-row">
        <span>{_shape_ar_textfile("الخصم:")}</span>
        <span>{_format_currency_cents(discount, currency)}</span>
    </div>
    <div class="total-row" style="border-top: 2px solid #000; padding-top: 5px;">
        <span>{_shape_ar_textfile("المجموع الكلي:")}</span>
        <span>{_format_currency_cents(total, currency)}</span>
    </div>

    <div class="footer">
        <div>{_shape_ar_textfile("شكراً لزيارتكم")}</div>
    </div>
</body>
</html>"""

    html_filename = f"receipt-{table_code}-{receipt_number}.html"
    html_path = _RECEIPTS_DIR / html_filename
    html_path.write_text(html_content, encoding='utf-8')

    print(f"[DEBUG] HTML saved: {html_path}")
    return html_path

def _generate_html_bar_ticket(table_code: str, items: List[dict]) -> Path:
    """Generate HTML bar ticket for kitchen/bar"""
    _ensure_dirs()

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    items_html = ""
    for it in items:
        name = _shape_ar_textfile(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))

        items_html += f"""
            <tr>
                <td class="item-name">{name}</td>
                <td class="item-qty">{qty}</td>
            </tr>"""

        notes = _note_segments(it.get("note", ""))
        for note in notes:
            shaped_note = _shape_ar_textfile(note)
            items_html += f"""
            <tr>
                <td colspan="2" style="font-size: 11px; color: #666; padding-right: 10px; font-style: italic;">
                    • {shaped_note}
                </td>
            </tr>"""

    bar_html_template = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bar Ticket</title>
    <style>
        body {{
            width: 80mm;
            margin: 0;
            padding: 10px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            direction: rtl;
        }}
        .header {{ text-align: center; margin-bottom: 15px; }}
        .cafe-name {{ font-size: 22px; font-weight: bold; }}
        .info-row {{ display: flex; justify-content: space-between; margin: 5px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th {{ border-bottom: 2px solid #000; padding: 8px; text-align: right; }}
        td {{ padding: 5px; border-bottom: 1px dotted #000; }}
        .footer {{ text-align: center; margin-top: 15px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="cafe-name">{_shape_ar_textfile("بار كافيه بيروت")}</div>
        <div>{_shape_ar_textfile("تذكرة طلبات البار")}</div>
    </div>

    <div class="info-row">
        <span>{_shape_ar_textfile("التاريخ:")}</span>
        <span>{ts}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_textfile("الطاولة:")}</span>
        <span>{table_code}</span>
    </div>

    <hr>
    <div style="text-align: center; font-weight: bold; margin: 10px 0;">{_shape_ar_textfile("الطلبات الجديدة")}</div>

    <table>
        <thead>
            <tr>
                <th>{_shape_ar_textfile("الصنف")}</th>
                <th>{_shape_ar_textfile("الكمية")}</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <div class="footer">
        <div>{_shape_ar_textfile("يتم التحضير فوراً - شكراً لتفهمكم")}</div>
    </div>
</body>
</html>"""

    bar_filename = f"bar-{table_code}-{datetime.now():%Y%m%d%H%M%S}.html"
    bar_path = _BAR_DIR / bar_filename
    bar_path.write_text(bar_html_template, encoding='utf-8')

    print(f"[DEBUG] HTML bar ticket saved: {bar_path}")
    return bar_path

# ---------------- Public API ----------------
class PrinterService:
    __slots__ = ("bar_printer", "cashier_printer", "_escpos_printer")

    def __init__(self):
        _ensure_dirs()
        self.bar_printer = "XP-80C"
        self.cashier_printer = "XP-80C"
        self._escpos_printer = _find_xp80c_printer()
        self.reload_from_settings()

    def reload_from_settings(self):
        bar  = (setting_get("bar_printer","") or "").strip()
        cash = (setting_get("cashier_printer","") or "").strip()
        if bar:  self.bar_printer = bar
        if cash: self.cashier_printer = cash

    def update_printers(self, bar: Optional[str], cashier: Optional[str]):
        if bar is not None:
            self.bar_printer = bar.strip() or "XP-80C"
        if cashier is not None:
            self.cashier_printer = cashier.strip() or "XP-80C"

    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        """Print bar ticket using ESC/POS thermal printer"""
        data = _collapse_items(items)

        if self._escpos_printer and not _DISABLE_ESCPOS:
            try:
                print(f"[DEBUG] Printing bar ticket to XP-80C for table {table_code}")
                _print_escpos_bar_ticket(self._escpos_printer, table_code, data)
                return True
            except Exception as e:
                print(f"[ERROR] ESC/POS bar ticket failed: {e}")
                return self._print_html_fallback(table_code, data, "bar")
        else:
            print("[WARN] ESC/POS not available, using HTML fallback for bar ticket")
            return self._print_html_fallback(table_code, data, "bar")

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
    ) -> bool:
        """Print cashier receipt using ESC/POS thermal printer"""
        data = _collapse_items(items)

        if self._escpos_printer and not _DISABLE_ESCPOS:
            try:
                print(f"[DEBUG] Printing receipt to XP-80C for table {table_code}")
                _print_escpos_receipt(
                    self._escpos_printer, table_code, data, subtotal,
                    discount, total, method, cashier
                )
                return True
            except Exception as e:
                print(f"[ERROR] ESC/POS receipt failed: {e}")
                return self._print_html_fallback(table_code, data, "receipt",
                                               subtotal, discount, total, method, cashier)
        else:
            print("[WARN] ESC/POS not available, using HTML fallback for receipt")
            return self._print_html_fallback(table_code, data, "receipt",
                                           subtotal, discount, total, method, cashier)

    def _print_html_fallback(self, table_code: str, items: List[dict],
                           ticket_type: str, subtotal: int = 0, discount: int = 0,
                           total: int = 0, method: str = "", cashier: str = "") -> bool:
        """HTML fallback when ESC/POS is not available"""
        try:
            if ticket_type == "bar":
                html_path = _generate_html_bar_ticket(table_code, items)
            else:
                html_path = _generate_html_receipt(
                    table_code, items, subtotal, discount, total, method, cashier
                )

            # Open HTML in browser for manual printing
            if sys.platform.startswith("win"):
                os.startfile(str(html_path))
            else:
                subprocess.Popen(["xdg-open", str(html_path)])

            print(f"[INFO] Opened {ticket_type} in browser for manual printing: {html_path}")
            return True

        except Exception as e:
            print(f"[ERROR] HTML fallback failed: {e}")
            return False

    def generate_html_receipt(
            self,
            table_code: str,
            items: Iterable,
            subtotal: int,
            discount: int,
            total: int,
            method: str,
            cashier: str,
            receipt_number: str = None,
    ) -> Path:
        """Generate HTML receipt for display/printing"""
        data = _collapse_items(items)
        return _generate_html_receipt(
            table_code=table_code,
            items=data,
            subtotal=subtotal,
            discount=discount,
            total=total,
            method=method,
            cashier=cashier,
            receipt_number=receipt_number
        )

    def generate_html_bar_ticket(self, table_code: str, items: Iterable) -> Path:
        """Generate HTML bar ticket"""
        data = _collapse_items(items)
        return _generate_html_bar_ticket(table_code=table_code, items=data)

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

        key = (name, unit_price, note)

        if key in grouped:
            grouped[key]["qty"] += float(getattr(it, "qty", 1.0) or 1.0)
            grouped[key]["total_cents"] += int(getattr(it, "total_cents", 0) or 0)
        else:
            grouped[key] = {
                "name": name,
                "qty": float(getattr(it, "qty", 1.0) or 1.0),
                "unit_price": unit_price,
                "total_cents": int(getattr(it, "total_cents", 0) or 0),
                "note": note,
            }

    return list(grouped.values())

# ---------------- Diagnostic function ----------------
def test_arabic_shaping():
    """Test if Arabic shaping works correctly"""
    test_text = "كافيه بيروت"

    print("=== Arabic Shaping Test ===")
    print(f"Original: {test_text}")

    if _AR_OK:
        reshaped = arabic_reshaper.reshape(test_text)
        print(f"Reshaped: {reshaped}")
        print(f"Textfile version: {_shape_ar_textfile(test_text)}")
    else:
        print("Arabic reshaping not available")

    print("===========================")

def test_printer():
    """Test printer connection and basic printing"""
    printer = _find_xp80c_printer()
    if printer:
        print("✅ Thermal printer connected!")
        try:
            printer.text("Printer Test - XP-80C\n")
            printer.text("Numbers: 1234567890\n")
            printer.text("Arabic: " + _shape_ar_textfile("كافيه بيروت") + "\n")
            printer.cut()
            print("✅ Test print completed!")
        except Exception as e:
            print(f"❌ Test print failed: {e}")
    else:
        print("❌ No thermal printer found")

test_arabic_shaping()
test_printer()