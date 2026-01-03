"""Styling helpers for the Jewelry UI."""

from __future__ import annotations

from pathlib import Path


def login_stylesheet(background_image: Path | None = None) -> str:
    palette = {
        "charcoal": "#1f1c1a",
        "charcoal_soft": "#2c2623",
        "gold": "#c9a33c",
        "gold_light": "#e4c067",
        "cream": "#f6f1ea",
        "text": "#2b2724",
        "muted": "#6f6a65",
        "border": "#d6ccc2",
    }
    background_rule = ""
    if background_image:
        background_rule = f"""
        QWidget#BrandPanel {{
            background-image: url("{background_image.as_posix()}");
            background-position: center;
            background-repeat: no-repeat;
        }}
        """
    return f"""
    QDialog#LoginDialog {{
        background: {palette["cream"]};
        font-family: "Avenir", "Segoe UI", "Helvetica Neue", sans-serif;
        font-size: 13px;
        color: {palette["text"]};
    }}
    QWidget#BrandPanel {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 {palette["charcoal"]},
            stop: 1 {palette["charcoal_soft"]}
        );
        border-top-left-radius: 18px;
        border-bottom-left-radius: 18px;
    }}
    QLabel#BrandTagline {{
        color: {palette["gold_light"]};
        font-size: 16px;
        letter-spacing: 1px;
    }}
    QLabel#BrandHero {{
        color: #ffffff;
        font-size: 28px;
        font-weight: 600;
    }}
    QWidget#FormPanel {{
        background: #ffffff;
        border-top-right-radius: 18px;
        border-bottom-right-radius: 18px;
    }}
    QLabel#FormTitle {{
        font-size: 20px;
        font-weight: 600;
        color: {palette["charcoal"]};
    }}
    QLabel#MutedLabel {{
        color: {palette["muted"]};
    }}
    QLineEdit {{
        background: {palette["cream"]};
        border: 1px solid {palette["border"]};
        border-radius: 10px;
        padding: 8px 12px;
    }}
    QPushButton#PrimaryButton {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 {palette["gold"]},
            stop: 1 {palette["gold_light"]}
        );
        color: {palette["charcoal"]};
        font-weight: 600;
        border: none;
        border-radius: 12px;
        padding: 10px 16px;
    }}
    QPushButton#PrimaryButton:hover {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 {palette["gold_light"]},
            stop: 1 {palette["gold"]}
        );
    }}
    QPushButton#LinkButton {{
        border: none;
        color: {palette["gold"]};
        text-decoration: underline;
    }}
    QPushButton#LinkButton:hover {{
        color: {palette["gold_light"]};
    }}
    {background_rule}
    """
