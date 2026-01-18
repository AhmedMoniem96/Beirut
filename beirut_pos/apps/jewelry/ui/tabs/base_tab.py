"""Shared base container for jewelry tabs."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class BaseTabContainer(QWidget):
    def __init__(self, *, show_header: bool = True) -> None:
        super().__init__()
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.header_label: Optional[QLabel] = None
        if show_header:
            header = QLabel()
            header.setStyleSheet("font-size: 18px; font-weight: bold;")
            root_layout.addWidget(header)
            self.header_label = header

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch()
        root_layout.addWidget(footer)

        self.scroll_area = scroll_area
        self.content_layout = content_layout
        self.footer_layout = footer_layout
