# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Check functions against the worked examples of AISC Design Guide 1, 2nd edition.

Only numerical values are quoted, each with its example number.
"""

import math

import pytest
from openconex.kernel.anchors import Edges, heavy_hex_bearing_area

from openfemconex import checks as ck
from openfemconex.checks import CURRENT, DG1_2ED

IN, KIP, KSI = 25.4, 4448.2216152605, 6.894757293168
FU36, FY36 = 58 * KSI, 36 * KSI
FC4 = 4 * KSI


def kips(result) -> float:
    return result.capacity / KIP


@pytest.mark.parametrize("d, expected", [(0.75, 14.4), (0.875, 19.6), (1.5, 57.7)])
def test_rod_tension_examples_4_3_4_5_4_7(d, expected):
    """φRn = 0.75 (0.75 Fu Ab): 14.4, 19.6 and 57.7 kips (Examples 4.3, 4.5, 4.7)."""
    r = ck.anchor_steel_tension(d * IN, FU36, FY36, 0.0, DG1_2ED)
    assert kips(r) == pytest.approx(expected, rel=5e-3)
    assert "J3.6" in r.clause


def test_rod_shear_example_4_10():
    """φRn = 0.75 (0.4 Fu Ab) = 7.69 kips for a 3/4 in. rod (Example 4.10)."""
    r = ck.anchor_steel_shear(0.75 * IN, FU36, FY36, 0.0, DG1_2ED)
    assert kips(r) == pytest.approx(7.69, rel=5e-3)


def test_breakout_tension_example_4_5():
    """Four rods on a 4 in. square, hef = 13 in., uncracked: φNcbg = 77.5 kips."""
    r = ck.anchor_breakout_tension(13 * IN, FC4, 69.8 * KIP, DG1_2ED, span_x=4 * IN,
                                   span_y=4 * IN, cracked=False)
    assert kips(r) == pytest.approx(77.5, rel=5e-3)
    assert r.ratio == pytest.approx(69.8 / 77.5, rel=5e-3)
    assert r.clause == "ACI 318-08 D.5.2"


def test_breakout_tension_pier_example_4_5b():
    """20 in. square pier: hef' = 5.33 in. and φNcbg = 25.6 kips."""
    edges = Edges(left=8 * IN, right=8 * IN, bottom=8 * IN, top=8 * IN)
    r = ck.anchor_breakout_tension(13 * IN, FC4, 69.8 * KIP, DG1_2ED, span_x=4 * IN,
                                   span_y=4 * IN, edges=edges, cracked=False)
    hef = next(s.value for s in r.steps if s.symbol == "h_{ef}")
    assert hef / IN == pytest.approx(5.33, abs=0.01)
    # The guide omits ψed,N (0.7 + 0.3 = 1.0 here because ca,min = 1.5 hef').
    assert kips(r) == pytest.approx(25.6, rel=1e-2)


def test_breakout_tension_example_4_7():
    """Two rods 12 in. apart, hef = 18 in., uncracked: φNcbg = 134 kips."""
    r = ck.anchor_breakout_tension(18 * IN, FC4, 76.0 * KIP, DG1_2ED, span_x=12 * IN,
                                   cracked=False)
    assert kips(r) == pytest.approx(134.0, rel=5e-3)


@pytest.mark.parametrize("d, expected", [(0.875, 27.3), (1.5, 70.1)])
def test_pullout_table_3_2(d, expected):
    """φNp = 0.70 (8 Abrg f'c) with a heavy hex nut, 4 ksi (Table 3.2; Examples 4.5, 4.7)."""
    area = heavy_hex_bearing_area(d * IN)
    r = ck.anchor_pullout(area, FC4, 0.0, DG1_2ED, cracked=True)
    assert kips(r) == pytest.approx(expected, rel=3e-2)  # the table rounds the nut bearing area


def test_breakout_shear_example_4_10():
    """Four 3/4 in. rods, c1 = 14 in., s = 4 in., uncracked: φVcbg = 32.7 kips."""
    r = ck.anchor_breakout_shear(0.75 * IN, 12 * IN, 14 * IN, FC4, 30.8 * KIP, DG1_2ED,
                                 spacing=4 * IN, cracked=False)
    assert kips(r) == pytest.approx(32.7, rel=5e-3)


def test_shear_breakout_cap_only_in_current_edition():
    old = ck.anchor_breakout_shear(1.5 * IN, 18 * IN, 14 * IN, FC4, 0.0, DG1_2ED)
    new = ck.anchor_breakout_shear(1.5 * IN, 18 * IN, 14 * IN, FC4, 0.0, CURRENT)
    assert new.capacity < old.capacity
    assert new.clause == "ACI 318-19 §17.7.2"


def test_fillet_weld_example_4_5():
    """3/16 in. fillet, E70, transverse: φrn = 6.26 kips/in.; demand 4.79 kips/in."""
    per_in = KIP / IN
    r = ck.fillet_weld_line(4.79 * per_in, 0.0, 3 / 16 * IN, 70 * KSI, fillets=1, ed=DG1_2ED)
    assert r.capacity / per_in == pytest.approx(6.26, rel=5e-3)
    assert r.ratio == pytest.approx(4.79 / 6.26, rel=5e-3)


def test_bearing_example_4_7():
    """Stress block of Example 4.7: C = 452 kips over Y = 9.30 in. at 2.21 ksi (A2/A1 = 1)."""
    N = B = 22 * IN
    Y = 9.30 * IN
    r = ck.concrete_bearing(452 * KIP, (N / 2 - Y / 2, 0.0), N, B, FC4, 1.0, DG1_2ED)
    assert r.capacity / KSI == pytest.approx(2.21, abs=0.005)
    assert r.ratio == pytest.approx(1.0, abs=0.01)
    confined = ck.concrete_bearing(1.0, (0.0, 0.0), N, B, FC4, 9.0, DG1_2ED)
    assert confined.capacity == pytest.approx(0.65 * 1.7 * FC4)


def test_plate_bending_tension_example_4_7():
    """Tu = 76.0 kips at x = 3.60 in., B = 22 in., Fy = 36 ksi: tp,req = 1.24 in."""
    T, x, B, Fy = 76.0 * KIP, 3.60 * IN, 22 * IN, 36 * KSI
    tp = 1.24 * IN
    r = ck.plate_bending_tension(T, x, B, tp, Fy, DG1_2ED)
    assert r.ratio == pytest.approx(1.0, abs=0.01)
    # same statement as the guide's formula 2.11 sqrt(T x / (B Fy))
    assert 2.11 * math.sqrt(T * x / (B * Fy)) / IN == pytest.approx(1.24, abs=0.005)


def test_current_edition_uses_aci_steel_area():
    """ACI 318-19: Nsa = Ase,N futa with Ase = 1.41 in² for a 1-1/2 in. rod, φ = 0.75."""
    r = ck.anchor_steel_tension(1.5 * IN, FU36, FY36, 0.0, CURRENT)
    assert kips(r) == pytest.approx(0.75 * 1.405 * 58, rel=5e-3)
    assert r.clause == "ACI 318-19 §17.6.1.2"


def test_interaction_rule():
    assert ck.anchor_interaction(0.15, 0.9).ratio == pytest.approx(0.9)
    r = ck.anchor_interaction(0.6, 0.7)
    assert r.demand == pytest.approx(1.3) and r.capacity == 1.2
    assert r.status.value == "ng"


@pytest.mark.parametrize("d, ft, fv, phiFnt", [(1.125, 46.7, 9.26, 25.1), (1.5, None, 5.20, None)])
def test_rod_combined_example_4_11(d, ft, fv, phiFnt):
    """Four rods, Vu = 36.8 kips, Tu = 69.8 kips, lever 0.750 in (Example 4.11).

    1-1/8 in.: f_t = 46.7 ksi > φF'nt = 25.1 ksi (n.g.); 1-1/2 in. rods are adequate.
    """
    r = ck.rod_combined(69.8 / 4 * KIP, 36.8 / 4 * KIP, d * IN, 0.75 * FU36, 0.40 * FU36,
                        0.750 * IN, DG1_2ED)
    step = {s.symbol: s.value for s in r.steps}
    assert step["f_v"] / KSI == pytest.approx(fv, rel=1e-2)
    if ft is not None:
        assert r.demand / KSI == pytest.approx(ft, rel=1e-2)
        assert r.capacity / KSI == pytest.approx(phiFnt, rel=1e-2)
        assert r.status.value == "ng"
    else:
        assert r.status.value == "ok"
