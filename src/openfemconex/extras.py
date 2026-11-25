# SPDX-License-Identifier: AGPL-3.0-or-later
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

__all__ = ["KEY", "LAWS", "CrossShape", "Extras", "Hairpins", "MaterialLaw", "PedestalRebar",
           "StiffenerSpec", "law_from_dict", "load_extended", "parse_extras", "split_data"]

KEY = "openfemconex"
STIFFENER_LAYOUTS = ("alma", "alma y bordes", "bordes", "radial")
HOOKS = ("90", "180", "recta")
LAWS = ("bilineal", "elastoplastica", "trilineal", "tabla")
"""Constitutive laws of the steels in the FEM model."""


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
    """``alma`` (one per flange, in line with the web), ``bordes`` (two per flange, at its
    edges), ``alma y bordes`` (three per
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
class CrossShape:
    """Second W-shape of a cruciform column, split in two tees welded to the main web."""

    name: str
    d: float
    bf: float
    tf: float
    tw: float


@dataclass(frozen=True)
class MaterialLaw:
    """Stress-strain law of a steel in the FEM model (true stress, plastic strain).

    ``bilineal``: yield at Fy, then the slope ``hardening`` up to the plastic strain
    ``eps_u``. ``elastoplastica``: perfectly plastic at Fy. ``trilineal``: plateau at
    Fy up to the plastic strain ``eps_sh``, then linear up to Fu at ``eps_u``.
    ``tabla``: the (stress, plastic strain) points of ``table``.
    """

    law: str = "bilineal"
    nu: float = 0.3
    hardening: float | None = None
    """Slope of the bilinear law [MPa]; None = E/1000."""
    eps_sh: float = 0.015
    eps_u: float = 0.15
    table: tuple[tuple[float, float], ...] = ()

    def curve(self, Fy: float, Fu: float, E: float) -> tuple[tuple[float, float], ...]:
        if self.law == "elastoplastica":
            return ((Fy, 0.0),)
        if self.law == "trilineal":
            return ((Fy, 0.0), (Fy, self.eps_sh), (max(Fu, Fy), self.eps_u))
        if self.law == "tabla":
            return self.table
        H = E / 1000 if self.hardening is None else self.hardening
        return ((Fy, 0.0), (Fy + H * self.eps_u, self.eps_u))

    def check(self, Fy: float, Fu: float) -> None:
        if not 0.0 <= self.nu < 0.5:
            raise ValueError("el coeficiente de Poisson debe estar entre 0 y 0.5")
        if self.law == "trilineal" and not 0.0 <= self.eps_sh < self.eps_u:
            raise ValueError("la deformación de endurecimiento debe ser menor que la última")
        if self.law in ("bilineal", "trilineal") and self.eps_u <= 0:
            raise ValueError("la deformación plástica última debe ser positiva")
        if self.law == "tabla":
            pts = self.table
            if not pts or pts[0][1] != 0.0:
                raise ValueError("la tabla del material debe empezar con deformación plástica 0")
            if any(b[1] <= a[1] or b[0] < a[0] for a, b in zip(pts, pts[1:], strict=False)):
                raise ValueError("la tabla del material debe crecer en deformación y no bajar "
                                 "en esfuerzo")


@dataclass(frozen=True)
class Extras:
    anchors: tuple[tuple[float, float], ...] | None = None
    pedestal: PedestalRebar | None = None
    stiffeners: StiffenerSpec | None = None
    hairpins: Hairpins | None = None
    cross: CrossShape | None = None
    """Cross W-shape of a cruciform column; None = the column of the project alone."""
    laws: dict[str, MaterialLaw] | None = None
    """FEM constitutive law of each steel by name; missing = bilinear E/1000."""
    cjp: bool = False
    """Column-to-plate weld of complete joint penetration instead of fillets."""
    connection: str = ""
    """Name of the connection (identification card of the report)."""

    def law(self, grade: str) -> MaterialLaw:
        return (self.laws or {}).get(grade) or MaterialLaw()


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
    cross = None
    c = ext.get("column")
    if c and c.get("type") == "cruciform":
        cross = cross_shape(project, str(c["cross"]))
    laws = {}
    for name, m in (ext.get("materials") or {}).items():
        laws[name] = law_from_dict(m, lambda v: q(v, Kind.STRESS))
    library = project.material_library()
    for name, law in laws.items():
        if name in library:
            law.check(library[name].Fy, library[name].Fu)
    weld = str(ext.get("column_weld", "filete")).lower()
    if weld not in ("filete", "cjp"):
        raise ValueError(f"soldadura columna-placa desconocida: {weld}")
    return Extras(anchors=anchors, pedestal=pedestal, stiffeners=stiffeners, hairpins=hairpins,
                  cross=cross, laws=laws or None, cjp=weld == "cjp",
                  connection=str(ext.get("connection", "")).strip())


def law_from_dict(m: dict[str, Any], stress) -> MaterialLaw:
    """Constitutive law of one entry of the ``materials`` block; ``stress`` parses a value."""
    law = m.get("law", "bilineal")
    if law not in LAWS:
        raise ValueError(f"ley constitutiva desconocida: {law}")
    return MaterialLaw(
        law=law, nu=float(m.get("nu", 0.3)),
        hardening=stress(m["hardening"]) if m.get("hardening") not in (None, "") else None,
        eps_sh=float(m.get("eps_sh", 0.015)), eps_u=float(m.get("eps_u", 0.15)),
        table=tuple((stress(sv), float(ev)) for sv, ev in m.get("table", ())))


def cross_shape(project: Project, label: str) -> CrossShape:
    """W-shape by label: a custom section of the project or the AISC catalog."""
    from openconex.core.shapes import aisc_shapes
    from openconex.io.project import WSectionInput

    for section in project.sections:
        if isinstance(section, WSectionInput) and section.label() == label:
            return CrossShape(label, *(project.quantity(v, Kind.LENGTH) for v in
                                       (section.d, section.bf, section.tf, section.tw)))
    shape = aisc_shapes().get(label)
    if shape.type not in ("W", "M", "S", "HP"):
        raise ValueError("el perfil cruzado de una columna cruciforme debe ser un perfil I")
    p = shape.properties
    return CrossShape(label, p["d"], p["bf"], p["tf"], p["tw"])


def load_extended(path: str | Path) -> tuple[Project, Extras]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format_version", FORMAT_VERSION) > FORMAT_VERSION:
        raise ValueError("el proyecto es de una versión más nueva de OpenConex")
    base, ext = split_data(data)
    project = Project.model_validate(base)
    return project, parse_extras(project, ext)
