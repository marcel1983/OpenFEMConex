# SPDX-License-Identifier: AGPL-3.0-or-later
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

__all__ = ["FIELDS", "draw_anchor_numbers", "draw_dimensions", "draw_model", "draw_results",
           "grid_from_mesh", "render_figures"]

# PyVista announces a future change of the default surface algorithm; not relevant here.
warnings.filterwarnings("ignore", message=".*extract_surface.*")

FIELDS = {
    "von Mises": ("von_Mises", "von Mises [MPa]", "turbo"),
    "Deformación plástica": ("PEEQ", "PEEQ [-]", "magma_r"),
    "Presión de contacto": ("CPRESS", "Contacto [MPa]", "viridis"),
    "Desplazamiento": ("U", "Desplazamiento [mm]", "cividis"),
}
COLORS = {1: "#8fa7c4", 2: "#5b7ba6", 3: "#c8c8c8", 4: "#d98c3f"}
STYLE = {"text": "black", "dims": "#1f5fa8"}
"""Colours of texts and dimension lines drawn in the scene (the viewer sets them for the
dark theme)."""


def _mm(value: float) -> str:
    return f"{value:.0f} mm"


def _distinct(values: list[float], tol: float = 0.5) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def draw_dimensions(plotter, model: BasePlateModel, length=_mm) -> None:
    """Dimension lines of the plate and of the anchor layout, on the top of the plate.

    Along x (plate length N) on the +y side and along y (width B) on the +x side (the
    sides facing the isometric view): the overall size and a chain through the anchor
    positions. ``length`` formats a length in mm for the labels.
    """
    import pyvista as pv

    N, B = model.N, model.B
    z = model.tp + 0.004 * max(N, B)
    size = max(N, B)
    off, tick = 0.09 * size, 0.012 * size
    points: list[tuple[float, float, float]] = []
    lines: list[int] = []
    label_at: list[tuple[float, float, float]] = []
    labels: list[str] = []

    def seg(a, b) -> None:
        points.extend([a, b])
        lines.extend([2, len(points) - 2, len(points) - 1])

    def chain(values: list[float], along_x: bool, level: float, start: float,
              inner: bool = False, prefix: str = "") -> None:
        """Dimension line through ``values`` at ``level`` (y for along_x, else x).

        The labels go outside the line, or inside it with ``inner`` (so that two
        parallel chains do not put their labels on top of each other).
        """
        side = -np.sign(level) if inner else np.sign(level)
        def at(v: float, w: float) -> tuple[float, float, float]:
            return (v, w, z) if along_x else (w, v, z)

        seg(at(values[0], level), at(values[-1], level))
        for v in values:
            seg(at(v, start), at(v, level - 0.4 * tick * np.sign(level)))  # extension
            seg(at(v - tick, level - tick), at(v + tick, level + tick))  # tick
        for a, b in zip(values, values[1:], strict=False):
            if b - a > 1.0:
                label_at.append(at((a + b) / 2, level + (1.6 if along_x else 4.0) * tick * side))
                labels.append(prefix + length(b - a))

    xs = _distinct([a.x for a in model.anchors] + [-N / 2, N / 2])
    ys = _distinct([a.y for a in model.anchors] + [-B / 2, B / 2])
    side_y, side_x = B / 2, N / 2
    if len(xs) > 2:
        chain(xs, True, side_y + off, side_y)
        chain([-N / 2, N / 2], True, side_y + 2 * off, side_y)
    else:
        chain([-N / 2, N / 2], True, side_y + off, side_y)
    if len(ys) > 2:
        chain(ys, False, side_x + off, side_x, inner=True)
        chain([-B / 2, B / 2], False, side_x + 2 * off, side_x)
    else:
        chain([-B / 2, B / 2], False, side_x + off, side_x)
    # f and hef: their labels may hide behind the column or below the plate
    front = len(labels)
    # f: from the column axis to the outer anchor rows, on the -y side
    x0 = model.ex
    rows = [x for x in (min(a.x for a in model.anchors), max(a.x for a in model.anchors))
            if abs(x - x0) > 1.0] if model.anchors else []
    if rows:
        chain(_distinct(rows + [x0]), True, -B / 2 - off, -B / 2, prefix="f = ")
    # hef: along the first anchor of the outer row, below the top of the concrete
    if model.anchors:
        a = max(model.anchors, key=lambda r: (r.x, r.y))
        xh = a.x + 0.75 * model.anchor.washer
        zs = (0.0, -model.anchor.hef)
        seg((xh, a.y, zs[0]), (xh, a.y, zs[1]))
        for zz in zs:
            seg((xh - tick, a.y, zz - tick), (xh + tick, a.y, zz + tick))
        label_at.append((xh + 1.5 * tick, a.y, zs[1] / 2))
        labels.append("hef = " + length(model.anchor.hef))
    poly = pv.PolyData(np.array(points, dtype=float), lines=np.array(lines))
    plotter.add_mesh(poly, color=STYLE["dims"], line_width=1.5)
    for chunk, visible in ((slice(0, front), True), (slice(front, None), False)):
        if labels[chunk]:
            plotter.add_point_labels(np.array(label_at[chunk]), labels[chunk], font_size=11,
                                     text_color=STYLE["dims"], shape=None,
                                     always_visible=visible, show_points=False)


def draw_anchor_numbers(plotter, model: BasePlateModel) -> None:
    """Number of every anchor (as in the anchor table and the anchor forces)."""
    if not model.anchors:
        return
    z = model.tp + 2.2 * model.anchor.diameter
    points = np.array([[a.x, a.y, z] for a in model.anchors])
    plotter.add_point_labels(points, [str(i) for i in range(1, len(points) + 1)],
                             font_size=13, bold=True, text_color="white",
                             shape_color="#b5651d", shape_opacity=0.95, always_visible=False,
                             show_points=False)


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


def _rebar(plotter, model: BasePlateModel) -> None:
    """Pedestal bars and ties, inside the (transparent) concrete block.

    Ties that take shear as anchor reinforcement are drawn in orange, the others grey.
    """
    import pyvista as pv

    r = model.rebar
    if r is None:
        return
    c = model.concrete
    bars = r.positions(c.N, c.B)
    if not bars:
        return
    top = -(r.cover + r.tie_diameter + r.bar_diameter / 2)
    if r.hook == "180":
        top -= 3.5 * r.bar_diameter  # the bend rises this much above the straight bar
    bottom = -c.H
    for x, y in bars:
        line = pv.Line((x, y, bottom), (x, y, top))
        plotter.add_mesh(line.tube(radius=r.bar_diameter / 2, n_sides=10), color="#55606b")
        _hook(plotter, r, x, y, top)
    inset = r.cover + r.tie_diameter / 2
    a, b = c.N / 2 - inset, c.B / 2 - inset
    z = -(r.cover + r.tie_diameter / 2)
    k = 0
    while z > bottom + r.cover:
        loop = pv.MultipleLines([(-a, -b, z), (a, -b, z), (a, b, z), (-a, b, z), (-a, -b, z)])
        color = "#e07a1f" if k < r.top_ties else "#8a949e"
        plotter.add_mesh(loop.tube(radius=r.tie_diameter / 2, n_sides=8), color=color)
        z -= r.tie_spacing
        k += 1


def _hairpins(plotter, model: BasePlateModel) -> None:
    """Inverted U bars over every anchor, in green."""
    import pyvista as pv

    h = model.hairpins
    if h is None:
        return
    top = -(h.cover + h.diameter / 2)
    bottom = top - h.leg_length
    for a in model.anchors:
        for k in range(h.count):
            dy = (k - (h.count - 1) / 2) * 3 * h.diameter
            y = a.y + dy
            path = np.array([(a.x - h.offset, y, bottom), (a.x - h.offset, y, top),
                             (a.x + h.offset, y, top), (a.x + h.offset, y, bottom)])
            plotter.add_mesh(pv.MultipleLines(path).tube(radius=h.diameter / 2, n_sides=10),
                             color="#2e9e4f")


def _hook(plotter, r, x: float, y: float, top: float) -> None:
    """Standard hook at the top of a pedestal bar, turned towards the section centre.

    90°: horizontal extension of 12 db. 180°: bend of inside diameter 6 db and a
    straight extension of max(4 db, 65 mm) back down (ACI 318-19 Table 25.3.1).
    """
    import pyvista as pv

    if not r.hooked:
        return
    db = r.bar_diameter
    norm = (x * x + y * y) ** 0.5 or 1.0
    u = np.array([-x / norm, -y / norm, 0.0])
    start = np.array([x, y, top])
    if r.hook == "90":
        path = [start, start + 12 * db * u]
    else:
        radius = 3 * db + db / 2
        centre = start + radius * u
        angles = np.linspace(np.pi, 0.0, 13)
        path = [centre + radius * np.cos(t) * u + radius * np.sin(t) * np.array([0, 0, 1.0])
                for t in angles]
        path.append(path[-1] - np.array([0, 0, max(4 * db, 65.0)]))
    line = pv.MultipleLines(np.array(path)) if len(path) > 2 else pv.Line(path[0], path[1])
    plotter.add_mesh(line.tube(radius=db / 2, n_sides=10), color="#55606b")


def _anchor_labels(plotter, model: BasePlateModel, results: Results, unit_force: float,
                   force_label: str) -> None:
    """Axial force (tension +) and shear of every anchor rod, next to it."""
    if not results.anchors:
        return
    points = np.array([[a.x, a.y, model.tp + 2.5 * model.anchor.diameter]
                       for a in results.anchors])
    labels = []
    for i, a in enumerate(results.anchors, start=1):
        v = float(np.hypot(a.Vx, a.Vy))
        text = f"#{i}  N = {a.tension * unit_force:.1f} {force_label}"
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
               reset: bool = True, *, dimensions=None, numbers: bool = False) -> None:
    """The model; ``dimensions`` is a length formatter to draw the dimension lines."""
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
    _rebar(plotter, model)
    _hairpins(plotter, model)
    if dimensions is not None:
        draw_dimensions(plotter, model, dimensions)
    if numbers:
        draw_anchor_numbers(plotter, model)
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
        _rebar(plotter, model)
        _hairpins(plotter, model)
    _anchor_labels(plotter, model, results, unit_force, force_label)
    _finish(plotter, reset)
    if name == "CPRESS":
        plotter.view_xy()
        plotter.reset_camera()


def render_figures(out: str | Path, model: BasePlateModel, mesh: Mesh,
                   solved: list[tuple[str, Path, Results]], *, scale: float = 20.0,
                   unit_force: float = 1e-3, force_label: str = "kN",
                   size: tuple[int, int] = (1100, 800),
                   length=_mm) -> dict[str, list[tuple[str, str]]]:
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

    previous = dict(STYLE)
    STYLE.update(text="black", dims="#1f5fa8")  # the report pages are white

    def plan(p) -> None:
        draw_model(p, model, mesh, dimensions=length, numbers=True, reset=False)
        p.view_xy()
        p.reset_camera()
        p.camera.zoom(1.4)

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
            (tr("Planta: dimensiones de la placa y del arreglo de anclajes"),
             shot("fig_planta.png", plan)),
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
        STYLE.update(previous)
    return figures
