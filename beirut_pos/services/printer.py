"""Receipt/ticket renderer for XP-80C thermal printers with PROPER formatting."""
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
    from escpos.printer import Usb
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
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

# ---------------- XP-80C USB Configuration ----------------
XP80C_VENDOR_ID = 0x0416   # Xprinter vendor ID
XP80C_PRODUCT_ID = 0x5011  # XP-80C product ID

def _ensure_dirs():
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)

# ---------------- Arabic shaping ----------------
_AR_OK = False
try:
    import arabic_reshaper
    _AR_OK = True
except ImportError:
    pass

def _shape_ar_text(text: str) -> str:
    """Arabic shaping for thermal printers - reshape ONLY."""
    if not text or not _AR_OK:
        return text
    try:
        return arabic_reshaper.reshape(text)
    except Exception:
        return text

def _format_currency_simple(cents: int | float) -> str:
    """SIMPLE currency format for thermal printers - NO EGP text"""
    try:
        amount = int(round(float(cents))) / 100  # Convert cents to currency units
        return f"{amount:.2f}"  # Just the number, no currency symbol
    except Exception:
        return str(cents)

def _format_qty(qty: float) -> str:
    """Return a friendly quantity string."""
    rounded = round(qty)
    if abs(qty - rounded) < 1e-6:
        return str(int(rounded))
    return f"{qty:.2f}".rstrip("0").rstrip(".")

def _note_segments(note: str) -> list[str]:
    """Split composite notes into parts."""
    if not note:
        return []
    cleaned = note.replace("\n", " ")
    parts = [seg.strip(" ؛-•") for seg in cleaned.split("؛")]
    return [seg for seg in parts if seg]

# ---------------- HTML Fallback Generation ----------------
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
    """Generate HTML receipt for fallback printing"""
    _ensure_dirs()

    currency = "EGP"
    client_name = "كافيه بيروت"
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    if not receipt_number:
        receipt_number = f"{datetime.now():%Y%m%d%H%M%S}"

    # Build items HTML
    items_html = ""
    for it in items:
        name = _shape_ar_text(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))
        price = _format_currency_simple(it.get("unit_price", 0))
        total_price = _format_currency_simple(it.get("total_cents", 0))

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
        <div class="cafe-name">{_shape_ar_text(client_name)}</div>
        <div>{_shape_ar_text("كافيه ومعلم")}</div>
    </div>

    <div class="info-row">
        <span>{_shape_ar_text("التاريخ:")}</span>
        <span>{ts}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_text("رقم الفاتورة:")}</span>
        <span>{receipt_number}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_text("الطاولة:")}</span>
        <span>{table_code}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_text("الكاشير:")}</span>
        <span>{_shape_ar_text(cashier)}</span>
    </div>

    <hr>
    <div style="text-align: center; font-weight: bold; margin: 10px 0;">{_shape_ar_text("الطلبات")}</div>

    <table>
        <thead>
            <tr>
                <th>{_shape_ar_text("الصنف")}</th>
                <th>{_shape_ar_text("الكمية")}</th>
                <th>{_shape_ar_text("السعر")}</th>
                <th>{_shape_ar_text("الإجمالي")}</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <hr>
    <div class="total-row">
        <span>{_shape_ar_text("المجموع الفرعي:")}</span>
        <span>{_format_currency_simple(subtotal)} {currency}</span>
    </div>
    <div class="total-row">
        <span>{_shape_ar_text("الخصم:")}</span>
        <span>{_format_currency_simple(discount)} {currency}</span>
    </div>
    <div class="total-row" style="border-top: 2px solid #000; padding-top: 5px;">
        <span>{_shape_ar_text("المجموع الكلي:")}</span>
        <span>{_format_currency_simple(total)} {currency}</span>
    </div>

    <div class="footer">
        <div>{_shape_ar_text("شكراً لزيارتكم")}</div>
    </div>
</body>
</html>"""

    html_filename = f"receipt-{table_code}-{receipt_number}.html"
    html_path = _RECEIPTS_DIR / html_filename
    html_path.write_text(html_content, encoding='utf-8')
    return html_path

def _generate_html_bar_ticket(table_code: str, items: List[dict]) -> Path:
    """Generate HTML bar ticket for fallback"""
    _ensure_dirs()

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    items_html = ""
    for it in items:
        name = _shape_ar_text(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))

        items_html += f"""
            <tr>
                <td class="item-name">{name}</td>
                <td class="item-qty">{qty}</td>
            </tr>"""

        notes = _note_segments(it.get("note", ""))
        for note in notes:
            shaped_note = _shape_ar_text(note)
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
        <div class="cafe-name">{_shape_ar_text("بار كافيه بيروت")}</div>
        <div>{_shape_ar_text("تذكرة طلبات البار")}</div>
    </div>

    <div class="info-row">
        <span>{_shape_ar_text("التاريخ:")}</span>
        <span>{ts}</span>
    </div>
    <div class="info-row">
        <span>{_shape_ar_text("الطاولة:")}</span>
        <span>{table_code}</span>
    </div>

    <hr>
    <div style="text-align: center; font-weight: bold; margin: 10px 0;">{_shape_ar_text("الطلبات الجديدة")}</div>

    <table>
        <thead>
            <tr>
                <th>{_shape_ar_text("الصنف")}</th>
                <th>{_shape_ar_text("الكمية")}</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>

    <div class="footer">
        <div>{_shape_ar_text("يتم التحضير فوراً - شكراً لتفهمكم")}</div>
    </div>
</body>
</html>"""

    bar_filename = f"bar-{table_code}-{datetime.now():%Y%m%d%H%M%S}.html"
    bar_path = _BAR_DIR / bar_filename
    bar_path.write_text(bar_html_template, encoding='utf-8')
    return bar_path

def _open_html_in_browser(html_path: Path):
    """Open HTML file in default browser"""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(html_path))
        elif sys.platform == "darwin":  # macOS
            subprocess.Popen(["open", str(html_path)])
        else:  # Linux
            subprocess.Popen(["xdg-open", str(html_path)])
        print(f"[INFO] Opened in browser: {html_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to open browser: {e}")
        return False

# ---------------- ESC/POS Thermal Printer Functions ----------------
def _find_xp80c_printer():
    """Find and initialize XP-80C thermal printer"""
    if not _ESCPOS_OK or _DISABLE_ESCPOS:
        return None

    try:
        # Try XP-80C first
        printer = Usb(XP80C_VENDOR_ID, XP80C_PRODUCT_ID)
        return printer
    except USBNotFoundError:
        # Try common thermal printers
        common_printers = [
            (0x0416, 0x5011),  # Xprinter XP-80C
            (0x04B8, 0x0202),  # Epson TM-series
        ]

        for vendor, product in common_printers:
            try:
                printer = Usb(vendor, product)
                return printer
            except USBNotFoundError:
                continue
    return None

def _print_escpos_receipt(printer, table_code: str, items: List[dict], subtotal: int,
                         discount: int, total: int, method: str, cashier: str):
    """Print receipt using ESC/POS commands with PROPER 80mm thermal formatting"""
    if not printer:
        raise ValueError("No printer available")

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    receipt_number = f"{datetime.now():%Y%m%d%H%M%S}"

    try:
        # Header - CENTERED
        printer.set(align='center', bold=True, double_height=True)
        printer.text(_shape_ar_text("كافيه بيروت") + "\n")
        printer.set(align='center', bold=True, double_height=False)
        printer.text(_shape_ar_text("كافيه ومعلم") + "\n")
        printer.text("\n")

        # Receipt info - SIMPLE FORMAT
        printer.set(align='left', bold=False)
        printer.text(f"{_shape_ar_text('التاريخ:')} {ts}\n")
        printer.text(f"{_shape_ar_text('الطاولة:')} {table_code}\n")
        printer.text(f"{_shape_ar_text('الكاشير:')} {_shape_ar_text(cashier)}\n")

        printer.text("-" * 32 + "\n")

        # Items header
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("الطلبات") + "\n")
        printer.set(align='left', bold=False)
        printer.text("-" * 32 + "\n")

        # ITEMS WITH PROPER THERMAL PRINTER COLUMNS
        for it in items:
            name = _shape_ar_text(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))
            price = _format_currency_simple(it.get("unit_price", 0))
            total_price = _format_currency_simple(it.get("total_cents", 0))

            # CRITICAL: Truncate name to fit thermal printer width
            if len(name) > 16:
                name = name[:13] + "..."

            # FIXED COLUMN WIDTHS FOR THERMAL PRINTER (32 chars total)
            item_line = f"{name:<16} {qty:>2} {price:>6} {total_price:>6}"
            printer.text(item_line + "\n")

            # Print notes if any (indented)
            notes = _note_segments(it.get("note", ""))
            for note in notes:
                shaped_note = _shape_ar_text(note)
                if len(shaped_note) > 28:
                    shaped_note = shaped_note[:25] + "..."
                printer.text(f"  • {shaped_note}\n")

        printer.text("=" * 32 + "\n")

        # Totals - RIGHT ALIGNED WITH SIMPLE NUMBERS
        printer.set(align='right', bold=True)
        printer.text(f"{_shape_ar_text('المجموع:')} {_format_currency_simple(subtotal):>10}\n")
        if discount > 0:
            printer.text(f"{_shape_ar_text('الخصم:')} {_format_currency_simple(discount):>10}\n")
        printer.text(f"{_shape_ar_text('الإجمالي:')} {_format_currency_simple(total):>10}\n")

        printer.text("\n")
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("شكراً لزيارتكم") + "\n")
        printer.text("\n" * 2)

        # Cut paper
        printer.cut()

    except Exception as e:
        print(f"[ERROR] ESC/POS printing failed: {e}")
        raise

def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]):
    """Print bar ticket using ESC/POS with proper thermal formatting"""
    if not printer:
        raise ValueError("No printer available")

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    try:
        # Header
        printer.set(align='center', bold=True, double_height=True)
        printer.text(_shape_ar_text("بار كافيه بيروت") + "\n")
        printer.set(align='center', bold=True, double_height=False)
        printer.text(_shape_ar_text("تذكرة البار") + "\n")
        printer.text("\n")

        # Ticket info
        printer.set(align='left', bold=False)
        printer.text(f"{_shape_ar_text('التاريخ:')} {ts}\n")
        printer.text(f"{_shape_ar_text('الطاولة:')} {table_code}\n")

        printer.text("-" * 32 + "\n")

        # Orders header
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("الطلبات") + "\n")
        printer.set(align='left', bold=False)
        printer.text("-" * 32 + "\n")

        # Items - SIMPLE FORMAT FOR BAR TICKET
        for it in items:
            name = _shape_ar_text(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))

            # Truncate long names
            if len(name) > 22:
                name = name[:19] + "..."

            # Simple format: "Product.................Qty"
            item_line = f"{name:<22} {qty:>3}"
            printer.text(item_line + "\n")

            # Print notes if any
            notes = _note_segments(it.get("note", ""))
            for note in notes:
                shaped_note = _shape_ar_text(note)
                if len(shaped_note) > 28:
                    shaped_note = shaped_note[:25] + "..."
                printer.text(f"  • {shaped_note}\n")

        printer.text("=" * 32 + "\n")
        printer.text("\n")

        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("شكراً لتفهمكم") + "\n")
        printer.text("\n" * 2)

        # Cut paper
        printer.cut()

    except Exception as e:
        print(f"[ERROR] ESC/POS bar ticket failed: {e}")
        raise

# ---------------- Data shaping with quantity grouping ----------------
def _collapse_items(items: Iterable) -> List[dict]:
    """Collapse items and GROUP identical products together"""
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

# ---------------- Public API ----------------
class PrinterService:
    def __init__(self):
        _ensure_dirs()
        self._escpos_printer = _find_xp80c_printer()

    def reload_from_settings(self):
        pass

    def update_printers(self, bar: Optional[str], cashier: Optional[str]):
        pass

    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        """Print bar ticket - tries thermal printer first, then web fallback"""
        data = _collapse_items(items)

        # Try thermal printer first
        if self._escpos_printer:
            try:
                print("[DEBUG] Trying thermal printer...")
                _print_escpos_bar_ticket(self._escpos_printer, table_code, data)
                return True
            except Exception as e:
                print(f"[ERROR] Thermal printing failed: {e}")

        # Fallback to web browser
        print("[DEBUG] Falling back to web browser...")
        try:
            html_path = _generate_html_bar_ticket(table_code, data)
            return _open_html_in_browser(html_path)
        except Exception as e:
            print(f"[ERROR] Web fallback failed: {e}")
            return False

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
        """Print cashier receipt - tries thermal printer first, then web fallback"""
        data = _collapse_items(items)

        # Try thermal printer first
        if self._escpos_printer:
            try:
                print("[DEBUG] Trying thermal printer...")
                _print_escpos_receipt(
                    self._escpos_printer, table_code, data, subtotal,
                    discount, total, method, cashier
                )
                return True
            except Exception as e:
                print(f"[ERROR] Thermal printing failed: {e}")

        # Fallback to web browser
        print("[DEBUG] Falling back to web browser...")
        try:
            html_path = _generate_html_receipt(
                table_code, data, subtotal, discount, total, method, cashier
            )
            return _open_html_in_browser(html_path)
        except Exception as e:
            print(f"[ERROR] Web fallback failed: {e}")
            return False

printer = PrinterService()

def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)

bus.subscribe("printers_changed", _apply_printer_settings)

# ---------------- Diagnostic function ----------------
def test_printer():
    """Test printer connection"""
    printer = _find_xp80c_printer()
    if printer:
        print("✅ Thermal printer connected!")
        try:
            printer.text("TEST RECEIPT\n")
            printer.text("Item1.............2 10.00 20.00\n")
            printer.text("=" * 32 + "\n")
            printer.text("المجموع:          150.00\n")
            printer.text("الخصم:            10.00\n")
            printer.text("الإجمالي:        140.00\n")
            printer.cut()
            print("✅ Test print completed!")
        except Exception as e:
            print(f"❌ Test print failed: {e}")
    else:
        print("❌ No thermal printer found - will use web fallback")

if __name__ == "__main__":
    test_printer()