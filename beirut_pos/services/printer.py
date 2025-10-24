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
    """Arabic shaping for text files - RESHAPE ONLY, NO BIDI for thermal printers."""
    if not text:
        return ""
    if not _AR_OK:
        _warn_arabic_missing()
        return text
    try:
        # CRITICAL FIX: Reshape Arabic but DON'T apply bidi algorithm
        # Thermal printers handle RTL automatically when Arabic text is properly shaped
        reshaped = arabic_reshaper.reshape(text)
        return reshaped  # ← NO get_display() for thermal printers!
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
    """Check if CUPS can print to a given printer on Linux/macOS."""
    if not printer_name or not shutil.which("lp"):
        return False
    try:
        out = subprocess.check_output(["lpstat", "-a"], text=True)
        return printer_name in out
    except Exception:
        return False

def _convert_html_to_pdf(html_path: Path) -> Optional[Path]:
    """Convert HTML to PDF with thermal-friendly settings (203 dpi, solid black)."""
    try:
        import pdfkit

        # Find wkhtmltopdf executable
        wkhtmltopdf_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "wkhtmltopdf",  # If it's in PATH
        ]

        config = None
        for path in wkhtmltopdf_paths:
            if os.path.exists(path):
                config = pdfkit.configuration(wkhtmltopdf=path)
                print(f"[DEBUG] Using wkhtmltopdf at: {path}")
                break

        if not config:
            print("[DEBUG] wkhtmltopdf not found, using default")
            config = pdfkit.configuration()

        pdf_path = html_path.with_suffix('.pdf')

        # Configuration for 80mm receipt - HIGH CONTRAST
        options = {
            'page-size': 'Custom',
            'page-width': '80mm',
            'page-height': '297mm',
            'margin-top': '0mm',
            'margin-right': '0mm',
            'margin-bottom': '0mm',
            'margin-left': '0mm',
            'encoding': "UTF-8",
            'no-outline': None,
            'disable-smart-shrinking': None,
            'enable-smart-shrinking': False,
            'print-media-type': None,
            'dpi': '203',
            'image-dpi': '203',
            'image-quality': '100',
            'load-error-handling': 'ignore',
            'load-media-error-handling': 'ignore'
        }

        pdfkit.from_file(str(html_path), str(pdf_path), configuration=config, options=options)
        print(f"[DEBUG] PDF conversion SUCCESS: {pdf_path}")
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
    """Generate beautiful HTML receipt for display/printing"""
    _ensure_dirs()

    currency = setting_get("currency", "EGP") or "EGP"
    client_name = get_client_name() or (setting_get("company_name", "Beirut") or "Beirut")
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    if not receipt_number:
        receipt_number = f"{datetime.now():%Y%m%d%H%M%S}"

    # Format items for HTML
    html_items = []
    for it in items:
        html_items.append({
            'name': _shape_ar_textfile(str(it["name"])),
            'qty': _format_qty(float(it.get("qty", 0) or 0)),
            'price': _format_currency_cents(it.get("unit_price", 0), currency),
            'total': _format_currency_cents(it.get("total_cents", 0), currency)
        })

    # Prepare data for JavaScript
    receipt_data = {
        'date': ts,
        'receiptNumber': receipt_number,
        'tableNumber': f"{table_code}",
        'cashier': _shape_ar_textfile(cashier),
        'items': html_items,
        'subtotal': _format_currency_cents(subtotal, currency),
        'discount': _format_currency_cents(discount, currency),
        'grandTotal': _format_currency_cents(total, currency),
        'paidAmount': _format_currency_cents(total, currency),
        'cashAmount': _format_currency_cents(total, currency),
        'changeAmount': _format_currency_cents(0, currency)
    }

    # HTML template with PROPER ARABIC (no bidi) and HIGH CONTRAST
    html_template = """<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receipt</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Courier New', monospace;
            color: #000000;
            font-weight: bold;
        }}
        
        body {{
            background-color: white;
            padding: 5px;
            font-size: 12px;
            line-height: 1.2;
            width: 80mm;
            max-width: 80mm;
            margin: 0 auto;
        }}
        
        .receipt {{
            width: 80mm;
            max-width: 80mm;
            background-color: white;
            padding: 8px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 2px solid #000000;
        }}
        
        .cafe-name {{
            font-size: 18px;
            font-weight: 900;
            margin-bottom: 2px;
        }}
        
        .cafe-subtitle {{
            font-size: 13px;
            margin-bottom: 6px;
            font-weight: bold;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
            font-size: 11px;
        }}
        
        .info-label {{
            font-weight: 900;
        }}
        
        .divider {{
            border-bottom: 2px dashed #000000;
            margin: 6px 0;
        }}
        
        .section-title {{
            font-weight: 900;
            text-align: center;
            margin: 6px 0 4px;
            font-size: 13px;
        }}
        
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 8px;
            font-size: 11px;
        }}
        
        .items-table th {{
            border-bottom: 2px solid #000000;
            padding: 3px 2px;
            text-align: right;
            font-weight: 900;
        }}
        
        .items-table td {{
            padding: 2px;
            border-bottom: 1px solid #000000;
            font-weight: bold;
        }}
        
        .item-name {{
            text-align: right;
        }}
        
        .item-qty, .item-price, .item-total {{
            text-align: center;
            width: 15%;
        }}
        
        .totals {{
            margin: 8px 0;
            font-size: 12px;
        }}
        
        .total-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
        }}
        
        .grand-total {{
            font-weight: 900;
            border-top: 2px solid #000000;
            padding-top: 4px;
            margin-top: 4px;
            font-size: 13px;
        }}
        
        .payment-details {{
            background-color: #000000;
            color: #FFFFFF;
            padding: 6px;
            margin: 8px 0;
            border-radius: 3px;
            font-weight: 900;
        }}
        
        .payment-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 2px;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 10px;
            padding-top: 6px;
            border-top: 2px dashed #000000;
            font-size: 10px;
            width: 100%;
        }}
        
        .address, .phone {{
            margin: 2px 0;
            width: 100%;
        }}
        
        .cashier {{
            margin-top: 4px;
            font-weight: 900;
            width: 100%;
        }}
        
        .thank-you {{
            margin-top: 6px;
            font-style: italic;
            width: 100%;
        }}

        /* HIGH-CONTRAST PRINT STYLES */
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
                color: #000000 !important;
                background: transparent !important;
                font-weight: bold !important;
            }}
            
            body {{
                margin: 0 !important;
                padding: 0 !important;
                width: 80mm !important;
                max-width: 80mm !important;
                background: white !important;
            }}
            
            .receipt {{
                border: none !important;
                box-shadow: none !important;
                width: 80mm !important;
                max-width: 80mm !important;
                margin: 0 !important;
                padding: 5px !important;
                background: white !important;
            }}
            
            .payment-details {{
                background-color: #000000 !important;
                color: #FFFFFF !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            
            @page {{
                size: 80mm auto;
                margin: 0;
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="receipt">
        <div class="header">
            <div class="cafe-name">{CLIENT_NAME}</div>
            <div class="cafe-subtitle">كافيه ومعلم</div>
            
            <div class="info-row">
                <div class="info-label">التاريخ والوقت:</div>
                <div id="receipt-date">2025/10/17 11:51:34</div>
            </div>
            
            <div class="info-row">
                <div class="info-label">رقم الفاتورة:</div>
                <div id="receipt-number">51</div>
            </div>
        </div>
        
        <div class="info-row">
            <div class="info-label">الطاولة:</div>
            <div id="table-number">24 (نادي)</div>
        </div>
        
        <div class="info-row">
            <div class="info-label">الكاشير:</div>
            <div id="cashier-name">rageh</div>
        </div>
        
        <div class="divider"></div>
        
        <div class="section-title">الطلبات</div>
        
        <table class="items-table" id="items-table">
            <thead>
                <tr>
                    <th class="item-name">الصنف</th>
                    <th class="item-qty">الكمية</th>
                    <th class="item-price">السعر</th>
                    <th class="item-total">الإجمالي</th>
                </tr>
            </thead>
            <tbody id="items-body">
                <!-- DYNAMIC ITEMS WILL BE INSERTED HERE -->
            </tbody>
        </table>
        
        <div class="divider"></div>
        
        <div class="totals">
            <div class="total-row">
                <div>الخصم:</div>
                <div id="discount">0.00</div>
            </div>
            <div class="total-row grand-total">
                <div>المجموع الكلي:</div>
                <div id="grand-total">240.00</div>
            </div>
        </div>
        
        <div class="payment-details">
            <div class="payment-row">
                <div>المبلغ المدفوع:</div>
                <div id="paid-amount">0.00</div>
            </div>
            <div class="payment-row grand-total">
                <div>الباقي:</div>
                <div id="change-amount">0.00</div>
            </div>
        </div>
        
        <div class="footer">
            <div class="address">امام سيشن الشلال بجوار مفسله بالثبت</div>
            <div class="phone">01110110823</div>
            <div class="cashier">الكاشير: <span id="footer-cashier">rageh</span></div>
            <div class="thank-you">شكراً لزيارتكم</div>
        </div>
    </div>

    <script>
        // Dynamic data population
        function populateReceipt(data) {{
            // Header info
            document.getElementById('receipt-date').textContent = data.date;
            document.getElementById('receipt-number').textContent = data.receiptNumber;
            document.getElementById('table-number').textContent = data.tableNumber;
            document.getElementById('cashier-name').textContent = data.cashier;
            document.getElementById('footer-cashier').textContent = data.cashier;
            
            // Items
            const itemsBody = document.getElementById('items-body');
            itemsBody.innerHTML = '';
            data.items.forEach(item => {{
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="item-name">${{item.name}}</td>
                    <td class="item-qty">${{item.qty}}</td>
                    <td class="item-price">${{item.price}}</td>
                    <td class="item-total">${{item.total}}</td>
                `;
                itemsBody.appendChild(row);
            }});
            
            // Totals
            document.getElementById('discount').textContent = data.discount;
            document.getElementById('grand-total').textContent = data.grandTotal;
            
            // Payment
            document.getElementById('paid-amount').textContent = data.paidAmount;
            document.getElementById('change-amount').textContent = data.changeAmount;
        }}

        // Populate with data from Python
        const receiptData = {DATA_PLACEHOLDER};
        populateReceipt(receiptData);
        
        // Auto-print and close
        window.onload = function() {{
            setTimeout(function() {{
                window.print();
                setTimeout(function() {{
                    window.close();
                }}, 1000);
            }}, 500);
        }};
    </script>
</body>
</html>"""

    # Fill the template with data
    json_data = json.dumps(receipt_data, ensure_ascii=False, indent=2)
    final_html = (
        html_template
        .replace('{DATA_PLACEHOLDER}', json_data)
        .replace('{CLIENT_NAME}', _shape_ar_textfile(client_name))
    )

    # Save HTML file
    html_filename = f"receipt-{table_code}-{receipt_number}.html"
    html_path = _RECEIPTS_DIR / html_filename
    html_path.write_text(final_html, encoding='utf-8')

    print(f"[DEBUG] HTML receipt saved: {html_path}")
    return html_path

def _generate_html_bar_ticket(table_code: str, items: List[dict]) -> Path:
    """Generate HTML bar ticket for kitchen/bar"""
    _ensure_dirs()

    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    # Format items for HTML (only new/unprinted items)
    html_items = []
    for it in items:
        item_data = {
            'name': _shape_ar_textfile(str(it["name"])),
            'qty': _format_qty(float(it.get("qty", 0) or 0))
        }

        # Add notes if any
        notes = _note_segments(it.get("note", ""))
        if notes:
            item_data['notes'] = [_shape_ar_textfile(note) for note in notes]

        html_items.append(item_data)

    # Bar ticket data
    bar_data = {
        'date': ts,
        'tableNumber': f"{table_code}",
        'items': html_items
    }

    # Bar ticket HTML template (with same fixes)
    bar_html_template = """<!DOCTYPE html>
<html lang="ar">
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
            color: #000000;
            font-weight: bold;
        }}
        
        body {{
            background-color: white;
            padding: 5px;
            font-size: 12px;
            line-height: 1.2;
            width: 80mm;
            max-width: 80mm;
            margin: 0 auto;
        }}
        
        .receipt {{
            width: 80mm;
            max-width: 80mm;
            background-color: white;
            padding: 8px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 2px solid #000000;
        }}
        
        .cafe-name {{
            font-size: 18px;
            font-weight: 900;
            margin-bottom: 2px;
        }}
        
        .cafe-subtitle {{
            font-size: 13px;
            margin-bottom: 6px;
            font-weight: bold;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 3px;
            font-size: 11px;
        }}
        
        .info-label {{
            font-weight: 900;
        }}
        
        .divider {{
            border-bottom: 2px dashed #000000;
            margin: 6px 0;
        }}
        
        .section-title {{
            font-weight: 900;
            text-align: center;
            margin: 6px 0 4px;
            font-size: 13px;
        }}
        
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 8px;
            font-size: 11px;
        }}
        
        .items-table th {{
            border-bottom: 2px solid #000000;
            padding: 3px 2px;
            text-align: right;
            font-weight: 900;
        }}
        
        .items-table td {{
            padding: 2px;
            border-bottom: 1px solid #000000;
            font-weight: bold;
        }}
        
        .item-name {{
            text-align: right;
            width: 70%;
        }}
        
        .item-qty {{
            text-align: center;
            width: 30%;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 10px;
            padding-top: 6px;
            border-top: 2px dashed #000000;
            font-size: 10px;
            width: 100%;
        }}

        /* HIGH-CONTRAST PRINT STYLES */
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
                color: #000000 !important;
                background: transparent !important;
                font-weight: bold !important;
            }}
            
            body {{
                margin: 0 !important;
                padding: 0 !important;
                width: 80mm !important;
                max-width: 80mm !important;
                background: white !important;
            }}
            
            .receipt {{
                border: none !important;
                box-shadow: none !important;
                width: 80mm !important;
                max-width: 80mm !important;
                margin: 0 !important;
                padding: 5px !important;
                background: white !important;
            }}
            
            @page {{
                size: 80mm auto;
                margin: 0;
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="receipt">
        <div class="header">
            <div class="cafe-name">بار {CLIENT_NAME}</div>
            <div class="cafe-subtitle">تذكرة طلبات البار</div>
            
            <div class="info-row">
                <div class="info-label">التاريخ والوقت:</div>
                <div id="bar-date">2025/10/17 11:51:34</div>
            </div>
        </div>
        
        <div class="info-row">
            <div class="info-label">الطاولة:</div>
            <div id="bar-table">24 (نادي)</div>
        </div>
        
        <div class="divider"></div>
        
        <div class="section-title">الطلبات الجديدة</div>
        
        <table class="items-table" id="bar-items-table">
            <thead>
                <tr>
                    <th class="item-name">الصنف</th>
                    <th class="item-qty">الكمية</th>
                </tr>
            </thead>
            <tbody id="bar-items-body">
                <!-- DYNAMIC BAR ITEMS WILL BE INSERTED HERE -->
            </tbody>
        </table>
        
        <div class="footer">
            <div>يتم التحضير فوراً - شكراً لتفهمكم</div>
        </div>
    </div>

    <script>
        // Dynamic data population for bar ticket
        function populateBarTicket(data) {{
            // Header info
            document.getElementById('bar-date').textContent = data.date;
            document.getElementById('bar-table').textContent = data.tableNumber;
            
            // Bar Items
            const itemsBody = document.getElementById('bar-items-body');
            itemsBody.innerHTML = '';
            data.items.forEach(item => {{
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="item-name">${{item.name}}</td>
                    <td class="item-qty">${{item.qty}}</td>
                `;
                itemsBody.appendChild(row);
                
                // Add notes if any
                if (item.notes && item.notes.length > 0) {{
                    item.notes.forEach(note => {{
                        const noteRow = document.createElement('tr');
                        noteRow.innerHTML = `
                            <td colspan="2" style="font-size: 9px; color: #000000 !important; padding-right: 10px; font-weight: bold !important;">• ${{note}}</td>
                        `;
                        itemsBody.appendChild(noteRow);
                    }});
                }}
            }});
        }}

        // Populate with data from Python
        const barData = {DATA_PLACEHOLDER};
        populateBarTicket(barData);
        
        // Auto-print and close
        window.onload = function() {{
            setTimeout(function() {{
                window.print();
                setTimeout(function() {{
                    window.close();
                }}, 1000);
            }}, 500);
        }};
    </script>
</body>
</html>"""

    # Fill and save bar ticket
    json_data = json.dumps(bar_data, ensure_ascii=False, indent=2)
    final_bar_html = (
        bar_html_template
        .replace('{DATA_PLACEHOLDER}', json_data)
        .replace('{CLIENT_NAME}', _shape_ar_textfile(get_client_name() or (setting_get("company_name", "بيروت") or "بيروت")))
    )

    bar_filename = f"bar-{table_code}-{datetime.now():%Y%m%d%H%M%S}.html"
    bar_path = _BAR_DIR / bar_filename
    bar_path.write_text(final_bar_html, encoding='utf-8')

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
        html_path = _generate_html_bar_ticket(table_code, data)
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
        html_path = _generate_html_receipt(
            table_code=table_code,
            items=data,
            subtotal=subtotal,
            discount=discount,
            total=total,
            method=method,
            cashier=cashier
        )
        self._print_html_file(html_path, self.cashier_printer)
        return html_path

    def _print_html_file(self, html_path: Path, printer_name: str) -> None:
        """Print HTML/PDF with thermal-friendly settings"""
        try:
            if sys.platform.startswith("win"):
                print(f"[DEBUG] Windows printing: {html_path}")
                # Prefer PDF (203 dpi)
                pdf_path = _convert_html_to_pdf(html_path)
                target_path = pdf_path if (pdf_path and pdf_path.exists()) else html_path

                # Use PowerShell PrintTo to honor the selected printer
                ps_cmd = [
                    "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "Start-Process",
                    f"'{str(target_path)}'",
                    "-Verb", "PrintTo",
                    "-ArgumentList", f"'{printer_name}'"
                ]
                try:
                    subprocess.run(ps_cmd, check=True)
                    print("[DEBUG] PrintTo sent successfully")
                    return
                except Exception as e:
                    print(f"[WARN] PrintTo failed ({e}); falling back to default 'print'")

                # Fallback: default printer (if PrintTo fails)
                try:
                    os.startfile(str(target_path), "print")
                    print("[DEBUG] Sent to default printer using 'print' verb")
                    return
                except Exception as e:
                    print(f"[ERROR] Default print failed: {e}")
                    # Last resort: just open (user can Ctrl+P)
                    os.startfile(str(target_path))
                    return

            else:
                # Linux / macOS
                print(f"[DEBUG] Unix printing: {html_path}")
                pdf_path = _convert_html_to_pdf(html_path)
                target_path = pdf_path if (pdf_path and pdf_path.exists()) else html_path
                if _can_system_print(printer_name):
                    subprocess.Popen(["lp", "-d", printer_name, str(target_path)])
                else:
                    subprocess.Popen(["lp", str(target_path)])
        except Exception as e:
            print(f"[ERROR] Print failed: {e}")
            # Platform-aware fallback: open only
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(html_path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(html_path)])
                else:
                    subprocess.Popen(["xdg-open", str(html_path)])
            except Exception as e2:
                print(f"[ERROR] Fallback open failed: {e2}")

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
        print(f"Thermal version: {_shape_ar_textfile(test_text)}")
    else:
        print("Arabic reshaping not available")

    print("===========================")

if __name__ == "__main__":
    test_arabic_shaping()