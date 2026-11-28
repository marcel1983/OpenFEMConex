# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Input data of the base plate FEM model, in N, mm and MPa.

Global axes: x along the column depth ``d`` (strong-axis bending is a moment
about y), y along the flange width, z vertical upwards. The plate bottom (the
contact plane with the grout/concrete) is at z = 0 and the plate centre is at
x = y = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import StrEnum

E_STEEL = 200_000.0
NU_STEEL = 0.3


def min_fillet(t: float) -> float:
    """Minimum fillet size for the thinner part joined (AISC 360 Table J2.4) [mm]."""
    t_in = t / 25.4
    size = 1 / 8 if t_in <= 1 / 4 else 3 / 16 if t_in <= 1 / 2 else 1 / 4 if t_in <= 3 / 4 \
        else 5 / 16
    return size * 25.4


class SectionKind(StrEnum):
    I = "I"  # W, M, S, HP  # noqa: E741
    HSS_RECT = "HSS_RECT"
    HSS_ROUND = "HSS_ROUND"
    CRUCIFORM = "CRUCIFORM"
    """A W-shape (``d``, ``bf``, ``tf``, ``tw``) with a second W-shape (``d2``, ``bf2``,
    ``tf2``, ``tw2``) split along its web into two tees welded to both faces of the
    main web: the cross flanges lie at y = ±d2/2."""


Box = tuple[float, float, float, float]
"""Rectangle (x0, y0, x1, y1) in plan, relative to the column axis."""


@dataclass(frozen=True)
class Section:
    """Column cross-section in plan, without fillets or corner radii.

    For I-shapes ``d``, ``bf``, ``tf``, ``tw``. For rectangular HSS ``d`` (along x),
    ``bf`` (along y) and the wall ``t``. For round HSS ``d`` is the diameter.
    Cruciform columns add the cross W-shape ``d2``, ``bf2``, ``tf2``, ``tw2``.
    """

    kind: SectionKind
    d: float
    bf: float
    tf: float = 0.0
    tw: float = 0.0
    t: float = 0.0
    name: str = ""
    d2: float = 0.0
    bf2: float = 0.0
    tf2: float = 0.0
    tw2: float = 0.0

    def boxes(self) -> list[Box]:
        """Non-overlapping rectangles of an I-shape or a cruciform section."""
        d2, b2, tf, tw2 = self.d / 2, self.bf / 2, self.tf, self.tw / 2
        out = [(-d2, -b2, -d2 + tf, b2), (d2 - tf, -b2, d2, b2), (-d2 + tf, -tw2, d2 - tf, tw2)]
        if self.kind is SectionKind.CRUCIFORM:
            c2, cb2, ctf, ctw2 = self.d2 / 2, self.bf2 / 2, self.tf2, self.tw2 / 2
            out += [(-cb2, -c2, cb2, -c2 + ctf), (-cb2, c2 - ctf, cb2, c2),
                    (-ctw2, -c2 + ctf, ctw2, -tw2), (-ctw2, tw2, ctw2, c2 - ctf)]
        return out

    def check(self) -> None:
        """Raise ValueError when the cross shape of a cruciform does not fit."""
        if self.kind is not SectionKind.CRUCIFORM:
            return
        if self.bf2 >= self.d - 2 * self.tf:
            raise ValueError("los patines del perfil cruzado no caben entre los patines del "
                             "perfil principal (bf2 debe ser menor que d − 2 tf)")
        if self.d2 / 2 - self.tf2 <= self.tw / 2:
            raise ValueError("el perfil cruzado es demasiado bajo para el alma del principal")

    def distance(self, x: float, y: float) -> float:
        """Distance from a point (relative to the column axis) to the steel of the section."""
        def to_box(x0: float, y0: float, x1: float, y1: float) -> float:
            return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))

        d2, b2 = self.d / 2, self.bf / 2
        if self.kind in (SectionKind.I, SectionKind.CRUCIFORM):
            return min(to_box(*b) for b in self.boxes())
        if self.kind is SectionKind.HSS_ROUND:
            r = math.hypot(x, y)
            return max(r - d2, d2 - self.t - r, 0.0)
        outside = to_box(-d2, -b2, d2, b2)
        if outside > 0:
            return outside
        return max(min(d2 - self.t - abs(x), b2 - self.t - abs(y)), 0.0)

    @property
    def min_wall(self) -> float:
        if self.kind is SectionKind.CRUCIFORM:
            return min(self.tf, self.tw, self.tf2, self.tw2)
        return min(self.tf, self.tw) if self.kind is SectionKind.I else self.t

    @property
    def max_dim(self) -> float:
        return max(self.d, self.bf, self.d2, self.bf2)


@dataclass(frozen=True)
class Steel:
    Fy: float
    Fu: float
    E: float = E_STEEL
    nu: float = NU_STEEL
    name: str = ""
    curve: tuple[tuple[float, float], ...] | None = None
    """(stress, plastic strain) points of the constitutive law; None = bilinear."""

    def plastic_curve(self, hardening: float | None = None) -> list[tuple[float, float]]:
        """(stress, plastic strain) points; bilinear with slope E/1000 by default."""
        if self.curve and hardening is None:
            return [tuple(p) for p in self.curve]
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
    welded_washers: bool = False
    """Plate washers welded to the plate: the rods then also take shear."""
    friction_only: bool = False
    """The shear goes by friction even without axial compression (through-bolts: the
    moment couple presses the plate on the wall); the rods only restrain sliding."""

    @property
    def area(self) -> float:
        return math.pi * self.diameter**2 / 4

    @property
    def inertia(self) -> float:
        return math.pi * self.diameter**4 / 64


@dataclass(frozen=True)
class Stiffener:
    """A vertical plate welded to the column and to the base plate.

    It starts at ``origin`` on the column face and runs ``length`` along ``direction``
    (unit vector in plan). Its height goes from ``height`` at the column to
    ``end_height`` at the free end.
    """

    origin: tuple[float, float]
    direction: tuple[float, float]
    length: float
    thickness: float
    height: float
    end_height: float
    embed: float = 0.0
    """Overlap into the column wall, so that the plan regions share an edge."""

    def corners(self) -> list[tuple[float, float]]:
        (x0, y0), (dx, dy), h = self.origin, self.direction, self.thickness / 2
        nx, ny = -dy, dx
        out = []
        for s, t in ((-self.embed, -h), (self.length, -h), (self.length, h), (-self.embed, h)):
            out.append((x0 + s * dx + t * nx, y0 + s * dy + t * ny))
        return out

    def local(self, x: float, y: float) -> tuple[float, float]:
        """(distance along the stiffener from the column face, offset across it)."""
        rx, ry = x - self.origin[0], y - self.origin[1]
        dx, dy = self.direction
        return rx * dx + ry * dy, -rx * dy + ry * dx

    def height_at(self, r):
        """Height at the distance ``r`` from the column face (number or array)."""
        t = (r / self.length)
        t = min(max(t, 0.0), 1.0) if isinstance(t, float) else t.clip(0.0, 1.0)
        return self.height + (self.end_height - self.height) * t


@dataclass(frozen=True)
class ShearLug:
    """Shear lug under the plate, centred on the column: it takes the shear in bearing."""

    width: float
    """Across the shear [mm]."""
    thickness: float
    embedment: float
    direction: str = "strong"
    """``strong`` resists shear along x, ``weak`` along y, ``both`` (cruciform) both."""


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
    opposite: Loads | None = None
    """Forces of the opposite beam (``BasePlateModel.opposite``), in its own axes: z out
    of the far face, x up, the same signs as these."""


@dataclass(frozen=True)
class MeshSettings:
    size_fine: float | None = None
    """Element size next to the column and holes (default: thinnest of wall and plate)."""
    size_coarse: float | None = None
    """Element size far from the column (default: 3 × size_fine)."""
    plate_layers: int = 4
    column_size: float | None = None
    """Element length along the column (default: 2 × size_fine, at least 10 mm)."""
    concrete_size: float | None = None
    """Concrete element size in plan (default: 1.5 × size_coarse)."""
    concrete_layers: int = 10
    fast: bool = False
    """Automatic sizes that favour solution time (about twice the element size, three
    plate layers); explicit sizes are kept."""
    fast_factor: float = 2.0
    """Size factor of the fast mesh; build_mesh lowers it if elements come out distorted."""
    size_wall: float | None = None
    """Element size along the column walls (default: size_fine). The fast mesh keeps
    the normal size there, where the welds are evaluated."""

    def wall_size(self, model: BasePlateModel) -> float:
        """Element size next to the column walls and the stiffeners.

        A quadrilateral much wider than the wall it spans comes out distorted, and
        CalculiX rejects it ("nonpositive jacobian"), so the size there is at most
        1.5 times the thinnest wall, whatever size_fine is.
        """
        walls = [model.section.min_wall] + [s.thickness for s in model.stiffeners]
        return min(self.size_wall or self.size_fine or 1e9, 1.5 * min(walls))

    def resolved(self, model: BasePlateModel) -> MeshSettings:
        # The column walls get their own size (see wall_size), so a very thin wall does
        # not force the whole plate to a tiny mesh.
        auto = normal = max(8.0, min(model.section.min_wall, model.tp))
        if self.fast:
            auto = max(self.fast_factor * auto, 7.5 * self.fast_factor)
        fine = self.size_fine or auto
        wall = self.size_wall
        coarse = self.size_coarse or 3.0 * fine
        layers = max(3, self.plate_layers)
        if self.fast:
            layers = 3
        return MeshSettings(
            size_fine=fine, size_coarse=coarse, plate_layers=layers,
            # the fast mesh keeps the normal first level of the column, where the weld
            # forces are read
            column_size=self.column_size or max(10.0, 2.0 * (normal if self.fast else fine)),
            concrete_size=self.concrete_size or 1.5 * coarse,
            concrete_layers=8 if self.fast else self.concrete_layers, fast=self.fast,
            fast_factor=self.fast_factor, size_wall=wall)


@dataclass(frozen=True)
class ContactSettings:
    mu: float = 0.55
    """Friction coefficient (DG1: 0.55 on grout, 0.7 on concrete)."""
    stiffness: float | None = None
    """Penalty slope K [N/mm³] (default 10·Ec / 25 mm)."""
    tension: float = 0.05
    """σ∞ of the linear pressure-overclosure law [MPa]."""


@dataclass(frozen=True)
class FarPlate:
    """Plate on the far face of the block (z = -H), anchoring the rods (through-bolts).

    With it the block is no longer fixed at its base: the rods pull this plate against
    the far face, and the block is held at its ends x = ±N/2 (a wall or column that
    continues above and below the connection).
    """

    width: float
    """Size along y."""
    height: float
    """Size along x."""
    thickness: float
    steel: Steel


@dataclass(frozen=True)
class ColumnFlange:
    """The block is the flange of a steel column (moment end plate).

    The block is then of steel (``steel``, elastic-plastic), as deep as the flange
    thickness, and the rods are bolts whose nuts bear on its far face (z = -H). The
    flange is held on its far face along the column web (|y| ≤ ``web``/2) and along
    each continuity plate (|x − x_c| ≤ t/2): the web and the plates are taken as rigid
    supports, which is the model of the column flange yield lines.
    """

    steel: Steel
    web: float
    """Thickness of the column web [mm]."""
    stiffeners: tuple[tuple[float, float], ...] = ()
    """(x of its centre, thickness) of each continuity plate [mm]."""
    pretension: float = 0.0
    """Bolt pretension [N]: the spring law starts with this force (0 = snug tight)."""


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
    stiffeners: tuple[Stiffener, ...] = ()
    lug: ShearLug | None = None
    hairpins: object | None = None
    """Hairpins over the anchors (extras.Hairpins); drawn and checked, not in the FEM."""
    rebar: object | None = None
    """Pedestal reinforcement (extras.PedestalRebar). It is not part of the FEM model
    (the concrete is a plain elastic block): it is drawn and used by the checks."""
    stiffener_steel: Steel | None = None
    weld: float = 0.0
    """Fillet size of the column-to-plate weld, for drawing (0 = not drawn)."""
    cjp: bool = False
    """The column-to-plate weld is of complete joint penetration."""
    stiffener_weld: float = 0.0
    """Fillet size of the stiffener welds, for drawing."""
    rows_weak: bool = False
    """The two anchor rows face the weak axis (at y = ±f); for the dimension of f."""
    column_length: float | None = None
    """Modelled column length above the plate (default 2.5 × largest section dimension)."""
    contact: ContactSettings = field(default_factory=ContactSettings)
    title: str = ""
    far: FarPlate | None = None
    """Flexible plate on the far face anchoring the rods (through-bolt connections)."""
    opposite: BasePlateModel | None = None
    """Second column (beam) with its plate on the far face, on the same rods: its plate
    and column are the mirror image below the block (through-bolt connection with an
    opposite beam). Its anchors and concrete are those of this model."""
    flange: ColumnFlange | None = None
    """The block is a steel column flange (moment end plate): see ColumnFlange."""

    @property
    def two_faces(self) -> bool:
        """The rods cross the block to a plate on its far face (block held at its ends)."""
        return self.far is not None or self.opposite is not None

    @property
    def free_nuts(self) -> bool:
        """The rod ends are nuts on a deformable part (not fixed to the ground)."""
        return self.two_faces or self.flange is not None

    @property
    def Lc(self) -> float:
        return self.column_length or 2.5 * self.section.max_dim

    def validate(self) -> None:
        self.section.check()
        r = self.anchor.washer / 2
        for a in self.anchors:
            if abs(a.x) + r > self.N / 2 or abs(a.y) + r > self.B / 2:
                raise ValueError(f"washer of anchor at ({a.x:.1f}, {a.y:.1f}) leaves the plate")
            if self.section.distance(a.x - self.ex, a.y - self.ey) < r:
                raise ValueError(f"washer of anchor at ({a.x:.1f}, {a.y:.1f}) overlaps the column")
        for i, a in enumerate(self.anchors):
            for b in self.anchors[i + 1:]:
                if math.hypot(a.x - b.x, a.y - b.y) < 2 * r:
                    raise ValueError(f"washers of the anchors at ({a.x:.1f}, {a.y:.1f}) and "
                                     f"({b.x:.1f}, {b.y:.1f}) overlap")
        for st in self.stiffeners:
            if st.height >= self.Lc:
                raise ValueError("the stiffener is taller than the modelled column")
            if st.end_height <= 0 or st.end_height > st.height:
                raise ValueError("the stiffener end height must be between 0 and its height")
            for x, y in st.corners():
                if abs(x) > self.N / 2 or abs(y) > self.B / 2:
                    raise ValueError("a stiffener leaves the plate")
            for a in self.anchors:
                s, t = st.local(a.x, a.y)
                gap = math.hypot(max(-s, 0.0, s - st.length), max(abs(t) - st.thickness / 2, 0.0))
                if gap < r:
                    raise ValueError(f"the washer of the anchor at ({a.x:.1f}, {a.y:.1f}) "
                                     "overlaps a stiffener")
        if self.concrete.N < self.N or self.concrete.B < self.B:
            raise ValueError("the concrete block must be at least the plate size")
        if self.anchor.hole >= self.anchor.washer:
            raise ValueError("the washer must be larger than the hole")
        if self.opposite is not None:
            o = self.opposite
            if self.far is not None or o.opposite is not None or o.far is not None:
                raise ValueError("an opposite column replaces the far plate")
            if len(o.anchors) != len(self.anchors) or any(
                    abs(a.x - b.x) > 1e-6 or abs(a.y - b.y) > 1e-6
                    for a, b in zip(o.anchors, self.anchors, strict=True)):
                raise ValueError("the opposite plate must have the same anchors")
            replace(o, concrete=self.concrete).validate()
        if self.flange is not None and self.two_faces:
            raise ValueError("a column flange has no far plate")
