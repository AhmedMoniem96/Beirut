"""Settings helpers for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass

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


def load_gallery_settings() -> GallerySettings:
    return GallerySettings(
        name_en=get_config_value("jw_gallery_name_en", "Crystal Gallery for hand made"),
        name_ar=get_config_value("jw_gallery_name_ar", "كريستال جاليري للمشغولات اليدوية"),
        address=get_config_value("jw_gallery_address", "Beirut, Lebanon"),
        phone=get_config_value("jw_gallery_phone", "+961 00 000 000"),
        logo_path=get_config_value("jw_gallery_logo", ""),
        font_path=get_config_value("jw_gallery_font", ""),
        rtl_enabled=bool(get_config_value("jw_rtl_enabled", False)),
    )


def save_gallery_settings(settings: GallerySettings) -> None:
    set_config_value("jw_gallery_name_en", settings.name_en)
    set_config_value("jw_gallery_name_ar", settings.name_ar)
    set_config_value("jw_gallery_address", settings.address)
    set_config_value("jw_gallery_phone", settings.phone)
    set_config_value("jw_gallery_logo", settings.logo_path)
    set_config_value("jw_gallery_font", settings.font_path)
    set_config_value("jw_rtl_enabled", settings.rtl_enabled)
