# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Through-bolted end plate on a concrete wall or column, against hand calculations."""

import math
from dataclasses import replace

import pytest
from openconex.connections.moment.end_plate import EndPlate, EndPlateLayout
from openconex.core.loads import Method
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, from_internal, to_internal

from openfemconex.checks import DG1_2ED
from openfemconex.report import check_title
from openfemconex.through_bolt import (
    BackPlate,
    ConcreteMember,
    Rebar,
    ShearTransfer,
    Support,
    ThroughBoltConnection,
    back_area,
    bolt_rows,
    check_through_bolt,
    forces,
    front_area,
)


def IN(v):
    return to_internal(v, "in", Kind.LENGTH)


@pytest.fixture
def conn():
    beam = aisc_shapes().get("W18X50").to_ishape()
    ep = EndPlate(layout=EndPlateLayout.EXTENDED_4, bolt=BoltSpec(diameter=IN(1.0)),
                  width=IN(8), thickness=IN(1), gage=IN(5.5), pf=IN(1.75), pf_o=IN(1.75),
                  pext=IN(3.5), Fy=248.2, Fu=399.9, web_weld=IN(5 / 16))
    wall = ConcreteMember(Support.WALL, thickness=400, fc=28, cover=40,
                          vertical=Rebar(16, 200), horizontal=Rebar(12, 200))
    back = BackPlate(width=IN(10), height=beam.d + 2 * IN(3.5), thickness=IN(1))
    return ThroughBoltConnection(beam, ep, back, wall)


def by_id(results):
    return {r.id: r for r in results}


def test_bolt_rows_and_forces(conn):
    b = conn.beam
    rows = bolt_rows(b, conn.end_plate)
    assert rows == pytest.approx([b.d / 2 + IN(1.75), b.d / 2 - b.tf - IN(1.75)])
    z = b.d - b.tf
    f = forces(conn, V=-150e3, M=-250e6, P=100e3)
    assert f.T == pytest.approx(250e6 / z - 50e3)
    assert f.C == pytest.approx(f.T + 100e3)
    assert f.V == 150e3
    assert forces(conn, 0, 1e6, P=1e6).T == 0


def test_bearing_area_from_plate_cantilever(conn):
    a = front_area(conn)
    fp = 0.65 * 0.85 * conn.member.fc * a.ratio
    tp = conn.end_plate.thickness
    assert a.cantilever == pytest.approx(tp * math.sqrt(0.9 * conn.end_plate.Fy / (2 * fp)))
    assert a.width == pytest.approx(min(conn.beam.bf + 2 * a.cantilever, conn.end_plate.width))
    assert 1.0 <= a.ratio <= 2.0
    r = by_id(check_through_bolt(conn, 150e3, 250e6))["through_bolt.bearing_front"]
    assert r.capacity == pytest.approx(0.65 * 0.85 * 28 * a.area * a.ratio)


def test_punching_in_a_wall_and_a_narrow_column(conn):
    back = back_area(conn)
    m = conn.member
    d = m.thickness - 40 - 12 - 8
    r = by_id(check_through_bolt(conn, 150e3, 250e6))["through_bolt.punching"]
    b0 = 2 * (back.width + d) + 2 * (back.height + d)
    lam_s = min(math.sqrt(2 / (1 + from_internal(d, Kind.LENGTH, "in") / 10)), 1.0)
    beta = max(back.width, back.height) / min(back.width, back.height)
    k = min(4, 2 + 4 / beta, 2 + 40 * d / b0)
    vc = to_internal(k * lam_s * math.sqrt(from_internal(28, Kind.STRESS, "psi")), "psi",
                     Kind.STRESS)
    assert r.capacity == pytest.approx(0.75 * vc * b0 * d)
    # a column barely wider than the plate keeps only the two horizontal sides
    col = replace(conn, member=replace(m, kind=Support.COLUMN, width=back.width + 50))
    r = by_id(check_through_bolt(col, 150e3, 250e6))["through_bolt.punching"]
    steps = {s.symbol: s.value for s in r.steps}
    assert steps["b_0"] == pytest.approx(2 * (back.width + 50))
    assert steps[r"\alpha_s"] == 20


def test_strut_and_tie_geometry(conn):
    m = conn.member
    back, front = back_area(conn), front_area(conn)
    jx = m.thickness - 2 * (40 + 12 + 8)
    jz = (back.z0 + back.z1) / 2 - (front.z0 + front.z1) / 2
    f = forces(conn, 150e3, 250e6)
    res = by_id(check_through_bolt(conn, 150e3, 250e6))
    assert res["through_bolt.stm_tie"].demand == pytest.approx(f.T * jz / jx)
    assert res["through_bolt.stm_strut"].demand == pytest.approx(f.T * math.hypot(jx, jz) / jx)
    # continuous wall: unlimited anchorage; a wall ending just above the plate is not
    assert res["through_bolt.stm_tie_anchorage"].capacity == math.inf
    short = replace(conn, member=replace(m, top=back.z1 + 50))
    r = by_id(check_through_bolt(short, 150e3, 250e6))["through_bolt.stm_tie_anchorage"]
    assert r.demand > r.capacity


def test_shear_scheme_selects_the_checks(conn):
    friction = by_id(check_through_bolt(conn, 150e3, 250e6))
    assert "through_bolt.friction" in friction
    assert "moment.end_plate_bolt_shear" not in friction
    f = forces(conn, 150e3, 250e6)
    steps = {s.symbol: s.value for s in friction["through_bolt.friction"].steps}
    assert steps[r"\phi V_n"] <= 0.65 * 0.55 * f.C + 1e-6
    grout = by_id(check_through_bolt(replace(conn, shear=ShearTransfer.GROUT), 150e3, 250e6))
    assert "through_bolt.friction" not in grout
    assert "moment.end_plate_bolt_shear" in grout


def test_asd_keeps_only_the_steel_checks(conn):
    ids = [r.id for r in check_through_bolt(conn, 100e3, 150e6, method=Method.ASD)]
    assert ids and all(i.startswith("moment.") for i in ids)


def test_member_flexure_of_a_wall_strip(conn):
    m = conn.member
    back = back_area(conn)
    r = by_id(check_through_bolt(conn, 150e3, 250e6))["through_bolt.member_flexure"]
    assert r.demand == pytest.approx(0.5 * (250e6 + 150e3 * m.thickness / 2))
    b = back.width + 2 * m.thickness
    n = math.floor(b / 200)
    As = n * m.vertical.bar_area
    d = m.thickness - (40 + 12 + 8)
    a = As * 420 / (0.85 * 28 * b)
    # singly reinforced section as a lower bound; the bars of the compressed face add a little
    single = 0.9 * As * 420 * (d - a / 2)
    assert single <= r.capacity <= 1.15 * single


def test_titles_and_older_edition(conn):
    res = check_through_bolt(conn, 150e3, 250e6, ed=DG1_2ED)
    ids = {r.id for r in res}
    assert {"through_bolt.punching", "through_bolt.stm_strut"} <= ids
    assert all(check_title(r) != r.id for r in res)
    strut = by_id(res)["through_bolt.stm_strut"]
    assert all(s.symbol != r"\beta_c" for s in strut.steps)
