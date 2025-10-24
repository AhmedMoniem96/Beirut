"""Receipt/ticket PDF renderer for 80mm thermal printers (XP-80C) with Arabic shaping.
ULTIMATE FIX: Uses ESC/POS direct commands - bypasses PDF completely for thermal printers.
"""

from __future__ import annotations
import os, sys, subprocess, shutil, re
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
    """Arabic shaping for ESC/POS printers - NO bidi reordering for thermal printers."""
    if not text:
        return ""
    if not _AR_OK:
        _warn_arabic_missing()
        return text
    try:
        # For ESC/POS thermal printers: reshape but DON'T apply bidi algorithm
        reshaped = arabic_reshaper.reshape(text)
        print(f"[DEBUG _shape_ar_escpos] '{text}' -> '{reshaped}'")
        return reshaped  # ← CRITICAL FIX: Remove get_display() for thermal printers
    except Exception as e:
        print(f"[WARN] Arabic reshaping failed: {e}")
        return text

def _shape_ar_textfile(text: str) -> str:
    """Arabic shaping for text files - use same as ESC/POS for consistency."""
    # SIMPLIFIED: Use the same shaping as ESC/POS to avoid reversed text
    print(f"[DEBUG _shape_ar_textfile] Input: '{text}'")
    result = _shape_ar_escpos(text)
    print(f"[DEBUG _shape_ar_textfile] Output: '{result}'")
    return result

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
    """Print bar ticket with BOX STYLE - only unprinted items + customizations"""
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
        p.set(align='center')

        # HEADER BOX
        p.text("┌──────────────────────────────┐\n")
        p.set(text_type='B', width=2, height=2)
        p.text(f"│{_shape_ar_escpos(texts.get('receipt.bar.header')):^30}│\n")
        p.set(text_type='NORMAL', width=1, height=1)
        p.text("├──────────────────────────────┤\n")
        p.set(align='right')
        p.text(f"│{_shape_ar_escpos(texts.get('receipt.bar.table', table_code=table_code)):<30}│\n")
        p.text(f"│{_shape_ar_escpos(texts.get('receipt.bar.issued_at', timestamp=ts)):<30}│\n")
        p.text("├──────────────────────────────┤\n")

        # ITEMS HEADER
        p.text(f"│{'الصنف':<18} {'الكمية':<8}│\n")
        p.text("├──────────────────────────────┤\n")

        # ITEMS LIST
        for it in items:
            name = _shape_ar_escpos(str(it["name"]))
            qty = _format_qty(float(it.get("qty", 0) or 0))

            # Truncate long names
            if len(name) > 18:
                name = name[:15] + "..."

            p.text(f"│ {name:<18} {qty:>8} │\n")

            # Show notes/customizations if any
            for segment in _note_segments(it.get("note", "")):
                note_display = _shape_ar_escpos(f"• {segment}")
                if len(note_display) > 28:
                    note_display = note_display[:25] + "..."
                p.text(f"│ {note_display:<28} │\n")

        p.text("└──────────────────────────────┘\n")
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
        printer_name: str,
        discount_label: str,
) -> bool:
    """Render cashier receipt following the updated branded layout."""
    p = _get_escpos_printer(printer_name)
    if not p:
        return False

    try:
        fn = getattr(p, "open", None)
        if callable(fn):
            fn()
    except Exception as e:
        print(f"[DEBUG] Cannot open ESC/POS device: {e}")
        return False

    try:
        currency = setting_get("currency", "EGP") or "EGP"
        client_name = get_client_name() or (setting_get("company_name", "Beirut") or "Beirut")
        subtitle = texts.get("receipt.cashier.subtitle")
        contact_address = texts.get("receipt.cashier.address")
        contact_phone = texts.get("receipt.cashier.phone")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        subtotal_display = _format_currency_cents(subtotal, currency)
        discount_display = _format_currency_cents(discount, currency)
        service_display = _format_currency_cents(service, currency)
        tax_display = _format_currency_cents(tax, currency)
        total_display = _format_currency_cents(total, currency)
        total_qty = sum(float(it.get("qty", 0) or 0) for it in items)

        divider_heavy = "═" * 32
        divider_light = "─" * 32

        # Initialize printer
        _set_ar_codepage(p)
        p.set(align='center')

        p.text(divider_heavy + "\n")
        p.set(text_type='B', width=2, height=2)
        p.text(_shape_ar_escpos(client_name) + "\n")
        p.set(text_type='NORMAL', width=1, height=1)
        if subtitle:
            p.text(_shape_ar_escpos(subtitle) + "\n")
        p.text(divider_heavy + "\n")

        p.set(align='right')
        p.text(_shape_ar_escpos(f"التاريخ والوقت: {ts}") + "\n")
        p.text(_shape_ar_escpos(f"الطاولة: {table_code}") + "\n")
        p.text(_shape_ar_escpos(f"النادل: {cashier}") + "\n")
        p.text(_shape_ar_escpos(f"طريقة الدفع: {method}") + "\n")
        p.text(divider_light + "\n")

        p.set(text_type='B')
        p.text(_shape_ar_escpos("الأصناف المطلوبة") + "\n")
        p.set(text_type='NORMAL')
        p.text(divider_light + "\n")

        for it in items:
            name = _shape_ar_escpos(str(it["name"]))
            qty_display = _format_qty(float(it.get("qty", 0) or 0))
            unit_display = _format_currency_cents(it.get("unit_price", 0), currency)
            item_total_display = _format_currency_cents(it.get("total_cents", 0), currency)

            p.text(name + "\n")
            p.text(_shape_ar_escpos(f"الكمية: {qty_display}  السعر: {unit_display}") + "\n")
            p.text(_shape_ar_escpos(f"الإجمالي: {item_total_display}") + "\n")

            for segment in _note_segments(it.get("note", "")):
                p.text(_shape_ar_escpos(f"• {segment}") + "\n")

            p.text(divider_light + "\n")

        discount_label_text = discount_label or texts.get("receipt.cashier.discount")

        p.text(_shape_ar_escpos(f"إجمالي القطع: {_format_qty(total_qty)}") + "\n")
        p.text(_shape_ar_escpos(f"المجموع الفرعي: {subtotal_display}") + "\n")
        p.text(_shape_ar_escpos(f"{discount_label_text}: {discount_display}") + "\n")
        if service:
            p.text(_shape_ar_escpos(f"الخدمة: {service_display}") + "\n")
        if tax:
            p.text(_shape_ar_escpos(f"الضريبة: {tax_display}") + "\n")

        p.text(divider_light + "\n")
        p.set(text_type='B')
        p.text(_shape_ar_escpos(f"الإجمالي المستحق: {total_display}") + "\n")
        p.set(text_type='NORMAL')
        p.text(divider_light + "\n")

        p.set(align='center')
        if contact_address:
            p.text(_shape_ar_escpos(contact_address) + "\n")
        if contact_phone:
            p.text(_shape_ar_escpos(contact_phone) + "\n")
        footer = texts.get("receipt.footer")
        if footer:
            p.text(_shape_ar_escpos(footer) + "\n")
        p.text("\n")

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
        is_bar: bool = False,
        discount_label: str | None = None,
) -> Path:
    """ULTRA-COMPACT text file receipt"""
    _ensure_dirs()

    currency = setting_get("currency", "EGP") or "EGP"
    client_name = get_client_name() or (setting_get("company_name", "Beirut") or "Beirut")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: List[str] = []
    divider_heavy = "═" * 32
    divider_light = "─" * 32

    print(f"[DEBUG _save_receipt_as_text] Starting to build receipt for table {table_code}")
    print(f"[DEBUG _save_receipt_as_text] is_bar: {is_bar}")

    if is_bar:
        lines.append(divider_heavy)
        bar_header = texts.get("receipt.bar.header")
        print(f"[DEBUG _save_receipt_as_text] Bar header raw: '{bar_header}'")
        shaped_bar_header = _shape_ar_textfile(bar_header)
        print(f"[DEBUG _save_receipt_as_text] Bar header shaped: '{shaped_bar_header}'")
        lines.append(shaped_bar_header)
        lines.append(divider_heavy)

        bar_table = texts.get("receipt.bar.table", table_code=table_code)
        print(f"[DEBUG _save_receipt_as_text] Bar table raw: '{bar_table}'")
        lines.append(_shape_ar_textfile(bar_table))

        bar_issued = texts.get("receipt.bar.issued_at", timestamp=ts)
        print(f"[DEBUG _save_receipt_as_text] Bar issued raw: '{bar_issued}'")
        lines.append(_shape_ar_textfile(bar_issued))
        lines.append(divider_light)

        for it in items:
            name_raw = str(it["name"])
            print(f"[DEBUG _save_receipt_as_text] Item name raw: '{name_raw}'")
            name_shaped = _shape_ar_textfile(name_raw)
            print(f"[DEBUG _save_receipt_as_text] Item name shaped: '{name_shaped}'")
            lines.append(name_shaped)

            qty_display = _format_qty(float(it.get("qty", 0) or 0))
            qty_text = f"الكمية: {qty_display}"
            print(f"[DEBUG _save_receipt_as_text] Qty text raw: '{qty_text}'")
            lines.append(_shape_ar_textfile(qty_text))

            for segment in _note_segments(it.get("note", "")):
                note_text = f"• {segment}"
                print(f"[DEBUG _save_receipt_as_text] Note text raw: '{note_text}'")
                lines.append(_shape_ar_textfile(note_text))
            lines.append(divider_light)
    else:
        subtitle = texts.get("receipt.cashier.subtitle")
        contact_address = texts.get("receipt.cashier.address")
        contact_phone = texts.get("receipt.cashier.phone")
        subtotal_display = _format_currency_cents(subtotal, currency)
        discount_display = _format_currency_cents(discount, currency)
        service_display = _format_currency_cents(service, currency)
        tax_display = _format_currency_cents(tax, currency)
        total_display = _format_currency_cents(total, currency)
        total_qty = sum(float(it.get("qty", 0) or 0) for it in items)
        discount_label_text = discount_label or texts.get("receipt.cashier.discount")

        print(f"[DEBUG _save_receipt_as_text] Client name raw: '{client_name}'")
        lines.append(divider_heavy)
        lines.append(_shape_ar_textfile(client_name))
        if subtitle:
            print(f"[DEBUG _save_receipt_as_text] Subtitle raw: '{subtitle}'")
            lines.append(_shape_ar_textfile(subtitle))
        lines.append(divider_heavy)

        date_text = f"التاريخ والوقت: {ts}"
        print(f"[DEBUG _save_receipt_as_text] Date text raw: '{date_text}'")
        lines.append(_shape_ar_textfile(date_text))

        table_text = f"الطاولة: {table_code}"
        print(f"[DEBUG _save_receipt_as_text] Table text raw: '{table_text}'")
        lines.append(_shape_ar_textfile(table_text))

        cashier_text = f"النادل: {cashier}"
        print(f"[DEBUG _save_receipt_as_text] Cashier text raw: '{cashier_text}'")
        lines.append(_shape_ar_textfile(cashier_text))

        method_text = f"طريقة الدفع: {method}"
        print(f"[DEBUG _save_receipt_as_text] Method text raw: '{method_text}'")
        lines.append(_shape_ar_textfile(method_text))
        lines.append(divider_light)

        items_header = "الأصناف المطلوبة"
        print(f"[DEBUG _save_receipt_as_text] Items header raw: '{items_header}'")
        lines.append(_shape_ar_textfile(items_header))
        lines.append(divider_light)

        for it in items:
            name_raw = str(it["name"])
            print(f"[DEBUG _save_receipt_as_text] Item name raw: '{name_raw}'")
            name_shaped = _shape_ar_textfile(name_raw)
            print(f"[DEBUG _save_receipt_as_text] Item name shaped: '{name_shaped}'")
            lines.append(name_shaped)

            qty_display = _format_qty(float(it.get("qty", 0) or 0))
            unit_display = _format_currency_cents(it.get("unit_price", 0), currency)
            qty_price_text = f"الكمية: {qty_display}  السعر: {unit_display}"
            print(f"[DEBUG _save_receipt_as_text] Qty/Price text raw: '{qty_price_text}'")
            lines.append(_shape_ar_textfile(qty_price_text))

            item_total_display = _format_currency_cents(it.get("total_cents", 0), currency)
            total_text = f"الإجمالي: {item_total_display}"
            print(f"[DEBUG _save_receipt_as_text] Total text raw: '{total_text}'")
            lines.append(_shape_ar_textfile(total_text))

            for segment in _note_segments(it.get("note", "")):
                note_text = f"• {segment}"
                print(f"[DEBUG _save_receipt_as_text] Note text raw: '{note_text}'")
                lines.append(_shape_ar_textfile(note_text))
            lines.append(divider_light)

        total_qty_text = f"إجمالي القطع: {_format_qty(total_qty)}"
        print(f"[DEBUG _save_receipt_as_text] Total qty text raw: '{total_qty_text}'")
        lines.append(_shape_ar_textfile(total_qty_text))

        subtotal_text = f"المجموع الفرعي: {subtotal_display}"
        print(f"[DEBUG _save_receipt_as_text] Subtotal text raw: '{subtotal_text}'")
        lines.append(_shape_ar_textfile(subtotal_text))

        discount_text = f"{discount_label_text}: {discount_display}"
        print(f"[DEBUG _save_receipt_as_text] Discount text raw: '{discount_text}'")
        lines.append(_shape_ar_textfile(discount_text))

        if service:
            service_text = f"الخدمة: {service_display}"
            print(f"[DEBUG _save_receipt_as_text] Service text raw: '{service_text}'")
            lines.append(_shape_ar_textfile(service_text))
        if tax:
            tax_text = f"الضريبة: {tax_display}"
            print(f"[DEBUG _save_receipt_as_text] Tax text raw: '{tax_text}'")
            lines.append(_shape_ar_textfile(tax_text))
        lines.append(divider_light)

        total_due_text = f"الإجمالي المستحق: {total_display}"
        print(f"[DEBUG _save_receipt_as_text] Total due text raw: '{total_due_text}'")
        lines.append(_shape_ar_textfile(total_due_text))
        lines.append(divider_light)

        if contact_address:
            print(f"[DEBUG _save_receipt_as_text] Address raw: '{contact_address}'")
            lines.append(_shape_ar_textfile(contact_address))
        if contact_phone:
            print(f"[DEBUG _save_receipt_as_text] Phone raw: '{contact_phone}'")
            lines.append(_shape_ar_textfile(contact_phone))
        footer = texts.get("receipt.footer")
        if footer:
            print(f"[DEBUG _save_receipt_as_text] Footer raw: '{footer}'")
            lines.append(_shape_ar_textfile(footer))

    lines.append("\n")

    folder = _BAR_DIR if is_bar else _RECEIPTS_DIR
    filename = f"{datetime.now():%Y%m%d-%H%M%S}-{'bar' if is_bar else 'cashier'}-{table_code}.txt"
    target = folder / filename

    print(f"[DEBUG _save_receipt_as_text] Writing to file: {target}")
    print(f"[DEBUG _save_receipt_as_text] First few lines preview:")
    for i, line in enumerate(lines[:10]):
        print(f"[DEBUG _save_receipt_as_text] Line {i}: '{line}'")

    target.write_text("\n".join(lines), encoding='utf-8')

    # Verify what was actually written
    written_content = target.read_text(encoding='utf-8')
    print(f"[DEBUG _save_receipt_as_text] ACTUAL FILE CONTENT (first 500 chars):")
    print(written_content[:500])

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

        # Fallback ONLY if ESC/POS failed: save and (optionably) CUPS-print text file
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
        data = _collapse_items(items)
        svc = service or 0
        tx = tax or 0
        label_text = discount_label or texts.get("orders.discount_summary_label")

        # Try ESC/POS first
        if _ESCPOS_OK and not _DISABLE_ESCPOS:
            success = _print_escpos_cashier_receipt(
                table_code,
                data,
                subtotal,
                discount,
                svc,
                tx,
                total,
                method,
                cashier,
                self.cashier_printer,
                label_text,
            )
            if success:
                # Save text file for records, DON'T send to printer again
                return _save_receipt_as_text(
                    table_code,
                    data,
                    subtotal,
                    discount,
                    svc,
                    tx,
                    total,
                    method,
                    cashier,
                    is_bar=False,
                    discount_label=label_text,
                )

        # Fallback ONLY if ESC/POS failed: save and (optionally) CUPS-print text file
        txt = _save_receipt_as_text(
            table_code,
            data,
            subtotal,
            discount,
            svc,
            tx,
            total,
            method,
            cashier,
            is_bar=False,
            discount_label=label_text,
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
        print(f"ESC/POS version: {_shape_ar_escpos(test_text)}")
        print(f"Textfile version: {_shape_ar_textfile(test_text)}")
    else:
        print("Arabic reshaping not available")

    print("===========================")

# Call diagnostic at module load
test_arabic_shaping()