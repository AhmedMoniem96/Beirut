"""Shared base container for jewelry tabs."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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
        self._page_content_widget: Optional[QWidget] = None
        self._page_content_layout: Optional[QLayout] = None
        self._tail_spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        self._scroll_layout.addItem(self._tail_spacer)
        self.content_layout: Optional[QVBoxLayout] = None
        self._content_tail_spacer: Optional[QSpacerItem] = None

    def set_page_content_widget(self, widget: QWidget) -> None:
        self._set_page_content(widget=widget)

    def set_page_content_layout(self, layout: QVBoxLayout) -> None:
        self._set_page_content(layout=layout)

    def set_content_layout(self, layout: QVBoxLayout) -> None:
        self.content_layout = layout
        self._content_tail_spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding,
        )
        self.content_layout.addItem(self._content_tail_spacer)

    def add_content_widget(self, widget: QWidget) -> None:
        if self.content_layout is None:
            return
        if self._content_tail_spacer is None:
            self._content_tail_spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
            self.content_layout.addItem(self._content_tail_spacer)
        index = self.content_layout.indexOf(self._content_tail_spacer)
        if index < 0:
            self.content_layout.addItem(self._content_tail_spacer)
            index = self.content_layout.indexOf(self._content_tail_spacer)
        if index < 0:
            index = self.content_layout.count()
        self.content_layout.insertWidget(index, widget)

    def add_content_layout(self, layout: QLayout) -> None:
        if self.content_layout is None:
            return
        if self._content_tail_spacer is None:
            self._content_tail_spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
            self.content_layout.addItem(self._content_tail_spacer)
        index = self.content_layout.indexOf(self._content_tail_spacer)
        if index < 0:
            self.content_layout.addItem(self._content_tail_spacer)
            index = self.content_layout.indexOf(self._content_tail_spacer)
        if index < 0:
            index = self.content_layout.count()
        self.content_layout.insertLayout(index, layout)

    def _set_page_content(
        self,
        *,
        widget: QWidget | None = None,
        layout: QVBoxLayout | None = None,
    ) -> None:
        if widget is None and layout is None:
            return
        self._clear_page_content()
        index = self._scroll_layout.indexOf(self._tail_spacer)
        if index < 0:
            self._scroll_layout.addItem(self._tail_spacer)
            index = self._scroll_layout.indexOf(self._tail_spacer)
        if index < 0:
            index = self._scroll_layout.count()
        if widget is not None:
            self._scroll_layout.insertWidget(index, widget)
            self._page_content_widget = widget
            self._page_content_layout = None
        else:
            self._scroll_layout.insertLayout(index, layout)
            self._page_content_layout = layout
            self._page_content_widget = None

    def _clear_page_content(self) -> None:
        if self._page_content_widget is not None:
            self._scroll_layout.removeWidget(self._page_content_widget)
            self._page_content_widget.setParent(None)
            self._page_content_widget = None
        if self._page_content_layout is not None:
            self._scroll_layout.removeItem(self._page_content_layout)
            self._page_content_layout.setParent(None)
            self._page_content_layout = None
