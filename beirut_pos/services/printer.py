"""Enhanced receipt/ticket renderer for XP-80C thermal printers with improved design."""
from __future__ import annotations

import glob
import os
import sys
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

# ---------------- ESC/POS availability ----------------
try:  # pragma: no cover - optional dependency
    from escpos.printer import File, Usb
    from escpos.exceptions import USBNotFoundError
    _ESCPOS_OK = True
except ImportError:  # pragma: no cover - optional dependency
    _ESCPOS_OK = False

    class USBNotFoundError(Exception):
        """Fallback USB error when python-escpos is unavailable."""

    Usb = None  # type: ignore[assignment]
    File = None  # type: ignore[assignment]
    print("❌ python-escpos not installed")

from ..core.paths import DATA_DIR
from ..core.bus import bus

# ---------------- Paths & constants ----------------
_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_LOG_PATH = _OUTPUT_ROOT / "printer.log"
_DISABLE_ESCPOS = os.environ.get("BEIRUT_POS_DISABLE_ESCPOS", "0") == "1"

# ---------------- Thermal USB Configuration ----------------
XP80C_VENDOR_ID = 0x0416
XP80C_PRODUCT_ID = 0x5011

USB_PRINTER_IDS = [
    (0x0483, 0x5743),  # STMicroelectronics USB Printer Port
    (XP80C_VENDOR_ID, XP80C_PRODUCT_ID),
    (0x04B8, 0x0202),  # Epson TM-T88IV
    (0x04B8, 0x0E15),  # Epson TM-T88V
    (0x067B, 0x2305),  # Prolific PL2305 bridge
]

# Paper width for 80mm thermal printer (~48 chars)
PAPER_WIDTH = 48


def _ensure_dirs() -> None:
    for path in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        path.mkdir(parents=True, exist_ok=True)
    try:
        _LOG_PATH.touch(exist_ok=True)
    except Exception:
        pass


def _log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    formatted = f"[{timestamp}] {message}"
    print(message)
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(formatted + "\n")
    except Exception as exc:
        print(f"⚠️  Failed to write printer log: {exc}")


# ---------------- Arabic shaping ----------------
_AR_OK = False
try:  # pragma: no cover - optional dependency
    import arabic_reshaper

    _AR_OK = True
except ImportError:  # pragma: no cover - optional dependency
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


def _note_segments(note: str, *, include_sugar: bool = False) -> list[str]:
    if not note:
        return []
    cleaned = note.replace("\n", " ")
    parts = [segment.strip(" ؛-•") for segment in cleaned.split("؛")]

    if include_sugar:
        result: list[str] = []
        for segment in parts:
            if "سكر:" in segment:
                segment = segment.replace("سكر:", "").strip()
            segment_cleaned = segment.replace("sugar:", "").strip()
            if segment_cleaned:
                result.append(segment_cleaned)
        return result

    filtered: list[str] = []
    for segment in parts:
        lower_segment = segment.lower()
        if "سكر" not in segment and "sugar" not in lower_segment:
            filtered.append(segment)
    return [segment for segment in filtered if segment]


def _center_text(text: str, width: int = PAPER_WIDTH) -> str:
    text_length = len(text)
    if text_length >= width:
        return text
    padding = (width - text_length) // 2
    return " " * padding + text


def _draw_line(char: str = "─", width: int = PAPER_WIDTH) -> str:
    return char * width


def _format_item_line(name: str, price: str, width: int = PAPER_WIDTH) -> str:
    name = name.strip()
    price = price.strip()

    name_length = len(name)
    price_length = len(price)

    if name_length + price_length >= width:
        available = width - price_length - 3
        if available > 0:
            name = name[:available] + ".."
            name_length = len(name)
        else:
            name = ""
            name_length = 0

    spacing = width - name_length - price_length
    if spacing < 1:
        spacing = 1
    return name + " " * spacing + price


# ---------------- Layout helpers ----------------
def _build_receipt_lines(
    table_code: str,
    items: Sequence[dict],
    subtotal: int,
    discount: int,
    total: int,
    cashier: str,
) -> List[str]:
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M")
    lines: List[str] = []

    lines.append(_center_text("╔" + "═" * 30 + "╗"))
    lines.append(_center_text("║  " + _shape_ar_text("كافيه بيروت") + "  ║"))
    lines.append(_center_text("║    Cafe Beirut    ║"))
    lines.append(_center_text("╚" + "═" * 30 + "╝"))
    lines.append("")

    lines.append(f"📅 {_shape_ar_text('التاريخ:')} {timestamp}")
    lines.append(f"🪑 {_shape_ar_text('الطاولة:')} {table_code}")
    lines.append(f"👤 {_shape_ar_text('الكاشير:')} {_shape_ar_text(cashier)}")
    lines.append(_draw_line("═"))
    lines.append("")

    lines.append(_center_text(_shape_ar_text("قائمة الطلبات")))
    lines.append(_draw_line("─"))

    for index, item in enumerate(items, 1):
        name = _shape_ar_text(str(item["name"]))
        qty = _format_qty(float(item.get("qty", 0) or 0))
        total_price = _format_currency_simple(item.get("total_cents", 0))
        notes = _note_segments(item.get("note", ""))

        if notes:
            first_note = _shape_ar_text(notes[0])
            line_text = f"{index}. {name} ({first_note}) × {qty}"
            remaining_notes = notes[1:]
        else:
            line_text = f"{index}. {name} × {qty}"
            remaining_notes = []

        lines.append(_format_item_line(line_text, total_price))

        for note in remaining_notes:
            lines.append(f"   ↳ {_shape_ar_text(note)}")

        if index < len(items):
            lines.append(_draw_line("·"))

    lines.append(_draw_line("═"))

    subtotal_str = _format_currency_simple(subtotal)
    lines.append(_format_item_line(_shape_ar_text("المجموع الفرعي:"), subtotal_str))

    if discount > 0:
        discount_str = _format_currency_simple(discount)
        lines.append(_format_item_line(_shape_ar_text("الخصم:"), f"-{discount_str}"))
        lines.append(_draw_line("─"))

    total_str = _format_currency_simple(total)
    lines.append(_format_item_line(_shape_ar_text("💰 الإجمالي:"), total_str))
    lines.append(_draw_line("═"))
    lines.append("")

    lines.append(_center_text(_shape_ar_text("شكراً لزيارتكم")))
    lines.append(_center_text("Thank you for visiting!"))
    lines.append(_center_text("★ ★ ★"))
    lines.append("")

    return lines


def _build_bar_ticket_lines(table_code: str, items: Sequence[dict]) -> List[str]:
    timestamp = datetime.now().strftime("%H:%M")
    lines: List[str] = []

    lines.append(f"🕐 {timestamp}  |  🪑 {_shape_ar_text('الطاولة:')} {table_code}")
    lines.append(_draw_line("═"))

    for index, item in enumerate(items, 1):
        name = _shape_ar_text(str(item["name"]))
        qty = _format_qty(float(item.get("qty", 0) or 0))
        notes = _note_segments(item.get("note", ""), include_sugar=True)

        if len(notes) >= 2:
            first_note = _shape_ar_text(notes[0])
            second_note = _shape_ar_text(notes[1])
            line_text = f"{index}. {name} ({first_note} {second_note}) × {qty}"
            remaining_notes = notes[2:]
        elif len(notes) == 1:
            first_note = _shape_ar_text(notes[0])
            line_text = f"{index}. {name} ({first_note}) × {qty}"
            remaining_notes = []
        else:
            line_text = f"{index}. {name} × {qty}"
            remaining_notes = []

        lines.append(line_text)

        for note in remaining_notes:
            lines.append(f"  • {_shape_ar_text(note)}")

        if index < len(items):
            lines.append("────────────────")

    lines.append("")
    lines.append(_draw_line("═"))

    return lines


# ---------------- Terminal preview ----------------
def _print_terminal_receipt(
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    total: int,
    cashier: str,
) -> None:
    _log("\n" + "=" * 50)
    _log("🧾 ENHANCED RECEIPT PREVIEW")
    _log("=" * 50)

    for line in _build_receipt_lines(table_code, items, subtotal, discount, total, cashier):
        _log(line)

    _log("\n" + "=" * 50)
    _log("✅ PREVIEW COMPLETED (No thermal printer)")
    _log("=" * 50 + "\n")


def _print_terminal_bar_ticket(table_code: str, items: List[dict]) -> None:
    _log("\n" + "=" * 50)
    _log("🍸 ENHANCED BAR TICKET PREVIEW")
    _log("=" * 50)

    for line in _build_bar_ticket_lines(table_code, items):
        _log(line)

    _log("\n" + "=" * 50)
    _log("✅ BAR TICKET PREVIEW COMPLETED")
    _log("=" * 50 + "\n")


# ---------------- Printer helpers ----------------
class MockPrinter:
    """Simple in-memory printer used when ESC/POS output is disabled."""

    def __init__(self, name: str = "MockPrinter") -> None:
        self.name = name
        self.buffer: list[str] = []
        self.state: dict[str, object] = {}

    def text(self, data: str) -> None:  # pragma: no cover - minimal behaviour
        self.buffer.append(data)

    def set(self, **kwargs) -> None:  # pragma: no cover - minimal behaviour
        self.state.update(kwargs)

    def cut(self) -> None:  # pragma: no cover - minimal behaviour
        self.buffer.append("<CUT>")

    def _raw(self, data: bytes) -> None:  # pragma: no cover - minimal behaviour
        self.buffer.append(f"<RAW {data.hex()}>")

    def close(self) -> None:  # pragma: no cover - minimal behaviour
        self.buffer.append("<CLOSE>")

    def flush(self) -> str:
        return "".join(self.buffer)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.name}(len={len(self.buffer)})"


def _log_printer_error(prefix: str, error: Exception) -> None:
    _log(f"❌ {prefix}: {error}")


def _usblp_device_paths() -> list[str]:
    return sorted(glob.glob("/dev/usb/lp*"))


def _try_usb_printer(*, allow_when_blocked: bool = False):
    if not _ESCPOS_OK or Usb is None:
        return None

    lp_devices = _usblp_device_paths()
    if lp_devices and not allow_when_blocked:
        devices = ", ".join(lp_devices)
        _log(f"ℹ️  Kernel usblp driver detected ({devices}); skipping ESC/POS USB backend")
        return None

    for vendor, product in USB_PRINTER_IDS:
        try:
            _log(f"🔍 Trying ESC/POS USB printer {vendor:04x}:{product:04x}")
            printer = Usb(vendor, product, interface=0, in_ep=0x82, out_ep=0x01)
            _log(f"✅ ESC/POS USB printer ready at {vendor:04x}:{product:04x}")
            return printer
        except TypeError:
            try:
                printer = Usb(vendor, product)
                _log(f"✅ ESC/POS USB printer ready with default endpoints {vendor:04x}:{product:04x}")
                return printer
            except USBNotFoundError:
                _log(f"❌ ESC/POS USB printer not found at {vendor:04x}:{product:04x}")
            except Exception as exc:
                _log_printer_error("Printer connection error", exc)
        except USBNotFoundError:
            _log(f"❌ ESC/POS USB printer not found at {vendor:04x}:{product:04x}")
        except Exception as exc:
            _log_printer_error("Printer connection error", exc)
    return None


def _try_file_printer():
    if File is None:
        _log("❌ ESC/POS File backend unavailable")
        return None

    lp_devices = _usblp_device_paths()
    if not lp_devices:
        _log("ℹ️  No /dev/usb/lp* devices detected")

    for path in lp_devices:
        try:
            _log(f"🔍 Trying /dev backend at {path}")
            printer = File(path)
            _log(f"✅ /dev backend ready at {path}")
            return printer
        except Exception as exc:
            _log_printer_error(f"Failed to open {path}", exc)
    return None


def _printer_set_safe(printer, **kwargs) -> None:
    try:
        printer.set(**kwargs)
    except Exception as exc:  # pragma: no cover - depends on device
        _log_printer_error("Failed to apply printer settings", exc)


def _emit_lines_to_printer(printer, lines: Sequence[str]) -> None:
    _printer_set_safe(printer, align="left", bold=False, double_width=False, double_height=False)
    for line in lines:
        try:
            printer.text(line + "\n")
        except Exception as exc:
            _log_printer_error("Failed to send line to printer", exc)
            raise


# ---------------- Thermal Printer Functions ----------------
def _find_xp80c_printer():
    _log("🖨️  Searching for thermal printer...")

    if not _ESCPOS_OK or Usb is None:
        _log("❌ ESC/POS library not available")
        return None

    if _DISABLE_ESCPOS:
        _log("ℹ️  ESC/POS disabled by environment variable")
        return None

    printer = _try_usb_printer()
    if printer:
        return printer

    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    _log("❌ No compatible thermal printers found")
    return None


def _setup_printer_arabic(printer) -> bool:
    _log("🔄 Setting up Arabic encoding...")
    try:
        printer._raw(b"\x1B@")  # Reset device state
    except Exception as exc:
        _log_printer_error("Failed to reset printer", exc)
        return False

    code_pages = [
        (b"\x1Bt\x13", "CP1256"),
        (b"\x1Bt\x12", "CP864"),
        (b"\x1Bt\x0f", "CP720"),
        (b"\x1Bt\x16", "CP862"),
    ]
    selected_label: str | None = None
    for command, label in code_pages:
        try:
            printer._raw(command)
            selected_label = label
            _log(f"✅ Selected code page {label}")
            break
        except Exception as exc:
            _log_printer_error(f"Failed to set code page {label}", exc)

    if not selected_label:
        _log("⚠️  Unable to confirm Arabic code page; continuing with defaults")
    else:
        _log(f"✅ Arabic encoding setup successful ({selected_label})")

    try:
        printer._raw(b"\x1B\x61\x00")  # Ensure left alignment for manual spacing
    except Exception:
        pass

    return selected_label is not None


def _print_escpos_lines(printer, lines: Sequence[str]) -> None:
    _setup_printer_arabic(printer)
    _emit_lines_to_printer(printer, lines)
    try:
        printer.text("\n" * 3)
    except Exception as exc:
        _log_printer_error("Failed to add trailing space", exc)
        raise
    try:
        printer.cut()
    except Exception as exc:
        _log_printer_error("Failed to cut paper", exc)
        raise


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
    target = getattr(printer, "name", printer.__class__.__name__)
    _log(f"🖨️  Starting thermal receipt print for table {table_code} -> {target}")
    lines = _build_receipt_lines(table_code, items, subtotal, discount, total, cashier)
    _print_escpos_lines(printer, lines)
    _log(f"✅ Enhanced receipt printed to {target}!")


def _print_escpos_bar_ticket(printer, table_code: str, items: List[dict]) -> None:
    target = getattr(printer, "name", printer.__class__.__name__)
    _log(f"🖨️  Starting thermal bar ticket print for table {table_code} -> {target}")
    lines = _build_bar_ticket_lines(table_code, items)
    _print_escpos_lines(printer, lines)
    _log(f"✅ Enhanced bar ticket printed to {target}!")


def _collapse_items(items: Iterable) -> List[dict]:
    grouped: dict[tuple[str, int, str], dict[str, object]] = {}
    for item in items:
        name = getattr(item, "product", str(item))
        unit_price = int(getattr(item, "unit_price_cents", 0) or 0)
        note = (getattr(item, "note", "") or "").strip()
        key = (name, unit_price, note)

        qty = float(getattr(item, "qty", 1.0) or 1.0)
        total_cents = int(getattr(item, "total_cents", 0) or 0)

        if key in grouped:
            grouped[key]["qty"] = float(grouped[key]["qty"]) + qty
            grouped[key]["total_cents"] = int(grouped[key]["total_cents"]) + total_cents
        else:
            grouped[key] = {
                "name": name,
                "qty": qty,
                "unit_price": unit_price,
                "total_cents": total_cents,
                "note": note,
            }
    return list(grouped.values())


# ---------------- Public API ----------------
class PrinterService:
    def __init__(self) -> None:
        _ensure_dirs()
        _log("🔄 Initializing PrinterService...")
        self._escpos_printer = _find_xp80c_printer()
        if self._escpos_printer:
            _log("✅ PrinterService ready with thermal printer")
        else:
            if _DISABLE_ESCPOS:
                _log("ℹ️  PrinterService in preview-only mode (ESC/POS disabled)")
            else:
                _log("ℹ️  PrinterService ready (terminal preview only)")

    def update_printers(self, bar: Optional[str], cash: Optional[str]) -> None:
        _log("🔁 Refreshing printer configuration...")
        if bar or cash:
            _log(f"ℹ️  Requested bar printer: {bar!r}, cashier printer: {cash!r}")
        new_printer = _find_xp80c_printer()
        if new_printer:
            try:
                if hasattr(self._escpos_printer, "close"):
                    self._escpos_printer.close()  # type: ignore[operator]
            except Exception as exc:
                _log_printer_error("Failed to close previous printer", exc)
            self._escpos_printer = new_printer
            _log("✅ Thermal printer handle refreshed")
        else:
            self._escpos_printer = None
            _log("ℹ️  No thermal printer available after refresh")

    def _current_printer(self):
        return self._escpos_printer

    def print_bar_ticket(self, table_code: str, items: Iterable) -> bool:
        _log(f"📋 Bar ticket requested for table {table_code}")
        data = _collapse_items(items)
        _log(f"📦 Processing {len(data)} unique items")

        _print_terminal_bar_ticket(table_code, data)

        printer = self._current_printer()
        if printer:
            try:
                _print_escpos_bar_ticket(printer, table_code, data)
            except Exception as exc:
                _log_printer_error("Thermal bar ticket failed", exc)
                _log("📺 Falling back to terminal preview only")
                raise
        else:
            _log("ℹ️  No thermal printer - using terminal preview only")

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
        _log(f"📋 Receipt requested for table {table_code}")
        data = _collapse_items(items)
        _log(f"📦 Processing {len(data)} unique items")

        _print_terminal_receipt(table_code, data, subtotal, discount, total, cashier)

        printer = self._current_printer()
        if printer:
            try:
                _print_escpos_receipt(
                    printer,
                    table_code,
                    data,
                    subtotal,
                    discount,
                    total,
                    method,
                    cashier,
                )
            except Exception as exc:
                _log_printer_error("Thermal receipt failed", exc)
                _log("📺 Falling back to terminal preview only")
                raise
        else:
            _log("ℹ️  No thermal printer - using terminal preview only")

        return True


# Create the 'printer' instance that main_window.py is looking for
printer = PrinterService()


def _apply_printer_settings(bar: Optional[str], cash: Optional[str]) -> None:
    printer.update_printers(bar, cash)


bus.subscribe("printers_changed", _apply_printer_settings)


# ---------------- Diagnostic function ----------------
def diagnose_printing() -> None:
    _log("\n" + "=" * 60)
    _log("🔧 PRINTING DIAGNOSTICS")
    _log("=" * 60)
    _log(f"Python: {sys.version.split()[0]}")
    _log(f"ESC/POS available: {_ESCPOS_OK}")
    _log(f"ESC/POS disabled: {_DISABLE_ESCPOS}")
    _log(f"Data directory: {DATA_DIR}")

    diagnostic_usb = _try_usb_printer(allow_when_blocked=True)
    if diagnostic_usb:
        _log("✅ Diagnostic: ESC/POS USB backend succeeded")
        try:
            if hasattr(diagnostic_usb, "close"):
                diagnostic_usb.close()  # type: ignore[operator]
        except Exception as exc:
            _log_printer_error("Failed to close diagnostic USB printer", exc)
    else:
        _log("⚠️  Diagnostic: ESC/POS USB backend unavailable")

    diagnostic_file = _try_file_printer()
    if diagnostic_file:
        _log("✅ Diagnostic: /dev backend succeeded")
        try:
            if hasattr(diagnostic_file, "close"):
                diagnostic_file.close()  # type: ignore[operator]
        except Exception as exc:
            _log_printer_error("Failed to close diagnostic file printer", exc)
    else:
        _log("⚠️  Diagnostic: /dev backend unavailable")

    printer_handle = printer._current_printer()
    if printer_handle:
        _log(f"🖨️  Active printer handle: {printer_handle}")
    else:
        _log("ℹ️  No active printer handle detected")

    try:
        printer.update_printers(None, None)
    except Exception as exc:
        _log_printer_error("Printer refresh failed during diagnostics", exc)
    finally:
        printer_handle = printer._current_printer()

    if printer_handle:
        _log("✅ Printer detected after refresh")
    else:
        _log("⚠️  Still no printer after refresh")

    sample_items = [
        {"name": "عصير برتقال", "qty": 2, "total_cents": 2000, "note": "سكر عالي؛ مثلج"},
        {"name": "شاي", "qty": 1, "total_cents": 500, "note": "سكر خفيف"},
    ]

    _log("\n📺 Rendering terminal preview sample...")
    _print_terminal_receipt("TEST", sample_items, 2500, 500, 2000, "محمد")

    if printer_handle:
        _log("\n🖨️  Attempting thermal sample print...")
        try:
            _print_escpos_receipt(
                printer_handle,
                "TEST",
                sample_items,
                2500,
                500,
                2000,
                "نقدي",
                "محمد",
            )
        except Exception as exc:
            _log_printer_error("Diagnostic thermal print failed", exc)
    else:
        _log("ℹ️  Skipping physical sample print - no printer handle")
        mock = MockPrinter("DiagnosticMock")
        _log("🧪 Capturing ESC/POS output with mock printer")
        try:
            _print_escpos_receipt(
                mock,
                "TEST",
                sample_items,
                2500,
                500,
                2000,
                "نقدي",
                "محمد",
            )
            _log(f"🧪 Mock buffer contains {len(mock.buffer)} entries")
        except Exception as exc:
            _log_printer_error("Diagnostic mock print failed", exc)

    _log("=" * 60 + "\n")


if __name__ == "__main__":
    diagnose_printing()
