"""Settings helpers for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from beirut_pos.core.config_store import get_config_value, set_config_value


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


def load_gallery_settings() -> GallerySettings:
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
