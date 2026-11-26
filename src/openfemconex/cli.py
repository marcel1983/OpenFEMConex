# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Command line: ``openfemconex run proyecto.ocnx``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openfemconex.model import MeshSettings
from openfemconex.results import Results
from openfemconex.units import display_units

KIP = 4448.2216152605
INCH = 25.4
KSI = 6.894757293168


def _report(res: Results, us: bool) -> str:
    f, fu = (1 / KIP, "kip") if us else (1e-3, "kN")
    s, su = (1 / KSI, "ksi") if us else (1.0, "MPa")
    d, du = (1 / INCH, "in") if us else (1.0, "mm")
    a = res.applied
    lines = [
        f"Combinación {res.load}: " + ("convergió" if res.converged else
                                      f"NO convergió (llegó al {100 * res.load_fraction:.0f} % "
                                      "de la carga)"),
        f"  Cargas: P = {a['P'] * f:.1f} {fu}, My = {a['My'] * f * d:.0f} {fu}·{du}, "
        f"Mx = {a['Mx'] * f * d:.0f} {fu}·{du}, Vx = {a['Vx'] * f:.1f} {fu}, "
        f"Vy = {a['Vy'] * f:.1f} {fu}",
        f"  Malla: {res.mesh.get('nodes', 0)} nodos, {res.mesh.get('elements', 0)} hexaedros; "
        f"ccx {res.solver.get('seconds', 0):.0f} s, {res.solver.get('increments', 0):.0f} "
        f"incrementos",
        "  Anclajes (tracción +):",
    ]
    for i, an in enumerate(res.anchors, start=1):
        lines.append(f"    {i}: x = {an.x * d:7.2f} {du}, y = {an.y * d:7.2f} {du}, "
                     f"T = {an.tension * f:7.1f} {fu}, Vx = {an.Vx * f:6.1f}, "
                     f"Vy = {an.Vy * f:6.1f} {fu}, levantamiento = {an.uplift:.3f} mm")
    lines += [
        f"  Tracción total en anclajes: {res.anchor_tension_total * f:.1f} {fu}",
        f"  Compresión sobre el concreto: {res.bearing_force * f:.1f} {fu}",
        f"  Cortante por fricción: Vx = {res.friction[0] * f:.1f} {fu}, "
        f"Vy = {res.friction[1] * f:.1f} {fu}",
        f"  Presión de contacto: máxima {res.bearing_pressure_max * s:.2f} {su}, media "
        f"{res.bearing_pressure_mean * s:.2f} {su}, longitud de apoyo "
        f"{res.bearing_length_x * d:.2f} {du}, centroide x = {res.bearing_centroid[0] * d:.2f} "
        f"{du}",
        f"  Placa: von Mises máx. {res.plate_von_mises_max * s:.1f} {su}, deformación plástica "
        f"equivalente máx. {100 * res.plate_peeq_max:.2f} %",
        f"  Columna: von Mises máx. {res.column_von_mises_max * s:.1f} {su}, PEEQ máx. "
        f"{100 * res.column_peeq_max:.2f} %",
        f"  Equilibrio: error vertical {100 * res.equilibrium_error:.2f} %, "
        f"error de momento {100 * res.moment_error:.2f} %",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openfemconex", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="genera el .inp, corre CalculiX y resume los resultados")
    run.add_argument("project", type=Path, help="proyecto de OpenConex (.ocnx)")
    run.add_argument("-c", "--combo", action="append",
                     help="combinación a resolver (por defecto todas)")
    run.add_argument("-o", "--out", type=Path, help="carpeta de salida")
    run.add_argument("--size", type=float, help="tamaño fino de malla [mm]")
    run.add_argument("--layers", type=int, default=4, help="capas en el espesor de la placa")
    run.add_argument("--rapida", "--fast", dest="fast", action="store_true",
                     help="malla automática más gruesa que prioriza el tiempo de solución")
    run.add_argument("--threads", type=int)
    run.add_argument("--ccx", help="ejecutable de CalculiX")
    run.add_argument("--only-inp", action="store_true", help="solo escribe el .inp")
    run.add_argument("--leveling-nuts", action="store_true",
                     help="los anclajes también toman compresión")
    run.add_argument("--mu", type=float, help="coeficiente de fricción placa-concreto")
    run.add_argument("--edition", choices=["current", "dg1-2ed"], default="current",
                     help="normas: vigentes (AISC 360-22, ACI 318-19) o las de la DG1 2.ª ed.")
    run.add_argument("--weld", type=float, help="tamaño del filete columna-placa [mm]")
    run.add_argument("--strain-limit", type=float, default=0.05,
                     help="límite de deformación plástica de la placa (0.05)")
    run.add_argument("--reuse", action="store_true",
                     help="reutiliza la solución de ccx si el .inp no cambió")
    run.add_argument("--no-figures", action="store_true",
                     help="no renderiza los gráficos del reporte")
    run.add_argument("--list", action="store_true", help="lista las combinaciones y sale")
    args = parser.parse_args(argv)

    from openconex.connections.base_plate.check import check_base_plate
    from openconex.core.loads import combine
    from openconex.report.builder import fmt
    from openconex.units import Kind

    from openfemconex.advice import advise
    from openfemconex.checks import EDITIONS, check_fem
    from openfemconex.diagnostics import diagnose
    from openfemconex.extras import load_extended
    from openfemconex.i18n import tr
    from openfemconex.mesh import build_mesh
    from openfemconex.openconex_bridge import dg1_bending, model_of, project_loads
    from openfemconex.report import ComboReport, check_title, write_report
    from openfemconex.solve import ColumnOverloaded, solve

    project, extras = load_extended(args.project)
    from openfemconex.i18n import set_language

    set_language(project.info.language)
    model = model_of(project, leveling_nuts=args.leveling_nuts, mu=args.mu, extras=extras)
    free = bool(extras.anchors) or extras.cross is not None or extras.rows_weak
    combos = project_loads(project)
    us = project.info.units == "US"
    if args.list:
        for c, ld in combos:
            print(f"{c.name} ({c.method}): P = {ld.P / 1e3:.1f} kN, My = {ld.My / 1e6:.1f} kN·m, "
                  f"Vx = {ld.Vx / 1e3:.1f} kN")
        return 0
    if args.combo:
        known = {c.name for c, _ in combos}
        if missing := [n for n in args.combo if n not in known]:
            parser.error(f"combinación desconocida: {missing}; disponibles: {sorted(known)}")
        combos = [(c, ld) for c, ld in combos if c.name in args.combo]
    out = args.out or args.project.with_suffix("").with_name(args.project.stem + "_fem")
    mesh = build_mesh(model, MeshSettings(size_fine=args.size, plate_layers=args.layers,
                                          fast=args.fast))
    print(f"Malla: {len(mesh.nodes)} nodos, {mesh.element_count} hexaedros"
          + (" (malla rápida: confirme la soldadura y la deformación plástica con la malla "
             "normal)" if mesh.settings.fast else ""))
    status = 0
    f, fu = (1 / KIP, "kip") if us else (1e-3, "kN")
    s, su = (1 / KSI, "ksi") if us else (1.0, "MPa")
    d, du = (1 / INCH, "in") if us else (1.0, "mm")
    bp = project.base_plate_model()
    edition = EDITIONS[args.edition]
    cases = project.case_forces()
    units = display_units(project.info)
    reports = []
    for combo, loads in combos:
        for note in diagnose(model, loads):
            print(tr("Aviso: {msg}", msg=note))
        try:
            res = solve(model, loads, out, mesh=mesh, threads=args.threads, ccx=args.ccx,
                        only_write=args.only_inp, reuse=args.reuse)
        except ColumnOverloaded:
            print(tr("{name}: no se resolvió porque la columna no resiste las cargas.",
                     name=loads.name))
            status = 1
            continue
        if isinstance(res, Path):
            print(f"Escrito {res}")
            continue
        print(_report(res, us))
        reference = {}
        if not (free or loads.Mx or loads.Vx or loads.Vy):
            ref = dg1_bending(bp, loads, combo.method)
            if ref.case != "not_possible":
                reference = {"T": ref.T, "Y": ref.Y, "fp": ref.fp_max}
                print(f"  Referencia DG1 (bloque rectangular, {combo.method}, {ref.case}): "
                      f"T = {ref.T * f:.1f} {fu}, Y = {ref.Y * d:.2f} {du}, "
                      f"fp = {ref.fp_max * s:.2f} {su}")
        checks = check_fem(bp, res, edition, combo.method, weld_size=args.weld,
                           strain_limit=args.strain_limit, extras=extras,
                           mu=model.contact.mu)
        print(f"  Verificaciones ({edition.aisc}, {edition.aci}):")
        for r in checks:
            mark = {"ok": "OK ", "ng": "NO "}.get(r.status.value, "-- ")
            print(f"    {mark} {r.ratio:5.2f}  "
                  f"{check_title(r)}  [{r.clause}]")
        analytical = []
        if edition.key == "current" and not free:
            try:
                analytical = check_base_plate(bp, combine(combo, cases), combo.method,
                                              combo.name)
            except Exception as exc:  # the analytical path must not hide the FEM result
                print(f"  (camino analítico no disponible: {exc})")
        advice = advise(bp, res, checks, units, edition, extras)
        for cid, items in advice.items():
            title = next((check_title(r) for r in checks if r.id == cid), cid)
            print(f"  {tr('Recomendaciones')} — {title}:")
            for item in items:
                print(f"    - {item}")
        reports.append(ComboReport(res, combo.method.value, checks, analytical, reference,
                                   advice))
        status |= 0 if res.converged and all(r.status.value != "ng" for r in checks) else 1
    if reports:
        inputs = [
            ("Columna", model.section.name + f" ({bp.column.grade})"),
            ("Placa", f"{fmt(bp.N, Kind.LENGTH, units)} × {fmt(bp.B, Kind.LENGTH, units)} × "
                      f"{fmt(bp.tp, Kind.THICKNESS, units)} ({bp.plate_grade})"),
            ("Anclajes", f"{bp.rods} de {fmt(bp.rod.diameter, Kind.LENGTH, units)} "
                         f"({bp.rod.grade}), hef = {fmt(bp.hef, Kind.LENGTH, units)}"),
            ("Concreto", f"f'c = {fmt(bp.fc, Kind.STRESS, units)}, A2/A1 = {bp.A2_over_A1:g}, "
                         + ("fisurado" if bp.cracked else "no fisurado")),
            ("Fricción", f"μ = {model.contact.mu:g}"),
            ("Malla", f"{len(mesh.nodes)} nodos, {mesh.element_count} hexaedros C3D8I"
                      + (" (malla rápida)" if mesh.settings.fast else "")),
        ]
        figures = {}
        if not args.no_figures:
            from openfemconex.study import Settings, Study

            study = Study(project, Settings(edition=args.edition), extras)
            figures = study.figures(out, reports, model, mesh)
        path = write_report(out / "reporte.html", project.info.name, edition, units, reports,
                            inputs, figures=figures)
        print(f"Reporte: {path}")
        print(f"Archivos por combinación (.inp, .json, .vtu, .frd, .dat) en {out}")
    return status


if __name__ == "__main__":
    sys.exit(main())
