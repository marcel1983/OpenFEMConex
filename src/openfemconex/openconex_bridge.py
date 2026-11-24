# SPDX-License-Identifier: GPL-3.0-or-later
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

from openfemconex.extras import Extras, StiffenerSpec, load_extended
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
)

__all__ = ["dg1_bending", "loads_from_forces", "model_from_base_plate", "model_from_project",
           "model_of",
           "project_loads", "section_of"]


def section_of(column: IShape | HSSShape) -> Section:
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

    if spec.layout == "radial":
        if section.kind is not SectionKind.HSS_ROUND:
            raise ValueError("la disposición radial es para columnas circulares")
        r = section.d / 2
        out = []
        for i in range(spec.count):
            a = 2 * math.pi * i / spec.count
            d = (math.cos(a), math.sin(a))
            out.append(make((r * d[0], r * d[1]), d, section.t / 2))
        return tuple(out)
    if section.kind is not SectionKind.I:
        raise ValueError(f"la disposición '{spec.layout}' es para perfiles W; en tubos "
                         "circulares use 'radial'")
    ys = [0.0]
    if spec.layout == "alma y bordes":
        edge = section.bf / 2 - spec.thickness / 2
        ys = [-edge, 0.0, edge]
    return tuple(make((sign * section.d / 2, y), (sign, 0.0), section.tf / 2)
                 for sign in (-1.0, 1.0) for y in ys)


def _rod_positions(bp: BasePlate) -> list[tuple[float, float]]:
    # Same layout as openconex.connections.base_plate.interference
    n = bp.rods_per_side
    ys = ([0.0] if n == 1 else
          [-bp.rod_spacing / 2 + i * bp.rod_spacing / (n - 1) for i in range(n)])
    return [(sx * bp.f, y) for sx in (-1, 1) for y in ys]


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
    col = bp.column
    plate = bp.materials[bp.plate_grade]
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
    positions = extras.anchors if extras and extras.anchors else _rod_positions(bp)
    section = section_of(col)
    stiffeners, stiffener_steel = (), None
    if extras and extras.stiffeners:
        stiffeners = stiffeners_of(section, extras.stiffeners)
        grade = bp.materials[extras.stiffeners.grade]
        stiffener_steel = Steel(grade.Fy, grade.Fu, name=extras.stiffeners.grade)
    return BasePlateModel(
        section=section, stiffeners=stiffeners, stiffener_steel=stiffener_steel,
        hairpins=extras.hairpins if extras else None,
        rebar=(extras.pedestal if extras and extras.pedestal and bp.pedestal_N
               and bp.pedestal_B else None),
        lug=(ShearLug(bp.shear_lug.width, bp.shear_lug.thickness, bp.shear_lug.embedment,
                      bp.shear_lug.direction) if bp.shear_lug else None),
        column_steel=Steel(col.material.Fy, col.material.Fu, name=col.grade),
        N=bp.N, B=bp.B, tp=bp.tp,
        plate_steel=Steel(plate.Fy, plate.Fu, name=bp.plate_grade),
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
