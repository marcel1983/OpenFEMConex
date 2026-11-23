# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D view of the model, the mesh and the FEM results (PyVista)."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.results import Results

# PyVista announces a future change of the default surface algorithm; not relevant here.
warnings.filterwarnings("ignore", message=".*extract_surface.*")

FIELDS = {
    "von Mises": ("von_Mises", "von Mises [MPa]", "turbo"),
    "Deformación plástica": ("PEEQ", "PEEQ [-]", "magma_r"),
    "Presión de contacto": ("CPRESS", "Contacto [MPa]", "viridis"),
    "Desplazamiento": ("U", "Desplazamiento [mm]", "cividis"),
}
COLORS = {1: "#8fa7c4", 2: "#5b7ba6", 3: "#c8c8c8"}


def grid_from_mesh(mesh: Mesh):
    """PyVista unstructured grid of the hexahedral mesh, with the part id per cell."""
    import pyvista as pv

    conn = np.vstack(list(mesh.parts.values())) - 1
    cells = np.hstack([np.full((len(conn), 1), 8), conn]).ravel()
    grid = pv.UnstructuredGrid(cells, np.full(len(conn), pv.CellType.HEXAHEDRON), mesh.nodes)
    grid.cell_data["part"] = np.concatenate(
        [np.full(len(c), i) for i, c in enumerate(mesh.parts.values(), start=1)])
    return grid


class Viewer(QWidget):
    """The 3D widget; without OpenGL (tests, OPENFEMCONEX_NO_3D) it is a placeholder."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plotter = None
        self.description = ""
        if os.environ.get("OPENFEMCONEX_NO_3D"):
            self._label = QLabel("Visor 3D desactivado")
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._label)
            return
        from pyvistaqt import QtInteractor

        self.plotter = QtInteractor(self)
        self.plotter.set_background("#f4f6f8", top="#dfe6ee")
        layout.addWidget(self.plotter.interactor)

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

    def _rods(self, model: BasePlateModel, color: str = "#b5651d") -> None:
        import pyvista as pv

        a = model.anchor
        top = model.tp + 1.6 * a.diameter
        bottom = -min(a.hef, 0.6 * model.concrete.H)
        for rod in model.anchors:
            body = pv.Cylinder(center=(rod.x, rod.y, (top + bottom) / 2), direction=(0, 0, 1),
                               radius=a.diameter / 2, height=top - bottom, resolution=20)
            washer = pv.Cylinder(center=(rod.x, rod.y, model.tp + 4), direction=(0, 0, 1),
                                 radius=a.washer / 2, height=8, resolution=28)
            nut = pv.Cylinder(center=(rod.x, rod.y, model.tp + 8 + 0.45 * a.diameter),
                              direction=(0, 0, 1), radius=0.85 * a.diameter,
                              height=0.9 * a.diameter, resolution=6)
            self.plotter.add_mesh(body, color=color)
            self.plotter.add_mesh(washer, color="#6f7f8f")
            self.plotter.add_mesh(nut, color="#4a5560")

    def _finish(self, reset: bool) -> None:
        self.plotter.add_axes(xlabel="x", ylabel="y", zlabel="z")
        if reset:
            self.plotter.view_isometric()
            self.plotter.reset_camera()
        self.plotter.render()

    # ------------------------------------------------------------------ views
    def show_model(self, model: BasePlateModel, mesh: Mesh, edges: bool = False,
                   reset: bool = True) -> None:
        if not self._begin(f"Modelo: {len(mesh.nodes)} nodos, {mesh.element_count} hexaedros"):
            return
        grid = grid_from_mesh(mesh)
        for part, color in COLORS.items():
            piece = grid.threshold([part - 0.5, part + 0.5], scalars="part")
            surface = piece.extract_surface()
            self.plotter.add_mesh(surface, color=color, show_edges=edges,
                                  edge_color="#3a3a3a", line_width=0.4,
                                  opacity=0.45 if part == 3 else 1.0)
            if not edges:
                self.plotter.add_mesh(surface.extract_feature_edges(feature_angle=40),
                                      color="#2b2b2b", line_width=1.2)
        self._rods(model)
        self._finish(reset)

    def show_results(self, vtu: str | Path, model: BasePlateModel, results: Results,
                     field: str = "von Mises", scale: float = 20.0, unit_force: float = 1e-3,
                     force_label: str = "kN", reset: bool = False) -> None:
        name, title, cmap = FIELDS[field]
        if not self._begin(f"Resultados {results.load}: {field}"):
            return
        import pyvista as pv

        grid = pv.read(str(vtu))
        bar = {"title": title + "\n", "vertical": True, "position_x": 0.84, "position_y": 0.25,
               "height": 0.5, "width": 0.06, "title_font_size": 14, "label_font_size": 12,
               "color": "black", "n_labels": 5, "fmt": "%.3g"}
        steel = grid.threshold([0.5, 2.5], scalars="part")
        concrete = grid.threshold([2.5, 3.5], scalars="part")
        if name == "CPRESS":
            plate = grid.threshold([0.5, 1.5], scalars="part").extract_surface()
            bottom = plate.clip(normal="z", origin=(0, 0, 1e-3), invert=True)
            self.plotter.add_mesh(bottom, scalars="CPRESS", cmap=cmap, scalar_bar_args=bar)
            self.plotter.add_mesh(plate.extract_feature_edges(feature_angle=40), color="black")
            self.plotter.add_mesh(steel.threshold([1.5, 2.5], scalars="part").extract_surface(),
                                  color="#5b7ba6", opacity=0.15)
        else:
            warped = steel.warp_by_vector("U", factor=scale)
            self.plotter.add_mesh(warped, scalars=name, cmap=cmap, scalar_bar_args=bar,
                                  show_edges=True, edge_color="#404040", line_width=0.2)
            self.plotter.add_mesh(concrete.extract_surface(), color=COLORS[3], opacity=0.3)
            self._rods(model)
        tension = [a for a in results.anchors if a.tension > 1.0]
        if tension:
            points = np.array([[a.x, a.y, model.tp + 2.5 * model.anchor.diameter]
                               for a in tension])
            labels = [f"T = {a.tension * unit_force:.1f} {force_label}" for a in tension]
            self.plotter.add_point_labels(points, labels, font_size=13, text_color="black",
                                          shape_color="white", shape_opacity=0.8,
                                          always_visible=True, show_points=False)
        self._finish(reset)
        if name == "CPRESS":
            self.plotter.view_xy()
            self.plotter.reset_camera()
            self.plotter.render()

    def screenshot(self, path: str | Path) -> Path | None:
        if self.plotter is None:
            return None
        self.plotter.screenshot(str(path))
        return Path(path)
