# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX model of the through-bolt connection, against the analytic force model."""

import copy
import shutil

import pytest

from openfemconex import through_bolt_project as tbp
from openfemconex.through_bolt_fem import fem_loads, fem_model, solve_combination
from openfemconex.units import display_units

SI = display_units("SI_kN_m")


def _data(opposite: bool = False):
    data = tbp.new_connection()
    if opposite:
        data["opposite"] = copy.deepcopy(tbp.OPPOSITE)
        data["shear"]["type"] = "grout"
    return data


def test_mapping_onto_the_base_plate_model():
    conn = tbp.build(_data(), SI)
    model = fem_model(conn)
    model.validate()
    assert len(model.anchors) == conn.bolts
    assert model.N == pytest.approx(conn.beam.d + 2 * 3.5 * 25.4)
    assert model.concrete.H == pytest.approx(500.0)
    assert model.anchor.hef == pytest.approx(500.0 + 25.4)  # wall + back plate
    assert not model.anchor.welded_washers  # friction: the bolts take no shear
    loads = fem_loads("C", 100e3, 180e6)
    assert loads.My == -180e6 and loads.Vx == -100e3  # tension at the top = +x side
    grout = tbp.build(_data(True), SI)
    assert fem_model(grout).anchor.welded_washers
    assert fem_model(grout, far=True).section.name == "W18X50"


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_fem_bolt_tension_and_bearing_match_the_couple(tmp_path):
    data = _data()
    conn = tbp.build(data, SI)
    combo = tbp.combinations(data, SI)[0]
    (side,) = solve_combination(conn, combo, tmp_path, fast=True)
    res = side.results
    assert res.converged
    T = tbp.run(data, SI)[0].T
    top = [a.tension for a in res.anchors if a.x > 0]
    bottom = [a.tension for a in res.anchors if a.x < 0]
    # the tension flange pulls the top bolts with T = M/z (prying adds a little)
    assert sum(top) == pytest.approx(T, rel=0.10)
    assert max(bottom) < 0.02 * T
    assert res.bearing_force == pytest.approx(T, rel=0.10)
    assert res.bearing_centroid[0] < 0  # compression under the bottom flange
    ids = {c.id for c in side.checks}
    assert {"through_bolt.fem_bolt_tension", "through_bolt.fem_bearing",
            "through_bolt.fem_friction", "through_bolt.fem_plate_strain"} <= ids
    assert all(c.status.value != "ng" for c in side.checks)
