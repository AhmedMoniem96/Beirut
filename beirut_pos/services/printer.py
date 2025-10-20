# beirut_pos/services/printer.py
"""Receipt/ticket PDF renderer for 80mm thermal printers (XP-80C) with Arabic shaping,
numbers kept LTR, and logo on the cashier receipt only.
"""

from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from ..core.db import setting_get
from ..core.paths import DATA_DIR
from ..utils.currency import format_pounds
from ..core.bus import bus

# ---------------- Paths & constants ----------------
_OUTPUT_ROOT  = DATA_DIR / "prints"
_RECEIPTS_DIR = _OUTPUT_ROOT / "receipts"
_BAR_DIR      = _OUTPUT_ROOT / "bar_tickets"

PT_PER_MM      = 72.0 / 25.4
PAGE_W         = 80 * PT_PER_MM            # ≈ 226.8 pt - 80mm roll
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 8, 8, 10, 10
LINE_H         = 16
FONT_SIZE      = 10
FONT_BOLD_SIZE = 11

# Logo (cashier only)
LOGO_MAX_W_PT  = 60 * PT_PER_MM            # ~60mm
LOGO_MAX_H_PT  = 35 * PT_PER_MM

# Prefer a bundled Arabic font first (put Cairo-Regular.ttf here)
ASSETS_FONT    = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Cairo-Regular.ttf"
_FONT_NAME     = "BeirutPOSFont"
_FONT_CANDIDATES = [
    "NotoNaskhArabic-Regular.ttf", "Amiri-Regular.ttf", "Cairo-Regular.ttf",
    "DejaVuSans.ttf", "Arial Unicode.ttf", "arialuni.ttf", "arial.ttf",
]

def _ensure_dirs():
    for p in (_OUTPUT_ROOT, _RECEIPTS_DIR, _BAR_DIR):
        p.mkdir(parents=True, exist_ok=True)

def _font_search_paths() -> List[Path]:
    paths: List[Path] = []
    if sys.platform.startswith("win"):
        windir = os.environ.get("WINDIR", r"C:\\Windows")
        if windir:
            paths.append(Path(windir) / "Fonts")
    else:
        paths += [Path.home()/".fonts", Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]
    return [p for p in paths if p.exists()]

def _register_font():
    """Prefer bundled Arabic TTF; then system; last resort Helvetica."""
    global _FONT_NAME
    if _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    # 1) bundled
    try:
        if ASSETS_FONT.exists():
            pdfmetrics.registerFont(TTFont(_FONT_NAME, str(ASSETS_FONT)))
            return
    except Exception:
        pass
    # 2) system
    for folder in _font_search_paths():
        for name in _FONT_CANDIDATES:
            f = folder / name
            if f.exists():
                try:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME, str(f)))
                    return
                except Exception:
                    continue
    # 3) fallback
    _FONT_NAME = "Helvetica"

# ---------------- Arabic shaping ----------------
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR_OK = True
except Exception:
    _AR_OK = False

def _rtl(s: str) -> str:
    if not s: return ""
    if not _AR_OK: return s
    return get_display(arabic_reshaper.reshape(s))

def _ltr(s: str) -> str:
    """Force LTR so 'EGP 15' renders correctly inside RTL context."""
    if not s: return ""
    LRE, PDF = "\u202A", "\u202C"
    return f"{LRE}{s}{PDF}"

# ---------------- Optional logo (cashier only) ----------------
try:
    from PIL import Image, ImageOps, ImageEnhance
    _PIL_OK = True
except Exception:
    _PIL_OK = False

def _prepare_logo_from_settings() -> Optional[tuple[ImageReader, float, float]]:
    if not _PIL_OK: return None
    p = Path((setting_get("logo_path", "") or "").strip())
    if not p.exists(): return None
    try:
        img = Image.open(p).convert("L")
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageOps.autocontrast(img)
        img_bw = img.convert("1")  # dithered
        w_px, h_px = img_bw.size
        aspect = (h_px / float(w_px)) if w_px else 1.0
        w_pt = min(LOGO_MAX_W_PT, PAGE_W - (MARGIN_L + MARGIN_R))
        h_pt = min(LOGO_MAX_H_PT, w_pt * aspect)
        if h_pt > LOGO_MAX_H_PT:
            h_pt = LOGO_MAX_H_PT
            w_pt = h_pt / aspect
        return (ImageReader(img_bw), float(w_pt), float(h_pt))
    except Exception:
        return None

# ---------------- Draw helpers ----------------
def _text(c: canvas.Canvas, x_left: float, y: float, text: str):
    c.drawString(x_left, y, text)

def _text_r(c: canvas.Canvas, x_right: float, y: float, text: str):
    w = pdfmetrics.stringWidth(text, _FONT_NAME, FONT_SIZE)
    c.drawString(x_right - w, y, text)

def _text_bold_r(c: canvas.Canvas, x_right: float, y: float, text: str):
    c.setFont(_FONT_NAME, FONT_BOLD_SIZE)
    w = pdfmetrics.stringWidth(text, _FONT_NAME, FONT_BOLD_SIZE)
    c.drawString(x_right - w, y, text)
    c.setFont(_FONT_NAME, FONT_SIZE)

def _hr(c: canvas.Canvas, x1: float, x2: float, y: float):
    c.setLineWidth(0.6); c.line(x1, y, x2, y)

def _wrap_text(text: str, max_width: float, font_size: int) -> List[str]:
    words = text.split()
    lines, buf = [], ""
    for w in words:
        trial = (buf + " " + w).strip()
        if pdfmetrics.stringWidth(trial, _FONT_NAME, font_size) <= max_width:
            buf = trial
        else:
            if buf: lines.append(buf)
            buf = w
    if buf: lines.append(buf)
    return lines or [""]

def _calc_height_for_items(items, col_w) -> int:
    name_w = col_w["name"]; rows = 0
    for it in items:
        nm_lines = _wrap_text(_rtl(str(it["name"])), name_w, FONT_SIZE)
        rows += max(1, len(nm_lines)) + 1  # +1 numeric row
        if (it.get("note") or "").strip():
            rows += 1
    return (rows + 6) * LINE_H

def _format_currency_cents(cents: int | float, currency: str) -> str:
    try: return format_pounds(int(round(float(cents))), currency)
    except Exception: return f"{cents} {currency}"

def _page_h(content_h: int) -> float:
    return max(PAGE_W, MARGIN_T + content_h + MARGIN_B)

# ---------------- Public API ----------------
BAR_PRINTER_NAME     = "Your-Bar-Printer-Name"
CASHIER_PRINTER_NAME = "Your-Cashier-Printer-Name"

class PrinterService:
    __slots__ = ("bar_printer", "cashier_printer")
    def __init__(self):
        _ensure_dirs(); _register_font()
        self.bar_printer = BAR_PRINTER_NAME
        self.cashier_printer = CASHIER_PRINTER_NAME
        self.reload_from_settings()

    def reload_from_settings(self):
        bar  = (setting_get("bar_printer","") or "").strip()
        cash = (setting_get("cashier_printer","") or "").strip()
        if bar:  self.bar_printer = bar
        if cash: self.cashier_printer = cash

    def update_printers(self, bar: Optional[str], cashier: Optional[str]):
        if bar is not None:    self.bar_printer = bar.strip() or BAR_PRINTER_NAME
        if cashier is not None:self.cashier_printer = cashier.strip() or CASHIER_PRINTER_NAME

    def print_bar_ticket(self, table_code: str, items: Iterable) -> Path:
        data = _collapse_items(items)
        pdf = _render_bar_pdf(table_code, data)
        _dispatch_pdf(pdf, self.bar_printer); return pdf

    def print_cashier_receipt(
        self, table_code: str, items: Iterable,
        subtotal: int, discount: int, total: int,
        method: str, cashier: str, service: int | None = None, tax: int | None = None,
    ) -> Path:
        data = _collapse_items(items)
        pdf = _render_receipt_pdf(
            table_code, data, subtotal, discount, service or 0, tax or 0, total, method, cashier
        )
        _dispatch_pdf(pdf, self.cashier_printer); return pdf

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

# ---------------- Renderers ----------------
def _draw_logo_if_any(c: canvas.Canvas, y: float) -> float:
    pack = _prepare_logo_from_settings()
    if not pack: return y
    reader, w_pt, h_pt = pack
    x = (PAGE_W - w_pt) / 2.0
    c.drawImage(reader, x, y - h_pt, width=w_pt, height=h_pt, mask="auto",
                preserveAspectRatio=True, anchor='sw')
    return y - h_pt - 6

def _render_bar_pdf(table_code: str, items: List[dict]) -> Path:
    _ensure_dirs(); _register_font()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    currency = setting_get("currency","EGP") or "EGP"

    col_w = { "name": PAGE_W - (MARGIN_L+MARGIN_R) - 110, "qty": 32, "total": 80 }
    content_h = 140 + _calc_height_for_items(items, col_w)
    page_h = _page_h(content_h)

    target = _RECEIPTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-bar-{table_code}.pdf"
    c = canvas.Canvas(str(target), pagesize=(PAGE_W, page_h))
    c.setTitle("Bar Ticket"); c.setAuthor("Beirut POS"); c.setFont(_FONT_NAME, FONT_SIZE)

    xL, xR = MARGIN_L, PAGE_W - MARGIN_R
    y = page_h - (MARGIN_T + 6)

    # No logo on bar ticket
    c.setFont(_FONT_NAME, FONT_BOLD_SIZE); _text_r(c, xR, y, _rtl("تذكرة البار")); y -= LINE_H
    c.setFont(_FONT_NAME, FONT_SIZE)
    _text_r(c, xR, y, _rtl(f"الطاولة: {table_code}")); y -= LINE_H
    _text_r(c, xR, y, _rtl(f"وقت الإصدار: {ts}")); y -= LINE_H
    _hr(c, xL, xR, y); y -= LINE_H

    _text_r(c, xR, y, _rtl("الإجمالي"))
    _text_r(c, xR - col_w["total"] - 8, y, _rtl("الكمية"))
    _text(c, xL, y, _rtl("الصنف")); y -= LINE_H
    _hr(c, xL, xR, y); y -= 4

    for it in items:
        name_lines = _wrap_text(_rtl(it["name"]), col_w["name"], FONT_SIZE)
        total_txt = _format_currency_cents(it["total_cents"], currency)
        qty_txt   = str(int(it["qty"])) if abs(it["qty"]-round(it["qty"])) < 1e-6 else f"{it['qty']:.2f}"

        _text_r(c, xR, y, _ltr(total_txt))
        _text_r(c, xR - col_w["total"] - 8, y, _ltr(qty_txt))
        _text(c, xL, y, name_lines[0]); y -= LINE_H
        for extra in name_lines[1:]:
            _text(c, xL, y, extra); y -= LINE_H

        note = (it.get("note") or "").strip()
        if note:
            _text(c, xL+12, y, _rtl(f"ملاحظة: {note}")); y -= LINE_H

    y -= 2
    _hr(c, xL, xR, y); y -= LINE_H
    c.showPage(); c.save()
    return target

def _render_receipt_pdf(
    table_code: str,
    items: List[dict],
    subtotal: int,
    discount: int,
    service: int,
    tax: int,
    total: int,
    method: str,
    cashier: str,
) -> Path:
    _ensure_dirs(); _register_font()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    company = setting_get("company_name", "Beirut") or "Beirut"
    currency = setting_get("currency", "EGP") or "EGP"

    col_w = {
        "name": PAGE_W - (MARGIN_L+MARGIN_R) - 160,
        "qty": 32,
        "unit": 64,
        "total": 64,
    }
    content_h = 220 + _calc_height_for_items(items, col_w)
    page_h = _page_h(content_h)

    target = _RECEIPTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-cashier-{table_code}.pdf"
    c = canvas.Canvas(str(target), pagesize=(PAGE_W, page_h))
    c.setTitle("Cashier Receipt"); c.setAuthor("Beirut POS"); c.setFont(_FONT_NAME, FONT_SIZE)

    xL, xR = MARGIN_L, PAGE_W - MARGIN_R
    y = page_h - (MARGIN_T + 6)

    # Logo on cashier receipt only
    y = _draw_logo_if_any(c, y)

    # Header
    c.setFont(_FONT_NAME, FONT_BOLD_SIZE); _text_r(c, xR, y, _rtl(company)); y -= LINE_H
    c.setFont(_FONT_NAME, FONT_SIZE)
    _text_r(c, xR, y, _rtl(f"الطاولة: {table_code} — الكاشير: {cashier}")); y -= LINE_H
    _text_r(c, xR, y, _rtl(f"وقت الإصدار: {ts}")); y -= LINE_H
    _text_r(c, xR, y, _rtl(f"طريقة الدفع: {method}")); y -= LINE_H
    _hr(c, xL, xR, y); y -= LINE_H

    # Table header
    _text_r(c, xR, y, _rtl("الإجمالي"))
    _text_r(c, xR - col_w["total"] - 8, y, _rtl("السعر"))
    _text_r(c, xR - col_w["total"] - col_w["unit"] - 16, y, _rtl("الكمية"))
    _text(c, xL, y, _rtl("الصنف")); y -= LINE_H
    _hr(c, xL, xR, y); y -= 4

    # Items
    for it in items:
        name_lines = _wrap_text(_rtl(it["name"]), col_w["name"], FONT_SIZE)
        qty_txt  = str(int(it["qty"])) if abs(it["qty"]-round(it["qty"])) < 1e-6 else f"{it['qty']:.2f}"
        unit_txt = _format_currency_cents(it["unit_price"], currency)
        tot_txt  = _format_currency_cents(it["total_cents"], currency)

        _text_r(c, xR, y, _ltr(tot_txt))
        _text_r(c, xR - col_w["total"] - 8, y, _ltr(unit_txt))
        _text_r(c, xR - col_w["total"] - col_w["unit"] - 16, y, _ltr(qty_txt))
        _text(c, xL, y, name_lines[0]); y -= LINE_H
        for extra in name_lines[1:]:
            _text(c, xL, y, extra); y -= LINE_H

        note = (it.get("note") or "").strip()
        if note:
            _text(c, xL+12, y, _rtl(f"ملاحظة: {note}")); y -= LINE_H

    y -= 2
    _hr(c, xL, xR, y); y -= LINE_H

    # Totals
    _text_r(c, xR, y, _rtl("الإجمالي قبل الخصم: ") + _ltr(_format_currency_cents(subtotal, currency))); y -= LINE_H
    if discount:
        _text_r(c, xR, y, _rtl("الخصم: ") + _ltr(_format_currency_cents(discount, currency))); y -= LINE_H
    if service:
        _text_r(c, xR, y, _rtl("الخدمة: ") + _ltr(_format_currency_cents(service, currency))); y -= LINE_H
    if tax:
        _text_r(c, xR, y, _rtl("الضريبة: ") + _ltr(_format_currency_cents(tax, currency))); y -= LINE_H

    _hr(c, xL, xR, y); y -= LINE_H
    _text_bold_r(c, xR, y, _rtl("الصافي: ") + _ltr(_format_currency_cents(total, currency))); y -= LINE_H
    _hr(c, xL, xR, y); y -= LINE_H

    _text_r(c, xR, y, _rtl("شكراً لزيارتكم 💛")); y -= LINE_H

    c.showPage(); c.save()
    return target

# ---------------- PDF dispatch (Windows Sumatra; CUPS elsewhere) ----------------
def _dispatch_pdf(pdf_path: Path, printer_name: Optional[str]):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return
    if sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
            str(Path.home() / "AppData/Local/SumatraPDF/SumatraPDF.exe"),
        ]
        exe = next((p for p in candidates if Path(p).exists()), None)
        if exe:
            try:
                args = [exe, "-silent"]
                if printer_name:
                    args += ["-print-to", printer_name]
                args += ["-print-settings", "noscale", str(pdf_path)]
                subprocess.run(args, check=False, timeout=20)
                return
            except Exception:
                pass
        # Adobe fallback
        acro_candidates = [
            r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
        ]
        acro = next((p for p in acro_candidates if Path(p).exists()), None)
        if acro and printer_name:
            try:
                subprocess.Popen([acro, "/t", str(pdf_path), printer_name, "", ""])
                return
            except Exception:
                pass
        # Last resort: default printer
        try:
            os.startfile(str(pdf_path), "print")  # type: ignore[attr-defined]
            return
        except Exception:
            return
    else:
        try:
            cmd = ["lp"]
            if printer_name:
                cmd += ["-d", printer_name, "-o", "fit-to-page=false", "-o", "media=Custom.80x200mm"]
            cmd += [str(pdf_path)]
            subprocess.Popen(cmd)
        except Exception:
            pass
