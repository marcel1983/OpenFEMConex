# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX model of a through-bolt connection.

The end plate of each beam bearing on the face of the wall or column is the same
problem as a base plate on its concrete block, so this module maps the connection
onto the base plate model and reuses its mesh, solver and result reader:

* "column" = the beam (I-shape) and "base plate" = its end plate;
* "concrete block" = the wall or column, as deep as its thickness h, with its far face
  fixed (the back plate or the other beam spreads the bolt forces there);
* "anchor rods" = the through-bolts: tension-only springs E·A/L with L = h + both plate
  thicknesses (unbonded in the sleeves), anchored on the far plate taken as rigid;
* shear by friction in the contact with the wall (``ShearTransfer.FRICTION``) or by the
  bolts bearing on the grout (lateral springs, ``ShearTransfer.GROUT``).

Model axes (those of the base plate): z along the beam, out of the wall; x up the beam
depth; y across. The beam moment M (positive with tension at the top) is My = -M and
its shear V (positive downwards) is Vx = -V.

With an opposite beam each side is solved on its own, with its own loads: the bolts of
a group carry the larger tension of the two sides (the zone model of
:mod:`through_bolt`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import BOLTS, STEELS
from openconex.units import Kind

from openfemconex.checks import (
    CURRENT,
    Edition,
    _calc,
    cjp_weld_line,
    concrete_bearing,
    fillet_weld_line,
    friction,
    plate_plastic_strain,
)
from openfemconex.model import (
    Anchor,
    AnchorSpec,
    BasePlateModel,
    Concrete,
    ContactSettings,
    Loads,
    Section,
    SectionKind,
    Steel,
)
from openfemconex.results import Results
from openfemconex.through_bolt import (
    ShearTransfer,
    ThroughBoltConnection,
    _plate_extension,
    bolt_rows,
    front_area,
)

__all__ = ["FemSide", "fem_checks", "fem_loads", "fem_model", "solve_combination"]

STRAIN_LIMIT = 0.05


def _steel(grade: str) -> Steel:
    s = STEELS[grade]
    return Steel(Fy=s.Fy, Fu=s.Fu, name=grade)


def _sides(conn: ThroughBoltConnection, far: bool):
    if far:
        if conn.opposite is None:
            raise ValueError("la conexión no tiene viga opuesta")
        o = conn.opposite
        t_far = conn.end_plate.thickness
        return o.beam, o.end_plate, t_far
    t_far = (conn.opposite.end_plate.thickness if conn.opposite is not None
             else conn.back_plate.thickness)
    return conn.beam, conn.end_plate, t_far


def fem_model(conn: ThroughBoltConnection, far: bool = False) -> BasePlateModel:
    """Base plate model of the end plate of beam 1 (or of the opposite beam)."""
    beam, ep, t_far = _sides(conn, far)
    m = conn.member
    hp = beam.d / 2 + _plate_extension(beam, ep)
    N, B = 2 * hp, ep.width
    rows = bolt_rows(beam, ep)
    zs = rows + [-z for z in rows]
    anchors = tuple(Anchor(z, y) for z in zs for y in (-ep.gage / 2, ep.gage / 2))
    section = Section(SectionKind.I, d=beam.d, bf=beam.bf, tf=beam.tf, tw=beam.tw,
                      name=beam.name)
    db = ep.bolt.diameter
    hole = db + (3.2 if db >= 25.0 else 1.6)
    # the largest washer that fits around every bolt: inside the plate, clear of the beam
    room = min(min(section.distance(a.x, a.y) for a in anchors),
               min(N / 2 - abs(a.x) for a in anchors), min(B / 2 - abs(a.y) for a in anchors),
               ep.gage / 2)
    washer = max(min(2.0 * db, 1.9 * room), hole + 1.0)
    bolt = BOLTS[ep.bolt.grade]
    spec = AnchorSpec(diameter=db, hole=hole, washer=washer, hef=m.thickness + t_far,
                      Fu=bolt.Fu, welded_washers=conn.shear is ShearTransfer.GROUT)
    # the block: the wall around the plate, at most one thickness beyond its edges
    margin = min(m.thickness, N)
    width = B + 2 * margin
    if math.isfinite(m.width):
        width = max(min(width, m.width), B)
    height = N + 2 * margin
    concrete = Concrete(fc=m.fc, N=height, B=width, H=m.thickness)
    mu = conn.mu if conn.shear is ShearTransfer.FRICTION else 0.0
    plate_grade = min(STEELS, key=lambda g: abs(STEELS[g].Fy - ep.Fy) + abs(STEELS[g].Fu - ep.Fu))
    return BasePlateModel(
        section=section, column_steel=_steel(beam.grade), N=N, B=B, tp=ep.thickness,
        plate_steel=_steel(plate_grade), anchors=anchors, anchor=spec, concrete=concrete,
        weld=ep.web_weld or 0.0, cjp=not (ep.web_weld or ep.flange_weld),
        contact=ContactSettings(mu=mu or 0.55), title=f"{beam.name} pernos pasantes")


def fem_loads(name: str, V: float, M: float, P: float = 0.0) -> Loads:
    """Beam end forces at the wall face in the axes of the model."""
    return Loads(P=P, Vx=-V, My=-M, name=name)


@dataclass
class FemSide:
    """FEM of one beam for one combination."""

    side: str
    """``viga 1`` or ``viga 2``."""
    combo: str
    results: Results
    model: BasePlateModel
    checks: list[CheckResult] = field(default_factory=list)
    vtu: Path | None = None


def _relabel(r: CheckResult, new_id: str, combo: str) -> CheckResult:
    return r.model_copy(update={"id": new_id, "combo": combo})


def bolt_tension(T: float, conn: ThroughBoltConnection, ed: Edition = CURRENT,
                 combo: str = "", method: Method = Method.LRFD) -> CheckResult:
    """Most loaded bolt with the FEM tension (prying included): φ Fnt Ab (J3.6)."""
    ep = conn.end_plate
    clause = f"{ed.aisc} J3.6"
    c = _calc(method, combo)
    ab = c.step("A_b", r"\pi d_b^2/4", math.pi * ep.bolt.diameter**2 / 4, Kind.AREA, clause)
    fnt = BOLTS[ep.bolt.grade].Fnt
    rn = c.step("R_n", r"F_{nt} A_b", fnt * ab, Kind.FORCE, clause, F_nt=(fnt, Kind.STRESS))
    cap = c.available(rn, ed.steel_tension, Kind.FORCE, clause, "R_n")
    return c.result("through_bolt.fem_bolt_tension", clause, T, cap, Kind.FORCE)


def fem_checks(conn: ThroughBoltConnection, res: Results, model: BasePlateModel, V: float,
               far: bool = False, ed: Edition = CURRENT, combo: str = "") -> list[CheckResult]:
    """Checks with the forces of the FEM of one beam (LRFD)."""
    beam, ep, _ = _sides(conn, far)
    label = f"{combo} · FEM" + (" · viga 2" if far else "")
    out = []
    T = max((a.tension for a in res.anchors), default=0.0)
    out.append(_relabel(bolt_tension(T, conn, ed, label), "through_bolt.fem_bolt_tension",
                        label))
    out.append(_relabel(plate_plastic_strain(res.plate_peeq_element, STRAIN_LIMIT, label),
                        "through_bolt.fem_plate_strain", label))
    if res.bearing_force > 0:
        ratio2 = front_area(conn).ratio ** 2
        out.append(_relabel(concrete_bearing(res.bearing_force, res.bearing_centroid, model.N,
                                             model.B, conn.member.fc, ratio2, ed,
                                             combo=label),
                            "through_bolt.fem_bearing", label))
    if conn.shear is ShearTransfer.FRICTION and V:
        out.append(_relabel(friction(res.bearing_force, model.N * model.B, conn.member.fc,
                                     abs(V), conn.mu, ed, label),
                            "through_bolt.fem_friction", label))
    for wall in ("flange", "web"):
        points = [w for w in res.weld if w.wall.startswith(wall)]
        if not points:
            continue
        worst = max(points, key=lambda w: math.hypot(max(w.normal, 0.0), w.shear))
        size = ep.flange_weld if wall == "flange" else ep.web_weld
        if size > 0:
            r = fillet_weld_line(worst.normal, worst.shear, size, conn.FEXX, 2, ed,
                                 combo=label)
        else:
            r = cjp_weld_line(worst.normal, worst.shear, worst.thickness, STEELS[beam.grade].Fy, ed,
                              combo=label)
        out.append(_relabel(r, f"through_bolt.fem_weld_{wall}", label))
    return out


def solve_combination(conn: ThroughBoltConnection, combo, workdir: str | Path, *,
                      ed: Edition = CURRENT, ccx: str | None = None, threads: int | None = None,
                      reuse: bool = True, cancel=None, progress=None, fast: bool = False
                      ) -> list[FemSide]:
    """Solve one combination (``through_bolt_project.Combination``) with CalculiX."""
    from openfemconex.model import MeshSettings
    from openfemconex.solve import file_stem, solve

    workdir = Path(workdir)
    sides = [(False, combo.V, combo.M, combo.P)]
    if conn.opposite is not None and (combo.V2 or combo.M2 or combo.P2):
        sides.append((True, combo.V2, combo.M2, combo.P2))
    out = []
    for far, V, M, P in sides:
        if not (V or M or P):
            continue
        model = fem_model(conn, far)
        model.validate()
        name = combo.name + (" viga 2" if far else "")
        res = solve(model, fem_loads(name, V, M, P), workdir, settings=MeshSettings(fast=fast),
                    ccx=ccx, threads=threads, reuse=reuse, cancel=cancel, progress=progress)
        side = FemSide("viga 2" if far else "viga 1", combo.name, res, model,
                       fem_checks(conn, res, model, V, far, ed, combo.name),
                       workdir / f"{file_stem(name)}.vtu")
        out.append(side)
    return out
