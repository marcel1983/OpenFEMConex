# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Render the isometric icons of the connection types (Agregar conexión dialog).

    .venv/bin/python tools/render_connection_icons.py

Writes ``src/openfemconex/gui/img/connections/<type>.png``. The pictures are drawn
here from simple boxes and cylinders; they are not taken from any other program.
"""

from __future__ import annotations

from pathlib import Path

import pyvista as pv

from openfemconex import tb_scene
from openfemconex.through_bolt_project import OPPOSITE, build, new_connection
from openfemconex.units import display_units

OUT = Path(__file__).resolve().parents[1] / "src" / "openfemconex" / "gui" / "img" / "connections"
STEEL, PLATE, BOLT, CONCRETE = tb_scene.STEEL, tb_scene.PLATE, tb_scene.BOLT, tb_scene.CONCRETE
SIZE = (360, 270)


def box(p, bounds, color, opacity=1.0):
    p.add_mesh(pv.Box(bounds=bounds), color=color, opacity=opacity)


def rod(p, center, direction, length, radius, color=BOLT):
    p.add_mesh(pv.Cylinder(center=center, direction=direction, radius=radius, height=length,
                           resolution=20), color=color)


def column_w(p, x0, x1, axis="z", d=320.0, bf=300.0, tf=24.0, tw=15.0):
    """W shape along ``axis`` from x0 to x1, its web along x."""
    if axis == "z":
        box(p, (-d / 2, -d / 2 + tf, -bf / 2, bf / 2, x0, x1), STEEL)
        box(p, (d / 2 - tf, d / 2, -bf / 2, bf / 2, x0, x1), STEEL)
        box(p, (-d / 2 + tf, d / 2 - tf, -tw / 2, tw / 2, x0, x1), STEEL)
    else:  # along x, web vertical
        box(p, (x0, x1, -bf / 2, bf / 2, d / 2 - tf, d / 2), STEEL)
        box(p, (x0, x1, -bf / 2, bf / 2, -d / 2, -d / 2 + tf), STEEL)
        box(p, (x0, x1, -tw / 2, tw / 2, -d / 2 + tf, d / 2 - tf), STEEL)


def base_plate(p):
    box(p, (-450, 450, -450, 450, -700, 0), CONCRETE, 0.45)
    box(p, (-280, 280, -280, 280, 0, 50), PLATE)
    column_w(p, 50, 1000)
    for x in (-220, 220):
        for y in (-150, 150):
            rod(p, (x, y, -200), (0, 0, 1), 400, 19)
            rod(p, (x, y, 70), (0, 0, 1), 40, 34)


def through_bolt(p, opposite=False):
    d = new_connection()
    if opposite:
        d["opposite"] = dict(OPPOSITE)
    tb_scene.draw(p, build(d, display_units("SI_kN_m")))


def shear_tab(p):
    column_w(p, -700, 700, "z", d=320, bf=300)
    box(p, (160, 330, -5, 5, -150, 150), PLATE)
    column_w(p, 180, 1100, "x", d=450, bf=190, tf=14, tw=9)
    for z in (-100, 0, 100):
        rod(p, (290, 0, z), (0, 1, 0), 50, 10)


def moment_end_plate(p):
    column_w(p, -800, 800, "z", d=320, bf=300)
    box(p, (160, 185, -110, 110, -290, 290), PLATE)
    column_w(p, 185, 1100, "x", d=460, bf=190, tf=16, tw=9)
    for z in (-265, -195, 195, 265):
        for y in (-70, 70):
            rod(p, (175, y, z), (1, 0, 0), 90, 11)


def splice(p):
    column_w(p, -900, -10, "x", d=460, bf=190, tf=16, tw=9)
    column_w(p, 10, 900, "x", d=460, bf=190, tf=16, tw=9)
    box(p, (-260, 260, -95, 95, 230, 246), PLATE)
    box(p, (-260, 260, -95, 95, -246, -230), PLATE)
    box(p, (-200, 200, 5, 15, -150, 150), PLATE)
    box(p, (-200, 200, -15, -5, -150, 150), PLATE)
    for x in (-200, -120, 120, 200):
        for y in (-55, 55):
            rod(p, (x, y, 238), (0, 0, 1), 60, 10)
            rod(p, (x, y, -238), (0, 0, 1), 60, 10)


TYPES = {
    "base_plate": base_plate,
    "through_bolt": through_bolt,
    "shear_tab": shear_tab,
    "moment_end_plate": moment_end_plate,
    "splice": splice,
}


ZOOM = {"through_bolt": 1.0, "splice": 1.1}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, draw in TYPES.items():
        p = pv.Plotter(off_screen=True, window_size=SIZE)
        p.set_background("white")
        draw(p)
        tb_scene.isometric(p)
        p.camera.zoom(ZOOM.get(name, 1.25))
        p.screenshot(str(OUT / f"{name}.png"), transparent_background=True)
        p.close()
        print(name)


if __name__ == "__main__":
    main()
