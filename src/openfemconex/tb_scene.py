# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D picture of a through-bolt connection (PyVista meshes, no solver).

Axes: x along the beam (the near face of the wall at x = 0, the beam towards +x),
y across the beam, z up. Units: mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openfemconex.through_bolt import ThroughBoltConnection, _plate_extension, bolt_rows

STEEL, PLATE, BOLT, CONCRETE, GROUT = "#8fa7c4", "#5b7ba6", "#d98c3f", "#c8c8c8", "#9c8f7a"
REBAR = "#9b2d20"


@dataclass
class Part:
    mesh: object
    color: str
    opacity: float = 1.0
    name: str = ""


def _box(x0, x1, y0, y1, z0, z1):
    import pyvista as pv

    return pv.Box(bounds=(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1),
                          min(z0, z1), max(z0, z1)))


def _beam(beam, x0: float, length: float, sign: float) -> list:
    d, bf, tf, tw = beam.d, beam.bf, beam.tf, beam.tw
    x1 = x0 + sign * length
    return [_box(x0, x1, -bf / 2, bf / 2, d / 2 - tf, d / 2),
            _box(x0, x1, -bf / 2, bf / 2, -d / 2, -d / 2 + tf),
            _box(x0, x1, -tw / 2, tw / 2, -d / 2 + tf, d / 2 - tf)]


def parts(conn: ThroughBoltConnection) -> list[Part]:
    """Meshes of the wall or column, beams, plates and bolts."""
    import pyvista as pv

    beam, ep, m = conn.beam, conn.end_plate, conn.member
    h = m.thickness
    rows = bolt_rows(beam, ep)
    zs = rows + [-z for z in rows]
    ext = _plate_extension(beam, ep)
    hp = beam.d / 2 + ext
    out: list[Part] = []
    # the wall (a strip) or the column
    width = m.width if math.isfinite(m.width) else max(4 * ep.width, 3 * beam.bf)
    height = max(3.0 * beam.d, 2 * hp + 2 * h)
    out.append(Part(_box(-h, 0, -width / 2, width / 2, -height / 2, height / 2), CONCRETE,
                    0.35, "concreto"))
    out += _rebar(conn, width, height)
    tp = ep.thickness
    out.append(Part(_box(0, tp, -ep.width / 2, ep.width / 2, -hp, hp), PLATE, 1.0,
                    "placa de extremo"))
    length = 2.2 * beam.d
    for mesh in _beam(beam, tp, length, 1.0):
        out.append(Part(mesh, STEEL, 1.0, "viga"))
    if conn.opposite is not None:
        o = conn.opposite
        tb = o.end_plate.thickness
        hb = o.beam.d / 2 + _plate_extension(o.beam, o.end_plate)
        out.append(Part(_box(-h - tb, -h, -o.end_plate.width / 2, o.end_plate.width / 2,
                             -hb, hb), PLATE, 1.0, "placa de la viga opuesta"))
        for mesh in _beam(o.beam, -h - tb, length, -1.0):
            out.append(Part(mesh, STEEL, 1.0, "viga opuesta"))
    else:
        bp = conn.back_plate
        tb = bp.thickness
        out.append(Part(_box(-h - tb, -h, -bp.width / 2, bp.width / 2, -bp.height / 2,
                             bp.height / 2), PLATE, 1.0, "placa posterior"))
    db = ep.bolt.diameter
    x0, x1 = -h - tb - 1.2 * db, tp + 1.2 * db
    for z in zs:
        for y in (-ep.gage / 2, ep.gage / 2):
            rod = pv.Cylinder(center=((x0 + x1) / 2, y, z), direction=(1, 0, 0),
                              radius=db / 2, height=x1 - x0, resolution=24)
            out.append(Part(rod, BOLT, 1.0, "pernos"))
            for xn in (tp + 0.45 * db, -h - tb - 0.45 * db):
                nut = pv.Cylinder(center=(xn, y, z), direction=(1, 0, 0), radius=0.85 * db,
                                  height=0.9 * db, resolution=6)
                out.append(Part(nut, BOLT, 1.0, "pernos"))
            if conn.grout_length > 0:
                g = pv.Cylinder(center=(-conn.grout_length / 2, y, z), direction=(1, 0, 0),
                                radius=0.8 * db, height=conn.grout_length, resolution=24)
                out.append(Part(g, GROUT, 0.8, "grout"))
    return out


def _positions(length: float, edge: float, spacing: float) -> list[float]:
    """Bars centred on the member, ``spacing`` apart, at least ``edge`` from its sides."""
    if spacing <= 0 or length <= 2 * edge:
        return []
    n = int(math.floor((length - 2 * edge) / spacing + 1e-9))
    return [(i - n / 2) * spacing for i in range(n + 1)]


def _rebar(conn: ThroughBoltConnection, width: float, height: float) -> list[Part]:
    """The bars of the wall or column at both faces: horizontal bars (ties in a
    column) outside, vertical bars inside them."""
    import pyvista as pv

    m = conn.member
    h, c = m.thickness, m.cover
    dv, dh = m.vertical.diameter, m.horizontal.diameter
    if dv <= 0 or dh <= 0:
        return []
    column = m.kind.value == "column" and math.isfinite(m.width)
    xh = [-(c + dh / 2), -(h - c - dh / 2)]
    xv = [-(c + dh + dv / 2), -(h - c - dh - dv / 2)]
    side = c + dh + dv / 2  # bar axis from the side face of a column
    bars = []
    ys = (_positions(width, side, m.vertical.spacing) if column
          else _positions(width, m.vertical.spacing / 2, m.vertical.spacing))
    for x in xv:
        for y in ys:
            bars.append(pv.Cylinder(center=(x, y, 0.0), direction=(0, 0, 1), radius=dv / 2,
                                    height=height, resolution=12))
    zs = _positions(height, m.horizontal.spacing / 2, m.horizontal.spacing)
    span = width - 2 * (c + dh / 2) if column else width
    for z in zs:
        for x in xh:
            bars.append(pv.Cylinder(center=(x, 0.0, z), direction=(0, 1, 0), radius=dh / 2,
                                    height=span, resolution=12))
        if column:  # the legs of the tie through the thickness
            for y in (-span / 2, span / 2):
                bars.append(pv.Cylinder(center=(-h / 2, y, z), direction=(1, 0, 0),
                                        radius=dh / 2, height=h - 2 * (c + dh / 2),
                                        resolution=12))
    if not bars:
        return []
    return [Part(pv.merge(bars), REBAR, 1.0, "refuerzo")]


def draw(plotter, conn: ThroughBoltConnection) -> None:
    for p in parts(conn):
        plotter.add_mesh(p.mesh, color=p.color, opacity=p.opacity, smooth_shading=False,
                         show_edges=False)


def isometric(plotter) -> None:
    plotter.camera_position = "iso"
    plotter.camera.azimuth = 200
    plotter.camera.elevation = 10
    plotter.reset_camera()
