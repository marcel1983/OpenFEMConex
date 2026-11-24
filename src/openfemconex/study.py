# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""One project with its analysis settings: solve a combination and check it.

Shared by the graphical interface; it has no Qt dependency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.base_plate.check import check_base_plate
from openconex.core.loads import LoadCombination, combine
from openconex.io.project import Project
from openconex.report.builder import fmt
from openconex.units import Kind

from openfemconex.checks import EDITIONS, Edition, check_fem
from openfemconex.extras import Extras
from openfemconex.mesh import Mesh, build_mesh
from openfemconex.model import BasePlateModel, Loads, MeshSettings
from openfemconex.openconex_bridge import dg1_bending, model_of, project_loads
from openfemconex.report import ComboReport, render_report
from openfemconex.solve import solve

__all__ = ["Settings", "Study"]


@dataclass
class Settings:
    size: float | None = None
    """Fine mesh size [mm]; None = automatic."""
    layers: int = 4
    edition: str = "current"
    weld_size: float | None = None
    strain_limit: float = 0.05
    leveling_nuts: bool = False
    mu: float | None = None
    threads: int = field(default_factory=lambda: max(1, (os.cpu_count() or 2) // 2))
    ccx: str | None = None


@dataclass
class Study:
    project: Project
    settings: Settings = field(default_factory=Settings)
    extras: Extras = field(default_factory=Extras)

    @property
    def edition(self) -> Edition:
        return EDITIONS[self.settings.edition]

    def model(self) -> BasePlateModel:
        model = model_of(self.project, leveling_nuts=self.settings.leveling_nuts,
                         mu=self.settings.mu, extras=self.extras)
        model.validate()
        bp = self.project.base_plate
        if self.extras.pedestal and not (bp.pedestal_N and bp.pedestal_B):
            raise ValueError("defina las dimensiones del pedestal para usar su refuerzo")
        return model

    def mesh(self, model: BasePlateModel | None = None) -> Mesh:
        return build_mesh(model or self.model(),
                          MeshSettings(size_fine=self.settings.size,
                                       plate_layers=self.settings.layers))

    def combinations(self) -> list[tuple[LoadCombination, Loads]]:
        return project_loads(self.project)

    def run(self, combo: LoadCombination, loads: Loads, out: Path, *, mesh: Mesh | None = None,
            model: BasePlateModel | None = None, reuse: bool = True, cancel=None) -> ComboReport:
        """Solve ``combo`` with ccx and evaluate the code checks."""
        model = model or self.model()
        mesh = mesh or self.mesh(model)
        st = self.settings
        res = solve(model, loads, out, mesh=mesh, threads=st.threads, ccx=st.ccx, reuse=reuse,
                    cancel=cancel)
        bp = self.project.base_plate_model()
        reference: dict[str, float] = {}
        free = bool(self.extras.anchors)
        if not (free or loads.Mx or loads.Vx or loads.Vy):
            ref = dg1_bending(bp, loads, combo.method)
            if ref.case != "not_possible":
                reference = {"T": ref.T, "Y": ref.Y, "fp": ref.fp_max}
        checks = check_fem(bp, res, self.edition, combo.method, weld_size=st.weld_size,
                           strain_limit=st.strain_limit, extras=self.extras)
        analytical = []
        if self.edition.key == "current" and not free:
            try:
                analytical = check_base_plate(bp, combine(combo, self.project.case_forces()),
                                              combo.method, combo.name)
            except Exception:  # the analytical path must not hide the FEM result
                analytical = []
        return ComboReport(res, combo.method.value, checks, analytical, reference)

    def inputs(self, model: BasePlateModel, mesh: Mesh | None = None) -> list[tuple[str, str]]:
        bp = self.project.base_plate_model()
        u = self.project.info.unit_system()
        rows = [
            ("Columna", f"{bp.column.name} ({bp.column.grade})"),
            ("Placa", f"{fmt(bp.N, Kind.LENGTH, u)} × {fmt(bp.B, Kind.LENGTH, u)} × "
                      f"{fmt(bp.tp, Kind.THICKNESS, u)} ({bp.plate_grade})"),
            ("Anclajes", f"{bp.rods} de {fmt(bp.rod.diameter, Kind.LENGTH, u)} "
                         f"({bp.rod.grade}), hef = {fmt(bp.hef, Kind.LENGTH, u)}"),
            ("Concreto", f"f'c = {fmt(bp.fc, Kind.STRESS, u)}, A2/A1 = {bp.A2_over_A1:g}, "
                         + ("fisurado" if bp.cracked else "no fisurado")),
            ("Fricción", f"μ = {model.contact.mu:g}"),
        ]
        if self.extras.anchors:
            rows[2] = ("Anclajes", f"{len(self.extras.anchors)} de "
                                   f"{fmt(bp.rod.diameter, Kind.LENGTH, u)} ({bp.rod.grade}) en "
                                   f"posiciones libres, hef = {fmt(bp.hef, Kind.LENGTH, u)}")
        r = self.extras.pedestal
        if r is not None and bp.pedestal_N and bp.pedestal_B:
            rows.append(("Pedestal", f"{fmt(bp.pedestal_N, Kind.LENGTH, u)} × "
                                     f"{fmt(bp.pedestal_B, Kind.LENGTH, u)}, {r.bars} barras de "
                                     f"{r.bar_diameter:.1f} mm, estribos de "
                                     f"{r.tie_diameter:.1f} mm cada {r.tie_spacing:.0f} mm, "
                                     f"fy = {fmt(r.fy, Kind.STRESS, u)}"))
        s = self.extras.stiffeners
        if s is not None:
            rows.append(("Rigidizadores", f"{s.layout}: {s.length:.0f} × {s.height:.0f} × "
                                          f"{s.thickness:.1f} mm ({s.grade})"))
        if mesh is not None:
            rows.append(("Malla", f"{len(mesh.nodes)} nodos, {mesh.element_count} hexaedros "
                                  "C3D8I"))
        return rows

    def report_html(self, reports: list[ComboReport], model: BasePlateModel,
                    mesh: Mesh | None = None, image: str | None = None,
                    traces: bool = True) -> str:
        return render_report(self.project.info.name, self.edition,
                             self.project.info.unit_system(), reports,
                             self.inputs(model, mesh), image=image, traces=traces)
