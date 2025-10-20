"""Receipt and ticket printing via PDF files for XP-58 printers."""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from reportlab.lib.pagesizes import portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..core.bus import bus
from ..core.db import setting_get
from ..core.paths import DATA_DIR
from ..utils.currency import format_pounds

try:  # pragma: no cover - optional Windows dependency
    import win32api  # type: ignore
except Exception:  # pragma: no cover - executed when pywin32 is missing
    win32api = None


_OUTPUT_ROOT = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR = _OUTPUT_ROOT / "bar_tickets"
_FONT_NAME = "Helvetica"
_FONT_CANDIDATES = [
    "arialuni.ttf",
    "arial.ttf",
    "segoeui.ttf",
    "tahoma.ttf",
    "times.ttf",
    "dejavusans.ttf",
    "NotoSans-Regular.ttf",
    "Cairo-Regular.ttf",
    "Amiri-Regular.ttf",
]

BAR_PRINTER_NAME = r"Your-Bar-Printer-Name"
CASHIER_PRINTER_NAME = r"Your-Cashier-Printer-Name"


def _ensure_dirs() -> None:
    for folder in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def _font_search_paths() -> List[Path]:
    paths: List[Path] = []
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", r"C:\\Windows"))
        paths.append(windir / "Fonts")
    else:
        paths.extend(
            [
                Path.home() / ".fonts",
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
            ]
        )
    return [p for p in paths if p.exists()]


def _register_font() -> None:
    global _FONT_NAME
    if "BeirutPOSFont" in pdfmetrics.getRegisteredFontNames():
        _FONT_NAME = "BeirutPOSFont"
        return

    for folder in _font_search_paths():
        for candidate in _FONT_CANDIDATES:
            path = folder / candidate
            if not path.exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont("BeirutPOSFont", str(path)))
            except Exception:
                continue
            else:
                _FONT_NAME = "BeirutPOSFont"
                return


def _sanitize_filename(value: str) -> str:
    safe = [ch if ch.isalnum() else "-" for ch in value]
    return "".join(safe).strip("-") or "ticket"


def _collapse_items(items: Iterable) -> List[dict]:
    grouped: OrderedDict[tuple, dict] = OrderedDict()
    for it in items:
        product = getattr(it, "product", str(it))
        note = (getattr(it, "note", "") or "").strip()
        try:
            qty = float(getattr(it, "qty", 1))
        except Exception:
            qty = 1.0
        unit_price = int(getattr(it, "unit_price_cents", 0))
        try:
            total_cents = int(getattr(it, "total_cents"))
        except Exception:
            total_cents = int(round(unit_price * qty))
        key = (product, note, unit_price)
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "product": product,
                "note": note,
                "qty": qty,
                "unit_price": unit_price,
                "total_cents": total_cents,
            }
        else:
            entry["qty"] += qty
            entry["total_cents"] += total_cents
    return list(grouped.values())


def _fmt_qty(qty: float) -> str:
    if abs(qty - round(qty)) < 1e-6:
        return str(int(round(qty)))
    return f"{qty:g}"


def _line_height() -> float:
    return 14.0


def _page_dimensions(line_count: int) -> tuple[float, float]:
    width = 226.8  # ≈80mm roll width in points
    base_height = 60
    height = max(base_height, base_height + line_count * _line_height())
    return portrait((width, height))


def _render_pdf(title: str, lines: List[str], folder: Path, prefix: str) -> Path:
    _ensure_dirs()
    _register_font()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _sanitize_filename(prefix)
    target = folder / f"{timestamp}-{slug}.pdf"
    width, height = _page_dimensions(len(lines) + 4)
    canv = canvas.Canvas(str(target), pagesize=(width, height))
    canv.setTitle(title)
    canv.setAuthor("Beirut POS")
    canv.setFont(_FONT_NAME, 11)

    x = width - 12
    y = height - 18
    for line in lines:
        canv.drawRightString(x, y, line)
        y -= _line_height()
    canv.showPage()
    canv.save()
    return target


def _dispatch_pdf(pdf_path: Path, printer_name: Optional[str]) -> None:
    """
    Robust Windows printing for PDFs:
    - Tries SumatraPDF (best: supports -print-to and noscale)
    - Then Adobe Reader (AcroRd32.exe /t)
    - Falls back to startfile/print (default printer only)
    On Linux/macOS, uses CUPS 'lp'.
    """
    import subprocess
    import shutil
    import time
    import sys
    from pathlib import Path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return

    if sys.platform.startswith("win"):
        # 1) Try SumatraPDF (portable or installed)
        # Common locations (adjust/add if needed)
        sumatra_candidates = [
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
            str(Path.home() / "AppData/Local/SumatraPDF/SumatraPDF.exe"),
        ]
        sumatra = next((p for p in sumatra_candidates if Path(p).exists()), shutil.which("SumatraPDF.exe"))

        if sumatra:
            # -print-to: choose printer by name
            # -print-settings "noscale": avoid driver scaling to Letter/A4
            cmd = [sumatra, "-silent"]
            if printer_name:
                cmd += ["-print-to", printer_name]
            # Explicit noscale keeps your 58/80mm width from getting stretched
            cmd += ["-print-settings", "noscale", str(pdf_path)]
            try:
                subprocess.run(cmd, check=False, timeout=20)
                return
            except Exception:
                pass

        # 2) Try Adobe Reader (AcroRd32.exe /t "file" "printer" "" "")
        # Note: Adobe sometimes needs a small sleep to release the file handle
        acro_candidates = [
            r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat Reader 2025\Reader\AcroRd32.exe",
        ]
        acro = next((p for p in acro_candidates if Path(p).exists()), shutil.which("AcroRd32.exe"))
        if acro:
            try:
                if not printer_name:
                    # Adobe /t REQUIRES a printer name; fallback to default via startfile
                    raise RuntimeError("No printer name set for Adobe silent print")
                # Arguments for /t: file, printer, driver, port
                # Driver/port can be empty strings; Adobe will resolve.
                cmd = [acro, "/t", str(pdf_path), printer_name, "", ""]
                subprocess.Popen(cmd)
                # Give Adobe a moment to dispatch the job then exit
                time.sleep(3)
                return
            except Exception:
                pass

        # 3) Fallback: default printer via startfile/print (ignores target name)
        try:
            os.startfile(str(pdf_path), "print")  # type: ignore[attr-defined]
            return
        except Exception:
            pass

    else:
        # Linux/macOS: CUPS
        try:
            cmd = ["lp"]
            if printer_name:
                cmd += ["-d", printer_name, "-o", "media=Custom.80x200mm"]
            cmd += [str(pdf_path)]
            subprocess.Popen(cmd)
            return
        except Exception:
            pass

def _format_bar_lines(table_code: str, items: Iterable) -> List[str]:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "تذكرة البار",
        f"الطاولة: {table_code.upper()}",
        f"التوقيت: {ts}",
        "------------------------------",
    ]
    for entry in _collapse_items(items):
        lines.append(f"{_fmt_qty(entry['qty'])} × {entry['product']}")
        note = entry["note"]
        if note:
            lines.append(f"ملاحظة: {note}")
    lines.append("------------------------------")
    return lines


def _format_cashier_lines(
    table_code: str,
    items: Iterable,
    subtotal: int,
    discount: int,
    total: int,
    method: str,
    cashier: str,
) -> List[str]:
    currency = setting_get("currency", "EGP") or "EGP"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "إيصال الكاشير",
        f"الطاولة: {table_code} — الكاشير: {cashier}",
        f"الوقت: {ts}",
        f"طريقة الدفع: {method}",
        "------------------------------",
    ]
    for entry in _collapse_items(items):
        lines.append(f"{_fmt_qty(entry['qty'])} × {entry['product']}")
        unit_txt = format_pounds(entry['unit_price'], currency)
        total_txt = format_pounds(entry['total_cents'], currency)
        lines.append(f"   @ {unit_txt} → {total_txt}")
        note = entry["note"]
        if note:
            lines.append(f"ملاحظة: {note}")
    lines.extend(
        [
            "------------------------------",
            f"الإجمالي قبل الخصم: {format_pounds(subtotal, currency)}",
            f"الخصم: {format_pounds(discount, currency)}",
            f"الإجمالي المستحق: {format_pounds(total, currency)}",
            "شكراً لزيارتكم",
        ]
    )
    return lines


class PrinterService:
    """Render receipts to PDFs and forward them to the configured printers."""

    __slots__ = ("bar_printer", "cashier_printer")

    def __init__(self) -> None:
        _ensure_dirs()
        _register_font()
        self.bar_printer = BAR_PRINTER_NAME
        self.cashier_printer = CASHIER_PRINTER_NAME
        self.reload_from_settings()

    def reload_from_settings(self) -> None:
        bar = setting_get("bar_printer", "").strip()
        cash = setting_get("cashier_printer", "").strip()
        if bar:
            self.bar_printer = bar
        if cash:
            self.cashier_printer = cash

    def update_printers(self, bar: Optional[str], cashier: Optional[str]) -> None:
        if bar is not None:
            self.bar_printer = bar.strip() or BAR_PRINTER_NAME
        if cashier is not None:
            self.cashier_printer = cashier.strip() or CASHIER_PRINTER_NAME

    def print_bar_ticket(self, table_code: str, items: Iterable) -> Path:
        lines = _format_bar_lines(table_code, items)
        pdf_path = _render_pdf("Bar Ticket", lines, _BAR_DIR, f"bar-{table_code}")
        _dispatch_pdf(pdf_path, self.bar_printer)
        return pdf_path

    def print_cashier_receipt(
        self,
        table_code: str,
        items: Iterable,
        subtotal: int,
        discount: int,
        total: int,
        method: str,
        cashier: str,
    ) -> Path:
        lines = _format_cashier_lines(table_code, items, subtotal, discount, total, method, cashier)
        pdf_path = _render_pdf("Cashier Receipt", lines, _RECEIPTS_DIR, f"cashier-{table_code}")
        _dispatch_pdf(pdf_path, self.cashier_printer)
        return pdf_path


printer = PrinterService()


def _apply_printer_settings(bar: Optional[str], cashier: Optional[str]) -> None:
    printer.update_printers(bar, cashier)


bus.subscribe("printers_changed", _apply_printer_settings)
