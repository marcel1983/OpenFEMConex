# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Run CalculiX (ccx) on an input deck."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CcxError", "CcxRun", "find_ccx", "run_ccx"]


class CcxError(RuntimeError):
    pass


@dataclass(frozen=True)
class CcxRun:
    inp: Path
    converged: bool
    step: int
    """Last step with a converged increment."""
    step_time: float
    """Fraction of that step reached (1.0 when it completed)."""
    increments: int
    iterations: int
    seconds: float
    log: Path

    @property
    def base(self) -> Path:
        return self.inp.with_suffix("")


def find_ccx(executable: str | None = None) -> str:
    """Path of the ccx executable: argument, $OPENFEMCONEX_CCX, or ccx* on PATH."""
    candidates = [executable, os.environ.get("OPENFEMCONEX_CCX"), "ccx", "ccx_2.22", "ccx_2.21",
                  "ccx_2.20", "ccx_dynamic"]
    for c in candidates:
        if c and (found := shutil.which(c)):
            return found
    raise CcxError("CalculiX (ccx) not found; install it (e.g. 'sudo apt install calculix-ccx') "
                   "or set OPENFEMCONEX_CCX to the executable")


def _read_sta(path: Path) -> tuple[int, float, int, int]:
    step, step_time, incs, iters = 0, 0.0, 0, 0
    if not path.exists():
        return step, step_time, incs, iters
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 7 and parts[0].isdigit():
            attempt = parts[2]
            iters += int(parts[3])
            if not attempt.endswith("U"):
                incs += 1
                step, step_time = int(parts[0]), float(parts[5])
    return step, step_time, incs, iters


def run_ccx(inp: str | Path, *, steps: int = 1, threads: int | None = None,
            executable: str | None = None, timeout: float | None = None) -> CcxRun:
    inp = Path(inp).resolve()
    ccx = find_ccx(executable)
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(threads or max(1, (os.cpu_count() or 2) // 2))
    log = inp.with_suffix(".log")
    for ext in (".sta", ".dat", ".frd", ".cvg"):
        inp.with_suffix(ext).unlink(missing_ok=True)
    t0 = time.monotonic()
    with log.open("w") as out:
        try:
            subprocess.run([ccx, "-i", inp.stem], cwd=inp.parent, env=env, stdout=out,
                           stderr=subprocess.STDOUT, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise CcxError(f"ccx exceeded {timeout} s; see {log}") from exc
    seconds = time.monotonic() - t0
    text = log.read_text(errors="replace")
    if "*ERROR" in text and not inp.with_suffix(".sta").exists():
        first = next(line for line in text.splitlines() if "*ERROR" in line)
        raise CcxError(f"ccx rejected the input: {first.strip()} (see {log})")
    step, step_time, incs, iters = _read_sta(inp.with_suffix(".sta"))
    converged = step == steps and abs(step_time - 1.0) < 1e-9 and "Job finished" in text
    return CcxRun(inp=inp, converged=converged, step=step, step_time=step_time, increments=incs,
                  iterations=iters, seconds=seconds, log=log)
