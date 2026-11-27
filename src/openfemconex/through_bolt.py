# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Beam end plates bolted through a new concrete wall or column (analytic checks).

The end plate of a beam is bolted with through-bolts that cross the wall or
column in sleeves (no bond to the concrete). On the far face the bolts are
anchored on a continuous back plate, or on the end plate of a second beam
framing from the other side (opposite connection, same bolts). The help topic
"Pernos pasantes en concreto" explains the load path.

Force model. For each beam, with lever arm z = d - tf between the flange centres,
end moment ``M`` (positive with tension at the top), shear ``V`` (positive
downwards) and axial force ``P`` (positive in compression):

* its tension flange pulls the bolts of that group (top or bottom) with
  T = |M|/z - P/2, and its compression flange bears on its face with C = T + P;
* the bolts of a group carry the larger tension of the two sides, Tb = max(T1, T2):
  the plate of the side that pulls less bears on its face with Tb - Ti;
* each face therefore has a bearing zone at the top and at the bottom; what is
  not balanced across the thickness, ΔF, is carried through the member by a
  diagonal strut and the vertical bars (strut-and-tie), and bends the member
  with ΔM = (M1 - M2) + (V1 - V2) h/2;
* the shear goes by friction under the compression on each face
  (``ShearTransfer.FRICTION``), or through the bolts bearing on grout in the
  sleeves (``ShearTransfer.GROUT``).

The steel side of each beam (end plate yielding, bolt rupture, welds, bolt shear
and bearing at the holes) reuses the end-plate checks of AISC Design Guides 16
and 4 from OpenConex. This module adds, for LRFD (ACI 318 strength design):

* bearing under each zone (§22.8), on an area limited by the plate bending;
* punching shear of the unbalanced force of each group (§22.6);
* shear by friction, or bolt tension, shear and bending with grout (AISC J3.7)
  and bolt bearing on the grout (§22.8);
* bursting behind each zone (anchorage zone of §25.9 used by analogy);
* strut-and-tie model of the unbalanced couple (Chapter 23): angle, strut,
  nodes, vertical bars of each face as ties and their development;
* flexure, with the axial force, of the member next to the connection (§22.4).

Units: N, mm, MPa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from openconex.connections.moment.end_plate import EndPlate, end_plate_checks
from openconex.connections.moment.fr_moment import FlangeDetail, MomentConnection
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import STEELS
from openconex.core.model import IShape
from openconex.kernel.anchors import straight_bar_ld
from openconex.kernel.design import Calc, Resistance
from openconex.units import Kind, from_internal, to_internal

from openfemconex.checks import CURRENT, Edition, friction, rod_combined
from openfemconex.pedestal import section_capacity

__all__ = [
    "BackPlate", "BeamLoad", "ConcreteMember", "Forces", "OppositeBeam", "Rebar",
    "ShearTransfer", "Support", "ThroughBoltConnection", "Zone", "bearing", "bolt_rows",
    "bursting", "check_through_bolt", "forces", "member_flexure", "punching",
    "strut_and_tie", "zones",
]

BEARING = Resistance(0.65, math.nan)
SHEAR = Resistance(0.75, math.nan)
STM = Resistance(0.75, math.nan)

NEAR, FAR = "front", "back"
TOP, BOTTOM = "top", "bottom"


class Support(StrEnum):
    WALL = "wall"
    COLUMN = "column"


class ShearTransfer(StrEnum):
    FRICTION = "friction"
    """Friction under the compression of each end plate; the bolts carry no shear."""
    GROUT = "grout"
    """Bolts bearing on grout in the sleeves, next to each loaded face."""


@dataclass(frozen=True)
class Rebar:
    """One layer of bars at each face of the member, in one direction."""

    diameter: float
    spacing: float
    fy: float = 420.0

    @property
    def bar_area(self) -> float:
        return math.pi * self.diameter**2 / 4


@dataclass(frozen=True)
class ConcreteMember:
    """New wall or column crossed by the bolts.

    ``thickness`` is measured along the bolts. ``width`` is the face width of a
    column (horizontal, across the beam); a wall has no lateral edges. ``top`` and
    ``bottom`` are the distances from the beam axis to the ends of the member
    (``inf``: it continues). ``axial`` is the compression of a column at the
    connection (positive), from the global analysis.
    """

    kind: Support
    thickness: float
    fc: float
    cover: float
    vertical: Rebar
    horizontal: Rebar
    width: float = math.inf
    top: float = math.inf
    bottom: float = math.inf
    axial: float = 0.0
    share_above: float = 0.5
    """Part of the moment carried by the member above the connection."""
    cross_ties: bool = False
    """Ties through the thickness crossing the strut (ACI 318 §23.5): βs = 0.75."""
    lambda_: float = 1.0

    @property
    def bar_line(self) -> float:
        """Distance from each face to the centre of the vertical bars."""
        return self.cover + self.horizontal.diameter + self.vertical.diameter / 2

    @property
    def depth(self) -> float:
        """Effective depth to the vertical bars of the far face."""
        return self.thickness - self.bar_line


@dataclass(frozen=True)
class BackPlate:
    """Continuous plate on the far face, centred on the beam axis."""

    width: float
    height: float
    thickness: float
    grade: str = "ASTM A36"
    washer: float = 0.0
    """Washer or nut bearing diameter; 0: twice the bolt diameter."""

    @property
    def Fy(self) -> float:
        return STEELS[self.grade].Fy

    @property
    def Fu(self) -> float:
        return STEELS[self.grade].Fu


@dataclass(frozen=True)
class OppositeBeam:
    """Second beam on the far face, with its end plate on the same bolts.

    Both beam axes are at the same height and both plates have the same bolt
    rows and gage (the plate thickness and the beam may differ)."""

    beam: IShape
    end_plate: EndPlate


@dataclass(frozen=True)
class ThroughBoltConnection:
    beam: IShape
    end_plate: EndPlate
    back_plate: BackPlate | None
    """Plate on the far face; ``None`` when ``opposite`` is given."""
    member: ConcreteMember
    shear: ShearTransfer = ShearTransfer.FRICTION
    mu: float = 0.55
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)
    opposite: OppositeBeam | None = None
    grout_length: float = 0.0
    """Grouted length of each sleeve next to a loaded face; 0: four bolt diameters."""
    grout_fc: float = 0.0
    """Grout strength; 0: the f'c of the member."""
    gap: float = 0.0
    """Gap between a plate and the grout (shim, leveling grout, hole clearance): the bolt
    bends over it with the grout scheme."""

    def __post_init__(self) -> None:
        if self.opposite is None and self.back_plate is None:
            raise ValueError("se necesita la placa posterior o la viga opuesta")
        if self.opposite is not None:
            o = self.opposite
            same = (len(bolt_rows(self.beam, self.end_plate)) == len(bolt_rows(o.beam,
                                                                             o.end_plate))
                    and all(abs(a - b) < 1.0 for a, b in zip(
                        bolt_rows(self.beam, self.end_plate), bolt_rows(o.beam, o.end_plate),
                        strict=True))
                    and abs(self.end_plate.gage - o.end_plate.gage) < 1.0
                    and abs(self.end_plate.bolt.diameter - o.end_plate.bolt.diameter) < 0.1)
            if not same:
                raise ValueError("las dos placas deben tener los mismos pernos: filas, gramil "
                                 "y diámetro")

    @property
    def lever(self) -> float:
        return self.beam.d - self.beam.tf

    @property
    def bolts(self) -> int:
        """All the bolts (two per row, rows mirrored at both flanges)."""
        return 4 * len(bolt_rows(self.beam, self.end_plate))

    def moment_connection(self, far: bool = False) -> MomentConnection:
        """OpenConex end-plate connection of one beam; the plate on the other face stands
        for the column flange on which the bolts bear."""
        if far:
            o = _required_opposite(self)
            beam, ep = o.beam, o.end_plate
            t, w, grade = self.end_plate.thickness, self.end_plate.width, _grade(self.end_plate)
        else:
            beam, ep = self.beam, self.end_plate
            if self.opposite is not None:
                o = self.opposite.end_plate
                t, w, grade = o.thickness, o.width, _grade(o)
            else:
                bp = self.back_plate
                t, w, grade = bp.thickness, bp.width, bp.grade
        dummy = IShape(name="far plate", d=10 * t + 1, bf=w, tf=t, tw=t / 2, grade=grade)
        return MomentConnection(detail=FlangeDetail.END_PLATE, beam=beam, beam_Sx=0.0,
                                column=dummy, end_plate=ep, FEXX=self.FEXX)


def _required_opposite(conn: ThroughBoltConnection) -> OppositeBeam:
    if conn.opposite is None:
        raise ValueError("no hay viga opuesta")
    return conn.opposite


def _grade(ep: EndPlate) -> str:
    """Catalog steel whose Fu is closest to the plate's (bearing of the bolts)."""
    return min(STEELS, key=lambda g: abs(STEELS[g].Fu - ep.Fu) + abs(STEELS[g].Fy - ep.Fy))


# ------------------------------------------------------------------------ geometry
def bolt_rows(beam: IShape, ep: EndPlate) -> list[float]:
    """Heights of the bolt rows at the top flange, from the beam axis (upwards); the
    rows at the bottom flange are the same, mirrored."""
    top = beam.d / 2
    rows = [top - beam.tf - ep.pf - k * ep.pb for k in range(ep.inside_rows)]
    if ep.outside_rows:
        rows.append(top + ep.pf_o)
    if ep.outside_rows == 2:
        rows.append(top + ep.pf_o + ep.pb)
    return sorted(rows, reverse=True)


def _plate_extension(beam: IShape, ep: EndPlate) -> float:
    """End plate beyond the outer face of the flange."""
    if ep.flush:
        return ep.pext
    return ep.pext or ep.pf_o + 1.5 * ep.bolt.diameter


@dataclass(frozen=True)
class BeamLoad:
    V: float = 0.0
    """Shear, positive downwards."""
    M: float = 0.0
    """End moment, positive with tension at the top flange."""
    P: float = 0.0
    """Axial force, positive in compression."""


@dataclass(frozen=True)
class Forces:
    """Flange forces of one beam: T pulls the bolts of the tension flange, C bears on
    the face at the compression flange."""

    T: float
    C: float
    V: float
    M: float
    top_tension: bool = True


def _beam_forces(beam: IShape, load: BeamLoad) -> Forces:
    z = beam.d - beam.tf
    T = max(abs(load.M) / z - load.P / 2, 0.0)
    C = max(T + load.P, 0.0)
    return Forces(T, C, abs(load.V), abs(load.M), load.M >= 0)


def forces(conn: ThroughBoltConnection, V: float, M: float, P: float = 0.0) -> Forces:
    """Flange forces of the near beam."""
    return _beam_forces(conn.beam, BeamLoad(V, M, P))


# ------------------------------------------------------------------------ bearing areas
def _spread(member: ConcreteMember, a: float, b: float, z0: float, z1: float) -> float:
    """√(A2/A1) ≤ 2 for a loaded area a (horizontal) × b (vertical, from z0 to z1):
    the frustum of slope 1:2 through the thickness, cut by the member edges."""
    e = 2 * member.thickness
    e = min(e, (member.width - a) / 2, member.top - z1, member.bottom + z0)
    e = max(e, 0.0)
    return min(math.sqrt((a + 2 * e) * (b + 2 * e) / (a * b)), 2.0)


@dataclass(frozen=True)
class BearingArea:
    width: float
    height: float
    z0: float
    z1: float
    cantilever: float
    ratio: float
    """√(A2/A1)."""

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def centre(self) -> float:
        return (self.z0 + self.z1) / 2


def _bearing_area(member: ConcreteMember, tp: float, Fy: float, core_w: float,
                  core_z0: float, core_z1: float, max_w: float, lo: float,
                  hi: float) -> BearingArea:
    """Area that a plate of thickness ``tp`` can load: the core (flange or washers)
    plus a cantilever l on each side, with φ Fy tp²/4 = fp l²/2 at the bearing
    strength fp, limited by the plate edges (width ``max_w``, heights ``lo``–``hi``)."""
    ratio = 1.0
    for _ in range(30):
        fp = BEARING.phi * 0.85 * member.fc * ratio
        lc = tp * math.sqrt(0.9 * Fy / (2 * fp))
        w = min(core_w + 2 * lc, max_w)
        z0, z1 = max(core_z0 - lc, lo), min(core_z1 + lc, hi)
        new = _spread(member, w, z1 - z0, z0, z1)
        if abs(new - ratio) < 1e-9:
            break
        ratio = new
    return BearingArea(w, z1 - z0, z0, z1, lc, ratio)


@dataclass(frozen=True)
class _Plate:
    thickness: float
    Fy: float
    width: float
    lo: float
    hi: float
    beam: IShape | None


def _plate(conn: ThroughBoltConnection, face: str) -> _Plate:
    if face == NEAR or conn.opposite is not None:
        beam, ep = (conn.beam, conn.end_plate) if face == NEAR else (conn.opposite.beam,
                                                                     conn.opposite.end_plate)
        h = beam.d / 2 + _plate_extension(beam, ep)
        return _Plate(ep.thickness, ep.Fy, ep.width, -h, h, beam)
    bp = conn.back_plate
    return _Plate(bp.thickness, bp.Fy, bp.width, -bp.height / 2, bp.height / 2, None)


def _area(conn: ThroughBoltConnection, face: str, group: str, flange: bool) -> BearingArea:
    """Bearing area of a plate at the top or bottom group, around the compression
    flange (``flange``) or around the washers of the bolt rows."""
    p = _plate(conn, face)
    sign = 1 if group == TOP else -1
    if flange and p.beam is not None:
        z0, z1 = sorted((sign * p.beam.d / 2, sign * (p.beam.d / 2 - p.beam.tf)))
        core_w = p.beam.bf
    else:
        rows = [sign * z for z in bolt_rows(conn.beam, conn.end_plate)]
        dw = (conn.back_plate.washer if conn.back_plate and face == FAR else 0.0) \
            or 2 * conn.end_plate.bolt.diameter
        z0, z1 = min(rows) - dw / 2, max(rows) + dw / 2
        core_w = conn.end_plate.gage + dw
    return _bearing_area(conn.member, p.thickness, p.Fy, core_w, z0, z1, p.width, p.lo, p.hi)


def front_area(conn: ThroughBoltConnection) -> BearingArea:
    """Bearing area of the near end plate at a bottom compression flange."""
    return _area(conn, NEAR, BOTTOM, True)


def back_area(conn: ThroughBoltConnection) -> BearingArea:
    """Bearing area of the far plate around the top bolts."""
    return _area(conn, FAR, TOP, False)


@dataclass(frozen=True)
class Zone:
    face: str
    group: str
    force: float
    area: BearingArea


def zones(conn: ThroughBoltConnection, near: BeamLoad,
          far: BeamLoad | None = None) -> tuple[list[Zone], dict[str, float]]:
    """Bearing zones on both faces and the bolt tension of each group (top, bottom)."""
    sides = {NEAR: _beam_forces(conn.beam, near)}
    if conn.opposite is not None:
        sides[FAR] = _beam_forces(conn.opposite.beam, far or BeamLoad())

    def pull(face: str, group: str) -> float:
        f = sides.get(face)
        return f.T if f and (group == TOP) == f.top_tension else 0.0

    def push(face: str, group: str) -> float:
        f = sides.get(face)
        return f.C if f and (group == TOP) != f.top_tension else 0.0

    bolts = {g: max(pull(NEAR, g), pull(FAR, g)) for g in (TOP, BOTTOM)}
    out = []
    for face in (NEAR, FAR):
        for g in (TOP, BOTTOM):
            c = push(face, g)
            force = bolts[g] - pull(face, g) + c
            out.append(Zone(face, g, force, _area(conn, face, g, c > 0)))
    return out, bolts


# ------------------------------------------------------------------------ concrete checks
def bearing(force: float, area: BearingArea, fc: float, check_id: str, where: str,
            ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """F ≤ φ 0.85 f'c A1 √(A2/A1), A1 limited by the plate bending."""
    clause = f"{ed.aci} §22.8.3; {ed.guide} (cantilever of the plate)"
    c = Calc(Method.LRFD, combo)
    c.step("l", r"t_p\sqrt{\frac{0.9F_y}{2f_p}}", area.cantilever, Kind.LENGTH, clause)
    a1 = c.step("A_1", f"b h ({where})", area.area, Kind.AREA, clause,
                b=(area.width, Kind.LENGTH), h=(area.height, Kind.LENGTH))
    r = c.step(r"\sqrt{A_2/A_1}", r"\le 2", area.ratio, clause=clause)
    rn = c.step("B_n", r"0.85 f'_c A_1 \sqrt{A_2/A_1}", 0.85 * fc * a1 * r, Kind.FORCE, clause)
    cap = c.available(rn, BEARING, Kind.FORCE, clause, "B_n")
    return c.result(check_id, clause, force, cap, Kind.FORCE)


def punching(force: float, area: BearingArea, member: ConcreteMember,
             ed: Edition = CURRENT, combo: str = "",
             check_id: str = "through_bolt.punching") -> CheckResult:
    """Two-way shear of the member around a bearing zone, through the whole thickness,
    under the force not balanced by the opposite face."""
    clause = f"{ed.aci} §22.6"
    c = Calc(Method.LRFD, combo)
    d = c.step("d", "h - c_c - d_{bh} - d_{bv}/2", member.depth, Kind.LENGTH, clause)
    half = (area.width + d) / 2
    z0, z1 = area.z0 - d / 2, area.z1 + d / 2
    sides = 0
    b0 = 0.0
    horizontal = min(area.width + d, member.width)
    if z1 <= member.top:
        b0, sides = b0 + horizontal, sides + 1
    if -z0 <= member.bottom:
        b0, sides = b0 + horizontal, sides + 1
    vertical = min(z1, member.top) - max(z0, -member.bottom)
    if half <= member.width / 2:
        b0, sides = b0 + 2 * vertical, sides + 2
    b0 = c.step("b_0", r"\text{perimeter at } d/2 \text{ inside the member}", b0, Kind.LENGTH,
                clause)
    alpha = {4: 40, 3: 30}.get(sides, 20)
    c.step(r"\alpha_s", "", alpha, clause=clause)
    beta = max(area.width, area.height) / min(area.width, area.height)
    d_in = from_internal(d, Kind.LENGTH, "in")
    lam_s = 1.0
    if ed.key == "current":
        lam_s = c.step(r"\lambda_s", r"\sqrt{2/(1 + d/10)} \le 1",
                       min(math.sqrt(2 / (1 + d_in / 10)), 1.0), clause=clause)
    root = math.sqrt(min(from_internal(member.fc, Kind.STRESS, "psi"), 10_000.0))
    k = min(4.0, 2 + 4 / beta, 2 + alpha * d / max(b0, 1e-9))
    vc = c.step("v_c", r"\min(4, 2 + 4/\beta, 2 + \alpha_s d/b_0)\lambda_s\lambda\sqrt{f'_c}",
                to_internal(k * lam_s * member.lambda_ * root, "psi", Kind.STRESS),
                Kind.STRESS, clause)
    rn = c.step("V_c", "v_c b_0 d", vc * b0 * d, Kind.FORCE, clause)
    cap = c.available(rn, SHEAR, Kind.FORCE, clause, "V_c")
    return c.result(check_id, clause, force, cap, Kind.FORCE)


def bursting(force: float, area: BearingArea, member: ConcreteMember, check_id: str,
             ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """Bursting behind a plate, as in a post-tensioning anchorage zone (by analogy):
    T_burst = 0.25 F (1 - a/H) in each direction, with the load spread over
    H = a + h within the member, against the face bars of both faces within H."""
    clause = f"{ed.aci} §25.9.4.4 (analogy); Chapter 23"
    c = Calc(Method.LRFD, combo)
    worst = (-1.0, 0.0, 0.0)
    h = member.thickness
    cases = (("v", area.height, min(area.height + h, member.top + member.bottom),
              member.vertical), ("h", area.width, min(area.width + h, member.width),
                                 member.horizontal))
    for name, a, H, bars in cases:
        tb = c.step(rf"T_{{burst,{name}}}", r"0.25 F (1 - a/H)",
                    0.25 * force * max(1 - a / H, 0), Kind.FORCE, clause,
                    a=(a, Kind.LENGTH), H=(H, Kind.LENGTH))
        n = 2 * max(math.floor(H / bars.spacing), 1)
        cap = c.step(rf"\phi A_s f_y ({name})", r"0.75 n A_b f_y",
                     STM.phi * n * bars.bar_area * bars.fy, Kind.FORCE, clause,
                     n=(n, Kind.DIMENSIONLESS))
        ratio = tb / cap if cap else math.inf
        if ratio > worst[0]:
            worst = (ratio, tb, cap)
    return c.result(check_id, clause, worst[1], worst[2], Kind.FORCE)


# ------------------------------------------------------------------------ strut and tie
def _clause(ed: Edition, current: str, old: str) -> str:
    return f"{ed.aci} {current if ed.key == 'current' else old}"


def _confinement(c: Calc, ratio: float, ed: Edition, clause: str) -> float:
    """βc = √(A2/A1) ≤ 2 at a bearing face (ACI 318-19 §23.4.4); 1.0 in ACI 318-08."""
    if ed.key != "current":
        return 1.0
    return c.step(r"\beta_c", r"\sqrt{A_2/A_1} \le 2", ratio, clause=clause)


@dataclass(frozen=True)
class _Couple:
    force: float
    """Unbalanced force ΔF that crosses the thickness."""
    top: Zone
    """Pushing zone at the top (start of the strut)."""
    bottom: Zone
    """Pushing zone at the bottom, on the other face."""


def _couple(zs: list[Zone]) -> _Couple | None:
    z = {(q.face, q.group): q for q in zs}
    net = z[NEAR, TOP].force - z[FAR, TOP].force
    scale = max(q.force for q in zs)
    if scale <= 0 or abs(net) < 1e-6 * scale:
        return None
    top_face, bottom_face = (NEAR, FAR) if net > 0 else (FAR, NEAR)
    return _Couple(abs(net), z[top_face, TOP], z[bottom_face, BOTTOM])


def strut_and_tie(couple: _Couple, member: ConcreteMember, ed: Edition = CURRENT,
                  combo: str = "") -> list[CheckResult]:
    """Unbalanced couple inside the member: diagonal strut from the pushing zone at the
    top of one face to the one at the bottom of the other face, vertical bars of each
    face as ties, and their development past the nodes."""
    m = member
    a, b = couple.top.area, couple.bottom.area
    out: list[CheckResult] = []
    jx = m.thickness - 2 * m.bar_line
    jz = a.centre - b.centre
    theta = math.atan2(jz, jx)
    T = couple.force
    clause = _clause(ed, "§23.2", "Appendix A")
    c = Calc(Method.LRFD, combo)
    c.step(r"\Delta F", r"|F_{front,top} - F_{back,top}|", T, Kind.FORCE, clause)
    c.step("j_x", "h - 2 c_b", jx, Kind.LENGTH, clause)
    c.step("j_z", "z_{top} - z_{bottom}", jz, Kind.LENGTH, clause)
    angle = c.step(r"\theta", r"\arctan(j_z / j_x)", math.degrees(theta), clause=clause)
    out.append(c.result("through_bolt.stm_angle", f"{clause} (25° ≤ angle to the tie)",
                        25.0, 90.0 - angle, Kind.DIMENSIONLESS))
    # strut
    clause = _clause(ed, "§23.4", "A.3")
    c = Calc(Method.LRFD, combo)
    fs = c.step("F_s", r"\Delta F / \cos\theta", T / math.cos(theta), Kind.FORCE, clause)
    wt = 2 * m.bar_line
    lb = min(a.height, b.height)
    ws = c.step("w_s", r"l_b \cos\theta + w_t \sin\theta", lb * math.cos(theta)
                + wt * math.sin(theta), Kind.LENGTH, clause, l_b=(lb, Kind.LENGTH))
    bs = min(a.width, b.width)
    beta_s = 0.75 if m.cross_ties else (0.4 if ed.key == "current" else 0.6)
    c.step(r"\beta_s", "", beta_s, clause=clause)
    beta_c = _confinement(c, min(a.ratio, b.ratio), ed, clause)
    fce = c.step("f_{ce}", r"0.85 \beta_c \beta_s f'_c", 0.85 * beta_c * beta_s * m.fc,
                 Kind.STRESS, clause)
    rn = c.step("F_{ns}", "f_{ce} w_s b_s", fce * ws * bs, Kind.FORCE, clause,
                b_s=(bs, Kind.LENGTH))
    cap = c.available(rn, STM, Kind.FORCE, clause, "F_{ns}")
    out.append(c.result("through_bolt.stm_strut", clause, fs, cap, Kind.FORCE))
    # nodes (C-C-T): the whole bearing force of each pushing zone
    clause = _clause(ed, "§23.9", "A.5")
    for key, zone in (("top", couple.top), ("bottom", couple.bottom)):
        c = Calc(Method.LRFD, combo)
        beta_c = _confinement(c, zone.area.ratio, ed, clause)
        fce = c.step("f_{ce}", r"0.85 \beta_c \beta_n f'_c", 0.85 * beta_c * 0.8 * m.fc,
                     Kind.STRESS, clause)
        rn = c.step("F_{nn}", "f_{ce} A_{nz}", fce * zone.area.area, Kind.FORCE, clause)
        cap = c.available(rn, STM, Kind.FORCE, clause, "F_{nn}")
        out.append(c.result(f"through_bolt.stm_node_{key}", clause, zone.force, cap,
                            Kind.FORCE))
    # ties: vertical bars of each face within b_eff
    clause = _clause(ed, "§23.7", "A.4")
    c = Calc(Method.LRFD, combo)
    ft = c.step("F_t", r"\Delta F \tan\theta", T * math.tan(theta), Kind.FORCE, clause)
    beff = c.step("b_{eff}", r"\min(b_p + 2h,\ b_c)", min(max(a.width, b.width)
                  + 2 * m.thickness, m.width), Kind.LENGTH, clause)
    n = max(math.floor(beff / m.vertical.spacing), 1)
    rn = c.step("F_{nt}", "n A_b f_y", n * m.vertical.bar_area * m.vertical.fy, Kind.FORCE,
                clause, n=(n, Kind.DIMENSIONLESS))
    cap = c.available(rn, STM, Kind.FORCE, clause, "F_{nt}")
    out.append(c.result("through_bolt.stm_tie", clause, ft, cap, Kind.FORCE))
    # development of the ties past the nodes: the bars of the top node continue above
    # it, those of the bottom node below it
    clause = _clause(ed, "§23.8.3; §25.4.2", "A.4.3; §12.2")
    c = Calc(Method.LRFD, combo)
    v = m.vertical
    cb = min(m.cover + m.horizontal.diameter + v.diameter / 2, v.spacing / 2)
    ld = c.step("l_d", r"\text{straight bar}", straight_bar_ld(v.fy, m.fc, v.diameter, cb)
                .ld, Kind.LENGTH, clause)
    avail = c.step("l_a", r"\min(top - z_{top},\ bottom + z_{bottom}) - l_{node}/2",
                   min(m.top - a.centre, m.bottom + b.centre) - max(a.height, b.height) / 2,
                   Kind.LENGTH, clause)
    out.append(c.result("through_bolt.stm_tie_anchorage", clause, ld, avail, Kind.LENGTH))
    return out


def member_flexure(near: BeamLoad, far: BeamLoad, member: ConcreteMember, width: float,
                   ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """Flexure with axial force of the member above or below the connection, with the
    larger share of the unbalanced moment ΔM = (M1 - M2) + (V1 - V2) h/2; a wall acts
    with a strip b_eff = b_p + 2h."""
    m = member
    clause = f"{ed.aci} §22.2–§22.4"
    c = Calc(Method.LRFD, combo)
    total = c.step(r"\Delta M", r"|(M_1 - M_2) + (V_1 - V_2) h/2|",
                   abs(near.M - far.M + (near.V - far.V) * m.thickness / 2), Kind.MOMENT,
                   clause, M_1=(near.M, Kind.MOMENT), M_2=(far.M, Kind.MOMENT))
    share = max(m.share_above, 1 - m.share_above)
    mu = c.step("M_u", r"\alpha \Delta M", share * total, Kind.MOMENT, clause,
                alpha=(share, Kind.DIMENSIONLESS))
    if m.kind is Support.WALL:
        b = c.step("b", "b_p + 2h", min(width + 2 * m.thickness, m.width), Kind.LENGTH, clause)
    else:
        b = c.step("b", "b_c", m.width, Kind.LENGTH, clause)
    n = max(math.floor(b / m.vertical.spacing), 2)
    x = m.thickness / 2 - m.bar_line
    mn, _ = section_capacity(m.axial, m.thickness, b, [x] * n + [-x] * n,
                             m.vertical.bar_area, m.fc, m.vertical.fy)
    c.step("P_u", "", m.axial, Kind.FORCE, clause)
    cap = c.step(r"\phi M_n", r"\text{strain compatibility at } P_u", mn, Kind.MOMENT, clause,
                 n=(n, Kind.DIMENSIONLESS))
    return c.result("through_bolt.member_flexure", clause, mu, cap, Kind.MOMENT)


# ------------------------------------------------------------------------ grout
def grout_bearing(V: float, conn: ThroughBoltConnection, ed: Edition = CURRENT,
                  combo: str = "", check_id: str = "through_bolt.grout_bearing") -> CheckResult:
    """Bolt bearing on the grout of its sleeve: V/n ≤ φ 0.85 f'cg d ℓ, with the bearing
    length ℓ = min(ℓg, 4d) (the pressure concentrates near the face)."""
    clause = f"{ed.aci} §22.8 (bolt bearing on the grout)"
    c = Calc(Method.LRFD, combo)
    d = conn.end_plate.bolt.diameter
    n = conn.bolts
    v = c.step("V_b", "V / n", abs(V) / n, Kind.FORCE, clause, n=(n, Kind.DIMENSIONLESS))
    lg = conn.grout_length or 4 * d
    ell = c.step(r"\ell", r"\min(\ell_g, 4d)", min(lg, 4 * d), Kind.LENGTH, clause)
    fc = conn.grout_fc or conn.member.fc
    rn = c.step("B_n", r"0.85 f'_{cg} d \ell", 0.85 * fc * d * ell, Kind.FORCE, clause,
                f_cg=(fc, Kind.STRESS))
    cap = c.available(rn, BEARING, Kind.FORCE, clause, "B_n")
    return c.result(check_id, clause, v, cap, Kind.FORCE)


def bolt_combined(T: float, V: float, conn: ThroughBoltConnection, ed: Edition = CURRENT,
                  method: Method = Method.LRFD, combo: str = "") -> CheckResult:
    """Most loaded bolt with grout: tension of its group, shear V/n of the more loaded
    side and bending over the gap (lever gap/2), AISC J3.7 (DG1 rod with plate washer)."""
    bolt = conn.end_plate.bolt
    n = conn.bolts
    r = rod_combined(T, abs(V) / n, bolt.diameter, bolt.material.Fnt, bolt.Fnv,
                     conn.gap / 2, ed, method, combo)
    return r.model_copy(update={"id": "through_bolt.bolt_combined",
                                "text_id": "check.through_bolt.bolt_combined"})


# ------------------------------------------------------------------------ all checks
def _side_label(combo: str, side: str) -> str:
    return f"{combo} · {side}" if combo else side


def check_through_bolt(conn: ThroughBoltConnection, V: float, M: float, P: float = 0.0,
                       ed: Edition = CURRENT, method: Method = Method.LRFD,
                       combo: str = "", V2: float = 0.0, M2: float = 0.0,
                       P2: float = 0.0) -> list[CheckResult]:
    """All the checks of the connection for one load combination.

    ``V``, ``M``, ``P`` load the near beam and ``V2``, ``M2``, ``P2`` the opposite one
    (each M positive with tension at the top). The steel checks use ``method``; the
    concrete checks are strength design and are evaluated for LRFD combinations only.
    """
    near, far = BeamLoad(V, M, P), BeamLoad(V2, M2, P2)
    loads = [(False, near)] + ([(True, far)] if conn.opposite is not None else [])
    out: list[CheckResult] = []
    for is_far, load in loads:
        if not (load.M or load.V or load.P):
            continue
        mc = conn.moment_connection(far=is_far)
        label = _side_label(combo, "viga 2") if is_far else combo
        steel, _, _ = end_plate_checks(mc, load.V, load.M, load.P, method, label)
        if conn.shear is ShearTransfer.FRICTION:
            steel = [r for r in steel if r.id != "moment.end_plate_bolt_shear"]
        out += steel
    zs, bolts = zones(conn, near, far)
    if conn.shear is ShearTransfer.GROUT:
        out.append(bolt_combined(max(bolts.values()) / (conn.bolts / 2),
                                 max(abs(V), abs(V2)), conn, ed, method, combo))
    if method is not Method.LRFD:
        return out
    m = conn.member
    for z in zs:
        if z.force <= 0:
            continue
        where = "end plate" if z.face == NEAR or conn.opposite else "back plate"
        key = f"{z.face}_{z.group}"
        out.append(bearing(z.force, z.area, m.fc, f"through_bolt.bearing_{key}",
                           f"{where}, {z.group}", ed, combo))
        out.append(bursting(z.force, z.area, m, f"through_bolt.bursting_{key}", ed, combo))
    by = {(z.face, z.group): z for z in zs}
    for g in (TOP, BOTTOM):
        a, b = by[NEAR, g], by[FAR, g]
        unbalanced = abs(a.force - b.force)
        if unbalanced > 0:
            area = a.area if a.force >= b.force else b.area
            out.append(punching(unbalanced, area, m, ed, combo, f"through_bolt.punching_{g}"))
    if conn.shear is ShearTransfer.FRICTION:
        for face, load, plate_beam, ep in (
                (NEAR, near, conn.beam, conn.end_plate),
                *([(FAR, far, conn.opposite.beam, conn.opposite.end_plate)]
                  if conn.opposite else [])):
            if not load.V:
                continue
            compression = by[face, TOP].force + by[face, BOTTOM].force
            height = plate_beam.d + 2 * _plate_extension(plate_beam, ep)
            r = friction(compression, ep.width * height, m.fc, abs(load.V), conn.mu, ed,
                         combo if face == NEAR else _side_label(combo, "viga 2"))
            out.append(r.model_copy(update={"id": f"through_bolt.friction_{face}",
                                             "text_id": f"check.through_bolt.friction_{face}"}))
    else:
        for face, load in ((NEAR, near), (FAR, far)):
            if load.V and (face == NEAR or conn.opposite):
                out.append(grout_bearing(load.V, conn, ed, combo,
                                         f"through_bolt.grout_bearing_{face}"))
    couple = _couple(zs)
    if couple is not None:
        out += strut_and_tie(couple, m, ed, combo)
    width = max(z.area.width for z in zs)
    out.append(member_flexure(near, far, m, width, ed, combo))
    return out

