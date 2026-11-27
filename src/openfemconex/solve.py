# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Model -> mesh -> .inp -> ccx -> results, for one load combination."""

from __future__ import annotations

import re
from pathlib import Path

from openfemconex.diagnostics import COLLAPSE, HOPELESS, column_usage, diagnose
from openfemconex.i18n import tr
from openfemconex.inp import write_inp
from openfemconex.mesh import Mesh, build_mesh
from openfemconex.model import BasePlateModel, Loads, MeshSettings
from openfemconex.results import Results, summarize
from openfemconex.runner import read_run, run_ccx
from openfemconex.vtk import write_vtu

__all__ = ["ColumnOverloaded", "file_stem", "solve"]


class ColumnOverloaded(RuntimeError):
    """The column cannot carry the loads; the analysis is not started."""


def file_stem(name: str) -> str:
    """File name used for the files of a load combination."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name) or "load"


def solve(model: BasePlateModel, loads: Loads, workdir: str | Path, *,
          mesh: Mesh | None = None, settings: MeshSettings | None = None,
          threads: int | None = None, ccx: str | None = None,
          only_write: bool = False, reuse: bool = False, cancel=None,
          progress=None) -> Results | Path:
    """Solve one combination; returns the results (or the .inp path with ``only_write``).

    With ``reuse`` an existing solution of the same input deck is read instead of
    running ccx again. ``progress`` receives a short text at each stage.
    """
    def stage(text: str) -> None:
        if progress is not None:
            progress(text)

    workdir = Path(workdir)
    warnings = diagnose(model, loads)
    # a column that cannot carry the loads will not converge with any anchor law
    usage = max(column_usage(model, loads))
    collapse = usage > COLLAPSE
    if usage > HOPELESS and not only_write:
        raise ColumnOverloaded(" ".join(warnings))
    workdir.mkdir(parents=True, exist_ok=True)
    if mesh is None:
        stage(tr("Generando la malla"))
        mesh = build_mesh(model, settings)
    stem = file_stem(loads.name)
    inp = workdir / f"{stem}.inp"
    exts = (".inp", ".frd", ".dat", ".sta", ".log", ".cvg")
    with_knee = inp.with_suffix(".knee")  # marks a solution found with the softened law
    previous = inp.read_text() if inp.exists() else None
    # with a column that cannot carry the loads, stop at the collapse instead of
    # cutting the increment down for a long time
    inc_min = 0.02 if collapse else 1e-6
    stage(tr("Escribiendo el archivo de CalculiX (.inp)"))
    numbering = write_inp(inp, model, mesh, loads, knee=with_knee.exists(),
                          min_increment=inc_min)
    if only_write:
        return inp
    # a run counts as solved only when its results were read to the end (the .json is
    # written last): a run that was stopped or crashed leaves .frd/.dat/.sta files of
    # its first increments, which must not be taken as the solution
    done = workdir / f"{stem}.json"
    solved = all(inp.with_suffix(e).exists() for e in (".frd", ".dat", ".sta")) and \
        done.exists() and done.stat().st_mtime >= inp.with_suffix(".frd").stat().st_mtime
    if reuse and solved and previous == inp.read_text():
        stage(tr("Los datos no cambiaron: se reutiliza la solución anterior"))
        run = read_run(inp, numbering.steps)
    else:
        with_knee.unlink(missing_ok=True)
        numbering = write_inp(inp, model, mesh, loads, min_increment=inc_min)
        stage(tr("CalculiX resolviendo"))
        run = run_ccx(inp, steps=numbering.steps, threads=threads, executable=ccx,
                      cancel=cancel)
        if not run.converged and not collapse:
            # Retry with the softened anchor law; keep it only if it gets further.
            keep = workdir / f"{stem}_first"
            for ext in exts:
                if inp.with_suffix(ext).exists():
                    inp.with_suffix(ext).replace(keep.with_suffix(ext))
            stage(tr("CalculiX no convergió: se reintenta con la ley de anclaje suavizada"))
            retry_numbering = write_inp(inp, model, mesh, loads, knee=True)
            retry = run_ccx(inp, steps=retry_numbering.steps, threads=threads, executable=ccx,
                            cancel=cancel)
            if (retry.step, retry.step_time) > (run.step, run.step_time):
                run, numbering = retry, retry_numbering
                with_knee.write_text("anchor law with knee\n")
                for ext in exts:
                    keep.with_suffix(ext).unlink(missing_ok=True)
            else:
                for ext in exts:
                    if keep.with_suffix(ext).exists():
                        keep.with_suffix(ext).replace(inp.with_suffix(ext))
    if run.step == 0 or not run.base.with_suffix(".dat").read_text().strip():
        reason = " ".join(warnings)
        raise RuntimeError(f"ccx did not converge on the first increment; see {run.log}"
                           + (f". {reason}" if reason else ""))
    # Fractions of the axial load and of the moments and shears actually reached.
    if numbering.steps == 2:
        fractions = (1.0, run.step_time) if run.step == 2 else (run.step_time, 0.0)
    else:
        fractions = (run.step_time, run.step_time)
    stage(tr("Leyendo los resultados"))
    res = summarize(run.base, model, mesh, numbering, loads, converged=run.converged,
                    fractions=fractions, seconds=run.seconds)
    res.solver.update(increments=run.increments, iterations=run.iterations)
    res.warnings = warnings
    res.to_json(workdir / f"{stem}.json")
    write_vtu(workdir / f"{stem}.vtu", mesh, run.base.with_suffix(".frd"))
    return res
