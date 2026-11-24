# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Checks of a model before it is solved: situations where CalculiX cannot converge.

They do not stop the analysis; they explain in advance why it may not finish.
"""

from __future__ import annotations

import math

from openfemconex.i18n import tr
from openfemconex.model import BasePlateModel, Loads, SectionKind

__all__ = ["COLLAPSE", "HOPELESS", "column_capacity", "column_usage", "diagnose"]

COLLAPSE = 1.5
"""Plastic usage of the column stub (with the conservative linear interaction) above
which the stub cannot carry the loads: stiffeners or strain hardening may still carry
a usage a little above 1, as the examples show."""
HOPELESS = 2.0
"""Usage above which the analysis is not even started: the column stub would carry
less than half the load and the solver would only spend time cutting increments."""


def column_capacity(model: BasePlateModel) -> dict[str, float]:
    """Plastic capacities of the modelled column stub (nominal, no φ): A, Py, Vpx, Vpy, Mpx, Mpy.

    x is the axis along the depth d: Vpx resists the shear along x and Mpy the moment
    about y (strong axis of an I-shape).
    """
    s, Fy = model.section, model.column_steel.Fy
    if s.kind is SectionKind.HSS_ROUND:
        d, t = s.d, s.t
        area = math.pi / 4 * (d**2 - (d - 2 * t) ** 2)
        z = (d**3 - (d - 2 * t) ** 3) / 6
        v = 0.6 * Fy * area / 2
        return {"A": area, "Py": Fy * area, "Vpx": v, "Vpy": v, "Mpx": Fy * z, "Mpy": Fy * z}
    if s.kind is SectionKind.HSS_RECT:
        d, b, t = s.d, s.bf, s.t
        area = d * b - (d - 2 * t) * (b - 2 * t)
        zy = (b * d**2 - (b - 2 * t) * (d - 2 * t) ** 2) / 4
        zx = (d * b**2 - (d - 2 * t) * (b - 2 * t) ** 2) / 4
        return {"A": area, "Py": Fy * area, "Vpx": 0.6 * Fy * 2 * t * (d - 2 * t),
                "Vpy": 0.6 * Fy * 2 * t * (b - 2 * t), "Mpx": Fy * zx, "Mpy": Fy * zy}
    d, b, tf, tw = s.d, s.bf, s.tf, s.tw
    area = 2 * b * tf + (d - 2 * tf) * tw
    zy = b * tf * (d - tf) + tw * (d - 2 * tf) ** 2 / 4
    zx = 2 * tf * b**2 / 4 + (d - 2 * tf) * tw**2 / 4
    return {"A": area, "Py": Fy * area, "Vpx": 0.6 * Fy * d * tw, "Vpy": 0.6 * Fy * 2 * b * tf,
            "Mpx": Fy * zx, "Mpy": Fy * zy}


def column_usage(model: BasePlateModel, loads: Loads) -> tuple[float, float]:
    """(shear, axial + bending) plastic usage of the modelled column stub.

    The stub carries the shear and, at its top, the moment V·Lc added to the base
    moment: above 1 the stub itself collapses and CalculiX cannot converge.
    """
    cap = column_capacity(model)
    h = model.Lc
    shear = max(abs(loads.Vx) / cap["Vpx"], abs(loads.Vy) / cap["Vpy"])
    my = max(abs(loads.My), abs(loads.My - loads.Vx * h))
    mx = max(abs(loads.Mx), abs(loads.Mx + loads.Vy * h))
    return shear, abs(loads.P) / cap["Py"] + my / cap["Mpy"] + mx / cap["Mpx"]


def diagnose(model: BasePlateModel, loads: Loads) -> list[str]:
    """Reasons why the analysis of ``loads`` may not converge, in the active language."""
    out: list[str] = []
    shear, combined = column_usage(model, loads)
    vx, vy = abs(loads.Vx), abs(loads.Vy)
    if max(shear, combined) > COLLAPSE:
        out.append(tr(
            "La columna {col} no resiste las cargas de {combo}: uso plástico {u} (cortante "
            "{v}, axial y flexión {m}). El tramo de columna del modelo fluye por completo y "
            "CalculiX no puede converger. Revise el perfil o las cargas.",
            col=model.section.name, combo=loads.name, u=f"{max(shear, combined):.2f}",
            v=f"{shear:.2f}", m=f"{combined:.2f}"))
    no_compression = loads.P <= 0
    has_shear = vx + vy > 0
    if has_shear and no_compression and model.lug is None and not model.anchor.welded_washers:
        out.append(tr(
            "En {combo} hay cortante sin compresión: no hay fricción. Sin llave de cortante "
            "ni arandelas soldadas, el modelo supone que los anclajes toman el cortante "
            "después de deslizar la placa en los agujeros (DG1).", combo=loads.name))
    return out
