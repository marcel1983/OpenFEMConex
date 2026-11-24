# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Data that OpenFEMConex adds to an OpenConex project.

They live under the top-level key ``"openfemconex"`` of the ``.ocnx`` file:
anchor rods at free coordinates, the pedestal reinforcement and stiffeners.
OpenConex itself rejects unknown keys, so a file that uses these additions
opens only with OpenFEMConex.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openconex.io.project import FORMAT_VERSION, Project
from openconex.units import Kind

__all__ = ["KEY", "Extras", "Hairpins", "PedestalRebar", "StiffenerSpec", "load_extended",
           "parse_extras", "split_data"]

KEY = "openfemconex"
STIFFENER_LAYOUTS = ("alma", "alma y bordes", "radial")
HOOKS = ("90", "180", "recta")


@dataclass(frozen=True)
class PedestalRebar:
    bars: int
    """Number of longitudinal bars, spread evenly along the perimeter."""
    bar_diameter: float
    cover: float
    """Clear cover to the ties [mm]."""
    fy: float
    tie_diameter: float
    tie_spacing: float
    tie_legs: int = 2
    """Tie legs crossing the shear breakout plane."""
    top_ties: int = 2
    """Ties within the top of the pedestal that act as anchor reinforcement in shear."""
    hook: str = "90"
    """End of the longitudinal bars at the top: ``90`` or ``180`` (standard hooks,
    ACI 318-19 Table 25.3.1) or ``recta`` (straight bar)."""
    height: float = 0.0
    """Pedestal height: shears add V·h to the moment at its base [mm]."""

    @property
    def hooked(self) -> bool:
        return self.hook in HOOKS[:2]

    @property
    def bar_area(self) -> float:
        return math.pi * self.bar_diameter**2 / 4

    @property
    def tie_area(self) -> float:
        return math.pi * self.tie_diameter**2 / 4

    def positions(self, N: float, B: float) -> list[tuple[float, float]]:
        """Bar centres on the rectangle inset by cover, tie and half a bar (N along x)."""
        inset = self.cover + self.tie_diameter + self.bar_diameter / 2
        a, b = N - 2 * inset, B - 2 * inset
        if a <= 0 or b <= 0 or self.bars < 4:
            return []
        perimeter = 2 * (a + b)
        out = []
        for i in range(self.bars):
            s = perimeter * i / self.bars
            if s < a:
                x, y = -a / 2 + s, -b / 2
            elif s < a + b:
                x, y = a / 2, -b / 2 + (s - a)
            elif s < 2 * a + b:
                x, y = a / 2 - (s - a - b), b / 2
            else:
                x, y = -a / 2, b / 2 - (s - 2 * a - b)
            out.append((x, y))
        return out


@dataclass(frozen=True)
class StiffenerSpec:
    layout: str
    """``alma`` (one per flange, in line with the web), ``alma y bordes`` (three per
    flange) or ``radial`` (round columns)."""
    length: float
    """Horizontal projection from the column face [mm]."""
    height: float
    """Height at the column face [mm]."""
    thickness: float
    end_height: float
    """Height at the free end (a small value gives a nearly triangular plate) [mm]."""
    grade: str = "ASTM A36"
    count: int = 8
    """Number of stiffeners of the radial layout."""
    weld: float | None = None
    """Fillet size of the stiffener welds; None = minimum of Table J2.4 [mm]."""


@dataclass(frozen=True)
class Hairpins:
    """Inverted U bars (hairpins) placed over each anchor as anchor reinforcement.

    Each hairpin straddles its anchor along x: two vertical legs at ``offset`` on each
    side, joined by the bend near the top of the concrete. Both legs cross the
    breakout cone of the anchor.
    """

    count: int
    """Hairpins per anchor."""
    diameter: float
    fy: float
    offset: float
    """Horizontal distance from the anchor axis to each leg [mm]."""
    leg_length: float
    """Length of each leg below the bend [mm]."""
    cover: float = 50.0
    """Clear cover from the top of the concrete to the bend [mm]."""

    @property
    def bar_area(self) -> float:
        return math.pi * self.diameter**2 / 4

    def legs(self, anchors: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Plan position of every leg; the hairpins of one anchor are spaced 3 db in y."""
        out = []
        for ax, ay in anchors:
            for k in range(self.count):
                dy = (k - (self.count - 1) / 2) * 3 * self.diameter
                out += [(ax - self.offset, ay + dy), (ax + self.offset, ay + dy)]
        return out


@dataclass(frozen=True)
class Extras:
    anchors: tuple[tuple[float, float], ...] | None = None
    pedestal: PedestalRebar | None = None
    stiffeners: StiffenerSpec | None = None
    hairpins: Hairpins | None = None


def split_data(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project data without the OpenFEMConex block, and that block."""
    ext = data.get(KEY) or {}
    return {k: v for k, v in data.items() if k != KEY}, ext


def _hook(block: dict[str, Any]) -> str:
    """Hook of the pedestal bars; older files have ``hooked`` (true = 90°)."""
    hook = str(block.get("hook", "90" if block.get("hooked", True) else "recta"))
    if hook not in HOOKS:
        raise ValueError(f"gancho desconocido: {hook}")
    return hook


def parse_extras(project: Project, ext: dict[str, Any]) -> Extras:
    """Convert the texts of the block (values with units) to internal units."""
    def q(value: Any, kind: Kind = Kind.LENGTH) -> float:
        return project.quantity(value, kind)

    anchors = None
    if ext.get("anchors"):
        anchors = tuple((q(x), q(y)) for x, y in ext["anchors"])
        if len(anchors) < 2:
            raise ValueError("se necesitan al menos dos anclajes")
    pedestal = None
    p = ext.get("pedestal")
    if p:
        pedestal = PedestalRebar(
            bars=int(p.get("bars", 8)), bar_diameter=q(p["bar_diameter"]),
            cover=q(p.get("cover", "40 mm")), fy=q(p.get("fy", "420 MPa"), Kind.STRESS),
            tie_diameter=q(p.get("tie_diameter", "10 mm")),
            tie_spacing=q(p.get("tie_spacing", "150 mm")), tie_legs=int(p.get("tie_legs", 2)),
            top_ties=int(p.get("top_ties", 2)), hook=_hook(p),
            height=q(p.get("height", 0.0)))
        if pedestal.bars < 4:
            raise ValueError("el pedestal necesita al menos 4 barras longitudinales")
    stiffeners = None
    s = ext.get("stiffeners")
    if s:
        layout = s.get("layout", "alma")
        if layout not in STIFFENER_LAYOUTS:
            raise ValueError(f"disposición de rigidizadores desconocida: {layout}")
        stiffeners = StiffenerSpec(
            layout=layout, length=q(s["length"]), height=q(s["height"]),
            thickness=q(s["thickness"], Kind.THICKNESS),
            end_height=q(s.get("end_height", "25 mm")), grade=s.get("grade", "ASTM A36"),
            count=int(s.get("count", 8)),
            weld=q(s["weld"], Kind.THICKNESS) if s.get("weld") else None)
        if stiffeners.end_height > stiffeners.height:
            raise ValueError("la altura del extremo del rigidizador supera la altura total")
    hairpins = None
    h = ext.get("hairpins")
    if h:
        hairpins = Hairpins(
            count=int(h.get("count", 1)), diameter=q(h.get("diameter", "16 mm")),
            fy=q(h.get("fy", "420 MPa"), Kind.STRESS), offset=q(h.get("offset", "75 mm")),
            leg_length=q(h.get("leg_length", "600 mm")), cover=q(h.get("cover", "50 mm")))
        if hairpins.count < 1:
            raise ValueError("se necesita al menos una horquilla por anclaje")
    return Extras(anchors=anchors, pedestal=pedestal, stiffeners=stiffeners, hairpins=hairpins)


def load_extended(path: str | Path) -> tuple[Project, Extras]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format_version", FORMAT_VERSION) > FORMAT_VERSION:
        raise ValueError("el proyecto es de una versión más nueva de OpenConex")
    base, ext = split_data(data)
    project = Project.model_validate(base)
    return project, parse_extras(project, ext)
