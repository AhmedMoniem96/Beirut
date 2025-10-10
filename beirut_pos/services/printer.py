# beirut_pos/services/printer.py
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

# ---- Set your Windows printer names EXACTLY as shown in Control Panel ----
BAR_PRINTER_NAME = r"Your-Bar-Printer-Name"
CASHIER_PRINTER_NAME = r"Your-Cashier-Printer-Name"
# --------------------------------------------------------------------------

def _is_windows() -> bool:
    return sys.platform.startswith("win")

def _safe_text(txt: str) -> str:
    return txt.replace("\r\n", "\n").replace("\r", "\n")

# --- File fallback (always available) --------------------------------------
class _FileFallback:
    def __init__(self):
        self.root = Path(__file__).resolve().parent.parent
        (self.root / "receipts").mkdir(exist_ok=True)
        (self.root / "bar_tickets").mkdir(exist_ok=True)

    def write(self, folder: str, name: str, content: str):
        try:
            p = self.root / folder / name
            p.write_text(content, encoding="utf-8")
        except Exception:
            pass

_FILE = _FileFallback()
# ---------------------------------------------------------------------------

def _print_windows_text(printer_name: str, text: str):
    try:
        import win32print
        # choose exact printer or default
        names = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        if printer_name not in names:
            printer_name = win32print.GetDefaultPrinter()

        handle = win32print.OpenPrinter(printer_name)
        try:
            job = win32print.StartDocPrinter(handle, 1, ("Receipt", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, _safe_text(text).encode("utf-8", errors="replace"))
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
    except Exception as e:
        # Fallback to file if Windows printing fails
        _FILE.write("receipts", f"PRINT_ERROR_{datetime.now():%Y%m%d-%H%M%S}.txt", f"[{e}]\n{text}")

def _print_text(printer_name: str, text: str, fallback_folder: str, fallback_basename: str):
    if _is_windows():
        _print_windows_text(printer_name, text)
    else:
        # On Linux/mac, just save to file (you can add CUPS here if needed)
        _FILE.write(fallback_folder, f"{fallback_basename}.txt", text)

def _format_bar_ticket(table_code: str, items) -> str:
    lines = [f"*** BAR TICKET ***",
             f"Table: {table_code}",
             "-"*30]
    for it in items:
        lines.append(f"{it.qty} x {it.product}")
    lines.append("-"*30)
    return "\n".join(lines)

def _format_cashier_receipt(table_code: str, items, subtotal, discount, total, method, cashier) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"*** CASHIER RECEIPT ***",
             f"Table: {table_code}   Cashier: {cashier}",
             f"Date: {ts}",
             f"Method: {method}",
             "-"*32]
    for it in items:
        lines.append(f"{it.qty} x {it.product}")
        lines.append(f"   @ {it.unit_price_cents/100:.2f}  -> {it.total_cents/100:.2f} EGP")
    lines += ["-"*32,
              f"Subtotal: {subtotal/100:.2f} EGP",
              f"Discount: {discount/100:.2f} EGP",
              f"TOTAL:    {total/100:.2f} EGP",
              "-"*32, "شكراً لزيارتكم"]
    return "\n".join(lines)

class PrinterService:
    """
    Dual-printer support (Windows 10):
      - Bar printer: BAR_PRINTER_NAME
      - Cashier printer: CASHIER_PRINTER_NAME
    Always falls back to file write so the POS never crashes due to printing.
    """
    def print_bar_ticket(self, table_code: str, items: Iterable):
        # Only bar-prepared items (heuristic)
        keywords = ("drinks","smoothies","coffee","shesha","cocktail","soda","fresh","hot")
        bar_items = [it for it in items if any(k in it.product.lower() for k in keywords)]
        if not bar_items:
            return
        txt = _format_bar_ticket(table_code, bar_items)
        # Print and file-copy
        _print_text(BAR_PRINTER_NAME, txt, "bar_tickets", f"{datetime.now():%Y%m%d}-{table_code}")
        _FILE.write("bar_tickets", f"{datetime.now():%Y%m%d}-{table_code}.txt", txt)

    def print_cashier_receipt(self, table_code: str, items, subtotal, discount, total, method, cashier):
        txt = _format_cashier_receipt(table_code, items, subtotal, discount, total, method, cashier)
        # Print and file-copy
        _print_text(CASHIER_PRINTER_NAME, txt, "receipts", f"{datetime.now():%Y%m%d}-{table_code}")
        _FILE.write("receipts", f"{datetime.now():%Y%m%d}-{table_code}.txt", txt)

printer = PrinterService()
