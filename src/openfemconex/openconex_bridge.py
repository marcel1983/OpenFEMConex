# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Build the FEM model from an OpenConex project (.ocnx).

OpenConex supplies the AISC shape catalog, the materials, the base plate data
and the load combinations; this module only maps them to :mod:`openfemconex.model`.
"""

from __future__ import annotations

import math
from pathlib import Path

from openconex.connections.base_plate.check import BasePlate
from openconex.connections.base_plate.plate import BendingResult, rectangular_bending
from openconex.core.bolting import base_plate_hole
from openconex.core.loads import Forces, LoadCombination, Method, combine
from openconex.core.model import HSSKind, HSSShape, IShape
from openconex.io.project import Project
from openconex.units import Kind, from_internal, to_internal

from openfemconex.extras import CrossShape, Extras, StiffenerSpec, load_extended
from openfemconex.model import (
    Anchor,
    AnchorSpec,
    BasePlateModel,
    Concrete,
    ContactSettings,
    Loads,
    Section,
    SectionKind,
    ShearLug,
    Steel,
    Stiffener,
    min_fillet,
)

__all__ = ["dg1_bending", "loads_from_forces", "model_from_base_plate", "model_from_project",
           "model_of",
           "project_loads", "section_of"]


def section_of(column: IShape | HSSShape, cross: CrossShape | None = None) -> Section:
    if cross is not None:
        if not isinstance(column, IShape):
            raise ValueError("una columna cruciforme necesita un perfil I como principal")
        return Section(SectionKind.CRUCIFORM, d=column.d, bf=column.bf, tf=column.tf,
                       tw=column.tw, name=f"{column.name} + {cross.name}", d2=cross.d,
                       bf2=cross.bf, tf2=cross.tf, tw2=cross.tw)
    if isinstance(column, IShape):
        return Section(SectionKind.I, d=column.d, bf=column.bf, tf=column.tf, tw=column.tw,
                       name=column.name)
    if column.kind is HSSKind.ROUND:
        return Section(SectionKind.HSS_ROUND, d=column.d, bf=column.d, t=column.t,
                       name=column.name)
    return Section(SectionKind.HSS_RECT, d=column.d, bf=column.bf, t=column.t, name=column.name)


def stiffeners_of(section: Section, spec: StiffenerSpec) -> tuple[Stiffener, ...]:
    """Stiffener plates of a layout for the given column section."""
    def make(origin, direction, embed):
        return Stiffener(origin, direction, spec.length, spec.thickness, spec.height,
                         spec.end_height, embed)

    if section.kind is SectionKind.HSS_RECT:
        return _rect_tube_stiffeners(section, spec, make)
    if spec.layout == "radial":
        if section.kind is not SectionKind.HSS_ROUND:
            raise ValueError("la disposición radial es para tubos circulares y rectangulares")
        r = section.d / 2
        out = []
        for i in range(spec.count):
            a = 2 * math.pi * i / spec.count
            d = (math.cos(a), math.sin(a))
            out.append(make((r * d[0], r * d[1]), d, section.t / 2))
        return tuple(out)
    if section.kind is SectionKind.CRUCIFORM:
        if spec.layout != "alma":
            raise ValueError("en columnas cruciformes los rigidizadores van en línea con las "
                             "almas (disposición 'alma')")
        return tuple([make((sign * section.d / 2, 0.0), (sign, 0.0), section.tf / 2)
                      for sign in (-1.0, 1.0)]
                     + [make((0.0, sign * section.d2 / 2), (0.0, sign), section.tf2 / 2)
                        for sign in (-1.0, 1.0)])
    if section.kind is not SectionKind.I:
        raise ValueError(f"la disposición '{spec.layout}' es para perfiles W y tubos "
                         "rectangulares; en tubos circulares use 'radial'")
    edge = section.bf / 2 - spec.thickness / 2
    ys = {"alma": [0.0], "alma y bordes": [-edge, 0.0, edge], "bordes": [-edge, edge]}[
        spec.layout]
    return tuple(make((sign * section.d / 2, y), (sign, 0.0), section.tf / 2)
                 for sign in (-1.0, 1.0) for y in ys)


def _rect_tube_stiffeners(section: Section, spec: StiffenerSpec, make) -> tuple[Stiffener, ...]:
    """Square or rectangular HSS.

    ``alma``: one plate at the middle of each face. ``alma y bordes``: three per face,
    the outer two just inside the side walls; ``bordes``: only those two. ``radial``:
    one on the diagonal at each corner, plus one at the middle of each face when
    ``count`` is 8 or more.
    """
    d2, b2, t = section.d / 2, section.bf / 2, section.t
    out = []
    if spec.layout != "radial" or spec.count >= 8:
        offsets_y = [0.0]
        offsets_x = [0.0]
        if spec.layout in ("alma y bordes", "bordes"):
            # just inside the side walls, so that the plates of two faces do not meet
            ey, ex = b2 - t - spec.thickness / 2, d2 - t - spec.thickness / 2
            offsets_y, offsets_x = [-ey, ey], [-ex, ex]
            if spec.layout == "alma y bordes":
                offsets_y, offsets_x = [-ey, 0.0, ey], [-ex, 0.0, ex]
        for sign in (-1.0, 1.0):
            out += [make((sign * d2, y), (sign, 0.0), t / 2) for y in offsets_y]
            out += [make((x, sign * b2), (0.0, sign), t / 2) for x in offsets_x]
    if spec.layout == "radial":
        r = math.sqrt(0.5)
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                out.append(make((sx * d2, sy * b2), (sx * r, sy * r), t))
    return tuple(out)


def steel_of(bp: BasePlate, grade: str, extras: Extras) -> Steel:
    """FEM steel of a grade of the project library, with its constitutive law."""
    m = bp.materials[grade]
    law = extras.law(grade)
    return Steel(m.Fy, m.Fu, E=m.E, nu=law.nu, name=grade, curve=law.curve(m.Fy, m.Fu, m.E))


def _rod_positions(bp: BasePlate, weak: bool = False) -> list[tuple[float, float]]:
    """Two rows of rods at x = ±f (OpenConex layout) or, with ``weak``, at y = ±f."""
    n = bp.rods_per_side
    ys = ([0.0] if n == 1 else
          [-bp.rod_spacing / 2 + i * bp.rod_spacing / (n - 1) for i in range(n)])
    rows = [(sx * bp.f, y) for sx in (-1, 1) for y in ys]
    return [(y, x) for x, y in rows] if weak else rows


def _hole_and_washer(diameter: float) -> tuple[float, float]:
    d_in = from_internal(diameter, Kind.LENGTH, "in")
    try:
        hole, washer, _ = base_plate_hole(d_in)
    except ValueError:
        hole = diameter + to_internal(0.3125, "in", Kind.LENGTH)
        washer = to_internal(max(2.0, 1.5 * d_in + 0.125), "in", Kind.LENGTH)
    return hole, washer


def model_from_base_plate(bp: BasePlate, *, mu: float | None = None,
                          leveling_nuts: bool = False, grout: float = 0.0,
                          title: str = "", extras: Extras | None = None) -> BasePlateModel:
    extras = extras or Extras()
    col = bp.column
    hole, washer = _hole_and_washer(bp.rod.diameter)
    # Concrete block: the pedestal when given, otherwise the plate scaled so that
    # A2/A1 matches the project (capped at the AISC limit of 4).
    ratio = math.sqrt(min(max(bp.A2_over_A1, 1.0), 4.0))
    cN = bp.pedestal_N or bp.N * ratio
    cB = bp.pedestal_B or bp.B * ratio
    concrete = Concrete(fc=bp.fc, N=max(cN, bp.N), B=max(cB, bp.B),
                        H=max(cN, cB, bp.N, bp.B), grout=grout)
    hef = bp.hef or 12 * bp.rod.diameter
    anchor = AnchorSpec(diameter=bp.rod.diameter, hole=hole, washer=washer, hef=hef,
                        Fu=bp.rod.material.Fu, leveling_nuts=leveling_nuts,
                        welded_washers=bp.washer_thickness is not None)
    positions = extras.anchors if extras.anchors else _rod_positions(bp, extras.rows_weak)
    section = section_of(col, extras.cross)
    stiffeners, stiffener_steel = (), None
    if extras.stiffeners:
        stiffeners = stiffeners_of(section, extras.stiffeners)
        stiffener_steel = steel_of(bp, extras.stiffeners.grade, extras)
    return BasePlateModel(
        section=section, stiffeners=stiffeners, stiffener_steel=stiffener_steel,
        hairpins=extras.hairpins,
        rebar=(extras.pedestal if extras.pedestal and bp.pedestal_N
               and bp.pedestal_B else None),
        lug=(ShearLug(bp.shear_lug.width, bp.shear_lug.thickness, bp.shear_lug.embedment,
                      bp.shear_lug.direction) if bp.shear_lug else None),
        column_steel=steel_of(bp, col.grade, extras),
        N=bp.N, B=bp.B, tp=bp.tp,
        plate_steel=steel_of(bp, bp.plate_grade, extras),
        weld=bp.flange_weld or min_fillet(min(section.min_wall, bp.tp)),
        cjp=extras.cjp,
        stiffener_weld=(extras.stiffeners.weld or min_fillet(extras.stiffeners.thickness)
                        if extras.stiffeners else 0.0),
        anchors=tuple(Anchor(x, y) for x, y in positions),
        anchor=anchor, concrete=concrete,
        # the same friction coefficient as the friction check of the project
        contact=ContactSettings(mu=mu if mu is not None else bp.friction_mu),
        title=title)


def loads_from_forces(forces: Forces, name: str) -> Loads:
    """OpenConex forces (P compression positive, V2/M3 strong axis) to FEM loads."""
    return Loads(P=forces.P, Vx=forces.V2, Vy=forces.V3, My=forces.M3, Mx=forces.M2, name=name)


def project_loads(project: Project) -> list[tuple[LoadCombination, Loads]]:
    cases = project.case_forces()
    return [(c, loads_from_forces(combine(c, cases), c.name))
            for c in project.load_combinations()]


def model_of(project: Project, **kwargs) -> BasePlateModel:
    """FEM model of an already loaded project."""
    bp = project.base_plate_model()
    grout = project.quantity(project.base_plate.grout, Kind.LENGTH)
    return model_from_base_plate(bp, grout=grout, title=project.info.name, **kwargs)


def model_from_project(path: str | Path, **kwargs) -> tuple[Project, BasePlateModel]:
    """Project and FEM model of a file, with the OpenFEMConex additions applied."""
    project, extras = load_extended(path)
    return project, model_of(project, extras=extras, **kwargs)


def dg1_bending(bp: BasePlate, loads: Loads, method: Method = Method.LRFD) -> BendingResult:
    """DG1 rectangular stress block for P and the strong-axis moment (analytical reference)."""
    return rectangular_bending(loads.P, abs(loads.My), bp.N, bp.B, bp.f, bp.fc, bp.A2_over_A1,
                               method)
