# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Model -> mesh -> .inp -> ccx -> results, for one load combination."""

from __future__ import annotations

import re
from pathlib import Path

from openfemconex.inp import write_inp
from openfemconex.mesh import Mesh, build_mesh
from openfemconex.model import BasePlateModel, Loads, MeshSettings
from openfemconex.results import Results, summarize
from openfemconex.runner import run_ccx
from openfemconex.vtk import write_vtu

__all__ = ["solve"]


def solve(model: BasePlateModel, loads: Loads, workdir: str | Path, *,
          mesh: Mesh | None = None, settings: MeshSettings | None = None,
          threads: int | None = None, ccx: str | None = None,
          only_write: bool = False) -> Results | Path:
    """Solve one combination; returns the results (or the .inp path with ``only_write``)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mesh = mesh or build_mesh(model, settings)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", loads.name) or "load"
    inp = workdir / f"{stem}.inp"
    numbering = write_inp(inp, model, mesh, loads)
    if only_write:
        return inp
    run = run_ccx(inp, steps=numbering.steps, threads=threads, executable=ccx)
    if run.step == 0:
        raise RuntimeError(f"ccx did not converge on the first increment; see {run.log}")
    # Fractions of the axial load and of the moments and shears actually reached.
    if numbering.steps == 2:
        fractions = (1.0, run.step_time) if run.step == 2 else (run.step_time, 0.0)
    else:
        fractions = (run.step_time, run.step_time)
    res = summarize(run.base, model, mesh, numbering, loads, converged=run.converged,
                    fractions=fractions, seconds=run.seconds)
    res.solver.update(increments=run.increments, iterations=run.iterations)
    res.to_json(workdir / f"{stem}.json")
    write_vtu(workdir / f"{stem}.vtu", mesh, run.base.with_suffix(".frd"))
    return res
