# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Light and dark themes (Fusion style with a palette) and saved preferences."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

__all__ = ["apply_theme", "settings"]


def settings() -> QSettings:
    """Preferences of the user (language, theme), kept by Qt per platform."""
    return QSettings("OpenFEMConex", "OpenFEMConex")


def _dark_palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: "#2b2f36", QPalette.ColorRole.WindowText: "#e6e6e6",
        QPalette.ColorRole.Base: "#1f2329", QPalette.ColorRole.AlternateBase: "#2b2f36",
        QPalette.ColorRole.ToolTipBase: "#3a3f47", QPalette.ColorRole.ToolTipText: "#e6e6e6",
        QPalette.ColorRole.Text: "#e6e6e6", QPalette.ColorRole.Button: "#353a42",
        QPalette.ColorRole.ButtonText: "#e6e6e6", QPalette.ColorRole.BrightText: "#ff6b6b",
        QPalette.ColorRole.Link: "#6fa8ff", QPalette.ColorRole.Highlight: "#3d6fb6",
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.Light: "#4a5059",
        QPalette.ColorRole.Midlight: "#3e444d", QPalette.ColorRole.Mid: "#4f5661",
        QPalette.ColorRole.Dark: "#b4bcc5", QPalette.ColorRole.Shadow: "#000000",
        QPalette.ColorRole.PlaceholderText: "#8a929c",
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor("#7a828c"))
    return p


_default: QPalette | None = None


# Fusion draws check boxes and radio buttons with an outline derived from the window
# colour, almost invisible on a dark window: give them a light border.
_DARK_SHEET = """/* dark */
QCheckBox::indicator, QTableView::indicator, QTreeView::indicator {
    width: 14px; height: 14px; border: 1px solid #9aa3ad; border-radius: 2px;
    background: #1f2329; }
QCheckBox::indicator:checked, QTableView::indicator:checked, QTreeView::indicator:checked {
    background: #4f86d9; border-color: #a9c6f0; }
QCheckBox::indicator:disabled { border-color: #5a616b; background: #2b2f36; }
QToolTip { color: #e6e6e6; background: #3a3f47; border: 1px solid #6b737d; }
"""
_LIGHT_SHEET = "/* light */"


def apply_theme(dark: bool) -> None:
    """Switch the whole application between the light and the dark theme.

    Setting the application style sheet again also re-polishes every widget, so the
    ``palette(...)`` colours of their own style sheets follow the new palette.
    """
    global _default
    app = QApplication.instance()
    if app is None:
        return
    if _default is None:
        _default = QPalette(app.palette())
    app.setStyle("Fusion")
    app.setPalette(_dark_palette() if dark else app.style().standardPalette())
    app.setStyleSheet(_DARK_SHEET if dark else _LIGHT_SHEET)
