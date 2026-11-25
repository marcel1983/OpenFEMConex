# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Recommendations for the checks that do not pass.

For every failed check, what to change among the parameters of the project. Where
the capacity has a closed form the minimum value is given (embedment, plate
thickness, rod diameter, weld size, reinforcement area); the checks that come from
the FEM model (plastic strain, contact) get qualitative advice, since changing a
parameter changes the whole solution. The values are estimates for one parameter
at a time: solve again after changing them.
"""

from __future__ import annotations

import math

from openconex.connections.base_plate.check import BasePlate
from openconex.core.checks import CheckResult
from openconex.core.materials import BOLTS
from openconex.report.builder import fmt
from openconex.units import Kind, UnitSystem

from openfemconex.checks import (
    CURRENT,
    Edition,
    _edges,
    _tension_group,
    anchor_breakout_tension,
    anchor_steel_shear,
    anchor_steel_tension,
)
from openfemconex.extras import Extras
from openfemconex.i18n import tr
from openfemconex.results import Results

__all__ = ["advise"]

ROD_DIAMETERS_IN = (0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.375, 1.5, 1.75, 2.0, 2.25,
                    2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0)
IN = 25.4


def _round_up(value: float, units: UnitSystem, kind: Kind) -> float:
    """Round a length up to a practical step: 1/8 in. or 1 mm (thickness), 5 mm (length)."""
    unit = units.thickness if kind is Kind.THICKNESS else units.length
    if "in" in unit or "ft" in unit:
        step = IN / 16 if kind is Kind.THICKNESS else IN / 8
    else:
        step = 1.0 if kind is Kind.THICKNESS else 5.0
    return math.ceil(value / step - 1e-9) * step


def _rod_alternatives(check: CheckResult, bp: BasePlate, ed: Edition, shear: bool,
                      units: UnitSystem) -> list[str]:
    """Smallest standard diameter, and a stronger grade of the same diameter, that pass."""
    out = []
    rod = bp.rod
    current = rod.material
    fn = anchor_steel_shear if shear else anchor_steel_tension
    for d_in in ROD_DIAMETERS_IN:
        d = d_in * IN
        if d <= rod.diameter + 1e-6:
            continue
        cap = fn(d, current.Fu, current.Fy or current.Fu, 0.0, ed).capacity
        if cap >= abs(check.demand):
            out.append(tr("Aumentar el diámetro del anclaje a {d} ({grade}).",
                          d=fmt(d, Kind.LENGTH, units), grade=rod.grade))
            break
    for name, grade in BOLTS.items():
        if "F1554" not in name or grade.Fu <= current.Fu:
            continue
        cap = fn(rod.diameter, grade.Fu, grade.Fy or grade.Fu, 0.0, ed).capacity
        if cap >= abs(check.demand):
            out.append(tr("O usar un grado más resistente con el mismo diámetro: {grade}.",
                          grade=name))
            break
    return out


def _breakout_hef(bp: BasePlate, res: Results, ed: Edition, demand: float,
                  units: UnitSystem) -> str | None:
    """Embedment that makes the group breakout pass (same layout and edges)."""
    group = _tension_group(res)
    if not group or not bp.hef:
        return None
    total = sum(a.tension for a in group)
    xs, ys = [a.x for a in group], [a.y for a in group]
    cx = sum(a.x * a.tension for a in group) / total
    cy = sum(a.y * a.tension for a in group) / total
    ecc = math.hypot(cx - sum(xs) / len(xs), cy - sum(ys) / len(ys))
    edges = _edges(bp, group, res.anchors)
    hef = bp.hef
    while hef < 25 * IN:
        hef += IN / 2
        cap = anchor_breakout_tension(hef, bp.fc, 0.0, ed, span_x=max(ys) - min(ys),
                                      span_y=max(xs) - min(xs), edges=edges, eccentricity=ecc,
                                      cracked=bp.cracked).capacity
        if cap >= demand:
            return tr("Aumentar el empotramiento hef a {h} como mínimo.",
                      h=fmt(_round_up(hef, units, Kind.LENGTH), Kind.LENGTH, units))
    return tr("Aumentar hef no basta con los bordes actuales (hasta 25 in.): use refuerzo de "
              "anclaje o un pedestal mayor.")


def _anchor_reinforcement(demand: float, fy: float, units: UnitSystem) -> str:
    area = demand / (0.75 * fy)
    return tr("O agregar refuerzo de anclaje (barras del pedestal a menos de 0.5·hef u "
              "horquillas en U) con As ≥ {a}, desarrollado a ambos lados del cono; así el "
              "arrancamiento deja de regir.", a=fmt(area, Kind.AREA, units))


def _one(check: CheckResult, bp: BasePlate, res: Results, ed: Edition, units: UnitSystem,
         extras: Extras) -> list[str]:
    ratio = check.ratio / (check.ratio_limit or 1.0)
    cid = check.id
    out: list[str] = []
    if cid == "anchor.steel_tension":
        out += _rod_alternatives(check, bp, ed, False, units)
        out.append(tr("O agregar anclajes para repartir la tracción."))
    elif cid == "anchor.steel_shear":
        out += _rod_alternatives(check, bp, ed, True, units)
        out.append(tr("O tomar el cortante con una llave de cortante o por fricción (sin "
                      "arandelas soldadas)."))
    elif cid == "anchor.concrete_breakout_tension":
        hef = _breakout_hef(bp, res, ed, check.demand, units)
        if hef:
            out.append(hef)
        out.append(tr("O separar más los anclajes o alejarlos de los bordes del pedestal."))
        fy = extras.pedestal.fy if extras.pedestal else 420.0
        out.append(_anchor_reinforcement(check.demand, fy, units))
    elif cid == "anchor.pullout":
        need = next((s.value for s in check.steps if s.symbol == "N_p"), 0.0) * ratio
        area = need / (8 * bp.fc) if bp.fc else 0.0
        side = math.sqrt(area + math.pi * bp.rod.diameter**2 / 4)
        out.append(tr("Aumentar el área de apoyo de la cabeza embebida a {a} (por ejemplo, una "
                      "placa de {s} × {s} bajo la tuerca).", a=fmt(area, Kind.AREA, units),
                      s=fmt(_round_up(side, units, Kind.LENGTH), Kind.LENGTH, units)))
        out.append(tr("O usar un diámetro de anclaje mayor (tuerca más grande)."))
    elif cid == "anchor.side_face_blowout":
        out.append(tr("Alejar los anclajes del borde lateral o agrandar el pedestal; también "
                      "puede reducirse hef para que no supere 2.5 veces la distancia al borde."))
    elif cid == "anchor.concrete_breakout_shear":
        out.append(tr("Aumentar la distancia al borde en la dirección del cortante "
                      "(pedestal más grande) o el espesor del pedestal."))
        out.append(tr("O agregar estribos superiores como refuerzo de anclaje a cortante con "
                      "Av ≥ {a}.", a=fmt(check.demand / (0.75 * 420.0), Kind.AREA, units)))
        out.append(tr("O tomar el cortante con una llave de cortante."))
    elif cid == "anchor.pryout":
        h = bp.hef * ratio ** (1 / 1.5)
        out.append(tr("Aumentar el empotramiento hef a {h} aproximadamente, o separar más los "
                      "anclajes.", h=fmt(_round_up(h, units, Kind.LENGTH), Kind.LENGTH, units)))
    elif cid == "anchor.interaction":
        out.append(tr("Bajar la mayor de las dos relaciones (tracción o cortante) con las "
                      "recomendaciones de su verificación; la suma debe quedar en 1.2 o menos."))
    elif cid == "anchor.combined_bending":
        d = bp.rod.diameter * ratio ** 0.4
        d_in = next((x for x in ROD_DIAMETERS_IN if x * IN >= d), ROD_DIAMETERS_IN[-1])
        out.append(tr("Aumentar el diámetro del anclaje a {d} aproximadamente.",
                      d=fmt(d_in * IN, Kind.LENGTH, units)))
        out.append(tr("O reducir el brazo de flexión: placa más delgada o arandela soldada "
                      "más delgada, o tomar el cortante con una llave."))
    elif cid == "fem.concrete_bearing":
        out.append(tr("Agrandar la placa: con el mismo largo N, el ancho B debería ser de {b} "
                      "aproximadamente.", b=fmt(_round_up(bp.B * ratio, units, Kind.LENGTH),
                                                Kind.LENGTH, units)))
        a2 = min(ratio**2 * max(bp.A2_over_A1, 1.0), 4.0)
        if a2 > bp.A2_over_A1 + 0.01:
            out.append(tr("O un pedestal mayor que la placa (A2/A1 = {r}, máximo 4).",
                          r=f"{a2:.2f}"))
        out.append(tr("O un concreto de f'c = {fc}.",
                      fc=fmt(bp.fc * ratio, Kind.STRESS, units)))
    elif cid == "fem.plate_bending_tension":
        tp = _round_up(bp.tp * math.sqrt(ratio), units, Kind.THICKNESS)
        out.append(tr("Aumentar el espesor de la placa a {t}.",
                      t=fmt(tp, Kind.THICKNESS, units)))
        out.append(tr("O acercar los anclajes a la columna, o agregar rigidizadores."))
    elif cid == "fem.plate_plastic_strain":
        out.append(tr("Aumentar el espesor de la placa (la deformación plástica baja rápido "
                      "con el espesor) o agregar rigidizadores; vuelva a resolver."))
    elif cid in ("fem.weld", "fem.stiffener_weld", "base_plate.lug_weld"):
        size = next((s.value for s in check.steps if s.symbol == "w"), None)
        if cid == "fem.weld":
            size = size or bp.flange_weld
        if cid == "fem.stiffener_weld" and extras.stiffeners:
            size = size or extras.stiffeners.weld
        if size:
            out.append(tr("Aumentar el tamaño del filete a {w}.", w=fmt(
                _round_up(size * ratio, units, Kind.THICKNESS), Kind.THICKNESS, units)))
        else:
            out.append(tr("Aumentar el tamaño del filete en proporción {r} (o usar soldadura de "
                          "penetración completa).", r=f"{ratio:.2f}"))
        out.append(tr("O un electrodo más resistente (E80XX)."))
    elif cid == "fem.stiffener_slenderness" and extras.stiffeners:
        out.append(tr("Aumentar el espesor del rigidizador a {t} o acortar su largo.", t=fmt(
            _round_up(extras.stiffeners.thickness * ratio, units, Kind.THICKNESS),
            Kind.THICKNESS, units)))
    elif cid == "fem.stiffener_plastic_strain":
        out.append(tr("Rigidizadores más gruesos o más altos; vuelva a resolver."))
    elif cid == "base_plate.friction":
        out.append(tr("Agregar una llave de cortante, o arandelas soldadas para que los "
                      "anclajes tomen el cortante."))
    elif cid in ("anchor.reinforcement",):
        fy = (extras.pedestal or extras.hairpins).fy if (extras.pedestal or extras.hairpins) \
            else 420.0
        out.append(tr("Aumentar el refuerzo de anclaje a As ≥ {a} (más barras a menos de "
                      "0.5·hef, más horquillas o de mayor diámetro).",
                      a=fmt(check.demand / (0.75 * fy), Kind.AREA, units)))
    elif cid in ("anchor.reinforcement_development", "anchor.hairpin_development_top"):
        short = check.demand - check.capacity
        out.append(tr("Falta largo de desarrollo sobre el cono: aumentar hef en {d} como mínimo, "
                      "usar barras más delgadas o con gancho.",
                      d=fmt(_round_up(short, units, Kind.THICKNESS), Kind.THICKNESS, units)))
    elif cid == "anchor.hairpin_development_bottom":
        short = _round_up(check.demand - check.capacity, units, Kind.THICKNESS)
        out.append(tr("Alargar las patas de las horquillas en {d} como mínimo.",
                      d=fmt(short, Kind.THICKNESS, units)))
    elif cid == "anchor.reinforcement_shear":
        out.append(tr("Más estribos superiores, más ramas o de mayor diámetro: Av ≥ {a}.",
                      a=fmt(check.demand / (0.75 * (extras.pedestal.fy if extras.pedestal
                                                    else 420.0)), Kind.AREA, units)))
    elif cid == "pedestal.flexure_axial":
        out.append(tr("Más barras longitudinales o de mayor diámetro, o un pedestal mayor."))
    elif cid == "pedestal.min_reinforcement" and extras.pedestal:
        n = math.ceil(check.demand / extras.pedestal.bar_area)
        out.append(tr("Usar al menos {n} barras del diámetro actual (1 % del área).", n=n))
    elif cid.startswith("base_plate.lug"):
        out.append(tr("Aumentar el espesor, el ancho o el empotramiento de la llave de "
                      "cortante, según el estado límite."))
    if not out:
        out.append(tr("Revise los datos de este componente; la relación es {r}.",
                      r=f"{check.ratio:.2f}"))
    return out


def advise(bp: BasePlate, res: Results, checks: list[CheckResult], units: UnitSystem,
           ed: Edition = CURRENT, extras: Extras | None = None) -> dict[str, list[str]]:
    """Recommendations for every applicable check that does not pass, by check id."""
    extras = extras or Extras()
    out: dict[str, list[str]] = {}
    for check in checks:
        if not check.applicable or check.status.value != "ng" or check.id in out:
            continue
        try:
            out[check.id] = _one(check, bp, res, ed, units, extras)
        except Exception:  # advice must never break the report
            out[check.id] = [tr("Revise los datos de este componente; la relación es {r}.",
                                r=f"{check.ratio:.2f}")]
    return out
