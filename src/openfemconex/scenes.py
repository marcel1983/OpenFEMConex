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
           "draw_solved_model", "grid_from_mesh", "render_figures",
           "render_through_bolt_figures"]

# PyVista announces a future change of the default surface algorithm; not relevant here.
warnings.filterwarnings("ignore", message=".*extract_surface.*")
warnings.filterwarnings("ignore", message=r"(?s).*default value of `algorithm`.*")

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
    # f: from the column axis to the outer anchor rows, measured across the two rows
    # (along x for rows facing the flanges, along y for rows facing the weak axis)
    if model.anchors:
        ax = _distinct([a.x for a in model.anchors])
        ay = _distinct([a.y for a in model.anchors])
        along_x = (not model.rows_weak if not (len(ay) == 2 and len(ax) > 2)
                   else False)
        c0 = model.ex if along_x else model.ey
        values = ax if along_x else ay
        rows = [v for v in (min(values), max(values)) if abs(v - c0) > 1.0]
        if rows:
            if along_x:
                chain(_distinct(rows + [c0]), True, -B / 2 - off, -B / 2, prefix="f = ")
            else:
                chain(_distinct(rows + [c0]), False, -N / 2 - off, -N / 2, prefix="f = ")
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


WELD_COLOR, CJP_COLOR = "#e8b923", "#d0392b"


def _outline(grid, part: int, z: float, outer_only: bool):
    """Boundary lines of the cross-section of a part at height ``z``."""
    body = grid.threshold([part - 0.5, part + 0.5], scalars="part")
    if body.n_cells == 0:
        return None
    cut = body.slice(normal="z", origin=(0.0, 0.0, z))
    if cut.n_points == 0:
        return None
    edges = cut.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                      manifold_edges=False, non_manifold_edges=False)
    if outer_only and edges.n_points:
        regions = edges.connectivity()
        ids = np.unique(regions["RegionId"])
        if len(ids) > 1:
            def span(i):
                b = regions.threshold([i - 0.5, i + 0.5], scalars="RegionId").bounds
                return (b[1] - b[0]) * (b[3] - b[2])

            edges = regions.threshold([max(ids, key=span) - 0.5, max(ids, key=span) + 0.5],
                                      scalars="RegionId").extract_surface()
    return edges


def draw_welds(plotter, model: BasePlateModel, grid) -> None:
    """Column-to-plate weld (fillet bead, or a CJP mark and label) and stiffener welds.

    Tubes are welded on the outside only; open shapes all around.
    """
    from openfemconex.model import SectionKind

    z = model.tp + 0.05
    tube = model.section.kind in (SectionKind.HSS_RECT, SectionKind.HSS_ROUND)
    col = _outline(grid, PARTS["COLUMN"], z, outer_only=tube)
    if col is not None and col.n_points:
        if model.cjp:
            r = 2.5
            plotter.add_mesh(col.tube(radius=r, n_sides=8).translate((0, 0, r), inplace=False),
                             color=CJP_COLOR)
            top = col.points[np.argmax(col.points[:, 0] + 0.5 * col.points[:, 1])]
            plotter.add_point_labels(np.array([[top[0], top[1], model.tp + 0.12 *
                                                model.section.max_dim]]), ["CJP"],
                                     font_size=13, bold=True, text_color="white",
                                     shape_color=CJP_COLOR, shape_opacity=0.95,
                                     always_visible=True, show_points=False)
        elif model.weld > 0:
            r = 0.5 * model.weld
            plotter.add_mesh(col.tube(radius=r, n_sides=10).translate((0, 0, 0.6 * r),
                                                                       inplace=False),
                             color=WELD_COLOR)
    if model.stiffeners and model.stiffener_weld > 0:
        st = _outline(grid, PARTS["STIFFENER"], z, outer_only=False)
        if st is not None and st.n_points:
            r = 0.5 * model.stiffener_weld
            plotter.add_mesh(st.tube(radius=r, n_sides=10).translate((0, 0, 0.6 * r),
                                                                      inplace=False),
                             color=WELD_COLOR)


# ---------------------------------------------------------------------------- drawings
CALLOUT = {"text": "#1b1b1b", "line": "#3a3a3a", "weld": "#b07d00", "cjp": CJP_COLOR}


def _wall_point(model: BasePlateModel, side: float) -> tuple[float, float]:
    """A point on the outer face of the column, on the +x (side 1) or -x (side -1) side."""
    from openfemconex.model import SectionKind

    s = model.section
    if s.kind is SectionKind.HSS_ROUND:
        r = s.d / 2
        return model.ex + side * r * 0.7071, model.ey + side * r * 0.7071
    return model.ex + side * s.d / 2, model.ey + side * 0.3 * s.bf


def _targets(model: BasePlateModel, view: str, plane: float) -> dict[str, np.ndarray]:
    """Point each callout points at, on the drawing plane (z for plan, y for elevation)."""
    N, B, tp = model.N, model.B, model.tp
    out: dict[str, tuple[float, float, float]] = {}

    def at(x: float, y: float, z: float) -> tuple[float, float, float]:
        return (x, y, plane) if view == "plan" else (x, plane, z)

    corner = max(model.anchors, key=lambda a: a.x + a.y) if model.anchors else None
    wx, wy = _wall_point(model, 1.0)
    if view == "plan":
        out["plate"] = at(0.75 * N / 2, -0.75 * B / 2, tp)
        out["column"] = at(wx - 0.5 * model.section.min_wall, wy, tp)
        lx, ly = _wall_point(model, -1.0)
        out["weld"] = at(lx, ly, tp)
    else:
        out["plate"] = at(0.7 * N / 2, 0, tp / 2)
        out["column"] = at(wx, 0, tp + 0.55 * model.Lc)
        out["weld"] = at(wx + 0.6 * model.weld, 0, tp + 0.6 * model.weld)
        c = model.concrete
        out["concrete"] = at(0.8 * c.N / 2, 0, -0.55 * c.H)
        if c.grout > 0:
            out["grout"] = at(-0.85 * N / 2, 0, -c.grout / 2)
        if model.lug is not None:
            out["lug"] = at(model.ex, 0, -0.5 * (model.lug.embedment + c.grout))
    if corner is not None:
        out["anchor"] = (at(corner.x, corner.y, tp) if view == "plan"
                         else at(corner.x, 0, -0.5 * model.anchor.hef))
    if model.stiffeners:
        st = (next((t for t in model.stiffeners if abs(t.direction[1]) > 0.7), model.stiffeners[0])
              if view == "plan" else
              max(model.stiffeners, key=lambda t: t.direction[0]))
        (ox, oy), (dx, dy) = st.origin, st.direction
        mid = 0.45 * st.length
        out["stiffener"] = at(ox + dx * mid, oy + dy * mid, tp + 0.4 * st.height)
        if model.stiffener_weld > 0:
            end = 0.85 * st.length
            out["stiffener_weld"] = at(ox + dx * end - dy * st.thickness,
                                       oy + dy * end + dx * st.thickness,
                                       tp + 0.5 * model.stiffener_weld)
    return {k: np.array(v, dtype=float) for k, v in out.items()}


def draw_callouts(plotter, model: BasePlateModel, view: str, texts: dict[str, str]) -> None:
    """Leader lines with arrows from a column of labels to each element (and the welds).

    ``view`` is ``plan`` (labels on the left) or ``elevation`` (labels on the right).
    """
    import pyvista as pv

    c = model.concrete
    size = max(c.N, c.B, model.N, model.B)
    if view == "plan":
        plane = model.tp + model.Lc + 5.0
        x_label = -max(c.N, model.N) / 2 - 0.30 * size
        span = (max(c.B, model.B) / 2, -max(c.B, model.B) / 2)
        along = 1
    else:
        plane = -max(c.B, model.B) / 2 - 5.0
        x_label = max(c.N, model.N) / 2 + 0.30 * size
        span = (model.tp + 0.85 * model.Lc, -0.85 * c.H)
        along = 2
    targets = {k: v for k, v in _targets(model, view, plane).items() if texts.get(k)}
    if not targets:
        return
    order = sorted(targets, key=lambda k: -targets[k][along])
    n = len(order)
    head = 0.025 * size
    labels, points = [], []
    for i, key in enumerate(order):
        target = targets[key]
        level = span[0] + (span[1] - span[0]) * (i + 0.5) / n
        start = target.copy()
        start[0] = x_label
        start[along] = level
        color = CALLOUT["weld"] if "weld" in key else CALLOUT["line"]
        if key == "weld" and model.cjp:
            color = CALLOUT["cjp"]
        direction = target - start
        length = float(np.linalg.norm(direction))
        if length < 1e-6:
            continue
        direction /= length
        plotter.add_mesh(pv.Line(start, target - direction * head), color=color, line_width=1.6)
        plotter.add_mesh(pv.Cone(center=target - direction * head / 2, direction=direction,
                                 height=head, radius=0.3 * head, resolution=12), color=color)
        labels.append(texts[key])
        points.append(start)
    plotter.add_point_labels(np.array(points), labels, font_size=11, text_color=CALLOUT["text"],
                             shape_color="white", shape_opacity=0.9, always_visible=True,
                             show_points=False,
                             justification_horizontal="right" if view == "plan" else "left")


def draw_elevation_dimensions(plotter, model: BasePlateModel, length=_mm) -> None:
    """Elevation (x-z): plate and anchor positions below the block, heights on the left."""
    import pyvista as pv

    c = model.concrete
    N, tp = model.N, model.tp
    size = max(c.N, c.B, N, model.B)
    y = -max(c.B, model.B) / 2 - 5.0
    off, tick = 0.07 * size, 0.012 * size
    points: list[tuple[float, float, float]] = []
    lines: list[int] = []
    label_at: list[tuple[float, float, float]] = []
    labels: list[str] = []

    def seg(a, b) -> None:
        points.extend([a, b])
        lines.extend([2, len(points) - 2, len(points) - 1])

    def chain(values: list[float], horizontal: bool, level: float, start: float,
              names: list[str] | None = None) -> None:
        def at(v: float, w: float):
            return (v, y, w) if horizontal else (w, y, v)

        seg(at(values[0], level), at(values[-1], level))
        for v in values:
            seg(at(v, start), at(v, level))
            seg(at(v - tick, level - tick), at(v + tick, level + tick))
        for i, (a, b) in enumerate(zip(values, values[1:], strict=False)):
            if b - a > 1.0:
                name = (names[i] + " = ") if names and names[i] else ""
                label_at.append(at((a + b) / 2, level - 2.2 * tick) if horizontal
                                else at((a + b) / 2, level - 2.5 * tick))
                labels.append(name + length(b - a))

    bottom = -c.H
    xs = _distinct([a.x for a in model.anchors] + [-N / 2, N / 2])
    chain(xs, True, bottom - off, bottom)
    chain([-N / 2, N / 2], True, bottom - 2 * off, bottom)
    left = -max(c.N, N) / 2
    heights = [-model.anchor.hef, 0.0, tp]
    names = ["hef", "tp"]
    if model.stiffeners:
        heights.append(tp + max(s.height for s in model.stiffeners))
        names.append("h")
    chain(heights, False, left - off, left, names)
    poly = pv.PolyData(np.array(points, dtype=float), lines=np.array(lines))
    plotter.add_mesh(poly, color=STYLE["dims"], line_width=1.5)
    plotter.add_point_labels(np.array(label_at), labels, font_size=11, text_color=STYLE["dims"],
                             shape=None, always_visible=True, show_points=False,
                             justification_horizontal="right")


def draw_drawing(plotter, model: BasePlateModel, mesh: Mesh, view: str,
                 texts: dict[str, str], length=_mm) -> None:
    """Plan or elevation with dimensions and callouts, in parallel projection."""
    draw_model(plotter, model, mesh, reset=False, numbers=view == "plan",
               dimensions=length if view == "plan" else None)
    if view == "elevation":
        draw_elevation_dimensions(plotter, model, length)
    draw_callouts(plotter, model, view, texts)
    plotter.enable_parallel_projection()
    if view == "plan":
        plotter.view_xy()
    else:
        plotter.view_xz()  # seen from -y, the side of the dimensions, x to the right
    plotter.reset_camera()
    # the labels stick out of the bounds of the model: make room on their side
    c = model.concrete
    shift = (-1.0 if view == "plan" else 1.0) * 0.28 * max(c.N, c.B, model.N, model.B)
    cam = plotter.camera
    cam.position = (cam.position[0] + shift, cam.position[1], cam.position[2])
    cam.focal_point = (cam.focal_point[0] + shift, cam.focal_point[1], cam.focal_point[2])
    cam.zoom(1.25 if view == "plan" else 0.85)


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
    # through-bolts: across the block to the nut on the far plate
    far_t = (model.far.thickness if model.far is not None
             else model.opposite.tp if model.opposite is not None else None)
    if far_t is None and model.flange is not None:
        far_t = 0.0  # the nut bears on the back of the column flange
    if far_t is not None:
        H = model.concrete.H
        bottom = -H - far_t - 1.6 * a.diameter
        for rod in model.anchors:
            plotter.add_mesh(pv.Cylinder(center=(rod.x, rod.y, -H - far_t - 4),
                                         direction=(0, 0, 1), radius=a.washer / 2, height=8,
                                         resolution=28), color="#6f7f8f")
            plotter.add_mesh(pv.Cylinder(center=(rod.x, rod.y,
                                                 -H - far_t - 8 - 0.45 * a.diameter),
                                         direction=(0, 0, 1), radius=0.85 * a.diameter,
                                         height=0.9 * a.diameter, resolution=6),
                             color="#4a5560")
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
        steel_block = part == 3 and model.flange is not None  # column flange
        plotter.add_mesh(surface, color="#a9b7c8" if steel_block else color,
                         show_edges=edges, edge_color="#3a3a3a", line_width=0.4,
                         opacity=0.45 if part == 3 and not steel_block else 1.0)
        if not edges:
            plotter.add_mesh(surface.extract_feature_edges(feature_angle=40), color="#2b2b2b",
                             line_width=1.2)
    _rods(plotter, model)
    _lug(plotter, model)
    _rebar(plotter, model)
    _hairpins(plotter, model)
    if not edges:
        draw_welds(plotter, model, grid)
    if dimensions is not None:
        draw_dimensions(plotter, model, dimensions)
    if numbers:
        draw_anchor_numbers(plotter, model)
    _finish(plotter, reset)


def draw_results(plotter, vtu: str | Path, model: BasePlateModel, results: Results,
                 field: str = "von Mises", scale: float = 20.0, unit_force: float = 1e-3,
                 force_label: str = "kN", reset: bool = True, face: str = "front") -> None:
    """One result field on the steel (deformed) or, for the contact pressure, on the
    face of a plate that bears on the concrete: ``face`` "front" is the plate on the
    top face (z = 0), "far" the plate on the opposite face of a through-bolt model
    (back plate or end plate of the opposite beam)."""
    import pyvista as pv

    name, title, cmap = FIELDS[field]
    grid = pv.read(str(vtu))
    bar = {"title": tr(title) + "\n", "vertical": True, "position_x": 0.84, "position_y": 0.25,
           "height": 0.5, "width": 0.06, "title_font_size": 14, "label_font_size": 12,
           "color": STYLE["text"], "n_labels": 5, "fmt": "%.3g"}
    part = grid.cell_data["part"]
    # a steel column flange (moment end plate) is drawn with its results like the rest
    flange = model.flange is not None
    steel = grid.extract_cells(np.nonzero(part != 3)[0]) if not flange else grid
    concrete = grid.threshold([2.5, 3.5], scalars="part")
    if name == "CPRESS":
        # cells above or below the middle of the concrete block: each face on its own
        z_mid = 0.5 * concrete.bounds[4] if concrete.n_cells else -1e9
        zc = grid.cell_centers().points[:, 2]
        side = zc > z_mid if face == "front" else zc < z_mid
        plate = grid.extract_cells(np.nonzero((part == 1) & side)[0]).extract_surface()
        if face == "front":
            bottom = plate.clip(normal="z", origin=(0, 0, 1e-3), invert=True)
        else:
            bottom = plate.clip(normal="z", origin=(0, 0, concrete.bounds[4] - 1e-3),
                                invert=False)
        plotter.add_mesh(bottom, scalars="CPRESS", cmap=cmap, scalar_bar_args=bar)
        plotter.add_mesh(plate.extract_feature_edges(feature_angle=40), color=STYLE["text"])
        column = grid.extract_cells(np.nonzero(((part == 2) | (part == 4)) & side)[0])
        if column.n_cells:
            plotter.add_mesh(column.extract_surface(), color="#5b7ba6", opacity=0.15)
    else:
        warped = steel.warp_by_vector("U", factor=scale)
        plotter.add_mesh(warped, scalars=name, cmap=cmap, scalar_bar_args=bar,
                         show_edges=True, edge_color="#404040", line_width=0.2)
        if not flange:
            plotter.add_mesh(concrete.extract_surface(), color=COLORS[3], opacity=0.3)
        _rods(plotter, model)
        _lug(plotter, model)
        _rebar(plotter, model)
        _hairpins(plotter, model)
    if face == "front":
        _anchor_labels(plotter, model, results, unit_force, force_label)
    _finish(plotter, reset)
    if name == "CPRESS":
        plotter.view_xy()
        # parallel projection: a tall column or beam does not hide the plate in perspective
        plotter.enable_parallel_projection()
        plotter.reset_camera(bounds=bottom.bounds if bottom.n_points else None)
        plotter.camera.zoom(0.8)  # room for the colour bar


def draw_solved_model(plotter, vtu: str | Path, model: BasePlateModel, edges: bool = False,
                      reset: bool = True) -> None:
    """The model as it was solved (the mesh of its .vtu file): parts in colour, or
    the element mesh with ``edges``. Used by models whose mesh is not kept in memory
    (the through-bolt connection)."""
    import pyvista as pv

    grid = pv.read(str(vtu))
    present = set(np.unique(grid.cell_data["part"]))
    for part, color in COLORS.items():
        if part not in present:
            continue
        surface = grid.threshold([part - 0.5, part + 0.5], scalars="part").extract_surface()
        steel_block = part == 3 and model.flange is not None  # column flange
        plotter.add_mesh(surface, color="#a9b7c8" if steel_block else color,
                         show_edges=edges, edge_color="#3a3a3a", line_width=0.4,
                         opacity=0.45 if part == 3 and not steel_block else 1.0)
        if not edges:
            plotter.add_mesh(surface.extract_feature_edges(feature_angle=40), color="#2b2b2b",
                             line_width=1.2)
    _rods(plotter, model)
    _finish(plotter, reset)


def _save_trimmed(image: np.ndarray, path: Path, margin: int = 16) -> None:
    """Save a screenshot without its white border."""
    from PIL import Image

    rgb = image[..., :3].astype(int)
    used = np.nonzero((rgb < 245).any(axis=2))
    if len(used[0]):
        top, bottom = max(used[0].min() - margin, 0), min(used[0].max() + margin, rgb.shape[0])
        left, right = max(used[1].min() - margin, 0), min(used[1].max() + margin, rgb.shape[1])
        image = image[top:bottom, left:right]
    Image.fromarray(np.ascontiguousarray(image)).save(path)


def render_figures(out: str | Path, model: BasePlateModel, mesh: Mesh,
                   solved: list[tuple[str, Path, Results]], *, scale: float = 20.0,
                   unit_force: float = 1e-3, force_label: str = "kN",
                   size: tuple[int, int] = (1100, 800),
                   length=_mm, callouts: dict[str, str] | None = None,
                   errors: list[str] | None = None) -> dict[str, list[tuple[str, str]]]:
    """Render the figures of the report as PNG files in ``out``.

    ``solved`` lists (combination, .vtu file, results). Returns, under the key
    ``""`` the geometry figures and under each combination its result figures, as
    (caption, file name). Needs PyVista and an OpenGL context; returns {} without them.
    """
    try:
        import pyvista as pv
    except ImportError as exc:
        if errors is not None:
            errors.append(f"PyVista: {exc}")
        return {}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    figures: dict[str, list[tuple[str, str]]] = {}

    previous = dict(STYLE)
    STYLE.update(text="black", dims="#1f5fa8")  # the report pages are white



    def shot(name: str, draw, trim: bool = False) -> str | None:
        plotter = pv.Plotter(off_screen=True, window_size=list(size))
        try:
            plotter.set_background("white")
            if trim:
                plotter.window_size = [int(1.4 * size[0]), int(1.4 * size[1])]
            draw(plotter)
            if trim:
                plotter.hide_axes()
                _save_trimmed(plotter.screenshot(None, return_img=True), out / name)
            else:
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
        if callouts is not None:
            figures["planos"] = [
                (tr("Planta acotada"), shot("fig_planta.png", lambda p: draw_drawing(
                    p, model, mesh, "plan", callouts, length), trim=True)),
                (tr("Elevación acotada"), shot("fig_elevacion.png", lambda p: draw_drawing(
                    p, model, mesh, "elevation", callouts, length), trim=True)),
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
    except Exception as exc:  # no OpenGL context: the report goes without (some) figures
        if errors is not None:
            errors.append(f"{type(exc).__name__}: {exc}")
        return figures if figures.get("") else {}
    finally:
        STYLE.update(previous)
    return figures


def render_through_bolt_figures(out: str | Path, sides: list, *, far_caption: str = "",
                                scale: float = 20.0, unit_force: float = 1e-3,
                                force_label: str = "kN", size: tuple[int, int] = (1100, 800),
                                errors: list[str] | None = None
                                ) -> dict[str, list[tuple[str, str]]]:
    """Report figures of the CalculiX models of a through-bolt connection.

    ``sides`` are ``through_bolt_fem.FemSide`` with a solved .vtu file. Returns under
    ``""`` the model and its mesh (isometric views) and, under each .vtu file name, the
    stresses, plastic strain, displacements and the contact pressure on the plate of
    the beam and, with a modelled far face, on the far plate (``far_caption`` names
    it). Without PyVista or OpenGL it returns what it could draw.
    """
    try:
        import pyvista as pv
    except ImportError as exc:
        if errors is not None:
            errors.append(f"PyVista: {exc}")
        return {}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    figures: dict[str, list[tuple[str, str]]] = {}
    previous = dict(STYLE)
    STYLE.update(text="black", dims="#1f5fa8")

    def shot(name: str, draw) -> str:
        plotter = pv.Plotter(off_screen=True, window_size=list(size))
        try:
            plotter.set_background("white")
            draw(plotter)
            # without the white border: the tall wall leaves much of the frame empty
            _save_trimmed(plotter.screenshot(None, return_img=True), out / name)
        finally:
            plotter.close()
        return name

    solved = [s for s in sides if s.vtu is not None and Path(s.vtu).exists()]
    try:
        if solved:
            first = solved[0]
            figures[""] = [
                (tr("Modelo de elementos finitos (vista isométrica)"),
                 shot("fem_modelo.png", lambda p: draw_solved_model(p, first.vtu, first.model))),
                (tr("Malla de elementos finitos (vista isométrica)"),
                 shot("fem_malla.png",
                      lambda p: draw_solved_model(p, first.vtu, first.model, True))),
            ]
        done = set()
        for side in solved:
            vtu = Path(side.vtu)
            if vtu.name in done:
                continue
            done.add(vtu.name)
            r, m = side.results, side.model
            stem = "fem_" + "".join(ch if ch.isalnum() else "_" for ch in vtu.stem)
            two = m.far is not None or m.opposite is not None
            plate = tr("placa de extremo") + (tr(" de la viga 1") if m.opposite else "")
            vm = max(r.plate_von_mises_max, r.far_von_mises_max, r.flange_von_mises_max)
            entries = [
                ("von Mises", "", tr("Esfuerzo de von Mises (deformada × {s}): máx. {v} MPa",
                                     s=f"{scale:g}", v=f"{vm:.0f}")),
                ("Deformación plástica", "",
                 tr("Deformación plástica equivalente: máx. {p} %",
                    p=f"{100 * max(r.plate_peeq_max, r.far_peeq_element,
                                   r.flange_peeq_element):.2f}")),
                ("Desplazamiento", "", tr("Desplazamiento total (deformada × {s})",
                                          s=f"{scale:g}")),
                ("Presión de contacto", "front",
                 tr("Presión de contacto de la placa de extremo sobre el ala de la columna: "
                    "máx. {p} MPa", p=f"{r.bearing_pressure_max:.1f}")
                 if m.flange is not None else
                 tr("Presión de contacto de la {plate} sobre el concreto: máx. {p} MPa",
                    plate=plate, p=f"{r.bearing_pressure_max:.1f}")),
            ]
            if two:
                entries.append(("Presión de contacto", "far",
                                tr("Presión de contacto de la {plate} sobre el concreto: "
                                   "máx. {p} MPa", plate=far_caption or tr("placa opuesta"),
                                   p=f"{r.far_pressure_max:.1f}")))
            figures[vtu.name] = [
                (caption, shot(f"{stem}_{FIELDS[field][0]}{'_far' if face == 'far' else ''}.png",
                               lambda p, f=field, fc=face or "front": draw_results(
                                   p, vtu, m, r, f, scale, unit_force, force_label,
                                   face=fc)))
                for field, face, caption in entries]
    except Exception as exc:  # no OpenGL context: the report goes without (some) figures
        if errors is not None:
            errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        STYLE.update(previous)
    return figures
