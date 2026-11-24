# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Anchors at free coordinates and the reinforced pedestal."""

import shutil
from pathlib import Path

import pytest

from openfemconex import pedestal as ped
from openfemconex.checks import CURRENT, check_fem
from openfemconex.extras import PedestalRebar, load_extended
from openfemconex.model import MeshSettings, Section, SectionKind
from openfemconex.openconex_bridge import model_of, project_loads
from openfemconex.solve import solve

EXAMPLE = Path(__file__).parents[1] / "examples" / "pedestal_anclajes_libres.ocnx"
REBAR = PedestalRebar(bars=8, bar_diameter=25.4, cover=40.0, fy=420.0, tie_diameter=10.0,
                      tie_spacing=150.0)


def test_extended_project_loads_free_anchors():
    project, extras = load_extended(EXAMPLE)
    assert len(extras.anchors) == 6 and extras.pedestal.bars == 12
    model = model_of(project, extras=extras)
    model.validate()
    assert [(a.x, a.y) for a in model.anchors][1] == (-240.0, 0.0)
    assert model.anchor.welded_washers


def test_section_distance():
    w = Section(SectionKind.I, d=300.0, bf=200.0, tf=15.0, tw=10.0)
    assert w.distance(200.0, 0.0) == pytest.approx(50.0)       # beyond the flange
    assert w.distance(0.0, 60.0) == pytest.approx(55.0)        # beside the web
    assert w.distance(0.0, 0.0) == 0.0
    pipe = Section(SectionKind.HSS_ROUND, d=200.0, bf=200.0, t=10.0)
    assert pipe.distance(150.0, 0.0) == pytest.approx(50.0)
    assert pipe.distance(0.0, 0.0) == pytest.approx(90.0)


def test_washer_on_the_column_is_rejected():
    project, extras = load_extended(EXAMPLE)
    bad = type(extras)(anchors=((-240.0, 0.0), (150.0, 0.0)), pedestal=extras.pedestal)
    with pytest.raises(ValueError, match="overlaps the column"):
        model_of(project, extras=bad).validate()


def test_bar_positions_are_on_the_perimeter():
    bars = REBAR.positions(500.0, 500.0)
    inset = 250.0 - (40.0 + 10.0 + 12.7)
    assert len(bars) == 8
    assert all(max(abs(x), abs(y)) == pytest.approx(inset) for x, y in bars)


def test_section_capacity_against_hand_calculation():
    """500 x 500 mm, f'c = 28 MPa, 8 bars of 25.4 mm, fy = 420 MPa."""
    bars = [x for x, _ in REBAR.positions(500.0, 500.0)]
    m0, pmax = ped.section_capacity(0.0, 500.0, 500.0, bars, REBAR.bar_area, 28.0, 420.0)
    ast = 8 * REBAR.bar_area
    assert pmax == pytest.approx(0.65 * 0.8 * (0.85 * 28 * (250000 - ast) + 420 * ast))
    # pure bending by hand: three bars yield in tension, the middle pair nearly so;
    # 0.9 [As fy (d - a/2)] with the three tension bars alone is a lower bound
    a = 3 * REBAR.bar_area * 420 / (0.85 * 28 * 500)
    lower = 0.9 * 3 * REBAR.bar_area * 420 * (437.3 - a / 2)
    assert lower < m0 < 1.45 * lower
    # the moment capacity grows with compression up to the balanced point
    m1, _ = ped.section_capacity(1000e3, 500.0, 500.0, bars, REBAR.bar_area, 28.0, 420.0)
    assert m1 > m0
    assert ped.section_capacity(1.1 * pmax, 500.0, 500.0, bars, REBAR.bar_area, 28.0,
                                420.0)[0] == 0.0


def test_anchor_reinforcement_tension():
    """Bars within 0.5 hef count; φ = 0.75 on As fy."""
    anchors = [(-150.0, -150.0), (-150.0, 150.0)]
    strength, development = ped.anchor_reinforcement_tension(
        200e3, anchors, REBAR, 500.0, 500.0, 400.0, 28.0, "ACI 318-19 §17.5.2.1(a)")
    n = next(s.value for s in strength.steps if s.symbol == "n")
    assert n == 5  # the bars on the side of the anchors and the two at mid-depth
    assert strength.capacity == pytest.approx(0.75 * 5 * REBAR.bar_area * 420.0)
    assert development.kind.value == "length"


def test_minimum_reinforcement():
    r = ped.minimum_reinforcement(REBAR, 500.0, 500.0, "ACI 318-19 §10.6.1.1")
    assert r.demand == pytest.approx(2500.0)
    assert r.status.value == "ok"


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_fem_with_free_anchors_and_pedestal(tmp_path):
    project, extras = load_extended(EXAMPLE)
    model = model_of(project, extras=extras)
    loads = dict((c.name, ld) for c, ld in project_loads(project))["LRFD-2"]
    res = solve(model, loads, tmp_path, settings=MeshSettings(size_fine=22.0))
    assert res.converged and res.equilibrium_error < 1e-3 and res.moment_error < 0.01
    # the middle rod of the tension row takes more than the corner ones
    row = sorted((a for a in res.anchors if a.x < 0), key=lambda a: a.y)
    assert row[1].tension > row[0].tension > 0
    assert row[0].tension == pytest.approx(row[2].tension, rel=0.02)
    # welded washers: the rods take the whole shear and friction none
    assert -sum(a.Vx for a in res.anchors) == pytest.approx(loads.Vx, rel=0.02)
    assert abs(res.friction[0]) < 0.02 * loads.Vx
    checks = {r.id: r for r in check_fem(project.base_plate_model(), res, CURRENT,
                                         extras=extras)}
    for key in ("anchor.reinforcement", "anchor.reinforcement_development",
                "anchor.reinforcement_shear", "pedestal.flexure_axial",
                "pedestal.min_reinforcement", "anchor.concrete_breakout_shear",
                "anchor.pryout", "anchor.interaction"):
        assert key in checks
    # breakout and anchor reinforcement are alternatives: at most one governs,
    # unless both fail
    pair = (checks["anchor.concrete_breakout_shear"], checks["anchor.reinforcement_shear"])
    assert sum(r.applicable for r in pair) == 1 or all(r.status.value == "ng" for r in pair)


def test_pedestal_rebar_reaches_the_model_but_not_the_deck(tmp_path):
    """The bars are drawn and checked; the FEM input deck does not change with them."""
    from openfemconex.inp import write_inp
    from openfemconex.mesh import build_mesh
    from openfemconex.model import MeshSettings

    project, extras = load_extended(EXAMPLE)
    with_bars = model_of(project, extras=extras)
    without = model_of(project, extras=type(extras)(anchors=extras.anchors))
    assert with_bars.rebar is extras.pedestal and without.rebar is None
    loads = project_loads(project)[0][1]
    mesh = build_mesh(without, MeshSettings(size_fine=25.0))
    write_inp(tmp_path / "a.inp", with_bars, mesh, loads)
    write_inp(tmp_path / "b.inp", without, mesh, loads)
    assert (tmp_path / "a.inp").read_text() == (tmp_path / "b.inp").read_text()
