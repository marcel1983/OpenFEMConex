# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Shear lug: model, input deck and FEM solution."""

import shutil
from pathlib import Path

import pytest

from openfemconex.checks import CURRENT, check_fem
from openfemconex.extras import load_extended
from openfemconex.inp import write_inp
from openfemconex.mesh import build_mesh
from openfemconex.model import MeshSettings
from openfemconex.openconex_bridge import model_of, project_loads
from openfemconex.solve import solve

EXAMPLE = Path(__file__).parents[1] / "examples" / "llave_de_cortante.ocnx"
KIP = 4448.2216152605


def _case(name):
    project, extras = load_extended(EXAMPLE)
    model = model_of(project, extras=extras)
    loads = dict((c.name, ld) for c, ld in project_loads(project))[name]
    return project, extras, model, loads


def test_lug_model_and_deck(tmp_path):
    _, _, model, loads = _case("LRFD-U")
    assert model.lug is not None and model.lug.direction == "strong"
    assert model.lug.width == pytest.approx(8 * 25.4)
    mesh = build_mesh(model, MeshSettings(size_fine=14.0))
    num = write_inp(tmp_path / "u.inp", model, mesh, loads)
    text = (tmp_path / "u.inp").read_text()
    assert "*NODE, NSET=LUGNODES" in text and "ELSET=LUG1" in text
    assert "ELSET=LUG2" not in text  # strong direction only
    assert len(num.lug_nodes) == 2 and num.lug_stiffness > 0
    assert "*NODE PRINT, NSET=LUGNODES" in text


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
@pytest.mark.parametrize("combo", ["LRFD-U", "LRFD-C"])
def test_lug_takes_the_shear(combo, tmp_path):
    project, extras, model, loads = _case(combo)
    res = solve(model, loads, tmp_path, settings=MeshSettings(size_fine=14.0))
    assert res.converged
    assert res.equilibrium_error < 1e-3 and res.moment_error < 0.02
    # horizontal equilibrium: lug + friction (+ rods, loose in their holes) = Vx
    total = -res.lug_shear[0] + res.friction[0] - sum(a.Vx for a in res.anchors)
    assert abs(total) == pytest.approx(abs(loads.Vx), rel=0.02)
    if combo == "LRFD-C":  # with compression friction takes part of it, by stiffness
        assert 0.05 * abs(loads.Vx) < abs(res.lug_shear[0]) < abs(loads.Vx)
    if combo == "LRFD-U":  # net uplift: no friction, the lug takes it all
        assert abs(res.lug_shear[0]) == pytest.approx(abs(loads.Vx), rel=0.02)
    checks = {r.id: r for r in check_fem(project.base_plate_model(), res, CURRENT,
                                         extras=extras, mu=model.contact.mu)}
    assert "base_plate.lug_bearing" in checks or any(k.startswith("base_plate.lug") for k in checks)
    assert "base_plate.friction" not in checks  # the lug is designed for the whole shear
    weld = checks["base_plate.lug_weld"]
    assert weld.demand > 0
