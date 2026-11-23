# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Input data of the base plate FEM model, in N, mm and MPa.

Global axes: x along the column depth ``d`` (strong-axis bending is a moment
about y), y along the flange width, z vertical upwards. The plate bottom (the
contact plane with the grout/concrete) is at z = 0 and the plate centre is at
x = y = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

E_STEEL = 200_000.0
NU_STEEL = 0.3


class SectionKind(StrEnum):
    I = "I"  # W, M, S, HP  # noqa: E741
    HSS_RECT = "HSS_RECT"
    HSS_ROUND = "HSS_ROUND"


@dataclass(frozen=True)
class Section:
    """Column cross-section in plan, without fillets or corner radii.

    For I-shapes ``d``, ``bf``, ``tf``, ``tw``. For rectangular HSS ``d`` (along x),
    ``bf`` (along y) and the wall ``t``. For round HSS ``d`` is the diameter.
    """

    kind: SectionKind
    d: float
    bf: float
    tf: float = 0.0
    tw: float = 0.0
    t: float = 0.0
    name: str = ""

    @property
    def min_wall(self) -> float:
        return min(self.tf, self.tw) if self.kind is SectionKind.I else self.t

    @property
    def max_dim(self) -> float:
        return max(self.d, self.bf)


@dataclass(frozen=True)
class Steel:
    Fy: float
    Fu: float
    E: float = E_STEEL
    nu: float = NU_STEEL
    name: str = ""

    def plastic_curve(self, hardening: float | None = None) -> list[tuple[float, float]]:
        """Bilinear (stress, plastic strain) points; hardening slope E/1000 by default."""
        H = self.E / 1000 if hardening is None else hardening
        eps_u = 0.15
        return [(self.Fy, 0.0), (self.Fy + H * eps_u, eps_u)]


@dataclass(frozen=True)
class Anchor:
    x: float
    y: float


@dataclass(frozen=True)
class AnchorSpec:
    diameter: float
    hole: float
    """Hole diameter in the plate."""
    washer: float
    """Plate washer size (treated as a circle of this diameter)."""
    hef: float
    E: float = E_STEEL
    Fu: float = 400.0
    leveling_nuts: bool = False
    """With leveling nuts the rods also take compression."""

    @property
    def area(self) -> float:
        return math.pi * self.diameter**2 / 4

    @property
    def inertia(self) -> float:
        return math.pi * self.diameter**4 / 64


@dataclass(frozen=True)
class Concrete:
    fc: float
    N: float
    """Block size along x."""
    B: float
    """Block size along y."""
    H: float
    """Block depth (its base is fixed)."""
    grout: float = 0.0
    nu: float = 0.2

    @property
    def E(self) -> float:
        """ACI 318 normal-weight modulus, 4700 √f'c [MPa]."""
        return 4700.0 * math.sqrt(self.fc)


@dataclass(frozen=True)
class Loads:
    """Design forces at the plate–concrete interface (z = 0), column axis.

    ``P`` is positive in compression. ``My`` is the strong-axis moment (positive
    compresses the +x side), ``Mx`` the weak-axis moment, ``Vx`` and ``Vy`` the
    shears. Units N and N·mm.
    """

    P: float = 0.0
    Vx: float = 0.0
    Vy: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    name: str = "LOAD"


@dataclass(frozen=True)
class MeshSettings:
    size_fine: float | None = None
    """Element size next to the column and holes (default: about half the thinnest wall)."""
    size_coarse: float | None = None
    """Element size far from the column (default: 3 × size_fine)."""
    plate_layers: int = 4
    column_size: float | None = None
    """Element length along the column (default: 2 × size_fine, at least 10 mm)."""
    concrete_size: float | None = None
    """Concrete element size in plan (default: 1.5 × size_coarse)."""
    concrete_layers: int = 10

    def resolved(self, model: BasePlateModel) -> MeshSettings:
        fine = self.size_fine or max(4.0, min(model.section.min_wall, model.tp) / 1.5)
        coarse = self.size_coarse or 3.0 * fine
        return MeshSettings(
            size_fine=fine, size_coarse=coarse, plate_layers=max(3, self.plate_layers),
            column_size=self.column_size or max(10.0, 2.0 * fine),
            concrete_size=self.concrete_size or 1.5 * coarse,
            concrete_layers=self.concrete_layers)


@dataclass(frozen=True)
class ContactSettings:
    mu: float = 0.55
    """Friction coefficient (DG1: 0.55 on grout, 0.7 on concrete)."""
    stiffness: float | None = None
    """Penalty slope K [N/mm³] (default 10·Ec / 25 mm)."""
    tension: float = 0.05
    """σ∞ of the linear pressure-overclosure law [MPa]."""


@dataclass(frozen=True)
class BasePlateModel:
    section: Section
    column_steel: Steel
    N: float
    """Plate size along x."""
    B: float
    """Plate size along y."""
    tp: float
    plate_steel: Steel
    anchors: tuple[Anchor, ...]
    anchor: AnchorSpec
    concrete: Concrete
    ex: float = 0.0
    ey: float = 0.0
    """Column eccentricity on the plate."""
    column_length: float | None = None
    """Modelled column length above the plate (default 2.5 × largest section dimension)."""
    contact: ContactSettings = field(default_factory=ContactSettings)
    title: str = ""

    @property
    def Lc(self) -> float:
        return self.column_length or 2.5 * self.section.max_dim

    def validate(self) -> None:
        r = self.anchor.washer / 2
        for a in self.anchors:
            if abs(a.x) + r > self.N / 2 or abs(a.y) + r > self.B / 2:
                raise ValueError(f"washer of anchor at ({a.x:.1f}, {a.y:.1f}) leaves the plate")
        if self.concrete.N < self.N or self.concrete.B < self.B:
            raise ValueError("the concrete block must be at least the plate size")
        if self.anchor.hole >= self.anchor.washer:
            raise ValueError("the washer must be larger than the hole")
