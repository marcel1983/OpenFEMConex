# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""A ribbon made of plain Qt widgets: one tab per stage, commands in titled groups."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from openfemconex.i18n import tr

STYLE = """
#ribbon { background: palette(window); border-bottom: 1px solid palette(mid); }
#ribbonGroup { border-right: 1px solid palette(mid); }
#ribbonGroupTitle { color: palette(dark); font-size: 11px; }
QToolButton#ribbonButton { border: 1px solid transparent; border-radius: 4px; padding: 3px; }
QToolButton#ribbonButton:hover { background: palette(midlight); border-color: palette(mid); }
QToolButton#ribbonButton:checked { background: palette(midlight); border-color: palette(dark); }
QToolButton#ribbonButton:disabled { color: palette(mid); }
"""


class RibbonGroup(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("ribbonGroup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 2)
        outer.setSpacing(1)
        self._row = QHBoxLayout()
        self._row.setSpacing(2)
        outer.addLayout(self._row, 1)
        label = QLabel(tr(title))
        label.setObjectName("ribbonGroupTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(label)

    def add_button(self, text: str, icon: QIcon, slot: Callable[[], None], tip: str = "",
                   checkable: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ribbonButton")
        button.setText(tr(text))
        button.setIcon(icon)
        button.setIconSize(QSize(30, 30))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setMinimumWidth(64)
        button.setToolTip(tr(tip or text))
        button.setCheckable(checkable)
        button.clicked.connect(lambda _=False: slot())
        self._row.addWidget(button)
        return button

    def add_widget(self, label: str, widget: QWidget) -> QWidget:
        box = QVBoxLayout()
        box.setSpacing(1)
        caption = QLabel(tr(label))
        caption.setObjectName("ribbonGroupTitle")
        box.addStretch(1)
        box.addWidget(caption)
        box.addWidget(widget)
        box.addStretch(1)
        self._row.addLayout(box)
        return widget


class Ribbon(QWidget):
    """Tab bar on top, the groups of the current tab below."""

    tab_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ribbon")
        self.setStyleSheet(STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.pages = QStackedWidget()
        self.pages.setFixedHeight(86)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages)
        self._names: list[str] = []
        self.tabs.currentChanged.connect(self._on_tab)

    def add_tab(self, name: str) -> Callable[[str], RibbonGroup]:
        """Add a tab and return a function that appends a titled group to it."""
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(0)
        row.addStretch(1)
        self.pages.addWidget(page)
        self._names.append(name)
        self.tabs.addTab(tr(name))

        def add_group(title: str) -> RibbonGroup:
            group = RibbonGroup(title)
            row.insertWidget(row.count() - 1, group)
            return group

        return add_group

    def _on_tab(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.tab_changed.emit(self._names[index])

    def current(self) -> str:
        return self._names[self.tabs.currentIndex()]

    def select(self, name: str) -> None:
        self.tabs.setCurrentIndex(self._names.index(name))
