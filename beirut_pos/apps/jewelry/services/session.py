"""Session store for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SessionUser:
    id: int
    username: str
    full_name: str
    role: str


_current_user: Optional[SessionUser] = None
_bootstrap_warning: Optional[str] = None


def set_current_user(user: SessionUser) -> None:
    global _current_user
    _current_user = user


def get_current_user() -> Optional[SessionUser]:
    return _current_user


def clear_current_user() -> None:
    global _current_user
    _current_user = None


def set_bootstrap_warning(message: str) -> None:
    global _bootstrap_warning
    _bootstrap_warning = message


def get_bootstrap_warning() -> Optional[str]:
    return _bootstrap_warning
