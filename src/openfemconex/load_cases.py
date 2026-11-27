# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Load cases and combinations shared by every connection type.

A connection keeps its service load cases in ``cases`` (a name, a type D, L, W, E...
and its forces, which depend on the connection type) and the options of its
combinations in ``combinations``: the ASCE 7-22 combinations generated from the case
types (``include_code``, ``methods``) and the user's own ones (``custom``), the same
format as the base plate of OpenConex.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from openconex.core.loads import (
    LoadCase,
    LoadCombination,
    LoadType,
    Method,
    SeismicParameters,
    asce7_combinations,
)
from openconex.io.project import CombinationOptions

__all__ = ["code_combinations", "combination_text", "factored", "load_combinations",
           "options"]


def combination_text(factors: Mapping[str, float]) -> str:
    """1.2D + 1.6L."""
    parts = []
    for name, f in factors.items():
        if f == 0:
            continue
        sign = "−" if f < 0 else "+"
        parts.append((sign, f"{abs(f):g}{name}" if abs(f) != 1 else name))
    if not parts:
        return "0"
    text = ("−" if parts[0][0] == "−" else "") + parts[0][1]
    return text + "".join(f" {s} {t}" for s, t in parts[1:])


def options(data: Mapping[str, Any] | None) -> CombinationOptions:
    return CombinationOptions.model_validate(dict(data or {}))


def _cases(cases: Iterable[Mapping[str, Any]]) -> list[LoadCase]:
    out = []
    for c in cases:
        name = str(c.get("name", "")).strip()
        if not name:
            raise ValueError("cada caso de carga necesita un nombre")
        out.append(LoadCase(name=name, type=LoadType(c.get("type") or "D")))
    names = [c.name for c in out]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"casos de carga repetidos: {repeated}")
    return out


def code_combinations(cases: Iterable[Mapping[str, Any]], opts: Mapping[str, Any] | None,
                      methods: Iterable[str] | None = None) -> list[LoadCombination]:
    """The ASCE 7-22 combinations of the case types, whether included or not."""
    o = options(opts)
    seismic = (SeismicParameters(SDS=o.SDS, rho=o.rho, omega0=o.omega0)
               if o.SDS is not None else None)
    allowed = {Method(m) for m in methods} if methods is not None else None
    out: list[LoadCombination] = []
    for method in o.methods:
        if allowed is None or method in allowed:
            out += asce7_combinations(_cases(cases), method, seismic, o.live_factor)
    return out


def load_combinations(cases: Iterable[Mapping[str, Any]], opts: Mapping[str, Any] | None,
                      methods: Iterable[str] | None = None) -> list[LoadCombination]:
    """Generated (when included) and own combinations, in that order.

    ``methods`` limits them to the design methods the connection checks (e.g. only
    LRFD); an own combination of another method is an error.
    """
    cases = list(cases)
    o = options(opts)
    names = {c.name for c in _cases(cases)}
    out = code_combinations(cases, opts, methods) if o.include_code else []
    allowed = {Method(m) for m in methods} if methods is not None else None
    for custom in o.custom:
        if allowed is not None and custom.method not in allowed:
            raise ValueError(f"la combinación {custom.name!r} es {custom.method.value}: "
                             f"esta conexión solo usa {', '.join(m.value for m in allowed)}")
        unknown = set(custom.factors) - names
        if unknown:
            raise ValueError(f"la combinación {custom.name!r} usa casos que no existen: "
                             f"{sorted(unknown)}")
        factors = {k: v for k, v in custom.factors.items() if v != 0.0}
        out.append(LoadCombination(
            name=custom.name, method=custom.method, factors=factors, seismic=custom.seismic,
            overstrength=custom.overstrength, allowable_increase=custom.allowable_increase,
            source=custom.source or "custom"))
    names_out = [c.name for c in out]
    repeated = sorted({n for n in names_out if names_out.count(n) > 1})
    if repeated:
        raise ValueError(f"combinaciones repetidas: {repeated}")
    if not out:
        raise ValueError("no hay combinaciones: incluya las de ASCE 7 o defina alguna propia")
    return out


def factored(combo: LoadCombination, values: Mapping[str, Mapping[str, float]]
             ) -> dict[str, float]:
    """Sum of the factored forces of the cases: ``values[case][key]``."""
    out: dict[str, float] = {}
    for case, f in combo.factors.items():
        for key, v in values[case].items():
            out[key] = out.get(key, 0.0) + f * v
    return out
