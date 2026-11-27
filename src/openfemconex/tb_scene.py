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


def draw(plotter, conn: ThroughBoltConnection) -> None:
    for p in parts(conn):
        plotter.add_mesh(p.mesh, color=p.color, opacity=p.opacity, smooth_shading=False,
                         show_edges=False)


def isometric(plotter) -> None:
    plotter.camera_position = "iso"
    plotter.camera.azimuth = 200
    plotter.camera.elevation = 10
    plotter.reset_camera()
