# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Run CalculiX (ccx) on an input deck."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CcxCancelled", "CcxError", "CcxRun", "find_ccx", "read_run", "run_ccx"]


class CcxError(RuntimeError):
    pass


class CcxCancelled(CcxError):
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
    """Path of the ccx executable.

    Order: argument, $OPENFEMCONEX_CCX, ccx* on PATH, and last the copy bundled with
    the packaged application (so a system CalculiX is preferred when there is one).
    """
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "ccx" / ("ccx.exe" if os.name == "nt"
                                                            else "ccx")
    candidates = [executable, os.environ.get("OPENFEMCONEX_CCX"), "ccx", "ccx_2.22", "ccx_2.21",
                  "ccx_2.20", "ccx_dynamic", str(bundled) if bundled.is_file() else None]
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


def _log_says(log: Path, text: str) -> bool:
    try:
        with log.open("rb") as f:
            f.seek(max(0, log.stat().st_size - 20000))
            return text.encode() in f.read()
    except OSError:
        return False


def run_ccx(inp: str | Path, *, steps: int = 1, threads: int | None = None,
            executable: str | None = None, timeout: float | None = None,
            cancel: threading.Event | None = None) -> CcxRun:
    inp = Path(inp).resolve()
    ccx = find_ccx(executable)
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = str(threads or max(1, (os.cpu_count() or 2) // 2))
    log = inp.with_suffix(".log")
    for ext in (".sta", ".dat", ".frd", ".cvg"):
        inp.with_suffix(ext).unlink(missing_ok=True)
    t0 = time.monotonic()
    with log.open("w") as out:
        proc = subprocess.Popen([ccx, "-i", inp.stem], cwd=inp.parent, env=env, stdout=out,
                                stderr=subprocess.STDOUT)
        polls = 0
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                proc.kill()
                proc.wait()
                raise CcxCancelled("analysis cancelled")
            polls += 1
            if polls % 10 == 0 and _log_says(log, "nonpositive jacobian"):
                proc.kill()
                proc.wait()
                raise CcxError(f"CalculiX found distorted elements (nonpositive jacobian); "
                               f"use a smaller mesh size (see {log})")
            if timeout is not None and time.monotonic() - t0 > timeout:
                proc.kill()
                proc.wait()
                raise CcxError(f"ccx exceeded {timeout} s; see {log}")
            time.sleep(0.1)
    seconds = time.monotonic() - t0
    text = log.read_text(errors="replace")
    if "nonpositive jacobian" in text:
        raise CcxError(f"CalculiX found distorted elements (nonpositive jacobian); use a "
                       f"smaller mesh size (see {log})")
    if "*ERROR" in text and not inp.with_suffix(".sta").exists():
        first = next(line for line in text.splitlines() if "*ERROR" in line)
        raise CcxError(f"ccx rejected the input: {first.strip()} (see {log})")
    return read_run(inp, steps, seconds)


def read_run(inp: str | Path, steps: int = 1, seconds: float = 0.0) -> CcxRun:
    """Status of a finished ccx run from its .sta and .log files."""
    inp = Path(inp).resolve()
    log = inp.with_suffix(".log")
    text = log.read_text(errors="replace") if log.exists() else ""
    step, step_time, incs, iters = _read_sta(inp.with_suffix(".sta"))
    converged = step == steps and abs(step_time - 1.0) < 1e-9 and "Job finished" in text
    return CcxRun(inp=inp, converged=converged, step=step, step_time=step_time,
                  increments=incs, iterations=iters, seconds=seconds, log=log)
