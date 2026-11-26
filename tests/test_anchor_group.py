# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Anchor group checks against a worked case: 8 rods of 3/4 in. at hef = 25 cm in a
30 × 60 cm pedestal, f'c = 281 kgf/cm², uncracked (ACI 318-08). Only numbers are quoted."""

import pytest
from openconex.kernel.anchors import Edges

from openfemconex import checks as ck

T = 9806.65  # N per tonne-force
CM = 10.0
FC = 281.226 * 0.0980665
ABRG = 4.22 * 100  # mm²


def test_side_face_blowout_single_with_corner():
    """Nsb = 9.50 T, × (1 + 17.5/6.5)/4 = 8.77 T next to the corner."""
    r = ck.anchor_side_face_blowout(6.5 * CM, ABRG, FC, 6.75 * T, 25 * CM, ck.DG1_2ED,
                                    ca2=17.5 * CM)
    assert r.applicable and r.id == "anchor.side_face_blowout"
    assert r.capacity / 0.70 / T == pytest.approx(8.769, rel=2e-3)


def test_side_face_blowout_of_the_row():
    """Four rods along the edge, s = 25 cm: Nsbg = (1 + 25/39) 9.50 = 15.59 T for 27 T."""
    r = ck.anchor_side_face_blowout(6.5 * CM, ABRG, FC, 27 * T, 25 * CM, ck.DG1_2ED,
                                    spacing=25 * CM)
    assert r.id == "anchor.side_face_blowout_group"
    assert r.capacity / 0.70 / T == pytest.approx(15.589, rel=2e-3)


def test_group_pryout_with_three_edges():
    """hef' = 17.5/1.5 = 11.67 cm, ANc = 1800 cm², Ncbg = 10.10 T, φVcpg = 14.14 T."""
    edges = Edges(left=6.5 * CM, right=6.5 * CM, bottom=17.5 * CM, top=17.5 * CM)
    w = ck.anchor_breakout_tension(25 * CM, FC, 0.0, ck.DG1_2ED, span_x=17 * CM,
                                   span_y=25 * CM, edges=edges, cracked=False)
    steps = {s.symbol: s.value for s in w.steps}
    assert steps["h_{ef}"] == pytest.approx(116.67, abs=0.01)
    assert steps["A_{Nc}"] == pytest.approx(1800 * 100)
    ncbg = steps["N_{cbg}"]
    assert ncbg / T == pytest.approx(10.101, rel=2e-3)
    p = ck.anchor_pryout(ncbg, 25 * CM, 21 * T, ck.DG1_2ED)
    assert p.capacity / T == pytest.approx(14.142, rel=2e-3)
    assert p.ratio == pytest.approx(1.48, abs=0.01)
