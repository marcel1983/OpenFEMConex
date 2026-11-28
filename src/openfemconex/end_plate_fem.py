# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX model of a moment end-plate connection.

The end plate bearing on the column flange is mapped onto the base plate model, as
for the through-bolts, and reuses its mesh, solver and result reader:

* "column" = a stub of the beam (I-shape), elastic, and "base plate" = its end plate,
  welded to it (shared nodes, as the base plate weld). The stub only brings the forces
  to the plate: the strength of the beam belongs to the frame design (and, for a
  seismic connection, to the AISC 358 checks), and an end plate is often designed for
  more than the beam's plastic moment (the probable moment at the column face);
* "block" = the column flange (``model.ColumnFlange``): elastic-plastic steel of the
  flange thickness and width, over a length of the column, held on its back face
  along the column web and along the continuity plates; frictionless contact with
  the end plate;
* "anchor rods" = the bolts: axial springs E·A/L over the grip (plate + flange),
  tension only, between a washer on the plate and the nut on the back of the flange;
  they take the shear by bearing (lateral springs). For the checks the bolts are snug
  tight, as in the strength models of the Design Guides (the pretension does not add
  to the required tension of AISC J3.6, and the force of a separated joint is the
  applied tension plus prying). With ``pretension`` the spring law starts at the
  Table J3.1 pretension (or its snug-tight fraction): the stiffness of the joint in
  service, for the moment-rotation curve;
* extension stiffeners (4ES, 8ES, 1/3 stiffened) and the stiffeners of the stiffened
  flush layouts: plates welded to the beam and to the end plate.

The web and continuity plates are taken as rigid supports of the flange, so the model
gives the local behaviour of the connection (plate, bolts, column flange); the panel
zone and the column web are checked analytically and their flexibility is added to
the moment-rotation curve separately.

Model axes (those of the base plate): z along the beam, out of the column flange; x
up the beam depth; y across. The plate centre is at x = 0 and the beam axis at x =
``ex`` (an unsymmetric plate). The beam moment M (positive with tension at the top)
is My = -M and its shear V (positive downwards) is Vx = -V; P is positive in
compression.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.moment.end_plate import (
    STIFFENED_EXTENSION,
    EndPlateLayout,
)
from openconex.connections.moment.fr_moment import MomentConnection
from openconex.core.bolting import min_pretension
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import BOLTS, STEELS
from openconex.units import Kind, from_internal, to_internal

from openfemconex.checks import CURRENT, Edition, _calc, fillet_weld_line
from openfemconex.ep_scene import bolt_rows, plate_height
from openfemconex.model import (
    E_STEEL,
    Anchor,
    AnchorSpec,
    BasePlateModel,
    ColumnFlange,
    Concrete,
    ContactSettings,
    Loads,
    MeshSettings,
    Section,
    SectionKind,
    Steel,
    Stiffener,
)
from openfemconex.results import Results

__all__ = ["STRAIN_LIMIT", "FemSide", "bolt_pretension", "fem_checks", "fem_loads",
           "fem_model", "solve_combination"]

STRAIN_LIMIT = 0.05
INCH = 25.4
STUB = 2.0
"""Length of the modelled beam stub, in beam depths (the load is applied at its end)."""
ELASTIC = 10.0
"""Strength factor that keeps the beam stub elastic."""


def _steel(grade: str) -> Steel:
    s = STEELS[grade]
    return Steel(Fy=s.Fy, Fu=s.Fu, name=grade)


def _plate_steel(Fy: float, Fu: float) -> Steel:
    grade = min(STEELS, key=lambda g: abs(STEELS[g].Fy - Fy) + abs(STEELS[g].Fu - Fu))
    return Steel(Fy=Fy, Fu=Fu, name=grade)


def bolt_pretension(mc: MomentConnection) -> float:
    """Bolt pretension T_b [N]: the given one, Table J3.1, or its snug-tight fraction
    (the values OpenConex uses for the end-plate design)."""
    ep = mc.end_plate
    if ep.pretension is not None:
        return ep.pretension
    d_in = from_internal(ep.bolt.diameter, Kind.LENGTH, "in")
    group = 150 if BOLTS[ep.bolt.grade].Fnt > to_internal(100.0, "ksi", Kind.STRESS) else 120
    try:
        full = min_pretension(d_in, group)
    except ValueError:
        full = 0.7 * BOLTS[ep.bolt.grade].Fu * math.pi * ep.bolt.diameter**2 / 4 * 0.75
    if not ep.snug_tight:
        return full
    f = 0.75 if d_in <= 5 / 8 + 1e-6 else 0.5 if d_in <= 3 / 4 + 1e-6 \
        else 0.375 if d_in <= 7 / 8 + 1e-6 else 0.25
    return f * full


def _stiffeners(mc: MomentConnection, ex: float, top: float, bottom: float
                ) -> tuple[Stiffener, ...]:
    beam, ep = mc.beam, mc.end_plate
    ts = max(ep.stiffener_thickness, beam.tw)
    out = []
    if ep.layout in STIFFENED_EXTENSION:
        # triangular plate in line with the web, 30° to the flange (DG4): from the face
        # of the flange to the plate edge, as long along the beam as h/tan 30°
        for sign, edge in ((1.0, top), (-1.0, bottom)):
            if sign < 0 and not ep.symmetric:
                continue
            h = abs(edge - ex) - beam.d / 2
            if h <= 0:
                continue
            length = h / math.tan(math.radians(30))
            out.append(Stiffener(origin=(ex + sign * beam.d / 2, 0.0), direction=(sign, 0.0),
                                 length=h, thickness=ts, height=length,
                                 end_height=min(INCH, 0.5 * length),
                                 embed=beam.tf / 2))
    if ep.layout in (EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN,
                     EndPlateLayout.FLUSH_4_STIFFENED_INSIDE):
        rows = bolt_rows(beam, ep)
        z = (rows[0] - ep.ps_o - ts / 2 if ep.layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN
             else rows[1] - ep.ps - ts / 2)
        span = (beam.bf - beam.tw) / 2
        for zz in ((z, -z) if ep.symmetric else (z,)):
            for s in (1.0, -1.0):
                out.append(Stiffener(origin=(ex + zz, s * beam.tw / 2), direction=(0.0, s),
                                     length=span, thickness=ts, height=4 * INCH,
                                     end_height=2 * INCH, embed=beam.tw / 2))
    return tuple(out)


def fem_model(mc: MomentConnection, pretension: bool = False) -> BasePlateModel:
    """Base plate model of the end plate of the beam bearing on the column flange."""
    beam, ep, col = mc.beam, mc.end_plate, mc.column
    if ep is None:
        raise ValueError("la conexión no tiene placa de extremo")
    top, bottom = plate_height(beam, ep)
    N, B = top - bottom, ep.width
    centre = (top + bottom) / 2
    ex = -centre  # the beam axis, from the plate centre
    zs = bolt_rows(beam, ep)
    anchors = tuple(Anchor(z - centre, y) for z in zs for y in (-ep.gage / 2, ep.gage / 2))
    section = Section(SectionKind.I, d=beam.d, bf=beam.bf, tf=beam.tf, tw=beam.tw,
                      name=beam.name)
    db = ep.bolt.diameter
    hole = db + (1 / 8 if db >= INCH - 1e-6 else 1 / 16) * INCH
    room = min(min(section.distance(a.x - ex, a.y) for a in anchors),
               min(N / 2 - abs(a.x) for a in anchors), min(B / 2 - abs(a.y) for a in anchors),
               ep.gage / 2)
    # heavy hex nut / head across flats ≈ 1.6 d; no larger than fits around the bolt
    washer = max(min(1.6 * db, 1.9 * room), hole + 1.0)
    bolt = BOLTS[ep.bolt.grade]
    spec = AnchorSpec(diameter=db, hole=hole, washer=washer, hef=col.tf, Fu=bolt.Fu,
                      welded_washers=True)
    if B > col.bf + 1e-6:
        raise ValueError("la placa de extremo es más ancha que el ala de la columna")
    # the flange over the plate and one flange width beyond it, above and below
    length = N + 2 * max(col.bf / 2, 4 * INCH)
    continuity = []
    if mc.continuity_plate > 0:
        t = mc.continuity_plate
        for zf in ((beam.d - beam.tf) / 2, -(beam.d - beam.tf) / 2):
            continuity.append((zf - centre, t))
    cs = _steel(col.grade)
    flange = ColumnFlange(steel=cs, web=col.tw, stiffeners=tuple(continuity),
                          pretension=bolt_pretension(mc) if pretension else 0.0)
    concrete = Concrete(fc=28.0, N=length, B=col.bf, H=col.tf)
    stiffeners = _stiffeners(mc, ex, top, bottom)
    bs = _steel(beam.grade)
    stub = Steel(Fy=ELASTIC * bs.Fy, Fu=ELASTIC * bs.Fu, name=f"{beam.grade} (elástico)")
    model = BasePlateModel(
        section=section, column_steel=stub, N=N, B=B, tp=ep.thickness,
        plate_steel=_plate_steel(ep.Fy, ep.Fu), anchors=anchors, anchor=spec,
        concrete=concrete, ex=ex, stiffeners=stiffeners,
        stiffener_steel=_plate_steel(ep.Fy, ep.Fu) if stiffeners else None,
        weld=ep.web_weld or 0.0, cjp=not (ep.web_weld or ep.flange_weld),
        stiffener_weld=ep.web_weld or 0.0, column_length=STUB * beam.d,
        # steel on steel: 0.05 mm of overclosure at 500 MPa, no friction (the bolts
        # take the shear in bearing)
        contact=ContactSettings(mu=0.0, stiffness=E_STEEL / 20.0, tension=0.5),
        title=f"{beam.name} a {col.name} placa de extremo", flange=flange)
    return model


def fem_loads(name: str, V: float, M: float, P: float = 0.0) -> Loads:
    """Beam end forces at the column face in the axes of the model."""
    return Loads(P=P, Vx=-V, My=-M, name=name)


@dataclass
class FemSide:
    """FEM of the beam for one combination."""

    side: str
    combo: str
    results: Results
    model: BasePlateModel
    checks: list[CheckResult] = field(default_factory=list)
    vtu: Path | None = None


def _relabel(r: CheckResult, new_id: str, combo: str) -> CheckResult:
    return r.model_copy(update={"id": new_id, "combo": combo})


def bolt_tension_shear(T: float, V: float, mc: MomentConnection, ed: Edition = CURRENT,
                       combo: str = "", method: Method = Method.LRFD) -> CheckResult:
    """Most loaded bolt with the FEM tension (prying included) and its
    shear: φ F'nt Ab with F'nt of J3.7."""
    ep = mc.end_plate
    clause = f"{ed.aisc} J3.6, J3.7"
    c = _calc(method, combo)
    ab = c.step("A_b", r"\pi d_b^2/4", math.pi * ep.bolt.diameter**2 / 4, Kind.AREA, clause)
    b = BOLTS[ep.bolt.grade]
    fnt, fnv = b.Fnt, ep.bolt.Fnv
    frv = c.step("f_{rv}", "V/A_b", V / ab, Kind.STRESS, clause)
    phi = ed.steel_tension.phi if method is Method.LRFD else 1.0
    omega = 1.0 if method is Method.LRFD else ed.steel_tension.omega
    f_prime = 1.3 * fnt - (fnt / (phi * fnv) if method is Method.LRFD
                           else omega * fnt / fnv) * frv
    f_prime = c.step("F'_{nt}", r"1.3F_{nt}-\frac{F_{nt}}{\phi F_{nv}}f_{rv}\le F_{nt}",
                     min(max(f_prime, 0.0), fnt), Kind.STRESS, clause,
                     F_nt=(fnt, Kind.STRESS), F_nv=(fnv, Kind.STRESS))
    rn = c.step("R_n", r"F'_{nt} A_b", f_prime * ab, Kind.FORCE, clause)
    cap = c.available(rn, ed.steel_tension, Kind.FORCE, clause, "R_n")
    return c.result("end_plate.fem_bolt_tension", clause, T, cap, Kind.FORCE)


def _strain(id_: str, strain: float, limit: float, combo: str) -> CheckResult:
    clause = "FEM criterion (EN 1993-1-5 C.8: 5 %)"
    c = _calc(Method.LRFD, combo)
    c.step(r"\varepsilon_{pl,lim}", "", limit, clause=clause)
    return c.result(id_, clause, strain, limit, Kind.DIMENSIONLESS)


def fem_checks(mc: MomentConnection, res: Results, model: BasePlateModel,
               ed: Edition = CURRENT, combo: str = "", method: Method = Method.LRFD,
               strain_limit: float = STRAIN_LIMIT) -> list[CheckResult]:
    """Checks with the forces and strains of the FEM of one combination."""
    ep = mc.end_plate
    label = f"{combo} · FEM"
    out = []
    if res.anchors:
        worst = max(res.anchors, key=lambda a: a.tension)
        V = math.hypot(worst.Vx, worst.Vy)
        out.append(bolt_tension_shear(worst.tension, V, mc, ed, label, method))
    out.append(_strain("end_plate.fem_plate_strain", res.plate_peeq_element, strain_limit,
                       label))
    out.append(_strain("end_plate.fem_flange_strain", res.flange_peeq_element, strain_limit,
                       label))
    if model.stiffeners:
        out.append(_strain("end_plate.fem_stiffener_strain", res.stiffener_peeq_element,
                           strain_limit, label))
    # Fillet welds: the flange welds with the force spread along each flange (as the
    # Design Guides design them), the web weld at its most loaded point. A CJP weld with
    # matching filler metal is as strong as the beam it joins, which is checked with
    # the beam, so it gets no FEM check here.
    for wall, size in (("flange", ep.flange_weld), ("web", ep.web_weld)):
        if size <= 0:
            continue
        points = [w for w in res.weld if w.wall.startswith(wall)]
        if not points:
            continue
        if wall == "flange":
            sides = {}
            for w in points:
                sides.setdefault(w.wall, []).append(w)
            candidates = [(sum(max(w.normal, 0.0) for w in g) / len(g),
                           sum(abs(w.shear) for w in g) / len(g)) for g in sides.values()]
        else:
            candidates = [(w.normal, w.shear) for w in points]
        normal, shear = max(candidates, key=lambda c: math.hypot(max(c[0], 0.0), c[1]))
        r = fillet_weld_line(normal, shear, size, mc.FEXX, 2, ed, method, label)
        out.append(_relabel(r, f"end_plate.fem_weld_{wall}", label))
    return out


def solve_combination(mc: MomentConnection, combo, workdir: str | Path, *,
                      ed: Edition = CURRENT, ccx: str | None = None,
                      threads: int | None = None, reuse: bool = True, cancel=None,
                      progress=None, fast: bool = False, settings: MeshSettings | None = None,
                      strain_limit: float = STRAIN_LIMIT, started=None) -> list[FemSide]:
    """Solve one combination (``end_plate_project.Combination``) with CalculiX.

    With a beam on both sides of the column the two connections are alike (the flange
    is held on the web), so one model is solved."""
    from openfemconex.solve import file_stem, solve

    workdir = Path(workdir)
    settings = settings or MeshSettings(fast=fast)
    if not (combo.V or combo.M or combo.P):
        return []
    model = fem_model(mc)
    model.validate()
    if started is not None:
        started(combo.name, workdir / f"{file_stem(combo.name)}.sta")
    res = solve(model, fem_loads(combo.name, combo.V, combo.M, combo.P), workdir,
                settings=settings, ccx=ccx, threads=threads, reuse=reuse, cancel=cancel,
                progress=progress)
    return [FemSide("viga", combo.name, res, model,
                    fem_checks(mc, res, model, ed, combo.name, combo.method, strain_limit),
                    workdir / f"{file_stem(combo.name)}.vtu")]
