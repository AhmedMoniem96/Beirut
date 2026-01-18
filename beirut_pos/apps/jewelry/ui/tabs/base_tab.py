"""Shared base container for jewelry tabs."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget


class BaseTabContainer(QWidget):
    def __init__(self, *, show_header: bool = True) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.header_label: Optional[QLabel] = None
        if show_header:
            header = QLabel()
            header.setStyleSheet("font-size: 18px; font-weight: bold;")
            root_layout.addWidget(header)
            self.header_label = header

        scroll_area = QScrollArea()
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch()
        root_layout.addWidget(footer)

        self.scroll_area = scroll_area
        self.content_layout = content_layout
        self.footer_layout = footer_layout
        self._tail_stretch: Optional[int] = None

    def add_content_widget(self, widget: QWidget) -> None:
        self._ensure_tail_stretch()
        if self._tail_stretch is None:
            return
        self.content_layout.insertWidget(self._tail_stretch, widget)
        self._tail_stretch += 1

    def add_content_layout(self, layout: QVBoxLayout) -> None:
        self._ensure_tail_stretch()
        if self._tail_stretch is None:
            return
        self.content_layout.insertLayout(self._tail_stretch, layout)
        self._tail_stretch += 1

    def _ensure_tail_stretch(self) -> None:
        if self._tail_stretch is None:
            last_index = self.content_layout.count() - 1
            if last_index >= 0:
                last_item = self.content_layout.itemAt(last_index)
                if last_item is not None and last_item.spacerItem() is not None:
                    self._tail_stretch = last_index
                    return
            self.content_layout.addStretch()
            self._tail_stretch = self.content_layout.count() - 1
