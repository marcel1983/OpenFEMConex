# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Checks of the reinforced concrete pedestal (ACI 318).

* longitudinal bars as anchor reinforcement in tension and ties as anchor
  reinforcement in shear, which replace the concrete breakout checks;
* combined axial force and bending of the pedestal section;
* minimum longitudinal reinforcement.
"""

from __future__ import annotations

import math

from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.kernel.anchors import hooked_bar_ldh, straight_bar_ld
from openconex.kernel.design import Calc, Resistance
from openconex.units import Kind

from openfemconex.extras import PedestalRebar

__all__ = ["anchor_reinforcement_shear", "anchor_reinforcement_tension", "interaction_point",
           "minimum_reinforcement", "section_capacity", "section_check"]

ANCHOR_REINFORCEMENT = Resistance(0.75, math.nan)
ES = 200_000.0
ECU = 0.003


def minimum_reinforcement(rebar: PedestalRebar, N: float, B: float, clause: str,
                          combo: str = "") -> CheckResult:
    """Longitudinal steel of at least 0.01 Ag."""
    c = Calc(Method.LRFD, combo)
    ag = c.step("A_g", "N_p B_p", N * B, Kind.AREA, clause)
    ast = c.step("A_{st}", r"n \pi d_b^2 / 4", rebar.bars * rebar.bar_area, Kind.AREA, clause)
    need = c.step("A_{st,min}", "0.01 A_g", 0.01 * ag, Kind.AREA, clause)
    return c.result("pedestal.min_reinforcement", clause, need, ast, Kind.AREA)


def anchor_reinforcement_tension(demand: float, anchors: list[tuple[float, float]],
                                 rebar: PedestalRebar, N: float, B: float, hef: float,
                                 fc: float, clause: str, combo: str = "") -> list[CheckResult]:
    """Longitudinal bars within 0.5 hef of the anchors in tension: φ As fy with φ = 0.75.

    Returns the strength check and the development of the bars above the breakout
    surface: ``hef - cover - g/1.5`` must reach l_dh (hooked) or l_d (straight), where
    ``g`` is the largest distance from a counted bar to its nearest anchor.
    """
    bars = rebar.positions(N, B)
    near = []
    for bx, by in bars:
        g = min(math.hypot(bx - ax, by - ay) for ax, ay in anchors)
        if g <= 0.5 * hef:
            near.append(g)
    c = Calc(Method.LRFD, combo)
    n = c.step("n", r"\text{bars within } 0.5 h_{ef}", float(len(near)), clause=clause)
    area = c.step("A_s", "n A_b", n * rebar.bar_area, Kind.AREA, clause)
    rn = c.step("N_n", "A_s f_y", area * rebar.fy, Kind.FORCE, clause)
    cap = c.available(rn, ANCHOR_REINFORCEMENT, Kind.FORCE, clause, "N_n")
    strength = c.result("anchor.reinforcement", clause, demand, cap, Kind.FORCE)

    c = Calc(Method.LRFD, combo)
    g = c.step("g", r"\max \text{ anchor-bar distance}", max(near, default=0.0), Kind.LENGTH,
               clause)
    top_cover = rebar.cover + rebar.tie_diameter
    available = c.step("l_{disp}", r"h_{ef} - c_c - \frac{g}{1.5}",
                       max(hef - top_cover - g / 1.5, 0.0), Kind.LENGTH, clause)
    if rebar.hooked:
        need = c.step("l_{dh}", r"\frac{f_y \psi_c}{55\sqrt{f'_c}} d_b^{1.5}",
                      hooked_bar_ldh(rebar.fy, fc, rebar.bar_diameter).ldh, Kind.LENGTH,
                      "ACI 318-19 Eq. 25.4.3.1a")
    else:
        need = c.step("l_d", r"\frac{3}{40}\frac{f_y\psi_t\psi_e\psi_s\psi_g}{\lambda\sqrt{f'_c}}"
                      r"\frac{d_b}{(c_b+K_{tr})/d_b}",
                      straight_bar_ld(rebar.fy, fc, rebar.bar_diameter,
                                      top_cover + rebar.bar_diameter / 2).ld, Kind.LENGTH,
                      "ACI 318-19 Eq. 25.4.2.4a")
    development = c.result("anchor.reinforcement_development", clause, need, available,
                           Kind.LENGTH)
    return [strength, development]


def anchor_reinforcement_shear(demand: float, rebar: PedestalRebar, clause: str,
                               combo: str = "") -> CheckResult:
    """Top ties enclosing the anchors as anchor reinforcement in shear: φ n Av fy, φ = 0.75."""
    c = Calc(Method.LRFD, combo)
    area = c.step("A_v", r"n_{ties}\, n_{legs}\, A_b",
                  rebar.top_ties * rebar.tie_legs * rebar.tie_area, Kind.AREA, clause)
    rn = c.step("V_n", "A_v f_y", area * rebar.fy, Kind.FORCE, clause)
    cap = c.available(rn, ANCHOR_REINFORCEMENT, Kind.FORCE, clause, "V_n")
    return c.result("anchor.reinforcement_shear", clause, demand, cap, Kind.FORCE)


# ------------------------------------------------------------------ section strength
def _beta1(fc: float) -> float:
    return min(0.85, max(0.65, 0.85 - 0.05 * (fc - 27.58) / 6.895))


def interaction_point(c: float, depth: float, width: float, bars: list[float], area: float,
                      fc: float, fy: float) -> tuple[float, float, float]:
    """(φPn, φMn, φ) for a neutral axis depth ``c`` from the compressed face.

    ``bars`` are the bar coordinates along the bending direction (0 at the section
    centre, positive towards the compressed face). Tied section, ACI 318-19 Table 21.2.2.
    """
    a = min(_beta1(fc) * c, depth)
    pn = 0.85 * fc * a * width
    mn = pn * (depth / 2 - a / 2)
    et = 0.0
    for x in bars:
        d_i = depth / 2 - x  # distance from the compressed face
        strain = ECU * (c - d_i) / c
        stress = max(-fy, min(fy, ES * strain))
        if d_i < a and stress > 0:
            stress -= 0.85 * fc  # concrete displaced by the bar
        pn += stress * area
        mn += stress * area * x
        et = max(et, -strain)
    ety = fy / ES
    phi = 0.65 if et <= ety else min(0.90, 0.65 + 0.25 * (et - ety) / 0.003)
    return phi * pn, phi * mn, phi


def section_capacity(P: float, depth: float, width: float, bars: list[float], area: float,
                     fc: float, fy: float) -> tuple[float, float]:
    """(φMn at the axial force ``P``, φPn,max) of the tied rectangular section.

    ``P`` is positive in compression. φMn is zero when ``P`` is outside the diagram.
    """
    ast = area * len(bars)
    pn_max = 0.65 * 0.80 * (0.85 * fc * (depth * width - ast) + fy * ast)
    points = []
    for k in range(1, 400):
        c = depth * 3.0 * k / 400
        p, m, _ = interaction_point(c, depth, width, bars, area, fc, fy)
        points.append((min(p, pn_max), m))
    points.insert(0, (-0.90 * fy * ast, 0.0))
    if P > pn_max or P < points[0][0]:
        return 0.0, pn_max
    best = 0.0
    for (p0, m0), (p1, m1) in zip(points, points[1:], strict=False):
        lo, hi = min(p0, p1), max(p0, p1)
        if lo <= P <= hi:
            t = 0.0 if hi == lo else (P - p0) / (p1 - p0)
            best = max(best, m0 + t * (m1 - m0))
    return best, pn_max


def section_check(P: float, Mx: float, My: float, rebar: PedestalRebar, N: float, B: float,
                  fc: float, clause: str, combo: str = "") -> CheckResult:
    """Axial force with biaxial bending of the pedestal, Mx/φMnx + My/φMny ≤ 1.

    ``My`` bends about the y axis (depth N), ``Mx`` about x (depth B). The linear sum
    is a conservative form of the load contour method.
    """
    bars = rebar.positions(N, B)
    c = Calc(Method.LRFD, combo)
    mny, pmax = section_capacity(P, N, B, [x for x, _ in bars], rebar.bar_area, fc, rebar.fy)
    mnx, _ = section_capacity(P, B, N, [y for _, y in bars], rebar.bar_area, fc, rebar.fy)
    c.step(r"\phi P_{n,max}", r"0.65 \cdot 0.80 [0.85 f'_c (A_g - A_{st}) + f_y A_{st}]", pmax,
           Kind.FORCE, clause)
    c.step("P_u", "", P, Kind.FORCE, clause)
    c.step(r"\phi M_{ny}", r"\text{strain compatibility at } P_u", mny, Kind.MOMENT, clause)
    c.step(r"\phi M_{nx}", r"\text{strain compatibility at } P_u", mnx, Kind.MOMENT, clause)
    c.step("M_{uy}", "", abs(My), Kind.MOMENT, clause)
    c.step("M_{ux}", "", abs(Mx), Kind.MOMENT, clause)
    if mny <= 0 or mnx <= 0:
        value = max(P / pmax, 1.01) if P > 0 else math.inf
    else:
        value = max(abs(My) / mny + abs(Mx) / mnx, P / pmax if P > 0 else 0.0)
    value = c.step("", r"\frac{M_{ux}}{\phi M_{nx}} + \frac{M_{uy}}{\phi M_{ny}}", value,
                   clause=clause)
    return c.result("pedestal.flexure_axial", clause, value, 1.0, Kind.DIMENSIONLESS)
