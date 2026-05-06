"""Centralized loyalty conversion helpers."""

from __future__ import annotations

import math
from PyQt6.QtCore import QSettings


def get_points_per_100() -> float:
    settings = QSettings()
    return max(float(settings.value("loyalty_points_per_100", 1.0, float) or 0.0), 0.0)


def points_to_currency(points: float) -> float:
    rate = get_points_per_100()
    if rate <= 0:
        return 0.0
    return max(float(points), 0.0) * (100.0 / rate)


def currency_to_points(amount: float) -> int:
    rate = get_points_per_100()
    if rate <= 0:
        return 0
    return max(0, int(math.floor((max(float(amount), 0.0) / 100.0) * rate)))

