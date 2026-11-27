# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Help window: the manual topics, shipped as Markdown inside the package."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openfemconex import __version__
from openfemconex.i18n import language, tr

__all__ = ["HelpDialog", "about", "topics"]


def topics(lang: str | None = None) -> list[tuple[str, str]]:
    """(title, Markdown text) of each help topic, in order."""
    lang = lang or language()
    folder = resources.files("openfemconex.help").joinpath(lang)
    if not folder.is_dir():
        folder = resources.files("openfemconex.help").joinpath("es")
    out = []
    for item in sorted(folder.iterdir(), key=lambda p: p.name):
        if item.name.endswith(".md"):
            text = item.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("# ").strip()
            out.append((title, text))
    return out


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, topic: int = 0) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Ayuda") + " — OpenFEMConex")
        self.resize(1000, 720)
        self.index = QListWidget()
        self.index.setMaximumWidth(240)
        self.page = QTextBrowser()
        self.page.setOpenExternalLinks(True)
        # the topics name their figures relative to the help package (img/<lang>/...)
        self.page.setSearchPaths([str(resources.files("openfemconex.help"))])
        self._topics = topics()
        for title, _ in self._topics:
            self.index.addItem(QListWidgetItem(title))
        self.index.currentRowChanged.connect(self._show)
        row = QHBoxLayout()
        row.addWidget(self.index)
        row.addWidget(self.page, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(row, 1)
        layout.addWidget(buttons)
        self.index.setCurrentRow(min(topic, len(self._topics) - 1))

    def _show(self, row: int) -> None:
        if 0 <= row < len(self._topics):
            self.page.setMarkdown(self._topics[row][1])


def about(parent: QWidget | None) -> None:
    text = {
        "es": "<h3>OpenFEMConex {v}</h3><p>Placas base de columna por elementos finitos "
              "(CalculiX) con verificaciones AISC 360 y ACI 318.</p><p>Software libre bajo "
              "AGPL-3.0-or-later. Usa CalculiX (GPL), Gmsh (GPL), OpenConex (GPL), Qt for "
              "Python (LGPL), VTK y PyVista (BSD/MIT).</p><p>Herramienta de apoyo: la "
              "responsabilidad del diseño corresponde al profesional que lo firma.</p>",
        "en": "<h3>OpenFEMConex {v}</h3><p>Column base plates by finite elements (CalculiX) "
              "with AISC 360 and ACI 318 checks.</p><p>Free software under AGPL-3.0-or-later. "
              "Uses CalculiX (GPL), Gmsh (GPL), OpenConex (GPL), Qt for Python (LGPL), VTK "
              "and PyVista (BSD/MIT).</p><p>A support tool: the design is the responsibility "
              "of the engineer who signs it.</p>",
    }[language()].format(v=__version__)
    box = QMessageBox(parent)
    box.setWindowTitle(tr("Acerca de"))
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(text)
    box.exec()
