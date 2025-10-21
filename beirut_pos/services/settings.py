"""Helpers for high-level application branding settings."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.bus import bus
from ..core.db import setting_get, setting_set


DEFAULT_CLIENT_NAME = "My Client"
DEFAULT_PRIMARY_COLOR = "#C89A5B"


@dataclass
class ClientBranding:
    name: str
    logo_path: str
    primary_color: str


def get_client_name() -> str:
    name = (setting_get("client_name", DEFAULT_CLIENT_NAME) or "").strip()
    return name or DEFAULT_CLIENT_NAME


def set_client_name(value: str) -> None:
    setting_set("client_name", value.strip() or DEFAULT_CLIENT_NAME)
    bus.emit("client_branding_changed")


def get_client_logo_path() -> str:
    return (setting_get("client_logo_path", "") or "").strip()


def set_client_logo_path(value: str) -> None:
    setting_set("client_logo_path", value.strip())
    bus.emit("client_branding_changed")


def get_primary_color() -> str:
    raw = (setting_get("primary_color", DEFAULT_PRIMARY_COLOR) or "").strip()
    return raw or DEFAULT_PRIMARY_COLOR


def set_primary_color(value: str) -> None:
    setting_set("primary_color", value.strip() or DEFAULT_PRIMARY_COLOR)
    bus.emit("client_branding_changed")


def get_branding() -> ClientBranding:
    return ClientBranding(
        name=get_client_name(),
        logo_path=get_client_logo_path(),
        primary_color=get_primary_color(),
    )
