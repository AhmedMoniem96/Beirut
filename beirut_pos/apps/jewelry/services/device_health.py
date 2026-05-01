"""Device health checks for Jewelry settings."""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from typing import TypedDict

from beirut_pos.core.config_store import get_config_value, set_config_value
from beirut_pos.services import printer as printer_service

from .settings import load_gallery_settings, load_scanner_profile, normalize_scanner_payload


class HealthResult(TypedDict):
    status: str
    detail: str


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _persist_result(key: str, result: HealthResult) -> None:
    set_config_value(f"jw_health_{key}_status", result["status"])
    set_config_value(f"jw_health_{key}_detail", result["detail"])
    set_config_value(f"jw_health_{key}_checked_at", _stamp())


def check_receipt_printer(printer_name: str, mode: str) -> HealthResult:
    effective_name = (printer_name or "auto").strip() or "auto"
    effective_mode = (mode or "auto").strip().lower() or "auto"
    if effective_mode == "windows" and platform.system().lower() != "windows":
        result = {"status": "error", "detail": "Windows backend selected but current OS is not Windows."}
    elif effective_mode == "windows":
        printers = printer_service.win_list_printers()
        if not printers:
            result = {"status": "error", "detail": "No Windows printers found or win32 backend dependency is unavailable."}
        elif effective_name != "auto" and effective_name not in printers:
            result = {"status": "error", "detail": f"Selected printer '{effective_name}' is not installed."}
        else:
            result = {"status": "ok", "detail": f"Windows backend ready ({effective_name})."}
    else:
        ok, detail = printer_service.probe_printer_handshake()
        result = {"status": "ok" if ok else "error", "detail": detail}
    _persist_result("receipt_printer", result)
    return result


def check_barcode_printer(printer_name: str, mode: str) -> HealthResult:
    effective_mode = (mode or "pdf").strip().lower() or "pdf"
    effective_name = (printer_name or "auto").strip() or "auto"
    if effective_mode == "pdf":
        result = {"status": "ok", "detail": "PDF export mode does not require direct printer access."}
    else:
        printers = printer_service.win_list_printers()
        if platform.system().lower() != "windows":
            result = {"status": "error", "detail": "Direct barcode print currently requires Windows printer backend."}
        elif not printers:
            result = {"status": "error", "detail": "No Windows printers found or required backend is unavailable."}
        elif effective_name != "auto" and effective_name not in printers:
            result = {"status": "error", "detail": f"Selected barcode printer '{effective_name}' is not installed."}
        else:
            result = {"status": "ok", "detail": f"Direct print backend ready ({effective_name})."}
    _persist_result("barcode_printer", result)
    return result


def check_barcode_scanner() -> HealthResult:
    profile = load_scanner_profile()
    profile_name = profile.name or "keyboard-hid"
    configured_suffix = profile.input_suffix.encode("unicode_escape").decode("ascii") if profile.input_suffix else "<none>"
    sample = normalize_scanner_payload(f"{profile.strip_prefix}12345{profile.strip_suffix}")
    if not sample:
        result = {
            "status": "warning",
            "detail": f"Scanner profile '{profile_name}' strips full payload. Verify prefix/suffix settings.",
        }
    else:
        result = {
            "status": "ok",
            "detail": f"Keyboard-HID fallback active; profile={profile_name}, suffix={configured_suffix}, sample={sample}",
        }
    _persist_result("barcode_scanner", result)
    return result


def load_last_health_result(key: str) -> dict[str, str]:
    return {
        "status": str(get_config_value(f"jw_health_{key}_status", "unknown")),
        "detail": str(get_config_value(f"jw_health_{key}_detail", "")),
        "checked_at": str(get_config_value(f"jw_health_{key}_checked_at", "")),
    }


def refresh_from_settings() -> dict[str, HealthResult]:
    settings = load_gallery_settings()
    return {
        "receipt": check_receipt_printer(settings.receipt_printer_name, settings.receipt_print_mode or "auto"),
        "barcode": check_barcode_printer(settings.barcode_printer_name, settings.barcode_print_mode),
        "scanner": check_barcode_scanner(),
    }
