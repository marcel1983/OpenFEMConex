# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""3D picture of a moment end-plate connection (PyVista meshes, no solver).

Axes: x along the beam (the face of the column flange at x = 0, the beam towards
+x), y across the beam, z up; the column web lies in the plane y = 0. Units: mm.
"""

from __future__ import annotations

import math

from openconex.connections.moment.end_plate import (
    STIFFENED_EXTENSION,
    EndPlate,
    EndPlateLayout,
)
from openconex.connections.moment.fr_moment import MomentConnection

from openfemconex.tb_scene import BOLT, PLATE, STEEL, Part, _beam, _box

__all__ = ["bolt_rows", "draw", "isometric", "parts", "plate_height"]

COLUMN = "#a9b7c8"
STIFFENER = "#3f5f86"
INCH = 25.4


def plate_height(beam, ep: EndPlate) -> tuple[float, float]:
    """(top, bottom) of the end plate, from the beam centreline."""
    top = beam.d / 2 + (ep.pext if ep.pext > 0 else 0.5 * INCH)
    bottom = top if ep.symmetric else beam.d / 2 + 0.5 * INCH
    return top, -bottom


def bolt_rows(beam, ep: EndPlate) -> list[float]:
    """Height z of every bolt row (two bolts each), from the beam centreline."""
    inner = beam.d / 2 - beam.tf
    pb = ep.pb or 3 * ep.bolt.diameter
    rows = [inner - ep.pf - i * pb for i in range(ep.inside_rows)]
    outer = beam.d / 2
    rows += [outer + ep.pf_o + i * pb for i in range(ep.outside_rows)]
    if ep.symmetric:
        return rows + [-z for z in rows]
    # two bolts at the compression flange, as in the Design Guide bolt force models
    return rows + [-(inner - ep.pf)]


def _prism(points_xz: list[tuple[float, float]], y0: float, y1: float):
    """A plate in the x-z plane, outline ``points_xz``, from y0 to y1."""
    import pyvista as pv

    pts = [(x, y0, z) for x, z in points_xz]
    face = [len(pts), *range(len(pts))]
    poly = pv.PolyData(pts, faces=face)
    return poly.extrude((0.0, y1 - y0, 0.0), capping=True)


def _column(mc: MomentConnection, height: float) -> list[Part]:
    c = mc.column
    d, bf, tf, tw = c.d, c.bf, c.tf, c.tw
    h = height / 2
    meshes = [_box(-tf, 0, -bf / 2, bf / 2, -h, h), _box(-d, -d + tf, -bf / 2, bf / 2, -h, h),
              _box(-d + tf, -tf, -tw / 2, tw / 2, -h, h)]
    return [Part(m, COLUMN, 1.0, "columna") for m in meshes]


def _column_plates(mc: MomentConnection) -> list[Part]:
    """Continuity plates at both beam flanges and the web doubler plate."""
    c, beam = mc.column, mc.beam
    out: list[Part] = []
    x0, x1 = -c.d + c.tf, -c.tf
    if mc.continuity_plate > 0:
        t = mc.continuity_plate
        width = mc.continuity_plate_width or (c.bf - c.tw) / 2
        for zc in ((beam.d - beam.tf) / 2, -(beam.d - beam.tf) / 2):
            for sign in (1.0, -1.0):
                y0 = sign * c.tw / 2
                out.append(Part(_box(x0, x1, y0, y0 + sign * width, zc - t / 2, zc + t / 2),
                                STIFFENER, 1.0, "placas de continuidad"))
    if mc.doubler_plate > 0:
        t = mc.doubler_plate
        h = beam.d / 2 + 2 * INCH
        out.append(Part(_box(x0, x1, c.tw / 2, c.tw / 2 + t, -h, h), STIFFENER, 1.0,
                        "placa doble"))
    return out


def _end_plate(mc: MomentConnection, x0: float, sign: float) -> list[Part]:
    """End plate, beam stub, extension stiffeners and bolts of one beam; ``sign`` is
    the direction of the beam (+1 towards +x from the face at ``x0``)."""
    beam, ep = mc.beam, mc.end_plate
    assert ep is not None
    tp = ep.thickness
    top, bottom = plate_height(beam, ep)
    out = [Part(_box(x0, x0 + sign * tp, -ep.width / 2, ep.width / 2, bottom, top), PLATE,
                1.0, "placa de extremo")]
    xb = x0 + sign * tp
    for mesh in _beam(beam, xb, 2.2 * beam.d, sign):
        out.append(Part(mesh, STEEL, 1.0, "viga"))
    ts = max(ep.stiffener_thickness, beam.tw, 10.0)
    if ep.layout in STIFFENED_EXTENSION:
        h = top - beam.d / 2
        length = h / math.tan(math.radians(30))
        for zf, s in ((beam.d / 2, 1.0), (-beam.d / 2, -1.0)):
            if s < 0 and not ep.symmetric:
                continue
            pts = [(xb, zf), (xb, zf + s * h), (xb + sign * length, zf)]
            out.append(Part(_prism(pts, -ts / 2, ts / 2), STIFFENER, 1.0,
                            "rigidizador de la extensión"))
    if ep.layout in (EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN,
                     EndPlateLayout.FLUSH_4_STIFFENED_INSIDE):
        rows = bolt_rows(beam, ep)
        if ep.layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN:
            z = rows[0] - ep.ps_o - ts / 2
        else:
            z = rows[1] - ep.ps - ts / 2
        span = (beam.bf - beam.tw) / 2
        for zz in ((z, -z) if ep.symmetric else (z,)):
            for s in (1.0, -1.0):
                out.append(Part(_box(xb, xb + sign * 4 * INCH, s * beam.tw / 2,
                                     s * (beam.tw / 2 + span), zz - ts / 2, zz + ts / 2),
                                STIFFENER, 1.0, "rigidizador"))
    return out


def _bolts(mc: MomentConnection, xa: float, xb: float) -> list[Part]:
    import pyvista as pv

    ep = mc.end_plate
    assert ep is not None
    db = ep.bolt.diameter
    x0, x1 = xa - 1.2 * db, xb + 1.2 * db
    out: list[Part] = []
    for z in bolt_rows(mc.beam, ep):
        for y in (-ep.gage / 2, ep.gage / 2):
            out.append(Part(pv.Cylinder(center=((x0 + x1) / 2, y, z), direction=(1, 0, 0),
                                        radius=db / 2, height=x1 - x0, resolution=24),
                            BOLT, 1.0, "pernos"))
            for xn in (xb + 0.45 * db, xa - 0.45 * db):
                out.append(Part(pv.Cylinder(center=(xn, y, z), direction=(1, 0, 0),
                                            radius=0.85 * db, height=0.9 * db, resolution=6),
                                BOLT, 1.0, "pernos"))
    return out


def parts(mc: MomentConnection) -> list[Part]:
    """Meshes of the column, its stiffening, the beam (two with ``two_sided``), the end
    plates and the bolts."""
    ep = mc.end_plate
    assert ep is not None
    top, bottom = plate_height(mc.beam, ep)
    height = max(3.0 * mc.beam.d, 2 * max(top, -bottom) + 2 * mc.column.d)
    out = _column(mc, height) + _column_plates(mc)
    tp = ep.thickness
    out += _end_plate(mc, 0.0, 1.0) + _bolts(mc, -mc.column.tf, tp)
    if mc.two_sided:
        xc = -mc.column.d
        out += _end_plate(mc, xc, -1.0) + _bolts(mc, xc - tp, xc + mc.column.tf)
    return out


def draw(plotter, mc: MomentConnection) -> None:
    for p in parts(mc):
        plotter.add_mesh(p.mesh, color=p.color, opacity=p.opacity, smooth_shading=False,
                         show_edges=False)


def isometric(plotter) -> None:
    plotter.camera_position = "iso"
    plotter.camera.azimuth = 35
    plotter.camera.elevation = 12
    plotter.reset_camera()
