# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX model of a through-bolt connection.

The end plate of each beam bearing on the face of the wall or column is the same
problem as a base plate on its concrete block, so this module maps the connection
onto the base plate model and reuses its mesh, solver and result reader:

* "column" = the beam (I-shape) and "base plate" = its end plate;
* "concrete block" = the wall or column, as deep as its thickness h, held at its ends
  above and below;
* the far face: the back plate as a flexible plate in contact with it
  (``model.FarPlate``), or the opposite beam and its end plate mirrored across the wall
  (``BasePlateModel.opposite``), loaded together with beam 1;
* "anchor rods" = the through-bolts: tension-only springs E·A/L with L = h + both plate
  thicknesses (unbonded in the sleeves) between the nuts on both plates;
* shear by friction in the contact with the wall (``ShearTransfer.FRICTION``) or by the
  bolts bearing on the grout (lateral springs, ``ShearTransfer.GROUT``).

Model axes (those of the base plate): z along the beam, out of the wall; x up the beam
depth; y across. The beam moment M (positive with tension at the top) is My = -M and
its shear V (positive downwards) is Vx = -V.

With ``flexible=False`` the far face is fixed instead (rigid back plate) and, with an
opposite beam, each side is solved on its own, with its own loads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
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
    FarPlate,
    Loads,
    Section,
    SectionKind,
    Steel,
)
from openfemconex.results import Results
from openfemconex.through_bolt import (
    BOTTOM,
    FAR,
    ShearTransfer,
    ThroughBoltConnection,
    _area,
    _plate_extension,
    back_area,
    bolt_rows,
    front_area,
)

__all__ = ["FemSide", "back_plate_checks", "fem_checks", "fem_loads", "fem_model",
           "solve_combination"]

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


def fem_model(conn: ThroughBoltConnection, far: bool = False,
              flexible: bool = True) -> BasePlateModel:
    """Base plate model of the end plate of beam 1 (or of the opposite beam).

    With ``flexible`` the far face is part of the model: the back plate, or the opposite
    beam with its end plate (``BasePlateModel.opposite``, both beams loaded together),
    bears on the far face of the wall and the bolts join the two plates; the wall is
    then held at its ends above and below. Otherwise the far face is fixed and the
    bolts are anchored there (rigid back plate; each beam on its own).
    """
    if flexible and not far and conn.opposite is not None:
        near = fem_model(conn, flexible=False)
        other = fem_model(conn, far=True, flexible=False)
        c = near.concrete
        concrete = replace(c, N=max(c.N, other.concrete.N), B=max(c.B, other.concrete.B))
        return replace(near, concrete=concrete,
                       opposite=replace(other, concrete=concrete, anchors=near.anchors),
                       title=f"{near.title} / {other.section.name}")
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
                      Fu=bolt.Fu, welded_washers=conn.shear is ShearTransfer.GROUT,
                      friction_only=conn.shear is ShearTransfer.FRICTION)
    # the block: the wall around the plate, at most one thickness beyond its edges
    margin = min(m.thickness, N)
    width = B + 2 * margin
    if math.isfinite(m.width):
        width = max(min(width, m.width), B)
    far_plate = None
    if flexible and not far and conn.opposite is None:
        bp = conn.back_plate
        far_plate = FarPlate(width=bp.width, height=bp.height, thickness=bp.thickness,
                             steel=_steel(bp.grade))
        if bp.width < ep.gage + washer or bp.height / 2 < max(abs(a.x) for a in anchors) \
                + washer / 2:
            raise ValueError("la placa posterior no cubre las tuercas de los pernos")
        width = max(width, bp.width)
    height = max(N, far_plate.height if far_plate else 0.0) + 2 * margin
    concrete = Concrete(fc=m.fc, N=height, B=width, H=m.thickness)
    mu = conn.mu if conn.shear is ShearTransfer.FRICTION else 0.0
    plate_grade = min(STEELS, key=lambda g: abs(STEELS[g].Fy - ep.Fy) + abs(STEELS[g].Fu - ep.Fu))
    return BasePlateModel(
        section=section, column_steel=_steel(beam.grade), N=N, B=B, tp=ep.thickness,
        plate_steel=_steel(plate_grade), anchors=anchors, anchor=spec, concrete=concrete,
        weld=ep.web_weld or 0.0, cjp=not (ep.web_weld or ep.flange_weld),
        contact=ContactSettings(mu=mu or 0.55), title=f"{beam.name} pernos pasantes",
        far=far_plate)


def fem_loads(name: str, V: float, M: float, P: float = 0.0,
              opposite: tuple[float, float, float] | None = None) -> Loads:
    """Beam end forces at the wall face in the axes of the model; ``opposite`` = (V2,
    M2, P2) of the opposite beam, with the same signs in its own axes."""
    far = None
    if opposite is not None:
        V2, M2, P2 = opposite
        far = Loads(P=P2, Vx=-V2, My=-M2, name=name)
    return Loads(P=P, Vx=-V, My=-M, name=name, opposite=far)


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
    """Checks with the forces of the FEM of one beam (LRFD).

    With ``far`` and a model of both faces (``model.opposite``) the checks of the
    opposite beam are read from the far face results of the same solution.
    """
    beam, ep, _ = _sides(conn, far)
    label = f"{combo} · FEM" + (" · viga 2" if far else "")
    merged = far and model.opposite is not None
    out = []
    if not merged:
        T = max((a.tension for a in res.anchors), default=0.0)
        out.append(_relabel(bolt_tension(T, conn, ed, label),
                            "through_bolt.fem_bolt_tension", label))
    if merged:
        peeq, C, centroid, weld = (res.far_peeq_element, res.far_bearing_force,
                                   res.far_bearing_centroid, res.far_weld)
        m = model.opposite
        ratio2 = _area(conn, FAR, BOTTOM, True).ratio ** 2
    else:
        peeq, C, centroid, weld = (res.plate_peeq_element, res.bearing_force,
                                   res.bearing_centroid, res.weld)
        m = model
        ratio2 = (front_area(conn) if not far else _area(conn, FAR, BOTTOM, True)).ratio ** 2
    out.append(_relabel(plate_plastic_strain(peeq, STRAIN_LIMIT, label),
                        "through_bolt.fem_plate_strain", label))
    if C > 0:
        out.append(_relabel(concrete_bearing(C, centroid, m.N, m.B, conn.member.fc, ratio2,
                                             ed, combo=label),
                            "through_bolt.fem_bearing", label))
    if conn.shear is ShearTransfer.FRICTION and V:
        out.append(_relabel(friction(C, m.N * m.B, conn.member.fc, abs(V), conn.mu, ed,
                                     label),
                            "through_bolt.fem_friction", label))
    for wall in ("flange", "web"):
        points = [w for w in weld if w.wall.startswith(wall)]
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
    if model.far is not None and not far:
        out += back_plate_checks(conn, res, model, ed, combo)
    return out


def back_plate_checks(conn: ThroughBoltConnection, res: Results, model: BasePlateModel,
                      ed: Edition = CURRENT, combo: str = "") -> list[CheckResult]:
    """The flexible back plate: its plastic strain and its bearing on the far face."""
    label = f"{combo} · FEM · placa posterior"
    out = [_relabel(plate_plastic_strain(res.far_peeq_element, STRAIN_LIMIT, label),
                    "through_bolt.fem_back_plate_strain", label)]
    if res.far_bearing_force > 0:
        fp = model.far
        out.append(_relabel(concrete_bearing(res.far_bearing_force, res.far_bearing_centroid,
                                             fp.height, fp.width, conn.member.fc,
                                             back_area(conn).ratio ** 2, ed, combo=label),
                            "through_bolt.fem_back_bearing", label))
    return out


def solve_combination(conn: ThroughBoltConnection, combo, workdir: str | Path, *,
                      ed: Edition = CURRENT, ccx: str | None = None, threads: int | None = None,
                      reuse: bool = True, cancel=None, progress=None, fast: bool = False,
                      flexible: bool = True) -> list[FemSide]:
    """Solve one combination (``through_bolt_project.Combination``) with CalculiX.

    With ``flexible`` (default) the far face is modelled: the back plate, or the
    opposite beam loaded at the same time (one model, one solution, two sides).
    Otherwise each beam is solved on its own against a rigid far face."""
    from openfemconex.model import MeshSettings
    from openfemconex.solve import file_stem, solve

    workdir = Path(workdir)
    if conn.opposite is not None and flexible:
        # both beams in one model, loaded together
        model = fem_model(conn)
        model.validate()
        loads = fem_loads(combo.name, combo.V, combo.M, combo.P,
                          opposite=(combo.V2, combo.M2, combo.P2))
        res = solve(model, loads, workdir, settings=MeshSettings(fast=fast), ccx=ccx,
                    threads=threads, reuse=reuse, cancel=cancel, progress=progress)
        vtu = workdir / f"{file_stem(combo.name)}.vtu"
        return [FemSide("viga 1", combo.name, res, model,
                        fem_checks(conn, res, model, combo.V, False, ed, combo.name), vtu),
                FemSide("viga 2", combo.name, res, model,
                        fem_checks(conn, res, model, combo.V2, True, ed, combo.name), vtu)]
    sides = [(False, combo.V, combo.M, combo.P)]
    if conn.opposite is not None and (combo.V2 or combo.M2 or combo.P2):
        sides.append((True, combo.V2, combo.M2, combo.P2))
    out = []
    for far, V, M, P in sides:
        if not (V or M or P):
            continue
        model = fem_model(conn, far, flexible=flexible)
        model.validate()
        name = combo.name + (" viga 2" if far else "")
        res = solve(model, fem_loads(name, V, M, P), workdir, settings=MeshSettings(fast=fast),
                    ccx=ccx, threads=threads, reuse=reuse, cancel=cancel, progress=progress)
        side = FemSide("viga 2" if far else "viga 1", combo.name, res, model,
                       fem_checks(conn, res, model, V, far, ed, combo.name),
                       workdir / f"{file_stem(name)}.vtu")
        out.append(side)
    return out
