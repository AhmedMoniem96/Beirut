"""Shared base container for jewelry tabs."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget


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
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch()
        root_layout.addWidget(footer)

        self.scroll_area = scroll_area
        self.footer_layout = footer_layout
        self._scroll_layout = scroll_layout
        self._page_content_index: Optional[int] = None
        self._tail_stretch: int = self._scroll_layout.addStretch()

    def set_page_content_widget(self, widget: QWidget) -> None:
        self._set_page_content(widget=widget)

    def set_page_content_layout(self, layout: QVBoxLayout) -> None:
        self._set_page_content(layout=layout)

    def _set_page_content(
        self,
        *,
        widget: QWidget | None = None,
        layout: QVBoxLayout | None = None,
    ) -> None:
        if widget is None and layout is None:
            return
        self._clear_page_content()
        if widget is not None:
            self._scroll_layout.insertWidget(self._tail_stretch, widget)
        else:
            self._scroll_layout.insertLayout(self._tail_stretch, layout)
        self._page_content_index = self._tail_stretch
        self._tail_stretch += 1

    def _clear_page_content(self) -> None:
        if self._page_content_index is None:
            return
        item = self._scroll_layout.takeAt(self._page_content_index)
        if item is not None:
            if item.widget() is not None:
                item.widget().setParent(None)
            elif item.layout() is not None:
                item.layout().setParent(None)
        self._tail_stretch -= 1
        self._page_content_index = None
