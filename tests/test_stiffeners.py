# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Stiffener plates: geometry, mesh and FEM solution."""

import dataclasses
import shutil
from pathlib import Path

import numpy as np
import pytest

from openfemconex.checks import CURRENT, check_fem, stiffener_slenderness
from openfemconex.extras import StiffenerSpec, load_extended
from openfemconex.mesh import build_mesh
from openfemconex.model import MeshSettings, Section, SectionKind, Stiffener
from openfemconex.openconex_bridge import model_of, project_loads, stiffeners_of
from openfemconex.solve import solve

EXAMPLES = Path(__file__).parents[1] / "examples"
SPEC = StiffenerSpec("alma", length=140.0, height=250.0, thickness=16.0, end_height=25.0)


def _volumes(nodes, conn):
    p = nodes[conn - 1]
    a = (p[:, [1, 2, 5, 6]] - p[:, [0, 3, 4, 7]]).mean(axis=1)
    b = (p[:, [3, 2, 7, 6]] - p[:, [0, 1, 4, 5]]).mean(axis=1)
    c = (p[:, 4:] - p[:, :4]).mean(axis=1)
    return np.einsum("ij,ij->i", np.cross(a, b), c)


def test_layouts():
    w = Section(SectionKind.I, d=300.0, bf=200.0, tf=15.0, tw=10.0)
    pipe = Section(SectionKind.HSS_ROUND, d=250.0, bf=250.0, t=10.0)
    web = stiffeners_of(w, SPEC)
    assert [s.origin for s in web] == [(-150.0, 0.0), (150.0, 0.0)]
    assert len(stiffeners_of(w, dataclasses.replace(SPEC, layout="alma y bordes"))) == 6
    radial = stiffeners_of(pipe, dataclasses.replace(SPEC, layout="radial", count=6))
    assert len(radial) == 6
    assert all(np.hypot(*s.origin) == pytest.approx(125.0) for s in radial)
    with pytest.raises(ValueError, match="circulares"):
        stiffeners_of(w, dataclasses.replace(SPEC, layout="radial"))
    with pytest.raises(ValueError, match="radial"):
        stiffeners_of(pipe, SPEC)


def test_stiffener_geometry():
    s = Stiffener((100.0, 0.0), (1.0, 0.0), 140.0, 16.0, 250.0, 25.0, embed=8.0)
    assert s.corners()[0] == pytest.approx((92.0, -8.0))
    assert s.local(170.0, 5.0) == pytest.approx((70.0, 5.0))
    assert s.height_at(0.0) == 250.0 and s.height_at(140.0) == 25.0
    assert s.height_at(70.0) == pytest.approx(137.5)


@pytest.mark.parametrize("name, count", [("rigidizadores_w.ocnx", 2),
                                         ("rigidizadores_tubo.ocnx", 8)])
def test_mesh_with_stiffeners(name, count):
    project, extras = load_extended(EXAMPLES / name)
    model = model_of(project, extras=extras)
    assert len(model.stiffeners) == count
    mesh = build_mesh(model, MeshSettings(size_fine=20.0))
    for part, conn in mesh.parts.items():
        assert (_volumes(mesh.nodes, conn) > 0).all(), part
    s = model.stiffeners[0]
    expected = count * s.length * s.thickness * (s.height + s.end_height) / 2
    volume = _volumes(mesh.nodes, mesh.parts["STIFFENER"]).sum()
    assert volume == pytest.approx(expected, rel=0.01)
    # stiffeners share nodes with the column and with the plate
    stiff = set(mesh.parts["STIFFENER"].ravel())
    assert stiff & set(mesh.parts["COLUMN"].ravel())
    assert stiff & set(mesh.parts["PLATE"].ravel())
    assert mesh.stiffener_levels[-1] == pytest.approx(s.height)
    assert len(mesh.stiffener_root_nodes) == count
    # element numbering stays consecutive across parts
    firsts = list(mesh.first_element.values())
    sizes = [len(c) for c in mesh.parts.values()]
    assert firsts == [1 + sum(sizes[:i]) for i in range(len(sizes))]


def test_stiffener_over_a_washer_is_rejected():
    project, extras = load_extended(EXAMPLES / "rigidizadores_w.ocnx")
    wide = dataclasses.replace(extras.stiffeners, layout="alma y bordes", length=150.0)
    with pytest.raises(ValueError, match="stiffener"):
        model_of(project, extras=dataclasses.replace(extras, stiffeners=wide)).validate()


def test_slenderness_limit():
    r = stiffener_slenderness(140.0, 16.0, 250.0)
    assert r.demand == pytest.approx(8.75)
    assert r.capacity == pytest.approx(0.56 * (200000 / 250) ** 0.5)


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_stiffeners_relieve_the_plate(tmp_path):
    project, extras = load_extended(EXAMPLES / "rigidizadores_w.ocnx")
    loads = dict((c.name, ld) for c, ld in project_loads(project))["LRFD-2"]
    settings = MeshSettings(size_fine=22.0)
    with_s = solve(model_of(project, extras=extras), loads, tmp_path / "con", settings=settings)
    without = solve(model_of(project), loads, tmp_path / "sin", settings=settings)
    for res in (with_s, without):
        assert res.converged and res.equilibrium_error < 1e-3 and res.moment_error < 0.01
    assert with_s.plate_peeq_element < without.plate_peeq_element
    assert with_s.anchors[0].uplift < without.anchors[0].uplift
    assert with_s.stiffener_weld and not without.stiffener_weld
    checks = {r.id: r for r in check_fem(project.base_plate_model(), with_s, CURRENT,
                                         extras=extras)}
    assert {"fem.stiffener_plastic_strain", "fem.stiffener_slenderness",
            "fem.stiffener_weld"} <= set(checks)
    assert not checks["fem.plate_bending_tension"].applicable


@pytest.mark.parametrize("layout, count, expected", [("alma", 8, 4), ("alma y bordes", 8, 12),
                                                     ("bordes", 8, 8),
                                                     ("radial", 4, 4), ("radial", 8, 8)])
def test_rectangular_tube_layouts(layout, count, expected):
    tube = Section(SectionKind.HSS_RECT, d=300, bf=200, t=12)
    spec = StiffenerSpec(layout, 80, 200, 12, 25, count=count)
    plates = stiffeners_of(tube, spec)
    assert len(plates) == expected
    for p in plates:
        # every plate starts on the tube wall and points away from the axis
        x, y = p.origin
        assert tube.distance(x, y) == 0.0
        assert x * p.direction[0] + y * p.direction[1] > 0


def test_w_shape_edges_only():
    w = Section(SectionKind.I, d=320, bf=300, tf=22, tw=14)
    plates = stiffeners_of(w, StiffenerSpec("bordes", 100, 200, 12, 25))
    assert len(plates) == 4
    assert all(abs(abs(p.origin[1]) - (150 - 6)) < 1e-9 for p in plates)


def test_cjp_weld_is_governed_by_the_wall():
    from openfemconex.checks import cjp_weld_line

    r = cjp_weld_line(1000.0, 0.0, 10.0, 345.0)
    assert r.capacity == pytest.approx(0.9 * 345.0 * 10.0)
    assert r.ratio == pytest.approx(1000.0 / (0.9 * 3450.0))
    shear = cjp_weld_line(0.0, 1000.0, 10.0, 345.0)
    assert shear.demand == pytest.approx(1000.0 * 3**0.5)
