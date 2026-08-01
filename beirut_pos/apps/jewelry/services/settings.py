"""Settings helpers for Jewelry app."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from beirut_pos.core.config_store import get_config_value, set_config_value


PRINTER_MODE_RECEIPT = "receipt"
PRINTER_MODE_LABEL = "label"
DEFAULT_PRINTER_MODE = PRINTER_MODE_RECEIPT

DEFAULT_BARCODE_LABEL_WIDTH_MM = 38.0
DEFAULT_BARCODE_LABEL_HEIGHT_MM = 25.0


def _safe_bool(value: object, default: bool = False) -> bool:
    """Coerce persisted booleans without treating the string ``false`` as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def _safe_float(value: object, default: float, *, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        return default
    return result


def _safe_int(value: object, default: int, *, minimum: int | None = None) -> int:
    try:
        # Do not silently truncate malformed values such as "2.5".
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if minimum is not None and result < minimum:
        return default
    return result


@dataclass
class BarcodePrinterSettings:
    """Persistent, device-specific barcode printer configuration."""

    enabled: bool = False
    model: str = ""
    exact_windows_name: str = ""
    width_mm: float = DEFAULT_BARCODE_LABEL_WIDTH_MM
    height_mm: float = DEFAULT_BARCODE_LABEL_HEIGHT_MM
    gap_mm: float = 3.0
    dpi: int = 203
    density: int = 8
    speed: int = 4
    default_copies: int = 1
    command_language: str = "ESC/POS"




@dataclass
class ScannerProfile:
    name: str
    input_suffix: str
    inter_key_timeout_ms: int
    strip_prefix: str
    strip_suffix: str

@dataclass
class GallerySettings:
    name_en: str
    name_ar: str
    address: str
    phone: str
    logo_path: str
    font_path: str
    rtl_enabled: bool
    barcode_print_mode: str
    barcode_printer_name: str
    receipt_print_mode: Optional[str]
    receipt_printer_name: str
    website_name: str
    website_url: str
    website_orders_enabled: bool
    printer_vendor_id: str
    printer_product_id: str
    printer_interface: str
    printer_out_ep: str
    printer_in_ep: str
    printer_backend_priority: str
    invoice_auto_print_after_save: bool
    invoice_print_preview: bool
    printer_mode: str
    barcode_label_width_mm: float
    barcode_label_height_mm: float
    barcode_horizontal_offset_px: int
    barcode_vertical_offset_px: int
    barcode_printer_settings: BarcodePrinterSettings = field(default_factory=BarcodePrinterSettings)

    def __post_init__(self) -> None:
        # Keep callers using the original flat label fields source-compatible.
        # A caller that supplies the focused value object remains authoritative.
        if self.barcode_printer_settings == BarcodePrinterSettings():
            printer_name = (self.barcode_printer_name or "").strip()
            self.barcode_printer_settings = BarcodePrinterSettings(
                exact_windows_name="" if printer_name.lower() == "auto" else printer_name,
                width_mm=self.barcode_label_width_mm,
                height_mm=self.barcode_label_height_mm,
            )


def _migrate_invoice_print_preferences() -> tuple[bool, bool]:
    """Load invoice preferences exclusively from the JSON configuration store."""
    return (
        _safe_bool(get_config_value("jw_invoice_auto_print_after_save", False)),
        _safe_bool(get_config_value("jw_invoice_print_preview", False)),
    )


def _load_barcode_printer_settings() -> BarcodePrinterSettings:
    # The former printer selector stored its value under this key.  Carry an
    # explicit selection forward, but deliberately leave the new opt-in switch
    # disabled so an upgrade can never start printing unexpectedly.
    legacy_name = str(get_config_value("jw_barcode_printer_name", "") or "").strip()
    if legacy_name.lower() == "auto":
        legacy_name = ""
    return BarcodePrinterSettings(
        enabled=_safe_bool(get_config_value("jw_barcode_printer_enabled", False)),
        model=str(get_config_value("jw_barcode_printer_model", "") or ""),
        exact_windows_name=str(
            get_config_value("jw_barcode_printer_windows_name", legacy_name) or legacy_name
        ).strip(),
        width_mm=_safe_float(
            get_config_value("jw_barcode_label_width_mm", DEFAULT_BARCODE_LABEL_WIDTH_MM),
            DEFAULT_BARCODE_LABEL_WIDTH_MM,
            minimum=0.1,
        ),
        height_mm=_safe_float(
            get_config_value("jw_barcode_label_height_mm", DEFAULT_BARCODE_LABEL_HEIGHT_MM),
            DEFAULT_BARCODE_LABEL_HEIGHT_MM,
            minimum=0.1,
        ),
        gap_mm=_safe_float(get_config_value("jw_barcode_label_gap_mm", 3.0), 3.0, minimum=0.0),
        dpi=_safe_int(get_config_value("jw_barcode_printer_dpi", 203), 203, minimum=1),
        density=_safe_int(get_config_value("jw_barcode_printer_density", 8), 8, minimum=0),
        speed=_safe_int(get_config_value("jw_barcode_printer_speed", 4), 4, minimum=1),
        default_copies=_safe_int(
            get_config_value("jw_barcode_printer_default_copies", 1), 1, minimum=1
        ),
        command_language=str(
            get_config_value("jw_barcode_printer_command_language", "ESC/POS") or "ESC/POS"
        ).strip(),
    )


def load_gallery_settings() -> GallerySettings:
    invoice_auto_print_after_save, invoice_print_preview = _migrate_invoice_print_preferences()
    barcode_printer = _load_barcode_printer_settings()
    return GallerySettings(
        name_en=get_config_value("jw_gallery_name_en", "Crystal Gallery for hand made"),
        name_ar=get_config_value("jw_gallery_name_ar", "كريستال جاليري للمشغولات اليدوية"),
        address=get_config_value("jw_gallery_address", "Beirut, Lebanon"),
        phone=get_config_value("jw_gallery_phone", "+961 00 000 000"),
        logo_path=get_config_value("jw_gallery_logo", ""),
        font_path=get_config_value("jw_gallery_font", ""),
        rtl_enabled=bool(get_config_value("jw_rtl_enabled", False)),
        barcode_print_mode=get_config_value("jw_barcode_print_mode", "pdf"),
        barcode_printer_name=get_config_value("jw_barcode_printer_name", "auto"),
        receipt_print_mode=get_config_value("jw_receipt_print_mode", "auto"),
        receipt_printer_name=get_config_value("jw_receipt_printer_name", "auto"),
        website_name=get_config_value("jw_website_name", ""),
        website_url=get_config_value("jw_website_url", ""),
        website_orders_enabled=bool(get_config_value("jw_website_orders_enabled", False)),
        printer_vendor_id=str(get_config_value("jw_printer_vendor_id", "0x0FE6")),
        printer_product_id=str(get_config_value("jw_printer_product_id", "0x811E")),
        printer_interface=str(get_config_value("jw_printer_interface", "0")),
        printer_out_ep=str(get_config_value("jw_printer_out_ep", "0x01")),
        printer_in_ep=str(get_config_value("jw_printer_in_ep", "0x81")),
        printer_backend_priority=str(get_config_value("jw_printer_backend_priority", "raw-usb-escpos,escpos-usb,file,windows")),
        invoice_auto_print_after_save=invoice_auto_print_after_save,
        invoice_print_preview=invoice_print_preview,
        printer_mode=get_printer_mode(),
        barcode_label_width_mm=barcode_printer.width_mm,
        barcode_label_height_mm=barcode_printer.height_mm,
        barcode_horizontal_offset_px=_safe_int(get_config_value("jw_barcode_horizontal_offset_px", 0), 0),
        barcode_vertical_offset_px=_safe_int(get_config_value("jw_barcode_vertical_offset_px", 0), 0),
        barcode_printer_settings=barcode_printer,
    )


def save_gallery_settings(settings: GallerySettings) -> None:
    barcode_printer = settings.barcode_printer_settings
    set_config_value("jw_gallery_name_en", settings.name_en)
    set_config_value("jw_gallery_name_ar", settings.name_ar)
    set_config_value("jw_gallery_address", settings.address)
    set_config_value("jw_gallery_phone", settings.phone)
    set_config_value("jw_gallery_logo", settings.logo_path)
    set_config_value("jw_gallery_font", settings.font_path)
    set_config_value("jw_rtl_enabled", settings.rtl_enabled)
    set_config_value("jw_barcode_print_mode", settings.barcode_print_mode)
    set_config_value("jw_barcode_printer_name", settings.barcode_printer_name)
    set_config_value("jw_receipt_print_mode", settings.receipt_print_mode or "auto")
    set_config_value("jw_receipt_printer_name", settings.receipt_printer_name)
    set_config_value("jw_website_name", settings.website_name)
    set_config_value("jw_website_url", settings.website_url)
    set_config_value("jw_website_orders_enabled", settings.website_orders_enabled)
    set_config_value("jw_printer_vendor_id", settings.printer_vendor_id)
    set_config_value("jw_printer_product_id", settings.printer_product_id)
    set_config_value("jw_printer_interface", settings.printer_interface)
    set_config_value("jw_printer_out_ep", settings.printer_out_ep)
    set_config_value("jw_printer_in_ep", settings.printer_in_ep)
    set_config_value("jw_printer_backend_priority", settings.printer_backend_priority)
    set_config_value("jw_invoice_auto_print_after_save", settings.invoice_auto_print_after_save)
    set_config_value("jw_invoice_print_preview", settings.invoice_print_preview)
    set_printer_mode(settings.printer_mode)
    set_config_value("jw_barcode_label_width_mm", barcode_printer.width_mm)
    set_config_value("jw_barcode_label_height_mm", barcode_printer.height_mm)
    set_config_value("jw_barcode_horizontal_offset_px", settings.barcode_horizontal_offset_px)
    set_config_value("jw_barcode_vertical_offset_px", settings.barcode_vertical_offset_px)
    set_config_value("jw_barcode_printer_enabled", barcode_printer.enabled)
    set_config_value("jw_barcode_printer_model", barcode_printer.model)
    set_config_value("jw_barcode_printer_windows_name", barcode_printer.exact_windows_name)
    set_config_value("jw_barcode_label_gap_mm", barcode_printer.gap_mm)
    set_config_value("jw_barcode_printer_dpi", barcode_printer.dpi)
    set_config_value("jw_barcode_printer_density", barcode_printer.density)
    set_config_value("jw_barcode_printer_speed", barcode_printer.speed)
    set_config_value("jw_barcode_printer_default_copies", barcode_printer.default_copies)
    set_config_value("jw_barcode_printer_command_language", barcode_printer.command_language)
    set_config_value("jw_printer_profiles", [{"name": "Admin Override", "vendor_id": settings.printer_vendor_id, "product_id": settings.printer_product_id, "interface": settings.printer_interface, "out_ep": settings.printer_out_ep, "in_ep": settings.printer_in_ep}])


def get_printer_mode() -> str:
    mode = str(get_config_value("jw_printer_mode", DEFAULT_PRINTER_MODE) or DEFAULT_PRINTER_MODE).strip().lower()
    if mode not in {PRINTER_MODE_RECEIPT, PRINTER_MODE_LABEL}:
        return DEFAULT_PRINTER_MODE
    return mode


def set_printer_mode(mode: str) -> None:
    normalized = (mode or "").strip().lower()
    if normalized not in {PRINTER_MODE_RECEIPT, PRINTER_MODE_LABEL}:
        normalized = DEFAULT_PRINTER_MODE
    set_config_value("jw_printer_mode", normalized)


def load_scanner_profile() -> ScannerProfile:
    return ScannerProfile(
        name=get_config_value("jw_scanner_profile_name", "U.POS UP-700"),
        input_suffix=get_config_value("jw_scanner_input_suffix", "\r"),
        inter_key_timeout_ms=int(get_config_value("jw_scanner_inter_key_timeout_ms", 60) or 60),
        strip_prefix=get_config_value("jw_scanner_strip_prefix", ""),
        strip_suffix=get_config_value("jw_scanner_strip_suffix", ""),
    )


def save_scanner_profile(profile: ScannerProfile) -> None:
    set_config_value("jw_scanner_profile_name", profile.name)
    set_config_value("jw_scanner_input_suffix", profile.input_suffix)
    set_config_value("jw_scanner_inter_key_timeout_ms", profile.inter_key_timeout_ms)
    set_config_value("jw_scanner_strip_prefix", profile.strip_prefix)
    set_config_value("jw_scanner_strip_suffix", profile.strip_suffix)


def normalize_scanner_payload(raw_value: str) -> str:
    value = (raw_value or "").strip()
    profile = load_scanner_profile()
    if profile.strip_prefix and value.startswith(profile.strip_prefix):
        value = value[len(profile.strip_prefix):]
    if profile.strip_suffix and value.endswith(profile.strip_suffix):
        value = value[:-len(profile.strip_suffix)]
    return value.strip()
