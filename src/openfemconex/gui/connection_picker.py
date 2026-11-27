# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Dialog to pick the type of a new connection, from isometric pictures."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
)

from openfemconex.i18n import tr


@dataclass(frozen=True)
class ConnectionType:
    key: str
    title: str
    description: str
    available: bool = True


TYPES = (
    ConnectionType("base_plate", "Placa base",
                   "Columna sobre placa base con anclajes en pedestal o fundación. Modelo "
                   "de elementos finitos con CalculiX y verificaciones AISC 360, DG1 y "
                   "ACI 318."),
    ConnectionType("through_bolt", "Pernos pasantes en concreto",
                   "Viga con placa de extremo y pernos pasantes en un muro o columna nuevo de "
                   "concreto, con placa posterior corrida o viga opuesta. Cálculo analítico "
                   "y modelo CalculiX de la placa de extremo."),
    ConnectionType("shear_tab", "Corte simple", "Placa simple a la columna. Próximamente.",
                   False),
    ConnectionType("moment_end_plate", "Momento con placa de extremo",
                   "Viga a columna de acero. Próximamente.", False),
    ConnectionType("splice", "Empalme de viga", "Empalme con cubreplacas. Próximamente.",
                   False),
)
"""Connection types, in the order of the dialog."""


def type_title(key: str) -> str:
    return tr(next((t.title for t in TYPES if t.key == key), key))


def type_icon(key: str) -> QIcon:
    return QIcon(type_pixmap(key))


def type_pixmap(key: str) -> QPixmap:
    path = resources.files("openfemconex.gui") / "img" / "connections" / f"{key}.png"
    pixmap = QPixmap()
    pixmap.loadFromData(path.read_bytes())
    return pixmap


class ConnectionPicker(QDialog):
    """A grid of large buttons, one per connection type, with its picture."""

    def __init__(self, parent=None, title: str = "Agregar conexión",
                 disabled: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr(title))
        self.selected = ""
        disabled = disabled or {}
        layout = QVBoxLayout(self)
        intro = QLabel(tr("Elija el tipo de conexión. Un proyecto puede tener varias "
                          "conexiones; cada una tiene sus datos, cargas y reporte."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        grid = QGridLayout()
        layout.addLayout(grid)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QToolButton] = {}
        for i, t in enumerate(TYPES):
            b = QToolButton()
            b.setObjectName(f"type_{t.key}")
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIcon(type_icon(t.key))
            b.setIconSize(QSize(216, 162))
            b.setText(tr(t.title) + ("" if t.available else "\n" + tr("(próximamente)")))
            b.setCheckable(True)
            b.setMinimumSize(236, 216)
            why = disabled.get(t.key, "")
            b.setEnabled(t.available and not why)
            b.setToolTip(tr(why) if why else tr(t.description))
            b.setStyleSheet("QToolButton { border: 1px solid palette(mid); border-radius: 6px;"
                            " padding: 6px; } QToolButton:checked { border: 2px solid "
                            "palette(highlight); background: palette(alternate-base); }")
            b.clicked.connect(lambda _=False, k=t.key: self._pick(k))
            b.setProperty("key", t.key)
            self.group.addButton(b)
            self.buttons[t.key] = b
            grid.addWidget(b, i // 3, i % 3)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(48)
        layout.addWidget(self.description)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        self.ok = box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setEnabled(False)
        layout.addWidget(box)
        for b in self.buttons.values():
            b.mouseDoubleClickEvent = lambda _e, b=b: (self._pick(b.property("key")),
                                                       self.accept())
        first = next((k for k, b in self.buttons.items() if b.isEnabled()), "")
        if first:
            self.buttons[first].setChecked(True)
            self._pick(first)

    def _pick(self, key: str) -> None:
        self.selected = key
        self.ok.setEnabled(bool(key))
        t = next(t for t in TYPES if t.key == key)
        self.description.setText(f"<b>{tr(t.title)}</b>. {tr(t.description)}")
