# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Moment end-plate connection: project data to the OpenConex engine.

* AISC Design Guide 4, 2nd ed., four-bolt extended Example A (W21X55 beam on a
  W14X109 column, 1 1/4 in. plate, 1 1/4 in. A490 bolts, M_u = 8,039 kip-in.):
  column side without continuity plates, t_fc,req = 1.10 in., F_fu = 396 kips.
* AISC Design Guide 39, Example 6.3-2 (4ES, W24X62 on W14X159, AISC 358-22):
  M_f = 10,400 kip-in., φV_n of the beam = 306 kips.

The numbers are those that OpenConex already reproduces in its own tests; here they
check that the project data reach the engine unchanged.
"""

import copy

import pytest
from openconex.connections.moment.end_plate import EndPlateLayout
from openconex.units import Kind, UnitSystem, from_internal

from openfemconex import end_plate_project as epp
from openfemconex.end_plate_advice import recommendations

UNITS = UnitSystem()


def kip(v):
    return from_internal(v, Kind.FORCE, "kip")


def inch(v):
    return from_internal(v, Kind.LENGTH, "in")


def by_id(checks):
    return {c.id: c for c in checks}


def test_template_passes():
    res = epp.run(epp.new_connection(), UNITS)
    assert len(res.combos) == 1
    assert res.ok
    assert not res.seismic
    r = by_id(res.combos[0].checks)
    # continuity plates: the column web checks do not apply
    assert not r["moment.column_web_local_yielding"].applicable
    assert r["moment.end_plate_bolt_rupture"].ratio == pytest.approx(0.953, abs=2e-3)


def test_dg4_example_a_column_side():
    data = epp.new_connection()
    data["column_side"]["continuity_plate"] = ""
    r = by_id(epp.run(data, UNITS).combos[0].checks)
    assert inch(r["moment.column_flange_bending"].demand) == pytest.approx(1.10, abs=0.01)
    assert kip(r["moment.column_flange_strength"].demand) == pytest.approx(396, rel=2e-3)
    assert kip(r["moment.column_web_local_yielding"].capacity) == pytest.approx(326, rel=5e-3)
    assert kip(r["moment.column_web_crippling"].capacity) == pytest.approx(284, rel=5e-3)
    # the example needs stiffeners: the program says what to add
    advice = recommendations([c for c in r.values()])
    assert advice and "continuidad" in advice[0][1][0]


def dg39_4es():
    data = epp.new_connection("DG39 6.3-2")
    data.update(beam="W24X62", column="W14X159", span="345 in")
    data["end_plate"].update(layout="extended_4_stiffened", thickness="1.125 in",
                             weld_reinforcement="5/16 in")
    data["column_side"].update(continuity_plate="", panel_zone=True,
                               panel_zone_inelastic=True)
    data["seismic"] = dict(epp.SEISMIC, system="smf", gravity_shear="31 kip",
                           column_axial="99.7 kip", column_shear="69 kip",
                           stiffener_thickness="1/2 in")
    data["cases"] = [{"name": "D", "type": "D", "V": "10 kip", "M": "50 kip*ft"}]
    data["combinations"] = {"methods": ["LRFD"], "include_code": True}
    return data


def test_dg39_4es_seismic():
    res = epp.run(dg39_4es(), UNITS)
    s = by_id(res.seismic)
    assert all(c.combo == epp.SEISMIC_COMBO for c in res.seismic)
    rupture = s["seismic.end_plate_bolt_rupture"]
    assert from_internal(rupture.demand, Kind.MOMENT, "kip*in") == pytest.approx(10400,
                                                                                 rel=1e-2)
    assert kip(s["seismic.beam_shear"].capacity) == pytest.approx(306, rel=5e-3)
    assert inch(s["seismic.end_plate_column_flange"].demand) == pytest.approx(1.08, rel=1e-2)
    # ASCE 7 combinations of the dead case
    assert {r.combo.name for r in res.combos}
    assert all(r.combo.method.value == "LRFD" for r in res.combos)


def test_seismic_needs_prequalified_layout():
    data = dg39_4es()
    data["end_plate"].update(layout="flush_4", pb="3 in")
    with pytest.raises(ValueError, match="precalificada"):
        epp.run(data, UNITS)
    assert epp.prequalified("extended_8_stiffened").value == "bseep"
    assert epp.prequalified("flush_2") is None


@pytest.mark.parametrize("layout", list(EndPlateLayout))
def test_every_layout_runs(layout):
    data = epp.new_connection()
    e = data["end_plate"]
    e.update(layout=layout.value, pb="3 1/2 in", ps_o="1 1/2 in", stiffener_thickness="1/2 in",
             ps="1 3/4 in", pext="6 in" if layout is EndPlateLayout.EXTENDED_8_STIFFENED
             else "3 5/8 in")
    res = epp.run(data, UNITS)
    ids = {c.id for c in res.combos[0].checks}
    assert "moment.end_plate_yielding" in ids
    assert "moment.end_plate_bolt_rupture" in ids
    assert epp.LAYOUTS[layout] in epp.summary(data)


def test_missing_value_is_named():
    data = epp.new_connection()
    data["end_plate"]["layout"] = "extended_8_stiffened"
    data["end_plate"]["pb"] = ""
    with pytest.raises(ValueError, match="p_b"):
        epp.run(data, UNITS)


def test_asd_combinations():
    data = epp.new_connection()
    data["cases"] = [{"name": "D", "type": "D", "V": "15 kip", "M": "2000 kip*in"},
                     {"name": "L", "type": "L", "V": "15 kip", "M": "2000 kip*in"}]
    data["combinations"] = {"methods": ["LRFD", "ASD"], "include_code": True}
    res = epp.run(data, UNITS)
    methods = {r.combo.method.value for r in res.combos}
    assert methods == {"LRFD", "ASD"}
    assert all(c.combo == r.combo.name for r in res.combos for c in r.checks)


def test_report_has_common_closing():
    data = dg39_4es()
    res = epp.run(data, UNITS)
    html = epp.report_html(data, res, UNITS, {"name": "Prueba"}, figures="esquemas")
    for text in ("Diseño sísmico (AISC 358-22 y AISC 341-22)", "Resumen de resultados",
                 "Requisitos de instalación", "Alcance y limitaciones",
                 "placa_extremo_fuerzas.png", "BSEEP"):
        assert text in html
    data2 = copy.deepcopy(data)
    data2["seismic"] = None
    html2 = epp.report_html(data2, epp.run(data2, UNITS), UNITS, {})
    assert "AISC 358" not in html2
