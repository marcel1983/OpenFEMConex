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

from openfemconex.extras import Hairpins, PedestalRebar
from openfemconex.i18n import tr

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


def _development(c: Calc, fy: float, fc: float, db: float, hooked: bool, cover: float,
                 clause: str) -> float:
    if hooked:
        return c.step("l_{dh}", r"\frac{f_y \psi_c}{55\sqrt{f'_c}} d_b^{1.5}",
                      hooked_bar_ldh(fy, fc, db).ldh, Kind.LENGTH, "ACI 318-19 Eq. 25.4.3.1a")
    return c.step("l_d", r"\frac{3}{40}\frac{f_y\psi_t\psi_e\psi_s\psi_g}{\lambda\sqrt{f'_c}}"
                  r"\frac{d_b}{(c_b+K_{tr})/d_b}",
                  straight_bar_ld(fy, fc, db, cover + db / 2).ld, Kind.LENGTH,
                  "ACI 318-19 Eq. 25.4.2.4a")


def anchor_reinforcement_tension(demand: float, anchors: list[tuple[float, float]],
                                 rebar: PedestalRebar | None, N: float, B: float, hef: float,
                                 fc: float, clause: str, combo: str = "",
                                 hairpins: Hairpins | None = None) -> list[CheckResult]:
    """Anchor reinforcement in tension: bars within 0.5 hef of the anchors, φ As fy, φ = 0.75.

    Two kinds of bars count: the longitudinal bars of the pedestal (``rebar``) and the
    legs of hairpins placed over the anchors (``hairpins``). Besides the strength, each
    kind must be developed on both sides of the breakout surface (ACI 318-19
    §17.5.2.1): above it, ``hef - cover - g/1.5`` against l_dh (hook or the bend of the
    hairpin) or l_d; below it, the rest of the hairpin leg against l_d. ``g`` is the
    largest distance from a counted bar to its anchor.
    """
    bars = rebar.positions(N, B) if rebar is not None else []
    legs = hairpins.legs(anchors) if hairpins is not None else []

    def counted(points):
        out = []
        for bx, by in points:
            g = min(math.hypot(bx - ax, by - ay) for ax, ay in anchors)
            if g <= 0.5 * hef:
                out.append(g)
        return out

    near_bars, near_legs = counted(bars), counted(legs)
    closest = min((math.hypot(bx - ax, by - ay) for bx, by in bars + legs
                   for ax, ay in anchors), default=math.inf)
    c = Calc(Method.LRFD, combo)
    c.step(r"g_{min}", r"\text{" + tr("barra más cercana a un anclaje en tracción") + "}",
           closest, Kind.LENGTH, clause)
    c.step(r"0.5\,h_{ef}", r"\text{" + tr("distancia máxima para contar una barra") + "}",
           0.5 * hef, Kind.LENGTH, clause)
    area = 0.0
    fy_area = 0.0
    if rebar is not None:
        n = c.step("n", r"\text{" + tr("barras con") + r"} g \le 0.5\,h_{ef}",
                   float(len(near_bars)), clause=clause)
        area_bars = c.step("A_{s,b}", "n A_b", n * rebar.bar_area, Kind.AREA, clause)
        area += area_bars
        fy_area += area_bars * rebar.fy
    if hairpins is not None:
        n = c.step("n_h", r"\text{" + tr("patas de horquilla con") + r"} g \le 0.5\,h_{ef}",
                   float(len(near_legs)), clause=clause)
        area_legs = c.step("A_{s,h}", "n_h A_b", n * hairpins.bar_area, Kind.AREA, clause)
        area += area_legs
        fy_area += area_legs * hairpins.fy
    rn = c.step("N_n", r"\sum A_s f_y", fy_area, Kind.FORCE, clause)
    cap = c.available(rn, ANCHOR_REINFORCEMENT, Kind.FORCE, clause, "N_n")
    any_bar = bool(near_bars or near_legs)
    out = [c.result("anchor.reinforcement", clause, demand, cap, Kind.FORCE,
                    applicable=any_bar)]
    if rebar is not None and (near_bars or not any_bar):
        c = Calc(Method.LRFD, combo)
        g = c.step("g", r"\max \text{ " + tr("distancia anclaje-barra contada") + "}",
                   max(near_bars, default=0.0), Kind.LENGTH, clause)
        top_cover = rebar.cover + rebar.tie_diameter
        available = c.step("l_{disp}", r"h_{ef} - c_c - \frac{g}{1.5}",
                           max(hef - top_cover - g / 1.5, 0.0), Kind.LENGTH, clause)
        if rebar.hooked:
            # the same development length for 90° and 180° standard hooks (§25.4.3)
            c.step(r"\text{hook}", f"{rebar.hook}^\\circ", float(rebar.hook),
                   clause="ACI 318-19 Table 25.3.1")
        need = _development(c, rebar.fy, fc, rebar.bar_diameter, rebar.hooked, top_cover,
                            clause)
        out.append(c.result("anchor.reinforcement_development", clause, need, available,
                            Kind.LENGTH, applicable=bool(near_bars)))
    if hairpins is not None and (near_legs or not any_bar):
        h = hairpins
        g = max(near_legs, default=h.offset)
        cone = max(hef - h.cover - g / 1.5, 0.0)  # leg length from the bend to the cone
        c = Calc(Method.LRFD, combo)
        c.step("g", r"\text{" + tr("distancia anclaje-pata") + "}", g, Kind.LENGTH, clause)
        available = c.step("l_{disp}", r"h_{ef} - c_c - \frac{g}{1.5}", cone, Kind.LENGTH,
                           clause)
        # the bend of the hairpin anchors it above the cone like a standard hook
        need = _development(c, h.fy, fc, h.diameter, True, h.cover, clause)
        out.append(c.result("anchor.hairpin_development_top", clause, need, available,
                            Kind.LENGTH, applicable=bool(near_legs)))
        c = Calc(Method.LRFD, combo)
        below = c.step("l_{inf}", r"L_{pata} - (h_{ef} - c_c - \frac{g}{1.5})",
                       max(h.leg_length - cone, 0.0), Kind.LENGTH, clause)
        need = _development(c, h.fy, fc, h.diameter, False, h.cover, clause)
        out.append(c.result("anchor.hairpin_development_bottom", clause, need, below,
                            Kind.LENGTH, applicable=bool(near_legs)))
    return out


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
