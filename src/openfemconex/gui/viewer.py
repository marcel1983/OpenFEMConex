# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D view of the model, the mesh and the FEM results (PyVista)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from openfemconex.i18n import tr
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.results import Results
from openfemconex.scenes import FIELDS, STYLE, draw_model, draw_results, grid_from_mesh

__all__ = ["FIELDS", "Viewer", "grid_from_mesh"]


class Viewer(QWidget):
    """The 3D widget; without OpenGL (tests, OPENFEMCONEX_NO_3D) it is a placeholder."""

    options_changed = Signal()
    """The dimensions or anchor numbers were switched on or off."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.plotter = None
        self.description = ""
        layout.addWidget(self._toolbar())
        if os.environ.get("OPENFEMCONEX_NO_3D"):
            self._label = QLabel(tr("Visor 3D desactivado"))
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._label, 1)
            return
        from pyvistaqt import QtInteractor

        self.plotter = QtInteractor(self)
        self.set_dark(False)
        layout.addWidget(self.plotter.interactor, 1)

    def _toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("viewerBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(2)
        self.buttons: dict[str, QToolButton] = {}
        for key, text, tip, slot in (
                ("zoom_in", "＋", "Acercar", lambda: self.zoom(1.25)),
                ("zoom_out", "－", "Alejar", lambda: self.zoom(0.8)),
                ("fit", tr("Centrar"), "Centrar el modelo y ajustarlo a la vista", self.fit),
                ("iso", tr("Isométrica"), "Vista isométrica", lambda: self.view("iso")),
                ("top", tr("Planta"), "Vista en planta (desde arriba)", lambda: self.view("xy")),
                ("front", tr("Frente"), "Vista de frente (plano x-z)", lambda: self.view("xz")),
                ("side", tr("Lateral"), "Vista lateral (plano y-z)", lambda: self.view("yz"))):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tr(tip))
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, f=slot: f())
            if key.startswith("zoom"):
                font = b.font()
                font.setPointSizeF(font.pointSizeF() * 1.3)
                font.setBold(True)
                b.setFont(font)
            self.buttons[key] = b
            row.addWidget(b)
        row.addSpacing(12)
        self.dims = QCheckBox(tr("Cotas"))
        self.dims.setChecked(True)
        self.dims.setToolTip(tr("Dimensiones de la placa y del arreglo de anclajes"))
        self.numbers = QCheckBox(tr("Números de anclaje"))
        self.numbers.setChecked(True)
        self.numbers.setToolTip(tr("Número de cada anclaje en posiciones libres (por "
                                   "coordenadas), como en la tabla de anclajes y en la de "
                                   "fuerzas"))
        for box in (self.dims, self.numbers):
            box.toggled.connect(lambda _=False: self.options_changed.emit())
            row.addWidget(box)
        row.addStretch(1)
        return bar

    # ------------------------------------------------------------------ camera
    def zoom(self, factor: float) -> None:
        if self.plotter is not None:
            self.plotter.camera.zoom(factor)
            self.plotter.reset_camera_clipping_range()
            self.plotter.render()

    def fit(self) -> None:
        """Bring the whole model back into the view, keeping the direction of sight."""
        if self.plotter is not None:
            self.plotter.reset_camera()
            self.plotter.render()

    def view(self, name: str) -> None:
        if self.plotter is None:
            return
        {"iso": self.plotter.view_isometric, "xy": self.plotter.view_xy,
         "xz": self.plotter.view_xz, "yz": self.plotter.view_yz}[name]()
        self.plotter.reset_camera()
        self.plotter.render()

    def set_dark(self, dark: bool) -> None:
        """Background and text colours of the 3D scene for the light or dark theme."""
        STYLE["text"] = "white" if dark else "black"
        STYLE["dims"] = "#7fb3ff" if dark else "#1f5fa8"
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
                   reset: bool = True, length=None, numbers: bool = True) -> None:
        """``length`` formats the dimensions; ``numbers`` allows the anchor numbers."""
        if not self._begin(tr("Modelo: {nodes} nodos, {elements} hexaedros",
                              nodes=len(mesh.nodes), elements=mesh.element_count)):
            return
        draw_model(self.plotter, model, mesh, edges, reset,
                   dimensions=(length or (lambda v: f"{v:.0f} mm")) if self.dims.isChecked()
                   else None, numbers=numbers and self.numbers.isChecked())
        self.plotter.render()

    def show_results(self, vtu: str | Path, model: BasePlateModel, results: Results,
                     field: str = "von Mises", scale: float = 20.0, unit_force: float = 1e-3,
                     force_label: str = "kN", reset: bool = False, face: str = "front") -> None:
        if not self._begin(tr("Resultados {combo}: {field}", combo=results.load, field=tr(field))):
            return
        draw_results(self.plotter, vtu, model, results, field, scale, unit_force, force_label,
                     reset, face=face)
        self.plotter.render()

    def show_through_bolt(self, conn, reset: bool = True) -> None:
        """Through-bolt connection: wall or column, beams, plates and bolts."""
        from openfemconex import tb_scene

        if not self._begin(tr("Pernos pasantes: {n} pernos", n=conn.bolts)):
            return
        camera = None if reset else self.plotter.camera_position
        tb_scene.draw(self.plotter, conn)
        if camera is None:
            tb_scene.isometric(self.plotter)
        else:
            self.plotter.camera_position = camera
        self.plotter.render()

    def show_end_plate(self, mc, reset: bool = True) -> None:
        """Moment end-plate connection: column, stiffening, beams, plates and bolts."""
        from openfemconex import ep_scene

        ep = mc.end_plate
        if not self._begin(tr("Placa de extremo: {n} pernos",
                              n=2 * len(ep_scene.bolt_rows(mc.beam, ep)))):
            return
        camera = None if reset else self.plotter.camera_position
        ep_scene.draw(self.plotter, mc)
        if camera is None:
            ep_scene.isometric(self.plotter)
        else:
            self.plotter.camera_position = camera
        self.plotter.render()

    def screenshot(self, path: str | Path) -> Path | None:
        if self.plotter is None:
            return None
        self.plotter.screenshot(str(path))
        return Path(path)
