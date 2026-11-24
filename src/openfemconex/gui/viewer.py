# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D view of the model, the mesh and the FEM results (PyVista)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from openfemconex.i18n import tr
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.results import Results
from openfemconex.scenes import FIELDS, STYLE, draw_model, draw_results, grid_from_mesh

__all__ = ["FIELDS", "Viewer", "grid_from_mesh"]


class Viewer(QWidget):
    """The 3D widget; without OpenGL (tests, OPENFEMCONEX_NO_3D) it is a placeholder."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plotter = None
        self.description = ""
        if os.environ.get("OPENFEMCONEX_NO_3D"):
            self._label = QLabel(tr("Visor 3D desactivado"))
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._label)
            return
        from pyvistaqt import QtInteractor

        self.plotter = QtInteractor(self)
        self.set_dark(False)
        layout.addWidget(self.plotter.interactor)

    def set_dark(self, dark: bool) -> None:
        """Background and text colours of the 3D scene for the light or dark theme."""
        STYLE["text"] = "white" if dark else "black"
        if self.plotter is not None:
            if dark:
                self.plotter.set_background("#1e2228", top="#2c333d")
            else:
                self.plotter.set_background("#f4f6f8", top="#dfe6ee")

    def close_plotter(self) -> None:
        if self.plotter is not None:
            self.plotter.close()
            self.plotter = None

    # ------------------------------------------------------------------ helpers
    def _begin(self, description: str) -> bool:
        self.description = description
        if self.plotter is None:
            self._label.setText(description)
            return False
        self.plotter.clear()
        return True

    # ------------------------------------------------------------------ views
    def show_model(self, model: BasePlateModel, mesh: Mesh, edges: bool = False,
                   reset: bool = True) -> None:
        if not self._begin(tr("Modelo: {nodes} nodos, {elements} hexaedros",
                              nodes=len(mesh.nodes), elements=mesh.element_count)):
            return
        draw_model(self.plotter, model, mesh, edges, reset)
        self.plotter.render()

    def show_results(self, vtu: str | Path, model: BasePlateModel, results: Results,
                     field: str = "von Mises", scale: float = 20.0, unit_force: float = 1e-3,
                     force_label: str = "kN", reset: bool = False) -> None:
        if not self._begin(tr("Resultados {combo}: {field}", combo=results.load, field=tr(field))):
            return
        draw_results(self.plotter, vtu, model, results, field, scale, unit_force, force_label,
                     reset)
        self.plotter.render()

    def screenshot(self, path: str | Path) -> Path | None:
        if self.plotter is None:
            return None
        self.plotter.screenshot(str(path))
        return Path(path)
