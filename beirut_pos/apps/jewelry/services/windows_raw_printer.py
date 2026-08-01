"""Windows RAW spooler backend used only by Jewelry barcode labels.

The pywin32 dependency is deliberately imported at dispatch time so importing
the Jewelry application remains safe on non-Windows hosts.
"""

from __future__ import annotations

import importlib
from typing import Any


_UNREADY_STATUS_NAMES = (
    ("PRINTER_STATUS_PAUSED", "paused"),
    ("PRINTER_STATUS_ERROR", "error"),
    ("PRINTER_STATUS_PENDING_DELETION", "pending deletion"),
    ("PRINTER_STATUS_PAPER_JAM", "paper jam"),
    ("PRINTER_STATUS_PAPER_OUT", "out of paper"),
    ("PRINTER_STATUS_MANUAL_FEED", "waiting for manual feed"),
    ("PRINTER_STATUS_PAPER_PROBLEM", "paper problem"),
    ("PRINTER_STATUS_OFFLINE", "offline"),
    ("PRINTER_STATUS_IO_ACTIVE", "I/O error"),
    ("PRINTER_STATUS_NOT_AVAILABLE", "not available"),
    ("PRINTER_STATUS_NO_TONER", "out of toner"),
    ("PRINTER_STATUS_OUT_OF_MEMORY", "out of memory"),
    ("PRINTER_STATUS_DOOR_OPEN", "door open"),
    ("PRINTER_STATUS_USER_INTERVENTION", "requires user intervention"),
)


def _load_win32print() -> Any:
    """Load pywin32 only when a Windows barcode job is submitted."""
    try:
        return importlib.import_module("win32print")
    except ImportError as exc:
        raise RuntimeError("Windows RAW printing requires the pywin32 package.") from exc


def _find_exact_printer(win32print: Any, printer_name: str) -> str:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    installed_names = [printer[2] for printer in win32print.EnumPrinters(flags)]
    if printer_name not in installed_names:
        raise RuntimeError(f"Configured barcode printer not found: {printer_name!r}.")
    return printer_name


def _inspect_printer_status(win32print: Any, handle: Any, printer_name: str) -> None:
    details = win32print.GetPrinter(handle, 2)
    status = int(details.get("Status", 0) or 0)
    problems = [
        description
        for constant_name, description in _UNREADY_STATUS_NAMES
        if status & int(getattr(win32print, constant_name, 0) or 0)
    ]
    if problems:
        raise RuntimeError(
            f"Configured barcode printer {printer_name!r} is not ready: "
            + ", ".join(problems)
            + "."
        )


def submit_raw_print_job(
    printer_name: str,
    command_bytes: bytes,
    *,
    document_name: str = "Beirut POS Jewelry Barcode",
) -> None:
    """Submit printer command bytes to one exact configured printer.

    No default-printer lookup or GDI rendering is performed by this backend.
    """
    target = (printer_name or "").strip()
    if not target:
        raise RuntimeError("No barcode label printer selected.")
    if not isinstance(command_bytes, bytes) or not command_bytes:
        raise ValueError("RAW barcode command payload must be non-empty bytes.")

    win32print = _load_win32print()
    _find_exact_printer(win32print, target)

    handle = win32print.OpenPrinter(target)
    document_started = False
    page_started = False
    try:
        _inspect_printer_status(win32print, handle, target)
        win32print.StartDocPrinter(handle, 1, (document_name, None, "RAW"))
        document_started = True
        win32print.StartPagePrinter(handle)
        page_started = True
        written = win32print.WritePrinter(handle, command_bytes)
        if written is not None and written != len(command_bytes):
            raise RuntimeError(
                f"Incomplete RAW barcode write: {written} of {len(command_bytes)} bytes."
            )
        win32print.EndPagePrinter(handle)
        page_started = False
        win32print.EndDocPrinter(handle)
        document_started = False
    finally:
        if page_started:
            win32print.EndPagePrinter(handle)
        if document_started:
            win32print.EndDocPrinter(handle)
        win32print.ClosePrinter(handle)

