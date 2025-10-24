"""Receipt/ticket PDF renderer for 80mm thermal printers (XP-80C) with Arabic shaping.
ULTIMATE FIX: Uses HTML generation for beautiful receipts with Arabic support.
"""

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
# Set this to "1" in env (or PyCharm Run Config) to force text fallback on dev machines
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

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

    # Be more flexible with version requirements
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

# ---------------- HTML Receipt Generation ----------------
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
    # Ensure directories exist
    output_dir = Path("prints/receipts")
    output_dir.mkdir(parents=True, exist_ok=True)

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

    # SIMPLE COMPLETE HTML TEMPLATE
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

    # Save HTML file
    html_filename = f"receipt-{table_code}-{receipt_number}.html"
    html_path = output_dir / html_filename
    html_path.write_text(html_content, encoding='utf-8')

    print(f"[DEBUG] HTML saved: {html_path}")
    return html_path


def _generate_html_bar_ticket(table_code: str, items: List[dict]) -> Path:
    """Generate HTML bar ticket for kitchen/bar"""
    _ensure_dirs()

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    # Build items HTML directly - NO JAVASCRIPT!
    items_html = ""
    for it in items:
        name = _shape_ar_textfile(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))

        items_html += f"""
            <tr>
                <td class="item-name">{name}</td>
                <td class="item-qty">{qty}</td>
            </tr>"""

        # Add notes if any
        notes = _note_segments(it.get("note", ""))
        for note in notes:
            shaped_note = _shape_ar_textfile(note)
            items_html += f"""
            <tr>
                <td colspan="2" style="font-size: 11px; color: #666; padding-right: 10px; font-style: italic;">
                    • {shaped_note}
                </td>
            </tr>"""

    # SIMPLE HTML TEMPLATE - NO BROKEN JAVASCRIPT!
    bar_html_template = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bar Ticket</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Courier New', monospace;
        }}

        body {{
            background: white;
            padding: 10px;
            direction: rtl;
            font-size: 14px;
            line-height: 1.3;
            width: 80mm;
            max-width: 80mm;
            margin: 0 auto;
        }}

        .receipt {{
            width: 100%;
            background: white;
            border: 2px solid #000;
            padding: 15px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px double #000;
        }}

        .cafe-name {{
            font-size: 22px;
            font-weight: 900;
            margin-bottom: 5px;
            color: #000;
        }}

        .cafe-subtitle {{
            font-size: 16px;
            margin-bottom: 10px;
            font-weight: bold;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 14px;
            padding: 2px 0;
        }}

        .info-label {{
            font-weight: 900;
            color: #000;
        }}

        .divider {{
            border-bottom: 2px dashed #000;
            margin: 15px 0;
            height: 2px;
        }}

        .section-title {{
            font-weight: 900;
            text-align: center;
            margin: 15px 0 10px;
            font-size: 16px;
            background: #000;
            color: white;
            padding: 5px;
            border-radius: 3px;
        }}

        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            font-size: 13px;
        }}

        .items-table th {{
            border-bottom: 2px solid #000;
            padding: 8px 5px;
            text-align: right;
            font-weight: 900;
            background: #f0f0f0;
        }}

        .items-table td {{
            padding: 6px 5px;
            border-bottom: 1px solid #ccc;
        }}

        .item-name {{
            text-align: right;
            font-weight: bold;
            width: 70%;
        }}

        .item-qty {{
            text-align: center;
            width: 30%;
            font-weight: bold;
        }}

        .footer {{
            text-align: center;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 2px dashed #000;
            font-size: 12px;
            color: #666;
        }}

        @media print {{
            body {{
                margin: 0 !important;
                padding: 5px !important;
                width: 80mm !important;
                background: white !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}

            .receipt {{
                border: 2px solid #000 !important;
                box-shadow: none !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 10px !important;
            }}

            .section-title {{
                background: #000 !important;
                color: white !important;
                -webkit-print-color-adjust: exact !important;
            }}

            @page {{
                size: 80mm auto;
                margin: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="receipt">
        <div class="header">
            <div class="cafe-name">{_shape_ar_textfile("بار كافيه بيروت")}</div>
            <div class="cafe-subtitle">{_shape_ar_textfile("تذكرة طلبات البار")}</div>
        </div>

        <div class="info-row">
            <div class="info-label">{_shape_ar_textfile("التاريخ:")}</div>
            <div>{ts}</div>
        </div>

        <div class="info-row">
            <div class="info-label">{_shape_ar_textfile("الطاولة:")}</div>
            <div>{table_code}</div>
        </div>

        <div class="divider"></div>

        <div class="section-title">{_shape_ar_textfile("الطلبات الجديدة")}</div>

        <table class="items-table">
            <thead>
                <tr>
                    <th class="item-name">{_shape_ar_textfile("الصنف")}</th>
                    <th class="item-qty">{_shape_ar_textfile("الكمية")}</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <div class="footer">
            <div>{_shape_ar_textfile("يتم التحضير فوراً - شكراً لتفهمكم")}</div>
        </div>
    </div>

    <script>
        // Auto-print only - no broken JavaScript data
        window.onload = function() {{
            setTimeout(() => {{
                window.print();
                setTimeout(() => {{
                    window.close();
                }}, 1000);
            }}, 500);
        }};
    </script>
</body>
</html>"""

    bar_filename = f"bar-{table_code}-{datetime.now():%Y%m%d%H%M%S}.html"
    bar_path = _BAR_DIR / bar_filename
    bar_path.write_text(bar_html_template, encoding='utf-8')

    print(f"[DEBUG] HTML bar ticket saved: {bar_path}")
    return bar_path

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
        """Print bar ticket using HTML generation"""
        data = _collapse_items(items)

        # Generate HTML bar ticket
        html_path = _generate_html_bar_ticket(table_code, data)

        # Print the HTML file
        self._print_html_file(html_path, self.bar_printer)

        return html_path

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
    ) -> Path:
        """Print cashier receipt using HTML generation"""
        data = _collapse_items(items)

        # Generate HTML receipt
        html_path = _generate_html_receipt(
            table_code=table_code,
            items=data,
            subtotal=subtotal,
            discount=discount,
            total=total,
            method=method,
            cashier=cashier
        )

        # Print the HTML file
        self._print_html_file(html_path, self.cashier_printer)

        return html_path

    def _print_html_file(self, html_path: Path, printer_name: str) -> None:
        """Print HTML file using system printing with Windows support"""
        try:
            if sys.platform.startswith("win"):
                print(f"[DEBUG] Windows printing: {html_path}")

                # METHOD 1: Try PDF with wkhtmltopdf FIRST
                pdf_path = _convert_html_to_pdf(html_path)
                if pdf_path and pdf_path.exists():
                    print(f"[DEBUG] PDF created, printing: {pdf_path}")
                    os.startfile(str(pdf_path), "print")
                    print("[DEBUG] PDF sent to printer")
                    return

                # METHOD 2: If PDF fails, use browser directly
                print("[DEBUG] Opening in browser for printing")
                os.startfile(str(html_path))

            else:
                # Linux/Mac
                print(f"[DEBUG] Unix printing: {html_path}")
                if _can_system_print(printer_name):
                    subprocess.Popen(["lp", "-d", printer_name, str(html_path)])
                else:
                    subprocess.Popen(["lp", str(html_path)])

        except Exception as e:
            print(f"[ERROR] Print failed: {e}")
            os.startfile(str(html_path))

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
        bidi = get_display(reshaped)
        print(f"Reshaped: {reshaped}")
        print(f"Bidi: {bidi}")
        print(f"Textfile version: {_shape_ar_textfile(test_text)}")
    else:
        print("Arabic reshaping not available")

    print("===========================")

test_arabic_shaping()