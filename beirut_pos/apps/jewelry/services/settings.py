"""Settings helpers for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QSettings

from beirut_pos.core.config_store import get_config_value, set_config_value




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


def _migrate_invoice_print_preferences() -> tuple[bool, bool]:
    auto_print = bool(get_config_value("jw_invoice_auto_print_after_save", False))
    preview = bool(get_config_value("jw_invoice_print_preview", False))

    qsettings = QSettings()
    if not auto_print and qsettings.contains("invoice_auto_print_after_save"):
        auto_print = qsettings.value("invoice_auto_print_after_save", False, bool)
        set_config_value("jw_invoice_auto_print_after_save", auto_print)
    if not preview and qsettings.contains("invoice_quick_preview"):
        preview = qsettings.value("invoice_quick_preview", False, bool)
        set_config_value("jw_invoice_print_preview", preview)

    return auto_print, preview


def load_gallery_settings() -> GallerySettings:
    invoice_auto_print_after_save, invoice_print_preview = _migrate_invoice_print_preferences()
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
    )


def save_gallery_settings(settings: GallerySettings) -> None:
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
    set_config_value("jw_printer_profiles", [{"name": "Admin Override", "vendor_id": settings.printer_vendor_id, "product_id": settings.printer_product_id, "interface": settings.printer_interface, "out_ep": settings.printer_out_ep, "in_ep": settings.printer_in_ep}])


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
