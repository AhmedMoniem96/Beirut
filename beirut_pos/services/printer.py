"""Enhanced receipt/ticket renderer for XP-80C thermal printers with improved design."""
from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional

# ---------------- ESC/POS availability ----------------
try:
    from escpos.printer import Usb
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:
    _ESCPOS_OK = False
    print("❌ python-escpos not installed")

from ..core.db import setting_get
from ..core.paths import DATA_DIR
from ..utils.currency import format_pounds
from ..core.bus import bus

# ---------------- Paths & constants ----------------
_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

# ---------------- XP-80C USB Configuration ----------------
XP80C_VENDOR_ID = 0x0416
XP80C_PRODUCT_ID = 0x5011

# Paper width for 80mm thermal printer (~48 chars)
PAPER_WIDTH = 48

def _ensure_dirs():
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)

# ---------------- Arabic shaping ----------------
_AR_OK = False
try:
    import arabic_reshaper
    _AR_OK = True
except ImportError:
    print("❌ arabic-reshaper not installed")

def _shape_ar_text(text: str) -> str:
    if not text or not _AR_OK:
        return text
    try:
        return arabic_reshaper.reshape(text)
    except Exception:
        return text

def _format_currency_simple(cents: int | float) -> str:
    try:
        amount = int(round(float(cents))) / 100
        return f"{amount:.2f}"
    except Exception:
        return str(cents)

def _format_qty(qty: float) -> str:
    rounded = round(qty)
    if abs(qty - rounded) < 1e-6:
        return str(int(rounded))
    return f"{qty:.2f}".rstrip("0").rstrip(".")

def _note_segments(note: str, include_sugar: bool = False) -> list[str]:
    if not note:
        return []
    cleaned = note.replace("\n", " ")
    parts = [seg.strip(" ؛-•") for seg in cleaned.split("؛")]

    if include_sugar:
        # Include all notes (for bar tickets) - clean sugar notes
        result = []
        for seg in parts:
            # Remove "سكر:" prefix if present
            if "سكر:" in seg:
                seg = seg.replace("سكر:", "").strip()
            # Remove "sugar:" prefix if present
            seg_cleaned = seg.replace("sugar:", "").strip()
            if seg_cleaned:
                result.append(seg_cleaned)
        return result
    else:
        # Filter out sugar-related notes (for receipts)
        filtered = []
        for seg in parts:
            seg_lower = seg.lower()
            # Skip if it's a sugar note (contains "سكر" or "sugar")
            if "سكر" not in seg and "sugar" not in seg_lower:
                filtered.append(seg)
        return [seg for seg in filtered if seg]

def _center_text(text: str, width: int = PAPER_WIDTH) -> str:
    """Center text within given width."""
    text_len = len(text)
    if text_len >= width:
        return text
    padding = (width - text_len) // 2
    return " " * padding + text

def _draw_line(char: str = "─", width: int = PAPER_WIDTH) -> str:
    """Draw a decorative line."""
    return char * width

def _format_item_line(name: str, price: str, width: int = PAPER_WIDTH) -> str:
    """Format item with right-aligned price - handles both LTR and RTL text."""
    # Strip any existing spaces
    name = name.strip()
    price = price.strip()

    # Calculate visual length (approximate for mixed text)
    name_len = len(name)
    price_len = len(price)

    # Ensure minimum spacing
    total_len = name_len + price_len
    if total_len >= width:
        # Truncate name if too long
        available = width - price_len - 3
        if available > 0:
            name = name[:available] + ".."
            name_len = len(name)
        else:
            name = ""
            name_len = 0

    # Calculate spacing
    spacing = width - name_len - price_len
    if spacing < 1:
        spacing = 1

    return name + " " * spacing + price

# ---------------- TERMINAL PREVIEW ----------------
def _print_terminal_receipt(table_code: str, items: List[dict], subtotal: int,
                           discount: int, total: int, cashier: str):
    """Enhanced receipt preview to terminal"""
    ts = datetime.now().strftime("%Y/%m/%d %H:%M")

    print("\n" + "="*50)
    print("🧾 ENHANCED RECEIPT PREVIEW")
    print("="*50)

    # Header with decorative borders
    print(_center_text("╔" + "═" * 30 + "╗"))
    print(_center_text("║  " + _shape_ar_text('كافيه بيروت') + "  ║"))
    print(_center_text("║    Cafe Beirut    ║"))
    print(_center_text("╚" + "═" * 30 + "╝"))
    print()

    # Info section
    print(f"📅 {_shape_ar_text('التاريخ:')} {ts}")
    print(f"🪑 {_shape_ar_text('الطاولة:')} {table_code}")
    print(f"👤 {_shape_ar_text('الكاشير:')} {_shape_ar_text(cashier)}")
    print(_draw_line("═"))
    print()

    # Items header
    print(_center_text(_shape_ar_text("قائمة الطلبات")))
    print(_draw_line("─"))

    # Items
    for idx, it in enumerate(items, 1):
        name = _shape_ar_text(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))
        total_price = _format_currency_simple(it.get("total_cents", 0))

        # Get notes
        notes = _note_segments(it.get("note", ""))

        # Add first note (customized) to product name if exists
        if notes:
            first_note = _shape_ar_text(notes[0])
            item_line = f"{idx}. {name} ({first_note}) × {qty}"
            remaining_notes = notes[1:]
        else:
            item_line = f"{idx}. {name} × {qty}"
            remaining_notes = []

        print(_format_item_line(item_line, total_price))

        # Print remaining notes if any
        for note in remaining_notes:
            shaped_note = _shape_ar_text(note)
            print(f"   ↳ {shaped_note}")

        if idx < len(items):
            print(_draw_line("·"))

    print(_draw_line("═"))

    # Totals section with proper alignment
    subtotal_str = _format_currency_simple(subtotal)
    print(_format_item_line(_shape_ar_text("المجموع الفرعي:"), subtotal_str))

    if discount > 0:
        discount_str = _format_currency_simple(discount)
        print(_format_item_line(_shape_ar_text("الخصم:"), f"-{discount_str}"))
        print(_draw_line("─"))

    total_str = _format_currency_simple(total)
    print(_format_item_line(_shape_ar_text("💰 الإجمالي:"), total_str))
    print(_draw_line("═"))
    print()

    # Footer
    print(_center_text(_shape_ar_text("شكراً لزيارتكم")))
    print(_center_text("Thank you for visiting!"))
    print(_center_text("★ ★ ★"))
    print()

    print("\n" + "="*50)
    print("✅ PREVIEW COMPLETED (No thermal printer)")
    print("="*50 + "\n")

def _print_terminal_bar_ticket(table_code: str, items: List[dict]):
    """Enhanced bar ticket preview to terminal"""
    print("\n" + "="*50)
    print("🍸 ENHANCED BAR TICKET PREVIEW")
    print("="*50)

    ts = datetime.now().strftime("%H:%M")
    print(f"🕐 {ts}  |  🪑 {_shape_ar_text('الطاولة:')} {table_code}")
    print(_draw_line("═"))

    for idx, it in enumerate(items, 1):
        name = _shape_ar_text(str(it["name"]))
        qty = _format_qty(float(it.get("qty", 0) or 0))

        # Get notes (include sugar for bar tickets)
        notes = _note_segments(it.get("note", ""), include_sugar=True)

        # Combine first two notes if available (customized + sugar)
        if len(notes) >= 2:
            first_note = _shape_ar_text(notes[0])
            second_note = _shape_ar_text(notes[1])
            item_line = f"{idx}. {name} ({first_note} {second_note}) × {qty}"
            remaining_notes = notes[2:]
        elif len(notes) == 1:
            first_note = _shape_ar_text(notes[0])
            item_line = f"{idx}. {name} ({first_note}) × {qty}"
            remaining_notes = []
        else:
            item_line = f"{idx}. {name} × {qty}"
            remaining_notes = []

        print(item_line)

        # Print remaining notes if any
        for note in remaining_notes:
            shaped_note = _shape_ar_text(note)
            print(f"  • {shaped_note}")

        if idx < len(items):
            print("────────────────")

    print("\n" + _draw_line("═"))

    print("\n" + "="*50)
    print("✅ BAR TICKET PREVIEW COMPLETED")
    print("="*50 + "\n")

# ---------------- Thermal Printer Functions ----------------
def _find_xp80c_printer():
    """Find and initialize XP-80C thermal printer with detailed debugging"""
    print("🖨️  Searching for thermal printer...")

    if not _ESCPOS_OK:
        print("❌ ESC/POS library not available")
        return None

    if _DISABLE_ESCPOS:
        print("ℹ️  ESC/POS disabled by environment variable")
        return None

    try:
        print(f"🔍 Trying XP-80C at USB {XP80C_VENDOR_ID:04x}:{XP80C_PRODUCT_ID:04x}")
        printer = Usb(XP80C_VENDOR_ID, XP80C_PRODUCT_ID)
        print("✅ XP-80C Thermal printer connected!")
        return printer

    except USBNotFoundError:
        print("❌ XP-80C not found at specified USB IDs")

        # Try common thermal printer vendors
        common_printers = [
            (0x0416, 0x5011),  # Xprinter XP-80C
            (0x04b8, 0x0202),  # Epson TM-T88IV
            (0x04b8, 0x0e15),  # Epson TM-T88V
            (0x067b, 0x2305),  # Prolific PL2305
        ]

        for vendor, product in common_printers:
            try:
                print(f"🔍 Trying USB {vendor:04x}:{product:04x}")
                printer = Usb(vendor, product)
                print(f"✅ Found compatible printer at {vendor:04x}:{product:04x}")
                return printer
            except USBNotFoundError:
                continue

        print("❌ No compatible thermal printers found")
        return None

    except Exception as e:
        print(f"❌ Printer connection error: {e}")
        return None

def _setup_printer_arabic(printer):
    """Configure printer for Arabic text support."""
    try:
        print("🔄 Setting up Arabic encoding...")
        printer._raw(b'\x1B@')  # Initialize printer
        printer._raw(b'\x1Bt\x16')  # Code page 862 (Hebrew/Arabic)
        printer._raw(b'\x1BR\x08')  # Arabic character set
        print("✅ Arabic encoding setup successful")
        return True
    except Exception as e:
        print(f"❌ Arabic setup failed: {e}")
        return False

def _print_escpos_receipt(printer, table_code: str, items: List[dict], subtotal: int,
                         discount: int, total: int, method: str, cashier: str):
    """Enhanced thermal receipt printing."""
    print(f"🖨️  Starting thermal receipt print for table {table_code}")

    if not printer:
        print("❌ No printer available - cannot print")
        raise ValueError("No printer available")

    ts = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"📋 Processing {len(items)} items...")

    try:
        if not _setup_printer_arabic(printer):
            print("❌ Failed to setup Arabic - printing may have issues")

        # Decorative header
        printer.set(align='center', bold=True, double_width=True)
        printer.text("═" * 24 + "\n")
        printer.text(_shape_ar_text("كافيه بيروت") + "\n")
        printer.set(double_width=False)
        printer.text("Cafe Beirut\n")
        printer.set(bold=True, double_width=True)
        printer.text("═" * 24 + "\n\n")

        # Info section
        printer.set(align='left', bold=False, double_width=False)
        printer.text(f"{_shape_ar_text('التاريخ:')} {ts}\n")
        printer.text(f"{_shape_ar_text('الطاولة:')} {table_code}\n")
        printer.text(f"{_shape_ar_text('الكاشير:')} {_shape_ar_text(cashier)}\n")
        printer.text("─" * PAPER_WIDTH + "\n\n")

        # Items header
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("قائمة الطلبات") + "\n")
        printer.set(align='left')
        printer.text("─" * PAPER_WIDTH + "\n")

        # Items
        for idx, it in enumerate(items, 1):
            name = _shape_ar_text(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))
            total_price = _format_currency_simple(it.get("total_cents", 0))

            # Get notes
            notes = _note_segments(it.get("note", ""))

            # Add first note (customized) to product name if exists
            if notes:
                first_note = _shape_ar_text(notes[0])
                item_text = f"{idx}. {name} ({first_note}) × {qty}"
                remaining_notes = notes[1:]
            else:
                item_text = f"{idx}. {name} × {qty}"
                remaining_notes = []

            # Item on one line - use left alignment for consistent display
            printer.set(bold=True, align='left')

            # Calculate spacing for right-aligned price
            spacing = PAPER_WIDTH - len(item_text) - len(total_price)
            if spacing < 1:
                # Truncate if too long
                max_len = PAPER_WIDTH - len(total_price) - 3
                if len(item_text) > max_len:
                    item_text = item_text[:max_len] + ".."
                    spacing = PAPER_WIDTH - len(item_text) - len(total_price)
                else:
                    spacing = 1

            printer.text(item_text + " " * spacing + total_price + "\n")

            # Print remaining notes if any
            if remaining_notes:
                printer.set(bold=False, align='left')
                for note in remaining_notes:
                    shaped_note = _shape_ar_text(note)
                    printer.text(f"   > {shaped_note}\n")

            if idx < len(items):
                printer.set(bold=False, align='left')
                printer.text("·" * PAPER_WIDTH + "\n")

        printer.text("═" * PAPER_WIDTH + "\n")

        # Totals section
        printer.set(align='right', bold=False)
        subtotal_str = _format_currency_simple(subtotal)
        printer.text(f"{_shape_ar_text('المجموع الفرعي:')} {subtotal_str}\n")

        if discount > 0:
            discount_str = _format_currency_simple(discount)
            printer.text(f"{_shape_ar_text('الخصم:')} -{discount_str}\n")
            printer.text("─" * PAPER_WIDTH + "\n")

        # Grand total (large and bold)
        printer.set(bold=True, double_height=True)
        total_str = _format_currency_simple(total)
        printer.text(f"{_shape_ar_text('الإجمالي:')} {total_str}\n")
        printer.set(double_height=False)

        printer.text("═" * PAPER_WIDTH + "\n\n")

        # Footer
        printer.set(align='center', bold=True)
        printer.text(_shape_ar_text("شكراً لزيارتكم") + "\n")
        printer.set(bold=False)
        printer.text("Thank you!\n")
        printer.text("★ ★ ★\n")
        printer.text("\n" * 3)

        printer.cut()
        print("✅ Enhanced receipt printed to thermal printer!")

    except Exception as e:
        print(f"❌ ESC/POS printing failed: {e}")
        raise

def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]):
    """Enhanced bar ticket printing."""
    print(f"🖨️  Starting thermal bar ticket print for table {table_code}")

    if not printer:
        print("❌ No printer available - cannot print")
        raise ValueError("No printer available")

    try:
        if not _setup_printer_arabic(printer):
            print("❌ Failed to setup Arabic - printing may have issues")

        ts = datetime.now().strftime("%H:%M")

        # Table and time info
        printer.set(align='left', bold=False, double_width=False)
        printer.text(f"{ts}  |  {_shape_ar_text('الطاولة:')} {table_code}\n")
        printer.text("─" * PAPER_WIDTH + "\n\n")

        # Items
        for idx, it in enumerate(items, 1):
            name = _shape_ar_text(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))

            # Get notes (include sugar for bar tickets)
            notes = _note_segments(it.get("note", ""), include_sugar=True)

            # Combine first two notes if available (customized + sugar)
            if len(notes) >= 2:
                first_note = _shape_ar_text(notes[0])
                second_note = _shape_ar_text(notes[1])
                item_text = f"{idx}. {name} ({first_note} {second_note}) × {qty}"
                remaining_notes = notes[2:]
            elif len(notes) == 1:
                first_note = _shape_ar_text(notes[0])
                item_text = f"{idx}. {name} ({first_note}) × {qty}"
                remaining_notes = []
            else:
                item_text = f"{idx}. {name} × {qty}"
                remaining_notes = []

            # Item on one line
            printer.set(bold=True)
            printer.text(item_text + "\n")

            # Print remaining notes if any
            if remaining_notes:
                printer.set(bold=False)
                for note in remaining_notes:
                    shaped_note = _shape_ar_text(note)
                    printer.text(f"   * {shaped_note}\n")

            if idx < len(items):
                printer.set(bold=False)
                printer.text("─" * PAPER_WIDTH + "\n")

        printer.text("\n" + "═" * PAPER_WIDTH + "\n")
        printer.text("\n" * 2)

        printer.cut()
        print("✅ Enhanced bar ticket printed to thermal printer!")

    except Exception as e:
        print(f"❌ ESC/POS bar ticket failed: {e}")
        raise

def _collapse_items(items: Iterable) -> List[dict]:
    """Collapse duplicate items into single entries with combined quantities."""
    grouped = {}
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
        print("🔄 Initializing PrinterService...")
        self._escpos_printer = _find_xp80c_printer()
        if self._escpos_printer:
            print("✅ PrinterService ready with thermal printer")
        else:
            print("ℹ️  PrinterService ready (terminal preview only)")

    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        """Print enhanced bar ticket."""
        print(f"📋 Bar ticket requested for table {table_code}")
        data = _collapse_items(items)
        print(f"📦 Processing {len(data)} unique items")

        # Always show terminal preview
        _print_terminal_bar_ticket(table_code, data)

        # Try thermal printer if available
        if self._escpos_printer:
            try:
                _print_escpos_bar_ticket(self._escpos_printer, table_code, data)
                return True
            except Exception as e:
                print(f"❌ Thermal printing failed: {e}")
                print("📺 Falling back to terminal preview only")
        else:
            print("ℹ️  No thermal printer - using terminal preview only")

        return True

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
        """Print enhanced cashier receipt."""
        print(f"📋 Receipt requested for table {table_code}")
        data = _collapse_items(items)
        print(f"📦 Processing {len(data)} unique items")

        # Always show terminal preview
        _print_terminal_receipt(table_code, data, subtotal, discount, total, cashier)

        # Try thermal printer if available
        if self._escpos_printer:
            try:
                _print_escpos_receipt(
                    self._escpos_printer, table_code, data, subtotal,
                    discount, total, method, cashier
                )
                return True
            except Exception as e:
                print(f"❌ Thermal printing failed: {e}")
                print("📺 Falling back to terminal preview only")
        else:
            print("ℹ️  No thermal printer - using terminal preview only")

        return True

# Create the 'printer' instance that main_window.py is looking for
printer = PrinterService()

def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)

bus.subscribe("printers_changed", _apply_printer_settings)

# ---------------- Diagnostic function ----------------
def diagnose_printing():
    """Run diagnostics to see why printing might not work"""
    print("\n" + "="*60)
    print("🔧 PRINTING DIAGNOSTICS")
    print("="*60)

    # Test data
    test_items = [
        {"name": "عصير برتقال", "qty": 2, "total_cents": 2000, "note": "سكر عالي؛ مثلج"},
        {"name": "شاي", "qty": 1, "total_cents": 500, "note": "سكر خفيف"},
    ]

    print("Testing receipt printing...")
    result = printer.print_cashier_receipt("TEST", test_items, 2500, 500, 2000, "نقدي", "محمد")
    print(f"Final result: {result}")

    print("="*60)

if __name__ == "__main__":
    diagnose_printing()