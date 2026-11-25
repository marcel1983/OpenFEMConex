# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Cruciform and built-up columns, and the constitutive laws of the steels."""

from pathlib import Path

import pytest

from openfemconex.diagnostics import column_capacity
from openfemconex.extras import MaterialLaw
from openfemconex.mesh import build_mesh
from openfemconex.model import MeshSettings, Section, SectionKind
from openfemconex.openconex_bridge import model_from_project

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_cruciform_boxes_cover_both_shapes():
    s = Section(SectionKind.CRUCIFORM, d=400, bf=300, tf=20, tw=10, d2=350, bf2=250, tf2=18,
                tw2=9)
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in s.boxes())
    # main W + cross W without the part of its web inside the main web
    expected = (2 * 300 * 20 + 360 * 10) + (2 * 250 * 18 + (350 - 36 - 10) * 9)
    assert area == pytest.approx(expected)
    assert s.distance(0, 170) == 0.0  # on a cross flange
    assert s.distance(0, 200) == pytest.approx(25.0)
    assert s.min_wall == 9
    s.check()
    with pytest.raises(ValueError):
        Section(SectionKind.CRUCIFORM, d=400, bf=300, tf=20, tw=10, d2=350, bf2=380, tf2=18,
                tw2=9).check()


def test_cruciform_example_meshes_and_has_plastic_capacity():
    _, model = model_from_project(EXAMPLES / "cruciforme.ocnx")
    model.validate()
    assert model.section.kind is SectionKind.CRUCIFORM
    cap = column_capacity(model)
    # the cross shape adds weak-axis capacity: well above that of the W14X90 alone (75.6 in³)
    assert cap["Mpx"] > 2 * 345 * 75.6 * 25.4**3 * 0.95
    mesh = build_mesh(model, MeshSettings())
    assert mesh.element_count > 1000


def test_built_up_section_and_custom_laws():
    _, model = model_from_project(EXAMPLES / "perfil_armado.ocnx")
    assert model.section.d == pytest.approx(450.0)
    assert model.column_steel.plastic_curve() == [(345.0, 0.0), (345.0, 0.015),
                                                  (450.0, 0.15)]
    assert model.plate_steel.plastic_curve()[2] == (330.0, 0.05)


def test_laws():
    assert MaterialLaw("elastoplastica").curve(250, 400, 2e5) == ((250, 0.0),)
    assert MaterialLaw().curve(250, 400, 2e5) == ((250, 0.0), (250 + 200 * 0.15, 0.15))
    with pytest.raises(ValueError):
        MaterialLaw("tabla", table=((250.0, 0.0), (240.0, 0.1))).check(250, 400)
    with pytest.raises(ValueError):
        MaterialLaw("trilineal", eps_sh=0.2, eps_u=0.1).check(250, 400)


@pytest.mark.parametrize("name", ["dg1_2ed_ej_4_7.ocnx", "rigidizadores_tubo.ocnx"])
def test_fast_mesh_is_coarser(name):
    """build_mesh rejects distorted elements, so a coarse first try falls back finer."""
    _, model = model_from_project(EXAMPLES / name)
    normal = build_mesh(model, MeshSettings())
    fast = build_mesh(model, MeshSettings(fast=True))
    assert fast.settings.fast and fast.settings.plate_layers == 3
    assert fast.element_count < 0.6 * normal.element_count
    assert fast.settings.size_fine > normal.settings.size_fine


def test_weld_sizes_for_drawing():
    from openfemconex.model import min_fillet

    _, model = model_from_project(EXAMPLES / "rigidizadores_w.ocnx")
    assert model.weld == pytest.approx(min_fillet(min(model.section.min_wall, model.tp)))
    assert model.stiffener_weld == pytest.approx(min_fillet(16.0))
    assert not model.cjp
