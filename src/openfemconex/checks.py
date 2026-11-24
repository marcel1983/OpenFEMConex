# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Code checks of the base plate with demands taken from the FEM solution.

Every check is a pure function that returns an OpenConex ``CheckResult`` with
its calculation trace and clause. The provisions are parametrised by
:class:`Edition`:

* ``CURRENT``: AISC 360-22 and ACI 318-19 Chapter 17;
* ``DG1_2ED``: AISC 360-05 and ACI 318-08 Appendix D as applied by AISC Design
  Guide 1, 2nd edition, to reproduce its worked examples.

Only numerical provisions are used, each with its reference. The concrete
(ACI) checks are strength-level, so they are evaluated for LRFD combinations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconex.connections.base_plate.check import BasePlate, concrete_edges
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import ELECTRODES
from openconex.kernel.anchors import (
    Edges,
    futa,
    heavy_hex_bearing_area,
    projected_area_tension,
    tensile_stress_area,
)
from openconex.kernel.design import Calc, Resistance
from openconex.units import Kind, from_internal, to_internal

from openfemconex import pedestal as ped
from openfemconex.extras import Extras
from openfemconex.openconex_bridge import section_of
from openfemconex.results import Results

__all__ = [
    "CURRENT", "DG1_2ED", "EDITIONS", "Edition", "anchor_breakout_shear",
    "anchor_breakout_tension", "anchor_interaction", "anchor_pryout", "anchor_pullout",
    "anchor_side_face_blowout", "anchor_steel_shear", "anchor_steel_tension",
    "check_fem", "concrete_bearing", "fillet_weld_line", "friction", "plate_bending_tension",
    "plate_plastic_strain",
]

NO_EDGES = Edges()


@dataclass(frozen=True)
class Edition:
    key: str
    aisc: str
    aci: str
    aci_anchor: str
    """Prefix of the anchorage clauses (``§17`` or ``D``)."""
    anchor_steel_aisc: bool
    """Rod steel by AISC J3.6 on the nominal area (0.75 Fu Ab, 0.4 Fu Ab) instead of ACI."""
    shear_breakout_cap: bool
    """Upper limit 9 λ √f'c ca1^1.5 on Vb (introduced in ACI 318-11)."""
    friction_phi: float
    steel_tension: Resistance = Resistance(0.75, 2.00)
    steel_shear: Resistance = Resistance(0.65, 2.00)
    concrete_b: Resistance = Resistance(0.70, math.nan)
    concrete_a: Resistance = Resistance(0.75, math.nan)
    pullout: Resistance = Resistance(0.70, math.nan)
    bearing: Resistance = Resistance(0.65, 2.31)
    weld: Resistance = Resistance(0.75, 2.00)
    flexure: Resistance = Resistance(0.90, 1.67)
    guide: str = "AISC DG1"

    def anchor(self, clause: str) -> str:
        """Clause label, e.g. ``anchor("6.2")`` -> ``ACI 318-19 §17.6.2``."""
        return f"{self.aci} {_CLAUSES[self.key][clause]}"


# Anchorage clause numbers of each edition (ACI 318-19 Chapter 17 / ACI 318-08 Appendix D).
_CLAUSES = {
    "current": {"steel_t": "§17.6.1.2", "breakout_t": "§17.6.2", "pullout": "§17.6.3",
                "blowout": "§17.6.4", "steel_v": "§17.7.1", "breakout_v": "§17.7.2",
                "pryout": "§17.7.3", "interaction": "§17.8", "reinf_t": "§17.5.2.1(a)",
                "reinf_v": "§17.5.2.1(b)", "col_min": "§10.6.1.1", "col_pm": "§22.4"},
    "dg1-2ed": {"steel_t": "D.5.1", "breakout_t": "D.5.2", "pullout": "D.5.3",
                "blowout": "D.5.4", "steel_v": "D.6.1", "breakout_v": "D.6.2",
                "pryout": "D.6.3", "interaction": "D.7", "reinf_t": "D.5.2.9",
                "reinf_v": "D.6.2.9", "col_min": "§10.9.1", "col_pm": "§10.3"},
}

CURRENT = Edition("current", "AISC 360-22", "ACI 318-19", "§17", anchor_steel_aisc=False,
                  shear_breakout_cap=True, friction_phi=0.65, guide="AISC DG1 3rd ed.")
# The guide takes the bearing factor 0.65 from ACI 318 (AISC 360-05 J8 has 0.60) and the rod
# steel strength from AISC J3.6 with φ = 0.75.
DG1_2ED = Edition("dg1-2ed", "AISC 360-05", "ACI 318-08", "D", anchor_steel_aisc=True,
                  shear_breakout_cap=False, friction_phi=0.75,
                  steel_shear=Resistance(0.75, 2.00), guide="AISC DG1 2nd ed.")
EDITIONS = {e.key: e for e in (CURRENT, DG1_2ED)}


def _in(v: float) -> float:
    return from_internal(v, Kind.LENGTH, "in")


def _psi(v: float) -> float:
    return from_internal(v, Kind.STRESS, "psi")


def _lbf(v: float) -> float:
    return to_internal(v, "lbf", Kind.FORCE)


def _calc(method: Method, combo: str) -> Calc:
    return Calc(method, combo)


# ------------------------------------------------------------------------- anchors: steel
def anchor_steel_tension(d: float, Fu: float, Fy: float, demand: float, ed: Edition = CURRENT,
                         method: Method = Method.LRFD, combo: str = "") -> CheckResult:
    """Steel strength of one anchor in tension."""
    c = _calc(method, combo)
    if ed.anchor_steel_aisc:
        clause = f"{ed.aisc} J3.6; {ed.guide} Table 3.1"
        ab = c.step("A_b", r"\pi d^2/4", math.pi * d * d / 4, Kind.AREA, clause)
        rn = c.step("R_n", "0.75 F_u A_b", 0.75 * Fu * ab, Kind.FORCE, clause)
        cap = c.available(rn, ed.steel_tension, Kind.FORCE, clause)
    else:
        clause = ed.anchor("steel_t")
        ase = c.step("A_{se,N}", r"\frac{\pi}{4}\left(d_a - \frac{0.9743}{n_t}\right)^2",
                     tensile_stress_area(d), Kind.AREA, clause)
        fu = c.step("f_{uta}", r"\min(f_{uta}, 1.9 f_{ya}, 125\ ksi)", futa(Fu, Fy),
                    Kind.STRESS, clause)
        rn = c.step("N_{sa}", "A_{se,N} f_{uta}", ase * fu, Kind.FORCE, clause)
        cap = c.available(rn, ed.steel_tension, Kind.FORCE, clause, "N_{sa}")
    return c.result("anchor.steel_tension", clause, demand, cap, Kind.FORCE)


def anchor_steel_shear(d: float, Fu: float, Fy: float, demand: float, ed: Edition = CURRENT,
                       method: Method = Method.LRFD, grout_pad: bool = False,
                       combo: str = "") -> CheckResult:
    """Steel strength of one anchor in shear (0.80 with a grout pad)."""
    c = _calc(method, combo)
    if ed.anchor_steel_aisc:
        clause = f"{ed.aisc} J3.6"
        rn = c.step("R_n", "0.4 F_u A_b", 0.4 * Fu * math.pi * d * d / 4, Kind.FORCE, clause)
        symbol = "R_n"
    else:
        clause = ed.anchor("steel_v")
        rn = c.step("V_{sa}", "0.6 A_{se,V} f_{uta}", 0.6 * tensile_stress_area(d) * futa(Fu, Fy),
                    Kind.FORCE, clause)
        symbol = "V_{sa}"
    if grout_pad:
        rn = c.step(symbol, f"0.80 {symbol}", 0.80 * rn, Kind.FORCE,
                    f"{ed.aci} grout pad factor")
    cap = c.available(rn, ed.steel_shear, Kind.FORCE, clause, symbol)
    return c.result("anchor.steel_shear", clause, demand, cap, Kind.FORCE)


# ---------------------------------------------------------------------- anchors: concrete
def _effective_hef(hef: float, edges: Edges, span_x: float, span_y: float) -> float:
    near = [e for e in edges.values() if e < 1.5 * hef]
    if len(near) >= 3:
        return min(hef, max(max(near) / 1.5, max(span_x, span_y) / 3))
    return hef


def anchor_breakout_tension(hef: float, fc: float, demand: float, ed: Edition = CURRENT,
                            span_x: float = 0.0, span_y: float = 0.0, edges: Edges = NO_EDGES,
                            eccentricity: float = 0.0, cracked: bool = True,
                            supplementary: bool = False, combo: str = "") -> CheckResult:
    """Concrete breakout of a group of cast-in anchors in tension (CCD method)."""
    clause = ed.anchor("breakout_t")
    c = _calc(Method.LRFD, combo)
    h = c.step("h_{ef}", "h_{ef}'", _effective_hef(hef, edges, span_x, span_y), Kind.LENGTH,
               clause)
    anc = c.step("A_{Nc}", r"(s_x + c_1 + c_2)(s_y + c_3 + c_4),\ c_i \le 1.5h_{ef}",
                 projected_area_tension(h, span_x, span_y, edges), Kind.AREA, clause)
    anco = c.step("A_{Nco}", "9 h_{ef}^2", 9 * h * h, Kind.AREA, clause)
    h_in, fc_psi = _in(h), _psi(fc)
    if 11 <= h_in <= 25:
        nb, expr = 16 * math.sqrt(fc_psi) * h_in ** (5 / 3), r"16 \sqrt{f'_c} h_{ef}^{5/3}"
    else:
        nb, expr = 24 * math.sqrt(fc_psi) * h_in**1.5, r"24 \sqrt{f'_c} h_{ef}^{1.5}"
    nb = c.step("N_b", expr, _lbf(nb), Kind.FORCE, clause)
    psi_ec = c.step(r"\psi_{ec,N}", r"\frac{1}{1 + e'_N/(1.5h_{ef})}",
                    1 / (1 + eccentricity / (1.5 * h)), clause=clause)
    ca_min = min(edges.values(), default=math.inf)
    psi_ed = c.step(r"\psi_{ed,N}", r"0.7 + 0.3\frac{c_{a,min}}{1.5h_{ef}} \le 1",
                    1.0 if ca_min >= 1.5 * h else 0.7 + 0.3 * ca_min / (1.5 * h), clause=clause)
    psi_c = c.step(r"\psi_{c,N}", "1.0 / 1.25", 1.0 if cracked else 1.25, clause=clause)
    rn = c.step("N_{cbg}", r"\frac{A_{Nc}}{A_{Nco}}\psi_{ec,N}\psi_{ed,N}\psi_{c,N}N_b",
                anc / anco * psi_ec * psi_ed * psi_c * nb, Kind.FORCE, clause)
    cap = c.available(rn, ed.concrete_a if supplementary else ed.concrete_b, Kind.FORCE, clause,
                      "N_{cbg}")
    return c.result("anchor.concrete_breakout_tension", clause, demand, cap, Kind.FORCE)


def anchor_pullout(bearing_area: float, fc: float, demand: float, ed: Edition = CURRENT,
                   cracked: bool = True, combo: str = "") -> CheckResult:
    """Pullout of one headed anchor, Np = 8 Abrg f'c."""
    clause = ed.anchor("pullout")
    c = _calc(Method.LRFD, combo)
    np_ = c.step("N_p", "8 A_{brg} f'_c", 8 * bearing_area * fc, Kind.FORCE, clause,
                 A_brg=(bearing_area, Kind.AREA))
    rn = c.step("N_{pn}", r"\psi_{c,P} N_p", (1.0 if cracked else 1.4) * np_, Kind.FORCE, clause)
    cap = c.available(rn, ed.pullout, Kind.FORCE, clause, "N_{pn}")
    return c.result("anchor.pullout", clause, demand, cap, Kind.FORCE)


def anchor_side_face_blowout(ca1: float, bearing_area: float, fc: float, demand: float,
                             hef: float, ed: Edition = CURRENT, spacing: float = 0.0,
                             combo: str = "") -> CheckResult:
    """Side-face blowout of headed anchors near an edge; applies if hef > 2.5 ca1."""
    clause = ed.anchor("blowout")
    c = _calc(Method.LRFD, combo)
    abrg = from_internal(bearing_area, Kind.AREA, "in**2")
    nsb = c.step("N_{sb}", r"160 c_{a1} \sqrt{A_{brg}} \sqrt{f'_c}",
                 _lbf(160 * _in(ca1) * math.sqrt(abrg) * math.sqrt(_psi(fc))), Kind.FORCE, clause)
    if spacing:
        nsb = c.step("N_{sbg}", r"\left(1 + \frac{s}{6c_{a1}}\right) N_{sb}",
                     (1 + spacing / (6 * ca1)) * nsb, Kind.FORCE, clause)
    cap = c.available(nsb, ed.concrete_b, Kind.FORCE, clause, "N_{sb}")
    return c.result("anchor.side_face_blowout", clause, demand, cap, Kind.FORCE,
                    applicable=hef > 2.5 * ca1)


def anchor_breakout_shear(d: float, hef: float, ca1: float, fc: float, demand: float,
                          ed: Edition = CURRENT, spacing: float = 0.0,
                          ca2: tuple[float | None, float | None] = (None, None),
                          cracked: bool = True, supplementary: bool = False,
                          combo: str = "") -> CheckResult:
    """Concrete breakout of an anchor group in shear toward an edge at ``ca1``."""
    clause = ed.anchor("breakout_v")
    c = _calc(Method.LRFD, combo)
    r = 1.5 * ca1
    width = spacing + sum(r if s is None else min(s, r) for s in ca2)
    avc = c.step("A_{Vc}", r"(s + c_{a2,1} + c_{a2,2})(1.5c_{a1})", width * r, Kind.AREA, clause)
    avco = c.step("A_{Vco}", "4.5 c_{a1}^2", 4.5 * ca1 * ca1, Kind.AREA, clause)
    le = min(hef, 8 * d)
    root = math.sqrt(_psi(fc)) * _in(ca1) ** 1.5
    vb = 7 * (_in(le) / _in(d)) ** 0.2 * math.sqrt(_in(d)) * root
    expr = r"7\left(\frac{l_e}{d_a}\right)^{0.2}\sqrt{d_a}\sqrt{f'_c}c_{a1}^{1.5}"
    if ed.shear_breakout_cap:
        vb, expr = min(vb, 9 * root), rf"\min\left[{expr},\ 9\sqrt{{f'_c}}c_{{a1}}^{{1.5}}\right]"
    vb = c.step("V_b", expr, _lbf(vb), Kind.FORCE, clause)
    ca2_min = min((s for s in ca2 if s is not None), default=math.inf)
    psi_ed = c.step(r"\psi_{ed,V}", r"0.7 + 0.3\frac{c_{a2}}{1.5c_{a1}} \le 1",
                    1.0 if ca2_min >= r else 0.7 + 0.3 * ca2_min / r, clause=clause)
    psi_c = c.step(r"\psi_{c,V}", "1.0 / 1.4", 1.0 if cracked else 1.4, clause=clause)
    rn = c.step("V_{cbg}", r"\frac{A_{Vc}}{A_{Vco}}\psi_{ed,V}\psi_{c,V}V_b",
                avc / avco * psi_ed * psi_c * vb, Kind.FORCE, clause)
    cap = c.available(rn, ed.concrete_a if supplementary else ed.concrete_b, Kind.FORCE, clause,
                      "V_{cbg}")
    return c.result("anchor.concrete_breakout_shear", clause, demand, cap, Kind.FORCE)


def anchor_pryout(Ncbg: float, hef: float, demand: float, ed: Edition = CURRENT,
                  combo: str = "") -> CheckResult:
    """Concrete pryout, Vcpg = kcp Ncbg."""
    clause = ed.anchor("pryout")
    c = _calc(Method.LRFD, combo)
    kcp = c.step("k_{cp}", "1.0\\ (h_{ef} < 2.5\\ in.)\\ /\\ 2.0", 1.0 if _in(hef) < 2.5 else 2.0,
                 clause=clause)
    rn = c.step("V_{cpg}", "k_{cp} N_{cbg}", kcp * Ncbg, Kind.FORCE, clause)
    cap = c.available(rn, ed.concrete_b, Kind.FORCE, clause, "V_{cpg}")
    return c.result("anchor.pryout", clause, demand, cap, Kind.FORCE)


def anchor_interaction(tension_ratio: float, shear_ratio: float, ed: Edition = CURRENT,
                       combo: str = "") -> CheckResult:
    """N/φNn + V/φVn ≤ 1.2, unless either ratio is at most 0.2."""
    clause = ed.anchor("interaction")
    c = _calc(Method.LRFD, combo)
    rn = c.step(r"N_{ua}/\phi N_n", "", tension_ratio, clause=clause)
    rv = c.step(r"V_{ua}/\phi V_n", "", shear_ratio, clause=clause)
    if rn <= 0.2 or rv <= 0.2:
        return c.result("anchor.interaction", clause, max(rn, rv), 1.0, Kind.DIMENSIONLESS)
    value = c.step("", r"\frac{N_{ua}}{\phi N_n} + \frac{V_{ua}}{\phi V_n}", rn + rv,
                   clause=clause)
    return c.result("anchor.interaction", clause, value, 1.2, Kind.DIMENSIONLESS)


# --------------------------------------------------------------------- bearing and plate
def concrete_bearing(compression: float, centroid: tuple[float, float], N: float, B: float,
                     fc: float, A2_over_A1: float, ed: Edition = CURRENT,
                     method: Method = Method.LRFD, combo: str = "") -> CheckResult:
    """Bearing on concrete with the FEM compression resultant.

    The resultant ``C`` acts at ``centroid`` (from the plate centre). The largest
    rectangular stress block centred on it, (N - 2|x|)(B - 2|y|), is the area that can
    carry it at a uniform pressure, which is compared with 0.85 f'c √(A2/A1) ≤ 1.7 f'c.
    It is the stress block of DG1 placed where the FEM puts the resultant.
    """
    clause = f"{ed.aisc} J8; {ed.guide}"
    c = _calc(method, combo)
    area = c.step("A_{eff}", r"(N - 2|x_C|)(B - 2|y_C|)",
                  max(N - 2 * abs(centroid[0]), 0.0) * max(B - 2 * abs(centroid[1]), 0.0),
                  Kind.AREA, clause, x_C=(centroid[0], Kind.LENGTH), y_C=(centroid[1], Kind.LENGTH))
    demand = c.step("f_{pu}", "C / A_{eff}", compression / area if area else math.inf,
                    Kind.STRESS, clause, C=(compression, Kind.FORCE))
    fp = c.step("f_{p}", r"0.85 f'_c \sqrt{A_2/A_1} \le 1.7 f'_c",
                min(0.85 * fc * math.sqrt(max(A2_over_A1, 1.0)), 1.7 * fc), Kind.STRESS, clause)
    cap = c.available(fp, ed.bearing, Kind.STRESS, clause, "f_p")
    return c.result("fem.concrete_bearing", clause, demand, cap, Kind.STRESS)


def friction(compression: float, area: float, fc: float, demand: float, mu: float,
             ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """Shear transferred by friction under the compression resultant ``C`` of the FEM.

    φ μ C, limited by φ 0.2 f'c Ac; the current guide adds the limit φ (0.8 ksi) Ac
    and uses φ = 0.65 on the friction term and 0.75 on the limits.
    """
    clause = f"{ed.guide}, shear by friction"
    c = _calc(Method.LRFD, combo)
    current = ed.key == "current"
    phi_limit = 0.75 if current else ed.friction_phi
    limits = [ed.friction_phi * mu * max(compression, 0.0), phi_limit * 0.2 * fc * area]
    expr = r"\min[\phi\mu C,\ \phi\,0.2f'_c A_c]"
    if current:
        limits.append(phi_limit * to_internal(0.8, "ksi", Kind.STRESS) * area)
        expr = r"\min[0.65\mu C,\ 0.75(0.2f'_c A_c),\ 0.75(0.8\ ksi)A_c]"
    v = c.step(r"\phi V_n", expr, min(limits), Kind.FORCE, clause,
               mu=(mu, Kind.DIMENSIONLESS), C=(compression, Kind.FORCE), A_c=(area, Kind.AREA))
    return c.result("base_plate.friction", clause, demand, v, Kind.FORCE)


def plate_plastic_strain(strain: float, limit: float = 0.05, combo: str = "",
                         method: Method = Method.LRFD) -> CheckResult:
    """Equivalent plastic strain of the plate against a reference limit (5 % by default)."""
    clause = "FEM criterion (EN 1993-1-5 C.8: 5 %)"
    c = _calc(method, combo)
    c.step(r"\varepsilon_{pl,lim}", "", limit, clause=clause)
    return c.result("fem.plate_plastic_strain", clause, strain, limit, Kind.DIMENSIONLESS)


def plate_bending_tension(T: float, lever: float, width: float, tp: float, Fy: float,
                          ed: Edition = CURRENT, method: Method = Method.LRFD,
                          combo: str = "") -> CheckResult:
    """Plate bending at the tension interface with the FEM rod forces (DG1).

    ``T`` is the total tension of the row, ``lever`` its distance to the centre of the
    flange and ``width`` the plate width resisting it: Mu = T x, φMn = φ Fy b tp² / 4.
    """
    clause = f"{ed.guide} (tension interface); {ed.aisc} F11"
    c = _calc(method, combo)
    mu = c.step("M", "T x", T * lever, Kind.MOMENT, clause, T=(T, Kind.FORCE),
                x=(lever, Kind.LENGTH))
    mn = c.step("M_n", r"F_y \frac{b\,t_p^2}{4}", Fy * width * tp * tp / 4, Kind.MOMENT, clause)
    cap = c.available(mn, ed.flexure, Kind.MOMENT, clause, "M_n")
    return c.result("fem.plate_bending_tension", clause, mu, cap, Kind.MOMENT)


def fillet_weld_line(normal: float, shear: float, size: float, FEXX: float, fillets: int = 2,
                     ed: Edition = CURRENT, method: Method = Method.LRFD,
                     combo: str = "") -> CheckResult:
    """Fillet weld per unit length with the directional strength increase (J2.4).

    ``normal`` (tension positive) and ``shear`` are forces per unit length of wall,
    shared by ``fillets`` welds. Compression is assumed to go in bearing.
    """
    clause = f"{ed.aisc} J2.4"
    c = _calc(method, combo)
    fn, fv = max(normal, 0.0) / fillets, abs(shear) / fillets
    r = c.step("r_u", r"\sqrt{f_n^2 + f_v^2}/n_w", math.hypot(fn, fv), Kind.FORCE_PER_LENGTH,
               clause)
    theta = math.atan2(fn, fv) if r > 0 else 0.0
    kd = c.step("k_{ds}", r"1.0 + 0.50 \sin^{1.5}\theta", 1.0 + 0.5 * math.sin(theta) ** 1.5,
                clause=clause)
    rn = c.step("r_n", r"0.60 F_{EXX}\,k_{ds}\,(0.707 w)", 0.6 * FEXX * kd * size / math.sqrt(2),
                Kind.FORCE_PER_LENGTH, clause)
    cap = c.available(rn, ed.weld, Kind.FORCE_PER_LENGTH, clause, "r_n")
    return c.result("fem.weld", clause, r, cap, Kind.FORCE_PER_LENGTH)


def stiffener_slenderness(width: float, thickness: float, Fy: float, E: float = 200_000.0,
                          ed: Edition = CURRENT, combo: str = "") -> CheckResult:
    """Width-to-thickness ratio of the stiffener outstand, b/t ≤ 0.56 √(E/Fy).

    Limit of plates projecting from rolled shapes (Table B4.1a, case 1); it guards
    against local buckling of the free edge, which the FEM model does not capture.
    """
    clause = f"{ed.aisc} Table B4.1a"
    c = _calc(Method.LRFD, combo)
    limit = c.step(r"\lambda_r", r"0.56\sqrt{E/F_y}", 0.56 * math.sqrt(E / Fy), clause=clause)
    ratio = c.step("b/t", "", width / thickness, clause=clause, b=(width, Kind.LENGTH),
                   t=(thickness, Kind.THICKNESS))
    return c.result("fem.stiffener_slenderness", clause, ratio, limit, Kind.DIMENSIONLESS)


# ------------------------------------------------------------------------------ assembly
def _min_fillet(t: float) -> float:
    """Minimum fillet size for the thinner part joined (AISC 360 Table J2.4) [mm]."""
    t_in = _in(t)
    size = 1 / 8 if t_in <= 1 / 4 else 3 / 16 if t_in <= 1 / 2 else 1 / 4 if t_in <= 3 / 4 \
        else 5 / 16
    return to_internal(size, "in", Kind.LENGTH)


def _tension_group(res: Results) -> list:
    tmax = max((a.tension for a in res.anchors), default=0.0)
    return [a for a in res.anchors if a.tension > max(0.02 * tmax, 1.0)]


def _edges(bp: BasePlate, group: list, model_anchors: list) -> Edges:
    """Edge distances from the outermost anchors of ``group`` to the pedestal faces."""
    if bp.edges.values():
        return bp.edges
    if not (bp.pedestal_N and bp.pedestal_B):
        return concrete_edges(bp)
    xs, ys = [a.x for a in group], [a.y for a in group]
    return Edges(left=bp.pedestal_B / 2 + min(ys), right=bp.pedestal_B / 2 - max(ys),
                 bottom=bp.pedestal_N / 2 + min(xs), top=bp.pedestal_N / 2 - max(xs))


def _not_governing(result: CheckResult) -> CheckResult:
    return result.model_copy(update={"applicable": False})


def _replace_breakout(out: list[CheckResult], breakout_id: str,
                      reinforcement: list[CheckResult]) -> None:
    """Anchor reinforcement and concrete breakout are alternatives: one has to work.

    The one that does not govern is kept in the list, marked as not applicable.
    """
    breakout = next((r for r in out if r.id == breakout_id), None)
    reinforced = all(r.status.value != "ng" for r in reinforcement)
    if breakout is None:
        out.extend(reinforcement)
    elif reinforced:
        out[out.index(breakout)] = _not_governing(breakout)
        out.extend(reinforcement)
    elif breakout.status.value != "ng":
        out.extend(_not_governing(r) for r in reinforcement)
    else:
        out.extend(reinforcement)


def check_fem(bp: BasePlate, res: Results, ed: Edition = CURRENT,
              method: Method = Method.LRFD, *, weld_size: float | None = None,
              strain_limit: float = 0.05, supplementary: bool = False,
              extras: Extras | None = None) -> list[CheckResult]:
    """All FEM-based checks of one solved combination.

    In the plan of the FEM model x runs along the plate length N and y along B, so
    the group spans are passed to the breakout functions as (span along B, span along N).
    """
    extras = extras or Extras()
    combo = res.load
    out: list[CheckResult] = []
    rod = bp.rod
    Fu = rod.material.Fu
    Fy = rod.material.Fy or Fu
    lrfd = method is Method.LRFD
    rebar = extras.pedestal if (bp.pedestal_N and bp.pedestal_B) else None

    # -- concrete bearing and plate
    if res.bearing_force > 0 and res.bearing_area > 0:
        out.append(concrete_bearing(res.bearing_force, res.bearing_centroid, bp.N, bp.B, bp.fc,
                                    bp.A2_over_A1, ed, method, combo))
    out.append(plate_plastic_strain(res.plate_peeq_element, strain_limit, combo, method))

    group = _tension_group(res)
    if group:
        col = bp.column
        if extras.anchors:
            # free layout: each rod bends the plate about the nearest column wall, over
            # a width spread at 45 degrees (DG1) and limited by the plate
            section = section_of(col)
            worst = None
            for a in group:
                lever = max(section.distance(a.x, a.y), 1.0)
                width = min(2 * lever, bp.N, bp.B)
                r = plate_bending_tension(a.tension, lever, width, bp.tp, bp.Fy, ed, method,
                                          combo)
                if worst is None or r.ratio > worst.ratio:
                    worst = r
            out.append(_not_governing(worst) if extras.stiffeners else worst)
        else:
            # rows of rods in tension bend the plate about the nearest flange
            for sign in (-1.0, 1.0):
                row = [a for a in group if a.x * sign > col.d / 2]
                if row:
                    lever = abs(sum(a.x for a in row) / len(row)) - col.d / 2 + col.tf / 2
                    bending = plate_bending_tension(sum(a.tension for a in row), lever, bp.B,
                                                    bp.tp, bp.Fy, ed, method, combo)
                    # with stiffeners the plate no longer cantilevers from the flange:
                    # its bending is judged by the plastic strain of the FEM
                    out.append(_not_governing(bending) if extras.stiffeners else bending)
        tmax = max(a.tension for a in group)
        out.append(anchor_steel_tension(rod.diameter, Fu, Fy, tmax, ed, method, combo))
        if lrfd:
            total = sum(a.tension for a in group)
            xs, ys = [a.x for a in group], [a.y for a in group]
            cx = sum(a.x * a.tension for a in group) / total
            cy = sum(a.y * a.tension for a in group) / total
            ecc = math.hypot(cx - sum(xs) / len(xs), cy - sum(ys) / len(ys))
            edges = _edges(bp, group, res.anchors)
            if bp.hef:
                out.append(anchor_breakout_tension(
                    bp.hef, bp.fc, total, ed, span_x=max(ys) - min(ys), span_y=max(xs) - min(xs),
                    edges=edges, eccentricity=ecc, cracked=bp.cracked,
                    supplementary=supplementary, combo=combo))
                if rebar is not None:
                    _replace_breakout(out, "anchor.concrete_breakout_tension",
                                      ped.anchor_reinforcement_tension(
                                          total, [(a.x, a.y) for a in group], rebar,
                                          bp.pedestal_N, bp.pedestal_B, bp.hef, bp.fc,
                                          ed.anchor("reinf_t"), combo))
            area = bp.bearing_area or heavy_hex_bearing_area(rod.diameter)
            out.append(anchor_pullout(area, bp.fc, tmax, ed, bp.cracked, combo))
            ca1 = min(edges.values(), default=None)
            if ca1 and bp.hef:
                blow = anchor_side_face_blowout(ca1, area, bp.fc, tmax, bp.hef, ed, combo=combo)
                if blow.applicable:
                    out.append(blow)

    # -- shear
    V = math.hypot(res.applied["Vx"], res.applied["Vy"]) * res.load_fraction
    if V > 0:
        rod_v = max(math.hypot(a.Vx, a.Vy) for a in res.anchors)
        by_rods = sum(math.hypot(a.Vx, a.Vy) for a in res.anchors)
        if by_rods > 0.05 * V:
            out.append(anchor_steel_shear(rod.diameter, Fu, Fy, rod_v, ed, method, bp.grout_pad,
                                          combo))
            if lrfd and bp.hef:
                every = res.anchors
                xs, ys = [a.x for a in every], [a.y for a in every]
                all_edges = _edges(bp, every, every)
                whole = anchor_breakout_tension(
                    bp.hef, bp.fc, 0.0, ed, span_x=max(ys) - min(ys), span_y=max(xs) - min(xs),
                    edges=all_edges, cracked=bp.cracked, combo=combo)
                ncbg = next(s.value for s in reversed(whole.steps) if s.symbol == "N_{cbg}")
                out.append(anchor_pryout(ncbg, bp.hef, by_rods, ed, combo))
                # breakout towards the edge the shear pushes to, measured from the far
                # row because welded washers make every rod work
                vx, vy = (abs(sum(a.Vx for a in every)), abs(sum(a.Vy for a in every)))
                if bp.pedestal_N and bp.pedestal_B:
                    cases = []
                    if vx > 0.05 * V:
                        back = min(xs) if res.applied["Vx"] > 0 else -max(xs)
                        cases.append((vx, bp.pedestal_N / 2 - back, max(ys) - min(ys),
                                      (all_edges.left, all_edges.right)))
                    if vy > 0.05 * V:
                        back = min(ys) if res.applied["Vy"] > 0 else -max(ys)
                        cases.append((vy, bp.pedestal_B / 2 - back, max(xs) - min(xs),
                                      (all_edges.bottom, all_edges.top)))
                    for v, ca1, spacing, ca2 in cases:
                        out.append(anchor_breakout_shear(
                            rod.diameter, bp.hef, ca1, bp.fc, v, ed, spacing=spacing, ca2=ca2,
                            cracked=bp.cracked, combo=combo))
                    if rebar is not None and cases:
                        _replace_breakout(out, "anchor.concrete_breakout_shear",
                                          [ped.anchor_reinforcement_shear(
                                              by_rods, rebar, ed.anchor("reinf_v"), combo)])
        if lrfd and by_rods < 0.95 * V:
            fx, fy = res.friction
            out.append(friction(res.bearing_force, res.bearing_area, bp.fc, math.hypot(fx, fy),
                                bp.friction_mu, ed, combo))
        if lrfd:
            tension = [r.ratio for r in out if r.applicable and r.id in (
                "anchor.steel_tension", "anchor.concrete_breakout_tension", "anchor.pullout",
                "anchor.side_face_blowout", "anchor.reinforcement")]
            shear = [r.ratio for r in out if r.applicable and r.id in (
                "anchor.steel_shear", "anchor.concrete_breakout_shear", "anchor.pryout",
                "anchor.reinforcement_shear")]
            if tension and shear:
                out.append(anchor_interaction(max(tension), max(shear), ed, combo))

    # -- pedestal
    if rebar is not None and lrfd:
        f = res.load_fraction
        a = res.applied
        out.append(ped.section_check(
            a["P"], abs(a["Mx"]) * f + abs(a["Vy"]) * f * rebar.height,
            abs(a["My"]) * f + abs(a["Vx"]) * f * rebar.height, rebar, bp.pedestal_N,
            bp.pedestal_B, bp.fc, ed.anchor("col_pm"), combo))
        out.append(ped.minimum_reinforcement(rebar, bp.pedestal_N, bp.pedestal_B,
                                             ed.anchor("col_min"), combo))

    # -- weld between column and plate
    if res.weld:
        fexx = (bp.electrodes[bp.electrode] if bp.electrode in bp.electrodes
                else ELECTRODES[bp.electrode]).FEXX
        fillets = 2 if hasattr(bp.column, "k_des") else 1
        worst = None
        for w in res.weld:
            size = weld_size or bp.flange_weld or _min_fillet(min(w.thickness, bp.tp))
            r = fillet_weld_line(w.normal, w.shear, size, fexx, fillets, ed, method, combo)
            if worst is None or r.ratio > worst.ratio:
                worst = r
        if worst is not None:
            out.append(worst)
    # -- stiffeners
    spec = extras.stiffeners
    if spec is not None and res.stiffener_weld:
        steel = bp.materials[spec.grade]
        strain = plate_plastic_strain(res.stiffener_peeq_element, strain_limit, combo, method)
        out.append(strain.model_copy(update={"id": "fem.stiffener_plastic_strain",
                                             "text_id": "check.fem.stiffener_plastic_strain"}))
        out.append(stiffener_slenderness(spec.length, spec.thickness, steel.Fy, steel.E, ed,
                                         combo))
        fexx = (bp.electrodes[bp.electrode] if bp.electrode in bp.electrodes
                else ELECTRODES[bp.electrode]).FEXX
        size = spec.weld or _min_fillet(spec.thickness)
        worst = None
        for w in res.stiffener_weld:
            r = fillet_weld_line(w.normal, w.shear, size, fexx, 2, ed, method, combo)
            if worst is None or r.ratio > worst.ratio:
                worst = r
        out.append(worst.model_copy(update={"id": "fem.stiffener_weld",
                                            "text_id": "check.fem.stiffener_weld"}))
    return out
