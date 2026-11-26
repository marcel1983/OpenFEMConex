# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Render the report figures of an example off screen and say whether they came out.

Diagnostic for the build machines: python packaging/render_check.py OUTDIR
"""

import sys
from pathlib import Path

from openfemconex.extras import load_extended
from openfemconex.study import Settings, Study

out = Path(sys.argv[1] if len(sys.argv) > 1 else "render_check")
out.mkdir(parents=True, exist_ok=True)
project, extras = load_extended(Path(__file__).parents[1] / "examples" / "dg1_2ed_ej_4_7.ocnx")
study = Study(project, Settings(fast=True), extras)
model = study.model()
figures = study.figures(out, [], model, study.mesh(model))
made = [name for items in figures.values() for _, name in items if name]
print("figures:", made)
print("errors:", study.figure_errors)
sys.exit(0 if made else 1)
