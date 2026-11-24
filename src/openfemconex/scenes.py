# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D scenes of the model and the results, drawn on any PyVista plotter.

Used by the interactive viewer and to render the figures of the report off screen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

from openfemconex.i18n import tr
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.results import Results
from openfemconex.vtk import PARTS

__all__ = ["FIELDS", "draw_model", "draw_results", "grid_from_mesh", "render_figures"]

# PyVista announces a future change of the default surface algorithm; not relevant here.
warnings.filterwarnings("ignore", message=".*extract_surface.*")

FIELDS = {
    "von Mises": ("von_Mises", "von Mises [MPa]", "turbo"),
    "Deformación plástica": ("PEEQ", "PEEQ [-]", "magma_r"),
    "Presión de contacto": ("CPRESS", "Contacto [MPa]", "viridis"),
    "Desplazamiento": ("U", "Desplazamiento [mm]", "cividis"),
}
COLORS = {1: "#8fa7c4", 2: "#5b7ba6", 3: "#c8c8c8", 4: "#d98c3f"}
STYLE = {"text": "black"}
"""Colour of texts drawn in the scene (the viewer sets it for the dark theme)."""


def grid_from_mesh(mesh: Mesh):
    """PyVista unstructured grid of the hexahedral mesh, with the part id per cell."""
    import pyvista as pv

    conn = np.vstack(list(mesh.parts.values())) - 1
    cells = np.hstack([np.full((len(conn), 1), 8), conn]).ravel()
    grid = pv.UnstructuredGrid(cells, np.full(len(conn), pv.CellType.HEXAHEDRON), mesh.nodes)
    grid.cell_data["part"] = np.concatenate(
        [np.full(len(c), PARTS[name]) for name, c in mesh.parts.items()])
    return grid


def _rods(plotter, model: BasePlateModel, color: str = "#b5651d") -> None:
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
        plotter.add_mesh(body, color=color)
        plotter.add_mesh(washer, color="#6f7f8f")
        plotter.add_mesh(nut, color="#4a5560")


def _lug(plotter, model: BasePlateModel) -> None:
    """The shear lug: a plate under the base plate, through the grout into the concrete."""
    import pyvista as pv

    lug = model.lug
    if lug is None:
        return
    depth = lug.embedment + model.concrete.grout
    sizes = {"strong": [(lug.thickness, lug.width)], "weak": [(lug.width, lug.thickness)],
             "both": [(lug.thickness, lug.width), (lug.width, lug.thickness)]}[lug.direction]
    for sx, sy in sizes:
        box = pv.Box(bounds=(model.ex - sx / 2, model.ex + sx / 2, model.ey - sy / 2,
                             model.ey + sy / 2, -depth, 0.0))
        plotter.add_mesh(box, color="#c0392b")
        plotter.add_mesh(box.extract_feature_edges(), color="#5a1a12", line_width=1.5)


def _anchor_labels(plotter, model: BasePlateModel, results: Results, unit_force: float,
                   force_label: str) -> None:
    """Axial force (tension +) and shear of every anchor rod, next to it."""
    if not results.anchors:
        return
    points = np.array([[a.x, a.y, model.tp + 2.5 * model.anchor.diameter]
                       for a in results.anchors])
    labels = []
    for a in results.anchors:
        v = float(np.hypot(a.Vx, a.Vy))
        text = f"N = {a.tension * unit_force:.1f} {force_label}"
        if v * unit_force >= 0.05:
            text += f"\nV = {v * unit_force:.1f} {force_label}"
        labels.append(text)
    plotter.add_point_labels(points, labels, font_size=12, text_color="black",
                             shape_color="white", shape_opacity=0.85, always_visible=True,
                             show_points=False)


def _finish(plotter, reset: bool) -> None:
    plotter.add_axes(xlabel="x", ylabel="y", zlabel="z")
    if reset:
        plotter.view_isometric()
        plotter.reset_camera()


def draw_model(plotter, model: BasePlateModel, mesh: Mesh, edges: bool = False,
               reset: bool = True) -> None:
    grid = grid_from_mesh(mesh)
    present = set(np.unique(grid.cell_data["part"]))
    for part, color in COLORS.items():
        if part not in present:
            continue
        surface = grid.threshold([part - 0.5, part + 0.5], scalars="part").extract_surface()
        plotter.add_mesh(surface, color=color, show_edges=edges, edge_color="#3a3a3a",
                         line_width=0.4, opacity=0.45 if part == 3 else 1.0)
        if not edges:
            plotter.add_mesh(surface.extract_feature_edges(feature_angle=40), color="#2b2b2b",
                             line_width=1.2)
    _rods(plotter, model)
    _lug(plotter, model)
    _finish(plotter, reset)


def draw_results(plotter, vtu: str | Path, model: BasePlateModel, results: Results,
                 field: str = "von Mises", scale: float = 20.0, unit_force: float = 1e-3,
                 force_label: str = "kN", reset: bool = True) -> None:
    import pyvista as pv

    name, title, cmap = FIELDS[field]
    grid = pv.read(str(vtu))
    bar = {"title": tr(title) + "\n", "vertical": True, "position_x": 0.84, "position_y": 0.25,
           "height": 0.5, "width": 0.06, "title_font_size": 14, "label_font_size": 12,
           "color": STYLE["text"], "n_labels": 5, "fmt": "%.3g"}
    part = grid.cell_data["part"]
    steel = grid.extract_cells(np.nonzero(part != 3)[0])
    concrete = grid.threshold([2.5, 3.5], scalars="part")
    if name == "CPRESS":
        plate = grid.threshold([0.5, 1.5], scalars="part").extract_surface()
        bottom = plate.clip(normal="z", origin=(0, 0, 1e-3), invert=True)
        plotter.add_mesh(bottom, scalars="CPRESS", cmap=cmap, scalar_bar_args=bar)
        plotter.add_mesh(plate.extract_feature_edges(feature_angle=40), color=STYLE["text"])
        column = grid.extract_cells(np.nonzero((part == 2) | (part == 4))[0])
        plotter.add_mesh(column.extract_surface(), color="#5b7ba6", opacity=0.15)
    else:
        warped = steel.warp_by_vector("U", factor=scale)
        plotter.add_mesh(warped, scalars=name, cmap=cmap, scalar_bar_args=bar,
                         show_edges=True, edge_color="#404040", line_width=0.2)
        plotter.add_mesh(concrete.extract_surface(), color=COLORS[3], opacity=0.3)
        _rods(plotter, model)
        _lug(plotter, model)
    _anchor_labels(plotter, model, results, unit_force, force_label)
    _finish(plotter, reset)
    if name == "CPRESS":
        plotter.view_xy()
        plotter.reset_camera()


def render_figures(out: str | Path, model: BasePlateModel, mesh: Mesh,
                   solved: list[tuple[str, Path, Results]], *, scale: float = 20.0,
                   unit_force: float = 1e-3, force_label: str = "kN",
                   size: tuple[int, int] = (1100, 800)) -> dict[str, list[tuple[str, str]]]:
    """Render the figures of the report as PNG files in ``out``.

    ``solved`` lists (combination, .vtu file, results). Returns, under the key
    ``""`` the geometry figures and under each combination its result figures, as
    (caption, file name). Needs PyVista and an OpenGL context; returns {} without them.
    """
    try:
        import pyvista as pv
    except ImportError:
        return {}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    figures: dict[str, list[tuple[str, str]]] = {}

    previous = STYLE["text"]
    STYLE["text"] = "black"  # the report pages are white

    def shot(name: str, draw) -> str | None:
        plotter = pv.Plotter(off_screen=True, window_size=list(size))
        try:
            plotter.set_background("white")
            draw(plotter)
            plotter.screenshot(str(out / name))
        finally:
            plotter.close()
        return name

    try:
        figures[""] = [
            (tr("Geometría del modelo"), shot("fig_geometria.png",
                                          lambda p: draw_model(p, model, mesh))),
            (tr("Malla de elementos finitos"), shot("fig_malla.png",
                                                lambda p: draw_model(p, model, mesh, True))),
        ]
        captions = {
            "von Mises": tr("Esfuerzo de von Mises (deformada × {s})", s=f"{scale:g}"),
            "Deformación plástica": tr("Deformación plástica equivalente"),
            "Desplazamiento": tr("Desplazamiento total (deformada × {s})", s=f"{scale:g}"),
            "Presión de contacto": tr("Presión de contacto bajo la placa"),
        }
        for combo, vtu, results in solved:
            stem = "".join(ch if ch.isalnum() else "_" for ch in combo)
            figures[combo] = [
                (caption, shot(f"fig_{stem}_{FIELDS[field][0]}.png",
                               lambda p, f=field: draw_results(
                                   p, vtu, model, results, f, scale, unit_force, force_label)))
                for field, caption in captions.items()]
    except Exception:  # no OpenGL context (headless machine): the report goes without figures
        return figures if figures.get("") else {}
    finally:
        STYLE["text"] = previous
    return figures
