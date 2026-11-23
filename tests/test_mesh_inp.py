# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
from pathlib import Path

import numpy as np
import pytest

from openfemconex.inp import anchor_stiffness, write_inp
from openfemconex.mesh import build_mesh
from openfemconex.model import (
    Anchor,
    AnchorSpec,
    BasePlateModel,
    Concrete,
    Loads,
    MeshSettings,
    Section,
    SectionKind,
    Steel,
)

A992 = Steel(345.0, 450.0)
A36 = Steel(250.0, 400.0)


def _model(section: Section) -> BasePlateModel:
    return BasePlateModel(
        section=section, column_steel=A992, N=500.0, B=450.0, tp=30.0, plate_steel=A36,
        anchors=tuple(Anchor(x, y) for x in (-190.0, 190.0) for y in (-150.0, 150.0)),
        anchor=AnchorSpec(diameter=25.4, hole=47.6, washer=76.2, hef=400.0),
        concrete=Concrete(fc=28.0, N=700.0, B=650.0, H=500.0, grout=30.0))


SECTIONS = {
    "W": Section(SectionKind.I, d=250.0, bf=200.0, tf=14.0, tw=9.0, name="W"),
    "HSS": Section(SectionKind.HSS_RECT, d=250.0, bf=150.0, t=9.5, name="HSS"),
    "PIPE": Section(SectionKind.HSS_ROUND, d=219.0, bf=219.0, t=8.2, name="PIPE"),
}


def _hex_volumes(nodes: np.ndarray, conn: np.ndarray) -> np.ndarray:
    p = nodes[conn - 1]
    # volume from the three mean edge vectors (exact for prisms extruded along z)
    a = (p[:, [1, 2, 5, 6]] - p[:, [0, 3, 4, 7]]).mean(axis=1)
    b = (p[:, [3, 2, 7, 6]] - p[:, [0, 1, 4, 5]]).mean(axis=1)
    c = (p[:, 4:] - p[:, :4]).mean(axis=1)
    return np.einsum("ij,ij->i", np.cross(a, b), c)


@pytest.mark.parametrize("name", SECTIONS)
def test_mesh_is_valid_and_conforming(name):
    model = _model(SECTIONS[name])
    mesh = build_mesh(model, MeshSettings(size_fine=10.0))
    for part, conn in mesh.parts.items():
        assert conn.min() >= 1 and conn.max() <= len(mesh.nodes)
        assert (_hex_volumes(mesh.nodes, conn) > 0).all(), part
    # the plate bottom covers the plate minus the holes
    holes = len(model.anchors) * np.pi * model.anchor.hole**2 / 4
    assert mesh.plate_bottom_area.sum() == pytest.approx(model.N * model.B - holes, rel=5e-3)
    # column and plate share the footprint nodes
    assert set(mesh.footprint_nodes) <= set(mesh.parts["PLATE"].ravel())
    assert set(mesh.footprint_nodes) <= set(mesh.parts["COLUMN"].ravel())
    # column volume matches the section area
    s = model.section
    area = {"W": 2 * s.bf * s.tf + (s.d - 2 * s.tf) * s.tw,
            "HSS": s.d * s.bf - (s.d - 2 * s.t) * (s.bf - 2 * s.t),
            "PIPE": np.pi / 4 * (s.d**2 - (s.d - 2 * s.t) ** 2)}[name]
    volume = _hex_volumes(mesh.nodes, mesh.parts["COLUMN"]).sum()
    assert volume == pytest.approx(area * model.Lc, rel=1e-2)
    for w in mesh.washer_weights:
        assert w.sum() == pytest.approx(1.0)
    assert np.allclose(mesh.nodes[mesh.column_top_nodes - 1, 2], model.tp + model.Lc)


def test_inp_has_the_expected_cards(tmp_path: Path):
    model = _model(SECTIONS["W"])
    mesh = build_mesh(model, MeshSettings(size_fine=12.0))
    loads = Loads(P=500e3, Vx=40e3, My=80e6, name="C1")
    num = write_inp(tmp_path / "c1.inp", model, mesh, loads)
    text = (tmp_path / "c1.inp").read_text()
    for card in ("*ELEMENT, TYPE=C3D8I, ELSET=PLATE", "*PLASTIC", "*CONTACT PAIR",
                 "*FRICTION", "*EQUATION", "*SPRING, ELSET=RODAX, NONLINEAR", "*RIGID BODY",
                 "*STATIC", "*CONTACT FILE"):
        assert card in text
    h = model.tp + model.Lc
    assert f"{num.load_ref}, 3, {-loads.P:.8e}" in text
    # the moment at the column top is reduced by the shear lever arm
    assert f"{num.load_rot}, 2, {loads.My - loads.Vx * h:.8e}" in text
    assert len(num.anchor_ref) == 4


def test_anchor_stiffness():
    model = _model(SECTIONS["W"])
    ks = anchor_stiffness(model)
    area = np.pi * 25.4**2 / 4
    assert ks.axial == pytest.approx(200000.0 * area / (400.0 + 30.0 + 30.0))
    assert ks.compression < 0.01 * ks.axial


def test_washer_outside_plate_is_rejected():
    model = _model(SECTIONS["W"])
    bad = BasePlateModel(**{**model.__dict__, "anchors": (Anchor(240.0, 0.0),)})
    with pytest.raises(ValueError, match="washer"):
        build_mesh(bad)
