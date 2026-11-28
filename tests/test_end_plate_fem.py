# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX model of the moment end plate: mapping, mesh, input deck and one solution."""

import copy
import dataclasses
import math
import shutil

import pytest
from openconex.units import UnitSystem

from openfemconex import end_plate_fem as epf
from openfemconex import end_plate_project as epp
from openfemconex.inp import anchor_stiffness, rod_force, write_inp
from openfemconex.mesh import build_mesh
from openfemconex.model import Loads, MeshSettings

US = UnitSystem()


def connection(**end_plate):
    data = copy.deepcopy(epp.TEMPLATE)
    data["end_plate"].update(end_plate)
    return epp.build(data, US)


def test_model_of_the_4e_example():
    mc = connection()
    m = epf.fem_model(mc)
    m.validate()
    ep, beam, col = mc.end_plate, mc.beam, mc.column
    assert m.tp == ep.thickness and m.B == ep.width
    assert len(m.anchors) == 8  # two rows outside and two inside, two bolts each
    assert m.concrete.H == col.tf and m.concrete.B == col.bf
    assert m.flange is not None and m.flange.web == col.tw
    # continuity plates at both beam flanges
    assert sorted(round(x) for x, _ in m.flange.stiffeners) == [
        round(-(beam.d - beam.tf) / 2), round((beam.d - beam.tf) / 2)]
    assert m.flange.pretension == 0.0  # snug tight for the checks
    assert epf.fem_model(mc, pretension=True).flange.pretension == pytest.approx(
        102 * 4448.2216, rel=1e-3)  # Table J3.1, 1 1/4 in A490: 102 kips
    assert m.column_steel.Fy > 5 * 345  # the beam stub stays elastic
    assert m.anchor.welded_washers  # the bolts take the shear in bearing


def test_unsymmetric_and_stiffened_layouts():
    flush = epf.fem_model(connection(layout="flush_2", pext="0 in"))
    flush.validate()
    assert len(flush.anchors) == 4
    es = epf.fem_model(connection(layout="extended_4_stiffened", stiffener_thickness="1/2 in"))
    es.validate()
    assert len(es.stiffeners) == 2
    s = es.stiffeners[0]
    assert s.height == pytest.approx(s.length / math.tan(math.radians(30)))


def test_mesh_and_deck(tmp_path):
    mc = connection()
    m = epf.fem_model(mc, pretension=True)
    mesh = build_mesh(m, MeshSettings(fast=True))
    assert len(mesh.flange_held_nodes) > 0
    assert len(mesh.far_washer_nodes) == len(m.anchors)
    # the held nodes are on the back of the flange, over the web or a continuity plate
    xyz = mesh.nodes[mesh.flange_held_nodes - 1]
    assert abs(xyz[:, 2] + m.concrete.H).max() < 1e-6
    on_web = abs(xyz[:, 1]) <= m.flange.web / 2 + 1e-6
    on_plates = [abs(xyz[:, 0] - x) <= t / 2 + 1e-6 for x, t in m.flange.stiffeners]
    assert (on_web | on_plates[0] | on_plates[1]).all()
    path = tmp_path / "ep.inp"
    write_inp(path, m, mesh, epf.fem_loads("U", 100e3, 300e6))
    text = path.read_text()
    assert "FLANGEHELD, 1, 3" in text and "CONCBOT, 1, 3" not in text
    ks = anchor_stiffness(m)
    assert ks.length == pytest.approx(m.tp + m.concrete.H)
    # the spring law starts at the pretension
    T0 = m.flange.pretension
    assert rod_force(m, ks, 0.0) == pytest.approx(T0)
    assert rod_force(m, ks, -2 * T0 / ks.axial) < 0.01 * T0


def test_loads_axes():
    loads = epf.fem_loads("U", V=10.0, M=20.0, P=5.0)
    assert loads == Loads(P=5.0, Vx=-10.0, My=-20.0, name="U")


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_solve_4e_service_moment(tmp_path):
    """A moment well below the strength: the plate stays elastic and the bolt forces
    are those of the flange couple, with some prying, on the tension side."""
    mc = connection()
    combo = epp.Combination("S", V=60e3, M=250e6)
    sides = epf.solve_combination(mc, combo, tmp_path, fast=True, reuse=False)
    assert len(sides) == 1
    res = sides[0].results
    assert res.converged
    beam = mc.beam
    couple = combo.M / (beam.d - beam.tf)
    top = sum(a.tension for a in res.anchors if a.x > 0)
    assert 0.8 * couple < top < 1.6 * couple
    assert res.plate_peeq_element < 1e-3
    ids = {c.id for c in sides[0].checks}
    assert {"end_plate.fem_bolt_tension", "end_plate.fem_plate_strain",
            "end_plate.fem_flange_strain", "end_plate.fem_weld_web"} <= ids
    assert all(c.status.value != "ng" for c in sides[0].checks)
    done = dataclasses.replace(combo, V=0.0, M=0.0)
    assert epf.solve_combination(mc, done, tmp_path) == []
