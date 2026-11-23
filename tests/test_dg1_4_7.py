# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""AISC Design Guide 1, 2nd ed., Example 4.7 (W12x96, large moment), solved by FEM."""

import shutil
from pathlib import Path

import pytest

from openfemconex.checks import CURRENT, DG1_2ED, check_fem
from openfemconex.model import MeshSettings
from openfemconex.openconex_bridge import dg1_bending, model_from_project, project_loads
from openfemconex.report import ComboReport, render_report
from openfemconex.solve import solve

EXAMPLE = Path(__file__).parents[1] / "examples" / "dg1_2ed_ej_4_7.ocnx"
KIP = 4448.2216152605


@pytest.fixture(scope="module")
def case():
    project, model = model_from_project(EXAMPLE)
    loads = dict((c.name, ld) for c, ld in project_loads(project))["LRFD-2"]
    return project, model, loads


def test_loads_match_the_guide(case):
    _, _, loads = case
    assert loads.P / KIP == pytest.approx(376.0, abs=0.01)
    assert loads.My / KIP / 25.4 == pytest.approx(3600.0, abs=0.1)


def test_dg1_reference_values(case):
    """The guide computes with f = 9.5 in: Y = 9.30 in and Tu = 76.0 kips."""
    project, _, loads = case
    bp = project.base_plate_model()
    published = dg1_bending(bp.__class__(**{**bp.__dict__, "f": 9.5 * 25.4}), loads)
    assert published.Y / 25.4 == pytest.approx(9.30, abs=0.02)
    # the guide rounds q_max and Y; the unrounded tension is 76.6 kips
    assert published.T / KIP == pytest.approx(76.0, abs=1.0)


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_fem_against_dg1(case, tmp_path):
    project, model, loads = case
    res = solve(model, loads, tmp_path, settings=MeshSettings(size_fine=20.0))
    assert res.converged
    # equilibrium of the FEM solution
    assert res.equilibrium_error < 1e-3
    assert res.bearing_force - res.anchor_tension_total == pytest.approx(loads.P, rel=1e-3)
    # compression on +x, tension only in the two rods on -x
    tension = [a.tension for a in res.anchors if a.x < 0]
    assert all(abs(a.tension) < 1e-3 * loads.P for a in res.anchors if a.x > 0)
    assert tension[0] == pytest.approx(tension[1], rel=0.02)
    # against the DG1 rectangular stress block with the modelled rod position
    ref = dg1_bending(project.base_plate_model(), loads)
    assert res.anchor_tension_total == pytest.approx(ref.T, rel=0.20)
    assert res.bearing_length_x == pytest.approx(ref.Y, rel=0.20)

    # code checks with the FEM demands, in the editions used by the guide
    bp = project.base_plate_model()
    checks = {r.id: r for r in check_fem(bp, res, DG1_2ED)}
    # guide: 38.0 / 57.7 = 0.66 per rod, 76.0 / 134 = 0.57 breakout, bearing at its limit
    assert checks["anchor.steel_tension"].ratio == pytest.approx(0.66, abs=0.03)
    assert checks["anchor.concrete_breakout_tension"].ratio == pytest.approx(0.57, abs=0.03)
    assert checks["fem.concrete_bearing"].ratio == pytest.approx(1.0, abs=0.06)
    assert checks["fem.plate_plastic_strain"].ratio < 0.2
    assert checks["anchor.steel_tension"].clause.startswith("AISC 360-05")
    assert {"fem.weld", "anchor.pullout", "fem.plate_bending_tension"} <= set(checks)
    current = {r.id: r for r in check_fem(bp, res, CURRENT)}
    assert current["anchor.steel_tension"].clause == "ACI 318-19 §17.6.1.2"
    html = render_report("DG1 4.7", DG1_2ED, project.info.unit_system(),
                         [ComboReport(res, "LRFD", list(checks.values()))], [("Columna", "W12X96")])
    assert "ACI 318-08 D.5.2" in html and "<math" in html
