# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Recommendations for checks that do not pass."""

from pathlib import Path

from openfemconex import checks as ck
from openfemconex.advice import advise
from openfemconex.extras import load_extended

EXAMPLE = Path(__file__).parents[1] / "examples" / "dg1_2ed_ej_4_7.ocnx"


def _project():
    project, extras = load_extended(EXAMPLE)
    return project, project.base_plate_model(), extras


def test_failing_rod_and_plate_get_a_larger_size():
    project, bp, extras = _project()
    units = project.info.unit_system()
    rod = bp.rod
    tension = ck.anchor_steel_tension(rod.diameter, rod.material.Fu, rod.material.Fy,
                                      4e5, ck.CURRENT)
    plate = ck.plate_bending_tension(1.5e6, 100.0, bp.B, bp.tp, 250.0)
    assert tension.ratio > 1 and plate.ratio > 1
    out = advise(bp, None, [tension, plate], units, ck.CURRENT, extras)
    assert set(out) == {tension.id, plate.id}
    assert "diámetro" in out[tension.id][0]
    assert "espesor de la placa" in out[plate.id][0]


def test_passing_checks_get_no_advice():
    project, bp, extras = _project()
    rod = bp.rod
    ok = ck.anchor_steel_tension(rod.diameter, rod.material.Fu, rod.material.Fy, 1.0,
                                 ck.CURRENT)
    assert advise(bp, None, [ok], project.info.unit_system()) == {}
