# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Thin-walled tube that did not converge: distorted mesh and overloaded column."""

from pathlib import Path

import numpy as np
import pytest

from openfemconex.diagnostics import HOPELESS, column_capacity, column_usage, diagnose
from openfemconex.extras import load_extended
from openfemconex.mesh import MeshError, build_mesh, distorted_elements
from openfemconex.model import MeshSettings
from openfemconex.openconex_bridge import model_of, project_loads
from openfemconex.solve import ColumnOverloaded, solve

DATA = Path(__file__).parent / "data" / "tubo_delgado.ocnx"
EXAMPLES = Path(__file__).parents[1] / "examples"


def _case():
    project, extras = load_extended(DATA)
    return project, model_of(project, extras=extras)


@pytest.mark.parametrize("size", [None, 12.0, 20.0, 30.0, 40.0])
def test_thin_tube_mesh_has_no_distorted_elements(size):
    """HSS6.000X0.125 (2.9 mm wall): a coarse mesh used to fold the wall elements."""
    _, model = _case()
    mesh = build_mesh(model, MeshSettings(size_fine=size))
    for conn in mesh.parts.values():
        assert len(distorted_elements(mesh.nodes, conn)) == 0


def test_distorted_mesh_is_rejected_before_solving(monkeypatch):
    """Without the wall size limit the old mesh comes back, and it is refused."""
    _, model = _case()
    monkeypatch.setattr(MeshSettings, "wall_size", lambda self, m: self.size_fine)
    with pytest.raises(MeshError, match="distorted"):
        build_mesh(model, MeshSettings(size_fine=30.0))


def test_distorted_elements_detects_an_inverted_hexahedron():
    nodes = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                      [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=float)
    good = np.arange(1, 9)[None, :]
    assert len(distorted_elements(nodes, good)) == 0
    inverted = good[:, [4, 5, 6, 7, 0, 1, 2, 3]]
    assert list(distorted_elements(nodes, inverted)) == [0]


def test_column_capacity_of_a_round_hss():
    _, model = _case()
    cap = column_capacity(model)
    d, t, Fy = model.section.d, model.section.t, model.column_steel.Fy
    assert cap["A"] == pytest.approx(np.pi / 4 * (d**2 - (d - 2 * t) ** 2))
    assert cap["Vpx"] == pytest.approx(0.6 * Fy * cap["A"] / 2)


def test_overloaded_column_is_reported_and_not_solved(tmp_path):
    project, model = _case()
    loads = dict((c.name, ld) for c, ld in project_loads(project))["LRFD-U"]
    assert max(column_usage(model, loads)) > HOPELESS
    notes = diagnose(model, loads)
    assert any("HSS6.000X0.125" in n for n in notes)
    assert any("fricción" in n for n in notes)  # uplift with shear, no lug
    with pytest.raises(ColumnOverloaded):
        solve(model, loads, tmp_path)


@pytest.mark.parametrize("name", ["dg1_2ed_ej_4_7", "dg1_2ed_ej_4_11", "llave_de_cortante",
                                  "rigidizadores_w", "pedestal_anclajes_libres",
                                  "dg1_3ed_ej_4_7_11", "dg1_2ed_ej_4_5"])
def test_examples_are_not_flagged(name):
    project, extras = load_extended(EXAMPLES / f"{name}.ocnx")
    model = model_of(project, extras=extras)
    for _, loads in project_loads(project):
        assert max(column_usage(model, loads)) < 1.0
