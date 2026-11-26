# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""One unit system for every input, table, dimension and report.

The OpenConex presets give lengths in m (SI kN-m, MKS) and plate sizes in mm. For a
connection every length is a detail dimension, so OpenFEMConex shows all of them
in the thickness unit of the preset (mm or in), and rewrites the values of a project
in the new units when the preset changes.
"""

from __future__ import annotations

from typing import Any

from openconex.units import _NUMBER as NUMBER
from openconex.units import (
    PRESETS,
    Kind,
    UnitError,
    UnitSystem,
    _check_kind,
    _unit,
    from_internal,
    parse,
)

__all__ = ["convert_data", "convert_text", "display_units", "kind_of", "with_unit"]

KINDS = (Kind.LENGTH, Kind.STRESS, Kind.FORCE, Kind.MOMENT, Kind.FORCE_PER_LENGTH, Kind.AREA)


def display_units(system: UnitSystem | str | Any) -> UnitSystem:
    """The preset (or a project's ``info``) with every length in its thickness unit."""
    if isinstance(system, str):
        system = PRESETS.get(system, PRESETS["SI_kN_m"])
    elif not isinstance(system, UnitSystem):
        system = system.unit_system()
    return system.model_copy(update={"length": system.thickness})


def kind_of(text: str) -> Kind | None:
    """Kind of a quantity typed with its unit (``"560 mm"``), None for anything else."""
    if not isinstance(text, str):
        return None
    match = NUMBER.match(text)
    if not match or not match["unit"]:
        return None
    try:
        unit = _unit(match["unit"].replace('"', "in"))
    except Exception:
        return None
    for kind in KINDS:
        try:
            _check_kind(unit, kind)
        except Exception:
            continue
        return kind
    return None


def _number(value: float) -> str:
    return f"{round(value, 4):.8g}"


def convert_text(text: str, units: UnitSystem) -> str:
    """``text`` in the units of ``units`` when it is a quantity; otherwise unchanged."""
    kind = kind_of(text)
    if kind is None:
        return text
    try:
        value = parse(text, kind)
    except UnitError:
        return text
    unit = units.unit(kind)
    return f"{_number(from_internal(value, kind, unit))} {unit}"


def with_unit(text: str, kind: Kind, units: UnitSystem) -> str:
    """A bare number typed by the user gets the unit of ``kind``; anything else is kept."""
    text = text.strip()
    match = NUMBER.match(text)
    if match and not match["unit"]:
        return f"{text} {units.unit(kind)}"
    return text


def convert_data(data: Any, units: UnitSystem) -> Any:
    """Every quantity of a project tree rewritten in ``units`` (``info`` is left alone)."""
    if isinstance(data, dict):
        return {k: (v if k == "info" else convert_data(v, units)) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_data(v, units) for v in data]
    if isinstance(data, str):
        return convert_text(data, units)
    return data
