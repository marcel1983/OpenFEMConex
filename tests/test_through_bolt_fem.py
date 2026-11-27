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
    # the back plate is flexible by default; rigid on request
    assert model.far is not None and model.far.thickness == pytest.approx(25.4)
    assert fem_model(conn, flexible=False).far is None
    grout = tbp.build(_data(True), SI)
    both = fem_model(grout)
    assert both.anchor.welded_washers and both.far is None
    assert both.opposite.section.name == "W18X50" and both.opposite.anchors == both.anchors
    assert fem_model(grout, far=True).section.name == "W18X50"
    two = fem_loads("E", 100e3, 180e6, opposite=(60e3, -90e6, 0.0))
    assert two.opposite.My == 90e6 and two.opposite.Vx == -60e3


def test_opposite_beam_is_mirrored_below_the_wall():
    from openfemconex.mesh import build_mesh
    from openfemconex.model import MeshSettings

    model = fem_model(tbp.build(_data(True), SI))
    mesh = build_mesh(model, MeshSettings(fast=True))
    H = model.concrete.H
    assert {"PLATE2", "COLUMN2"} <= set(mesh.parts)
    z2 = mesh.nodes[mesh.parts["PLATE2"] - 1, 2]
    assert z2.max() == pytest.approx(-H) and z2.min() == pytest.approx(-H - model.opposite.tp)
    assert mesh.nodes[mesh.opposite.column_top_nodes - 1, 2].max() == pytest.approx(
        -H - model.opposite.tp - model.opposite.Lc)
    assert len(mesh.far_washer_nodes) == len(model.anchors)


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_fem_bolt_tension_and_bearing_match_the_couple(tmp_path):
    data = _data()
    conn = tbp.build(data, SI)
    combo = tbp.combinations(data, SI)[1]  # 1.2D + 1.6L
    (side,) = solve_combination(conn, combo, tmp_path, fast=True)
    res = side.results
    assert res.converged
    T = tbp.run(data, SI)[1].T
    top = [a.tension for a in res.anchors if a.x > 0]
    bottom = [a.tension for a in res.anchors if a.x < 0]
    # the tension flange pulls the top bolts with T = M/z (prying adds a little)
    assert sum(top) == pytest.approx(T, rel=0.10)
    assert max(bottom) < 0.02 * T
    assert res.bearing_force == pytest.approx(T, rel=0.10)
    assert res.bearing_centroid[0] < 0  # compression under the bottom flange
    # friction: the shear goes through the contact, not through the bolts
    assert sum(abs(a.Vx) for a in res.anchors) < 0.05 * combo.V
    # the flexible back plate bears on the far face behind the top bolts
    assert res.far_bearing_force == pytest.approx(sum(top) + sum(bottom), rel=0.02)
    assert res.far_bearing_centroid[0] > 0
    ids = {c.id for c in side.checks}
    assert {"through_bolt.fem_bolt_tension", "through_bolt.fem_bearing",
            "through_bolt.fem_friction", "through_bolt.fem_plate_strain",
            "through_bolt.fem_back_plate_strain", "through_bolt.fem_back_bearing"} <= ids
    assert all(c.status.value != "ng" for c in side.checks)
    # the report: FEM first with its figures (contact pressure on both plates)
    results = tbp.run(data, SI)
    results[1].fem = [side]
    figures = {}
    try:
        from openfemconex.scenes import render_through_bolt_figures

        figures = render_through_bolt_figures(tmp_path / "rep", [side], size=(400, 300))
    except Exception:  # no OpenGL context here: the report without figures
        pass
    html = tbp.report_html(data, results, SI, {}, fem_figures=figures)
    assert "modelo de elementos finitos (CalculiX)" in html
    combo2 = html.index(f"Combinación {combo.name}")
    assert combo2 < html.index("Modelo CalculiX", combo2) < html.index(
        "Verificaciones analíticas", combo2)
    if figures:
        names = [f for _, f in figures[side.vtu.name]]
        assert any(n.endswith("CPRESS.png") for n in names)
        assert any(n.endswith("CPRESS_far.png") for n in names)
        assert "fem_malla.png" in html and "CPRESS_far.png" in html


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_fem_opposite_beam_in_one_model(tmp_path):
    """Seismic case: the two beams bend the same way, so the front plate bears at the
    bottom and the opposite one at the top, and both bolt groups pull."""
    data = _data(True)
    data["shear"]["type"] = "friction"
    data["combinations"] = [{"name": "E", "V": "120 kN", "M": "130 kN*m", "V2": "60 kN",
                             "M2": "-90 kN*m"}]
    conn = tbp.build(data, SI)
    combo = tbp.combinations(data, SI)[0]
    one, two = solve_combination(conn, combo, tmp_path, fast=True)
    res = one.results
    assert res.converged and two.results is res
    (analytic,) = tbp.run(data, SI)
    demand = {c.id: c.demand for c in analytic.checks}
    C = demand["through_bolt.bearing_front_bottom"]
    assert res.bearing_force == pytest.approx(C, rel=0.10)
    assert res.far_bearing_force == pytest.approx(demand["through_bolt.bearing_back_top"],
                                                  rel=0.10)
    assert res.bearing_centroid[0] < 0 < res.far_bearing_centroid[0]
    top = sum(a.tension for a in res.anchors if a.x > 0)
    bottom = sum(a.tension for a in res.anchors if a.x < 0)
    assert top > bottom > 0.5 * top  # M1 = 130 pulls the top, M2 = -90 the bottom
    assert {c.id for c in two.checks} >= {"through_bolt.fem_bearing",
                                          "through_bolt.fem_weld_flange"}
    assert all("viga 2" in c.combo for c in two.checks)
    assert all(c.status.value != "ng" for c in one.checks + two.checks)
