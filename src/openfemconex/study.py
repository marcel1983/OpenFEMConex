# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""One project with its analysis settings: solve a combination and check it.

Shared by the graphical interface; it has no Qt dependency.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path

from openconex.connections.base_plate.check import check_base_plate
from openconex.core.loads import LoadCombination, combine
from openconex.io.project import Project
from openconex.report.builder import fmt
from openconex.units import Kind

from openfemconex.advice import advise
from openfemconex.checks import EDITIONS, Edition, check_fem
from openfemconex.extras import Extras
from openfemconex.i18n import tr
from openfemconex.mesh import Mesh, build_mesh
from openfemconex.model import BasePlateModel, Loads, MeshSettings
from openfemconex.openconex_bridge import dg1_bending, model_of, project_loads
from openfemconex.report import ComboReport, render_report, report_blocks
from openfemconex.solve import solve
from openfemconex.units import display_units

__all__ = ["Settings", "Study"]


@dataclass
class Settings:
    size: float | None = None
    """Fine mesh size [mm]; None = automatic."""
    layers: int = 4
    fast: bool = False
    """Automatic mesh that favours solution time."""
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
                                       plate_layers=self.settings.layers,
                                       fast=self.settings.fast))

    def combinations(self) -> list[tuple[LoadCombination, Loads]]:
        return project_loads(self.project)

    def run(self, combo: LoadCombination, loads: Loads, out: Path, *, mesh: Mesh | None = None,
            model: BasePlateModel | None = None, reuse: bool = True, cancel=None,
            progress=None) -> ComboReport:
        """Solve ``combo`` with ccx and evaluate the code checks."""
        model = model or self.model()
        mesh = mesh or self.mesh(model)
        st = self.settings
        res = solve(model, loads, out, mesh=mesh, threads=st.threads, ccx=st.ccx, reuse=reuse,
                    cancel=cancel, progress=progress)
        if progress is not None:
            progress(tr("Verificaciones de AISC y ACI"))
        if mesh.settings.fast:
            res.warnings.append(tr(
                "Resuelto con la malla rápida: las fuerzas en anclajes y el aplastamiento "
                "difieren menos de 3 % de la malla normal, pero la soldadura columna-placa puede "
                "quedar hasta 10 % por debajo y la deformación plástica bastante por debajo. "
                "Confirme con la malla normal antes de la memoria final."))
        bp = self.project.base_plate_model()
        reference: dict[str, float] = {}
        # free anchors or a cruciform column: the DG1 rigid-plate path does not apply
        free = (bool(self.extras.anchors) or self.extras.cross is not None
                or self.extras.rows_weak)
        if not (free or loads.Mx or loads.Vx or loads.Vy):
            ref = dg1_bending(bp, loads, combo.method)
            if ref.case != "not_possible":
                reference = {"T": ref.T, "Y": ref.Y, "fp": ref.fp_max}
        checks = check_fem(bp, res, self.edition, combo.method, weld_size=st.weld_size,
                           strain_limit=st.strain_limit, extras=self.extras,
                           mu=model.contact.mu)
        analytical = []
        if self.edition.key == "current" and not free:
            try:
                analytical = check_base_plate(bp, combine(combo, self.project.case_forces()),
                                              combo.method, combo.name)
            except Exception:  # the analytical path must not hide the FEM result
                analytical = []
        advice = advise(bp, res, checks, display_units(self.project.info), self.edition,
                        self.extras)
        return ComboReport(res, combo.method.value, checks, analytical, reference, advice)

    def column_text(self) -> str:
        col = self.project.base_plate_model().column
        cross = self.extras.cross
        if cross is not None:
            return tr("cruciforme {main} + {cross} ({grade})", main=col.name, cross=cross.name,
                      grade=col.grade)
        return f"{col.name} ({col.grade})"

    def inputs(self, model: BasePlateModel, mesh: Mesh | None = None) -> list[tuple[str, str]]:
        bp = self.project.base_plate_model()
        u = display_units(self.project.info)
        cracked = tr("fisurado") if bp.cracked else tr("no fisurado")
        rows = [
            (tr("Columna"), self.column_text()),
            (tr("Placa"), f"{fmt(bp.N, Kind.LENGTH, u)} × {fmt(bp.B, Kind.LENGTH, u)} × "
                          f"{fmt(bp.tp, Kind.THICKNESS, u)} ({bp.plate_grade})"),
            (tr("Anclajes"), tr("{n} de {d} ({grade}), hef = {hef}", n=bp.rods,
                                d=fmt(bp.rod.diameter, Kind.LENGTH, u), grade=bp.rod.grade,
                                hef=fmt(bp.hef, Kind.LENGTH, u))),
            (tr("Concreto"), f"f'c = {fmt(bp.fc, Kind.STRESS, u)}, A2/A1 = {bp.A2_over_A1:g}, "
                             + cracked),
            (tr("Fricción"), f"μ = {model.contact.mu:g}"),
        ]
        if self.extras.anchors:
            rows[2] = (tr("Anclajes"), tr("{n} de {d} ({grade}) en posiciones libres, hef = {hef}",
                                          n=len(self.extras.anchors),
                                          d=fmt(bp.rod.diameter, Kind.LENGTH, u),
                                          grade=bp.rod.grade, hef=fmt(bp.hef, Kind.LENGTH, u)))
        r = self.extras.pedestal
        if r is not None and bp.pedestal_N and bp.pedestal_B:
            rows.append((tr("Pedestal"), f"{fmt(bp.pedestal_N, Kind.LENGTH, u)} × "
                                         f"{fmt(bp.pedestal_B, Kind.LENGTH, u)}, " + tr(
                "{n} barras de {d}, estribos de {t} cada {s}, fy = {fy}", n=r.bars,
                d=self.length_text(r.bar_diameter), t=self.length_text(r.tie_diameter),
                s=self.length_text(r.tie_spacing), fy=fmt(r.fy, Kind.STRESS, u))))
        h = self.extras.hairpins
        if h is not None:
            rows.append((tr("Horquillas en U"), tr(
                "{n} por anclaje de {d}, patas a {o} del anclaje, largo {L}, fy = {fy}",
                n=h.count, d=self.length_text(h.diameter), o=self.length_text(h.offset),
                L=self.length_text(h.leg_length), fy=fmt(h.fy, Kind.STRESS, u))))
        s = self.extras.stiffeners
        if s is not None:
            L = self.length_text
            rows.append((tr("Rigidizadores"), f"{tr(s.layout)}: {L(s.length)} × {L(s.height)} × "
                                              f"{L(s.thickness)} ({s.grade})"))
        if mesh is not None:
            rows.append((tr("Malla"), tr("{nodes} nodos, {elements} hexaedros C3D8I",
                                         nodes=len(mesh.nodes), elements=mesh.element_count)
                         + (" " + tr("(malla rápida)") if mesh.settings.fast else "")))
        return rows

    def force_unit(self) -> tuple[float, str]:
        """(factor from N, label) of the force unit used for presentation."""
        sample = fmt(1000.0, Kind.FORCE, display_units(self.project.info), 6).split()
        return float(sample[0]) / 1000.0, sample[-1]

    def length_text(self, value: float) -> str:
        """A dimension in the project units (mm or in)."""
        return fmt(value, Kind.THICKNESS, display_units(self.project.info), 4)

    def callouts(self, model: BasePlateModel) -> dict[str, str]:
        """Texts of the callouts of the plan and elevation drawings: element and material."""
        bp = self.project.base_plate_model()
        u = display_units(self.project.info)
        L = self.length_text
        ex = self.extras
        col = bp.column
        out = {
            "column": tr("Columna {name} — {grade}", name=model.section.name, grade=col.grade),
            "plate": tr("Placa base {n} × {b} × {t} — {grade}", n=L(bp.N), b=L(bp.B), t=L(bp.tp),
                        grade=bp.plate_grade),
            "anchor": tr("{n} anclajes Ø {d} — {grade}, hef = {hef}", n=len(model.anchors),
                         d=L(bp.rod.diameter), grade=bp.rod.grade,
                         hef=L(model.anchor.hef)),
            "concrete": (tr("Pedestal {n} × {b}, f'c = {fc}", n=L(bp.pedestal_N),
                            b=L(bp.pedestal_B), fc=fmt(bp.fc, Kind.STRESS, u))
                         if bp.pedestal_N and bp.pedestal_B else
                         tr("Concreto f'c = {fc}", fc=fmt(bp.fc, Kind.STRESS, u))),
        }
        if model.concrete.grout > 0:
            out["grout"] = tr("Mortero de nivelación {t}", t=L(model.concrete.grout))
        if ex.cjp:
            out["weld"] = tr("Soldadura de penetración completa (CJP) columna-placa")
        else:
            electrode = bp.electrode
            out["weld"] = tr("Soldadura de filete {w} ({e}) todo alrededor", w=L(model.weld),
                             e=electrode)
        if ex.stiffeners and model.stiffeners:
            out["stiffener"] = tr("{n} rigidizadores PL {t} — {grade}", n=len(model.stiffeners),
                                  t=L(ex.stiffeners.thickness), grade=ex.stiffeners.grade)
            out["stiffener_weld"] = tr("Filete {w} a ambos lados del rigidizador",
                                       w=L(model.stiffener_weld))
        if model.lug is not None and bp.shear_lug is not None:
            out["lug"] = tr("Llave de cortante PL {w} × {t}, empotrada {e} — {grade}",
                            w=L(model.lug.width), t=L(model.lug.thickness),
                            e=L(model.lug.embedment), grade=bp.shear_lug.grade)
        return out

    def figures(self, out: Path, reports: list[ComboReport], model: BasePlateModel,
                mesh: Mesh) -> dict[str, list[tuple[str, str]]]:
        """Render the report figures into ``out`` (empty without PyVista or OpenGL)."""
        from openfemconex.scenes import render_figures
        from openfemconex.solve import file_stem

        factor, label = self.force_unit()
        solved = [(r.results.load, out / f"{file_stem(r.results.load)}.vtu", r.results)
                  for r in reports]
        solved = [s for s in solved if s[1].exists()]
        self.figure_errors: list[str] = []
        figures = render_figures(out, model, mesh, solved, unit_force=factor, force_label=label,
                                 length=self.length_text, callouts=self.callouts(model),
                                 errors=self.figure_errors)
        # add the peak value of each figure to its caption
        u = display_units(self.project.info)
        for r in reports:
            res = r.results
            top = max(abs(v) for v in res.column_top_displacement)
            peaks = {
                "von_Mises": tr("máx. placa {p}, columna {c}",
                                p=fmt(res.plate_von_mises_max, Kind.STRESS, u),
                                c=fmt(res.column_von_mises_max, Kind.STRESS, u)),
                "PEEQ": tr("máx. placa {p}, columna {c}", p=f"{100 * res.plate_peeq_max:.2f} %",
                           c=f"{100 * res.column_peeq_max:.2f} %"),
                "_U": tr("cabeza de la columna {d}", d=fmt(top, Kind.THICKNESS, u, 3)),
                "CPRESS": tr("máx. {m}, media {a}",
                             m=fmt(res.bearing_pressure_max, Kind.STRESS, u),
                             a=fmt(res.bearing_pressure_mean, Kind.STRESS, u)),
            }
            figures[res.load] = [
                (caption + next((f": {text}" for key, text in peaks.items()
                                 if name and name.endswith(f"{key.lstrip('_')}.png")), ""), name)
                for caption, name in figures.get(res.load, [])]
        return figures

    def ficha(self) -> list[tuple[str, str]]:
        """Identification card at the head of the report."""
        info = self.project.info
        rows = [(tr("Proyecto"), info.name), (tr("Número de proyecto"), info.number),
                (tr("Cliente"), info.client), (tr("Conexión"), self.extras.connection),
                (tr("Ingeniero"), info.engineer), (tr("Revisión"), info.revision),
                (tr("Fecha"), info.date or dt.date.today().isoformat())]
        return [(k, v) for k, v in rows if v]

    def installation(self, model: BasePlateModel) -> list[str]:
        """Installation requirements that make the assumptions of the analysis valid."""
        from openfemconex.advice import installation_notes

        return installation_notes(model, display_units(self.project.info))

    def report_title(self) -> str:
        name = self.extras.connection or self.project.info.name
        return tr("Memoria de cálculo: {name}", name=name) if name else tr("Memoria de cálculo")

    def report_blocks(self, reports: list[ComboReport], model: BasePlateModel,
                      mesh: Mesh | None = None, traces: bool = True,
                      figures: dict | None = None) -> list:
        return report_blocks(self.report_title(), self.edition,
                             display_units(self.project.info), reports,
                             self.inputs(model, mesh), traces=traces, figures=figures,
                             ficha=self.ficha(), installation=self.installation(model))

    def report_html(self, reports: list[ComboReport], model: BasePlateModel,
                    mesh: Mesh | None = None, image: str | None = None,
                    traces: bool = True, figures: dict | None = None,
                    figure_base: str = "") -> str:
        return render_report(self.report_title(), self.edition,
                             display_units(self.project.info), reports,
                             self.inputs(model, mesh), image=image, traces=traces,
                             figures=figures, figure_base=figure_base, ficha=self.ficha(),
                             installation=self.installation(model))

    def report_docx(self, path: Path, reports: list[ComboReport], model: BasePlateModel,
                    mesh: Mesh | None = None, figures: dict | None = None,
                    figure_dir: Path | None = None) -> Path:
        """Editable Word report; the figures are read from ``figure_dir``."""
        from openfemconex.report_docx import write_docx

        blocks = self.report_blocks(reports, model, mesh, traces=True, figures=figures)
        return write_docx(blocks, path, figure_dir or Path(path).parent)
