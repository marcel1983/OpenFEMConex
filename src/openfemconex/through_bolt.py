# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Beam end plate bolted through a new concrete wall or column (analytic checks).

The beam end plate is bolted with through-bolts that cross the wall or column in
sleeves (no bond to the concrete) and are anchored on a continuous back plate on
the far face. The help topic "Pernos pasantes" explains the load path.

Force model for a beam end moment ``M``, shear ``V`` and axial force ``P``
(positive in compression), with lever arm z = d - tf between the flange centres:

* the bolts at the tension flange carry T = |M|/z - P/2 to the back plate, which
  bears on the far face of the concrete;
* the end plate bears on the near face at the compression flange with C = T + P;
* the shear goes by friction under C (``ShearTransfer.FRICTION``), or through the
  bolts bearing on grout in the sleeves (``ShearTransfer.GROUT``).

The steel side (end plate yielding, bolt rupture, welds) reuses the end-plate
checks of AISC Design Guides 16 and 4 from OpenConex. This module adds the
concrete side, for LRFD (ACI 318 strength design):

* bearing under each plate (§22.8), on an area limited by the plate bending;
* punching shear of the member around the back plate (§22.6);
* shear by friction under the compression of the end plate;
* bursting behind each plate (anchorage zone of §25.9 used by analogy);
* strut-and-tie model of the couple T·z inside the member (Chapter 23): diagonal
  strut, nodes, vertical bars of each face as ties and their development;
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

from openfemconex.checks import CURRENT, Edition, friction
from openfemconex.pedestal import section_capacity

__all__ = [
    "BackPlate", "ConcreteMember", "Forces", "Rebar", "Support", "ShearTransfer",
    "ThroughBoltConnection", "bearing", "bolt_rows", "bursting", "check_through_bolt",
    "forces", "member_flexure", "punching", "strut_and_tie",
]

BEARING = Resistance(0.65, math.nan)
SHEAR = Resistance(0.75, math.nan)
STM = Resistance(0.75, math.nan)

class Support(StrEnum):
    WALL = "wall"
    COLUMN = "column"

class ShearTransfer(StrEnum):
    FRICTION = "friction"
    """Friction under the compression of the end plate; the bolts carry no shear."""
    GROUT = "grout"
    """Bolts bearing on grout in the sleeves (bolt shear from the end-plate checks)."""

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
class ThroughBoltConnection:
    beam: IShape
    end_plate: EndPlate
    back_plate: BackPlate
    member: ConcreteMember
    shear: ShearTransfer = ShearTransfer.FRICTION
    mu: float = 0.55
    FEXX: float = to_internal(70.0, "ksi", Kind.STRESS)

    @property
    def lever(self) -> float:
        return self.beam.d - self.beam.tf

    def moment_connection(self) -> MomentConnection:
        """OpenConex end-plate connection; the back plate stands for the column flange
        on which the bolts bear."""
        bp = self.back_plate
        dummy = IShape(name="back plate", d=10 * bp.thickness + 1, bf=bp.width,
                       tf=bp.thickness, tw=bp.thickness / 2, grade=bp.grade)
        return MomentConnection(detail=FlangeDetail.END_PLATE, beam=self.beam, beam_Sx=0.0,
                                column=dummy, end_plate=self.end_plate, FEXX=self.FEXX)

# ------------------------------------------------------------------------ geometry
def bolt_rows(beam: IShape, ep: EndPlate) -> list[float]:
    """Heights of the bolt rows at the tension flange, from the beam axis (upwards)."""
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
class Forces:
    T: float
    """Tension of the bolts at the tension flange (to the back plate)."""
    C: float
    """Compression of the end plate on the concrete."""
    V: float
    M: float

def forces(conn: ThroughBoltConnection, V: float, M: float, P: float = 0.0) -> Forces:
    z = conn.lever
    T = max(abs(M) / z - P / 2, 0.0)
    C = max(T + P, 0.0)
    return Forces(T, C, abs(V), abs(M))

# ------------------------------------------------------------------------ bearing
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

def front_area(conn: ThroughBoltConnection) -> BearingArea:
    """Bearing area of the end plate at the compression flange (drawn at the bottom)."""
    beam, ep = conn.beam, conn.end_plate
    bottom = -beam.d / 2
    return _bearing_area(conn.member, ep.thickness, ep.Fy, beam.bf, bottom, bottom + beam.tf,
                         ep.width, bottom - _plate_extension(beam, ep), beam.d / 2)

def back_area(conn: ThroughBoltConnection) -> BearingArea:
    """Bearing area of the back plate around the tension bolts (drawn at the top)."""
    rows = bolt_rows(conn.beam, conn.end_plate)
    bp = conn.back_plate
    dw = bp.washer or 2 * conn.end_plate.bolt.diameter
    return _bearing_area(conn.member, bp.thickness, bp.Fy, conn.end_plate.gage + dw,
                         min(rows) - dw / 2, max(rows) + dw / 2, bp.width, -bp.height / 2,
                         bp.height / 2)

def bearing(force: float, area: BearingArea, fc: float, check_id: str, where: str,
            ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """C ≤ φ 0.85 f'c A1 √(A2/A1), A1 limited by the plate bending."""
    clause = f"{ed.aci} §22.8.3; {ed.guide} (cantilever of the plate)"
    c = Calc(Method.LRFD, combo)
    c.step("l", r"t_p\sqrt{\frac{0.9F_y}{2f_p}}", area.cantilever, Kind.LENGTH, clause)
    a1 = c.step("A_1", f"b h ({where})", area.area, Kind.AREA, clause,
                b=(area.width, Kind.LENGTH), h=(area.height, Kind.LENGTH))
    r = c.step(r"\sqrt{A_2/A_1}", r"\le 2", area.ratio, clause=clause)
    rn = c.step("B_n", r"0.85 f'_c A_1 \sqrt{A_2/A_1}", 0.85 * fc * a1 * r, Kind.FORCE, clause)
    cap = c.available(rn, BEARING, Kind.FORCE, clause, "B_n")
    return c.result(check_id, clause, force, cap, Kind.FORCE)

# ------------------------------------------------------------------------ punching
def punching(T: float, area: BearingArea, member: ConcreteMember, ed: Edition = CURRENT,
             combo: str = "") -> CheckResult:
    """Two-way shear of the member around the back plate, through the whole thickness."""
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
    return c.result("through_bolt.punching", clause, T, cap, Kind.FORCE)

# ------------------------------------------------------------------------ bursting
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
        tb = c.step(rf"T_{{burst,{name}}}", r"0.25 F (1 - a/H)", 0.25 * force * max(1 - a / H, 0),
                    Kind.FORCE, clause, a=(a, Kind.LENGTH), H=(H, Kind.LENGTH))
        n = 2 * max(math.floor(H / bars.spacing), 1)
        cap = c.step(rf"\phi A_s f_y ({name})", r"0.75 n A_b f_y", STM.phi * n * bars.bar_area
                     * bars.fy, Kind.FORCE, clause, n=(n, Kind.DIMENSIONLESS))
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


def strut_and_tie(f: Forces, conn: ThroughBoltConnection, back: BearingArea,
                  front: BearingArea, ed: Edition = CURRENT,
                  combo: str = "") -> list[CheckResult]:
    """Couple T·z inside the member: diagonal strut from the back plate (top, far face)
    to the compression zone of the end plate (bottom, near face), vertical bars of
    each face as ties, and their development past the nodes."""
    m = conn.member
    out: list[CheckResult] = []
    jx = m.thickness - 2 * m.bar_line
    zt, zc = (back.z0 + back.z1) / 2, (front.z0 + front.z1) / 2
    jz = zt - zc
    theta = math.atan2(jz, jx)
    clause = _clause(ed, "§23.2", "Appendix A")
    c = Calc(Method.LRFD, combo)
    c.step("j_x", "h - 2 c_b", jx, Kind.LENGTH, clause)
    c.step("j_z", "z_T - z_C", jz, Kind.LENGTH, clause)
    angle = c.step(r"\theta", r"\arctan(j_z / j_x)", math.degrees(theta), clause=clause)
    out.append(c.result("through_bolt.stm_angle", f"{clause} (25° ≤ angle to the tie)",
                        25.0, 90.0 - angle, Kind.DIMENSIONLESS))
    # strut
    clause = _clause(ed, "§23.4", "A.3")
    c = Calc(Method.LRFD, combo)
    fs = c.step("F_s", r"T / \cos\theta", f.T / math.cos(theta), Kind.FORCE, clause)
    wt = 2 * m.bar_line
    lb = min(back.height, front.height)
    ws = c.step("w_s", r"l_b \cos\theta + w_t \sin\theta", lb * math.cos(theta)
                + wt * math.sin(theta), Kind.LENGTH, clause, l_b=(lb, Kind.LENGTH))
    bs = min(back.width, front.width)
    beta_s = 0.75 if m.cross_ties else (0.4 if ed.key == "current" else 0.6)
    c.step(r"\beta_s", "", beta_s, clause=clause)
    beta_c = _confinement(c, min(back.ratio, front.ratio), ed, clause)
    fce = c.step("f_{ce}", r"0.85 \beta_c \beta_s f'_c", 0.85 * beta_c * beta_s * m.fc,
                 Kind.STRESS, clause)
    rn = c.step("F_{ns}", "f_{ce} w_s b_s", fce * ws * bs, Kind.FORCE, clause,
                b_s=(bs, Kind.LENGTH))
    cap = c.available(rn, STM, Kind.FORCE, clause, "F_{ns}")
    out.append(c.result("through_bolt.stm_strut", clause, fs, cap, Kind.FORCE))
    # nodes (C-C-T)
    clause = _clause(ed, "§23.9", "A.5")
    for key, force, area in (("back", f.T, back), ("front", f.C, front)):
        c = Calc(Method.LRFD, combo)
        beta_c = _confinement(c, area.ratio, ed, clause)
        fce = c.step("f_{ce}", r"0.85 \beta_c \beta_n f'_c", 0.85 * beta_c * 0.8 * m.fc,
                     Kind.STRESS, clause)
        rn = c.step("F_{nn}", "f_{ce} A_{nz}", fce * area.area, Kind.FORCE, clause)
        cap = c.available(rn, STM, Kind.FORCE, clause, "F_{nn}")
        out.append(c.result(f"through_bolt.stm_node_{key}", clause, force, cap, Kind.FORCE))
    # ties: vertical bars of each face within b_eff
    clause = _clause(ed, "§23.7", "A.4")
    c = Calc(Method.LRFD, combo)
    ft = c.step("F_t", r"T \tan\theta", f.T * math.tan(theta), Kind.FORCE, clause)
    beff = c.step("b_{eff}", r"\min(b_{bp} + 2h,\ b_c)", min(back.width + 2 * m.thickness,
                  m.width), Kind.LENGTH, clause)
    n = max(math.floor(beff / m.vertical.spacing), 1)
    rn = c.step("F_{nt}", "n A_b f_y", n * m.vertical.bar_area * m.vertical.fy, Kind.FORCE,
                clause, n=(n, Kind.DIMENSIONLESS))
    cap = c.available(rn, STM, Kind.FORCE, clause, "F_{nt}")
    out.append(c.result("through_bolt.stm_tie", clause, ft, cap, Kind.FORCE))
    # development of the ties past the nodes (front bars below the front node, back bars
    # above the back node)
    clause = _clause(ed, "§23.8.3; §25.4.2", "A.4.3; §12.2")
    c = Calc(Method.LRFD, combo)
    v = m.vertical
    cb = min(m.cover + m.horizontal.diameter + v.diameter / 2, v.spacing / 2)
    ld = c.step("l_d", r"\text{straight bar}", straight_bar_ld(v.fy, m.fc, v.diameter, cb)
                .ld, Kind.LENGTH, clause)
    avail = c.step("l_a", r"\min(z_T + top,\ bottom - z_C) - l_{node}/2",
                   min(m.top - zt, m.bottom + zc) - max(back.height, front.height) / 2,
                   Kind.LENGTH, clause)
    out.append(c.result("through_bolt.stm_tie_anchorage", clause, ld, avail, Kind.LENGTH))
    return out

# ------------------------------------------------------------------------ member flexure
def member_flexure(f: Forces, conn: ThroughBoltConnection, back: BearingArea,
                   ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """Flexure with axial force of the member above or below the connection, with the
    larger share of M + V h/2; a wall acts with a strip b_eff = b_bp + 2h."""
    m = conn.member
    clause = f"{ed.aci} §22.2–§22.4"
    c = Calc(Method.LRFD, combo)
    total = c.step("M_m", "M + V h/2", f.M + f.V * m.thickness / 2, Kind.MOMENT, clause)
    share = max(m.share_above, 1 - m.share_above)
    mu = c.step("M_u", r"\alpha M_m", share * total, Kind.MOMENT, clause,
                alpha=(share, Kind.DIMENSIONLESS))
    if m.kind is Support.WALL:
        b = c.step("b", "b_{bp} + 2h", min(back.width + 2 * m.thickness, m.width), Kind.LENGTH,
                   clause)
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

# ------------------------------------------------------------------------ all checks
def check_through_bolt(conn: ThroughBoltConnection, V: float, M: float, P: float = 0.0,
                       ed: Edition = CURRENT, method: Method = Method.LRFD,
                       combo: str = "") -> list[CheckResult]:
    """All the checks of the connection for one load combination.

    The steel checks use ``method``; the concrete checks are strength design and are
    evaluated for LRFD combinations only.
    """
    mc = conn.moment_connection()
    steel, _, _ = end_plate_checks(mc, V, M, P, method, combo)
    if conn.shear is ShearTransfer.FRICTION:
        steel = [r for r in steel if r.id != "moment.end_plate_bolt_shear"]
    out = list(steel)
    if method is not Method.LRFD:
        return out
    f = forces(conn, V, M, P)
    front, back = front_area(conn), back_area(conn)
    m = conn.member
    out.append(bearing(f.C, front, m.fc, "through_bolt.bearing_front", "end plate", ed, combo))
    out.append(bearing(f.T, back, m.fc, "through_bolt.bearing_back", "back plate", ed, combo))
    out.append(punching(f.T, back, m, ed, combo))
    if conn.shear is ShearTransfer.FRICTION:
        ep = conn.end_plate
        height = conn.beam.d + 2 * _plate_extension(conn.beam, ep)
        r = friction(f.C, ep.width * height, m.fc, f.V, conn.mu, ed, combo)
        out.append(r.model_copy(update={"id": "through_bolt.friction",
                                         "text_id": "check.through_bolt.friction"}))
    out.append(bursting(f.C, front, m, "through_bolt.bursting_front", ed, combo))
    out.append(bursting(f.T, back, m, "through_bolt.bursting_back", ed, combo))
    if f.T > 0:
        out += strut_and_tie(f, conn, back, front, ed, combo)
    out.append(member_flexure(f, conn, back, ed, combo))
    return out
