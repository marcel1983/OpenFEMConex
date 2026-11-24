# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""CalculiX input (.inp) writer for the base plate model.

Components (CBFEM-style):

* column and plate: C3D8I solids, bilinear elastic-plastic steel;
* column–plate weld: shared nodes on the column footprint;
* concrete (with grout): elastic C3D8I block, base fixed, in frictional
  surface-to-surface contact with the plate (no tension);
* anchor rods: a reference node at each plate washer whose translation is the
  area-weighted mean of the plate nodes under the washer (*EQUATION), connected to a
  fixed ground node by
  SPRING2 elements: axial (tension only unless leveling nuts) and lateral (engaged
  only with welded plate washers; otherwise shear goes through friction);
* loads: a *RIGID BODY at the column top; the forces given at the plate base are
  transferred to the top (moments corrected for the shear lever arm). The axial
  compression is applied in a first step and moments and shears in a second one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import numpy as np

from openfemconex.mesh import FACE_BOTTOM, FACE_TOP, Mesh
from openfemconex.model import BasePlateModel, Loads

__all__ = ["AnchorStiffness", "InpNumbering", "anchor_stiffness", "write_inp"]


@dataclass(frozen=True)
class AnchorStiffness:
    axial: float
    """Tension stiffness E·A/L [N/mm], L from the nut to the embedded head."""
    compression: float
    lateral: float
    """Shear stiffness of each direction [N/mm]."""
    length: float


def anchor_stiffness(model: BasePlateModel) -> AnchorStiffness:
    a = model.anchor
    L = a.hef + model.concrete.grout + model.tp
    k = a.E * a.area / L
    # Lateral: rod bending over the grout plus half the plate, both ends fixed.
    lb = max(model.concrete.grout + model.tp / 2, a.diameter)
    k_lat = 12 * a.E * a.inertia / lb**3
    return AnchorStiffness(axial=k, compression=k if a.leveling_nuts else 1e-3 * k,
                           lateral=k_lat, length=L)


@dataclass(frozen=True)
class InpNumbering:
    """Ids of the auxiliary nodes and elements added by the writer."""

    load_ref: int
    load_rot: int
    anchor_ref: tuple[int, ...]
    anchor_ground: tuple[int, ...]
    spring_axial: tuple[int, ...]
    steps: int = 1
    """With two steps the first one applies only the axial compression."""
    anchor_base: tuple[int, ...] = ()
    """Nodes that follow the plate bottom under each washer (lateral springs)."""
    anchor_concrete: tuple[int, ...] = ()
    """Concrete surface node next to each rod, the other end of the lateral springs."""
    lateral_stiffness: float = 0.0


def _write_rows(f: TextIO, rows, per_line: int = 8) -> None:
    rows = [int(r) for r in rows]
    for i in range(0, len(rows), per_line):
        f.write(", ".join(str(r) for r in rows[i:i + per_line]) + "\n")


def _nset(f: TextIO, name: str, ids) -> None:
    f.write(f"*NSET, NSET={name}\n")
    _write_rows(f, ids, 16)


def _material(f: TextIO, name: str, E: float, nu: float,
              plastic: list[tuple[float, float]] | None = None) -> None:
    f.write(f"*MATERIAL, NAME={name}\n*ELASTIC\n{E:.6e}, {nu:.4e}\n")
    if plastic:
        f.write("*PLASTIC\n")
        for s, e in plastic:
            f.write(f"{s:.6e}, {e:.6e}\n")


def write_inp(path: str | Path, model: BasePlateModel, mesh: Mesh, loads: Loads,
              *, increments: int = 200, initial_increment: float = 0.05) -> InpNumbering:
    path = Path(path)
    nn = len(mesh.nodes)
    na = len(model.anchors)
    load_ref, load_rot = nn + 1, nn + 2
    anchor_ref = tuple(nn + 3 + i for i in range(na))
    anchor_ground = tuple(nn + 3 + na + i for i in range(na))
    anchor_base = tuple(nn + 3 + 2 * na + i for i in range(na))
    ne = mesh.element_count
    spring_axial = tuple(ne + 1 + i for i in range(na))
    spring_x = tuple(ne + 1 + na + i for i in range(na))
    spring_y = tuple(ne + 1 + 2 * na + i for i in range(na))
    ks = anchor_stiffness(model)
    conc = np.unique(mesh.parts["CONCRETE"])
    surface = conc[np.abs(mesh.nodes[conc - 1, 2]) < 1e-6]
    sxy = mesh.nodes[surface - 1, :2]
    anchor_concrete = tuple(
        int(surface[np.argmin(np.hypot(sxy[:, 0] - a.x, sxy[:, 1] - a.y))])
        for a in model.anchors)
    k_lat = ks.lateral if model.anchor.welded_washers else 1e-3 * ks.lateral
    c = model.concrete
    top_z = model.tp + model.Lc

    with path.open("w") as f:
        f.write("*HEADING\n")
        f.write(f"OpenFEMConex base plate: {model.title or model.section.name} / {loads.name}\n")
        f.write("** Units: N, mm, MPa\n")

        # ---- nodes ----
        f.write("*NODE, NSET=NALL\n")
        for i, (x, y, z) in enumerate(mesh.nodes, start=1):
            f.write(f"{i}, {x:.6f}, {y:.6f}, {z:.6f}\n")
        f.write("*NODE, NSET=LOADNODES\n")
        f.write(f"{load_ref}, {model.ex:.6f}, {model.ey:.6f}, {top_z:.6f}\n")
        f.write(f"{load_rot}, {model.ex:.6f}, {model.ey:.6f}, {top_z:.6f}\n")
        f.write("*NODE, NSET=ANCHORREF\n")
        for nid, a in zip(anchor_ref, model.anchors):
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, {model.tp:.6f}\n")
        f.write("*NODE, NSET=ANCHORBASE\n")
        for nid, a in zip(anchor_base, model.anchors):
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, 0.\n")
        f.write("*NODE, NSET=ANCHORGND\n")
        for nid, a in zip(anchor_ground, model.anchors):
            # Coincident with the washer node: springs between separated nodes that act
            # on one translation would add a spurious couple to the model.
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, {model.tp:.6f}\n")

        # ---- solid elements ----
        for part, conn in mesh.parts.items():
            f.write(f"*ELEMENT, TYPE=C3D8I, ELSET={part}\n")
            for eid, row in zip(mesh.element_ids(part), conn):
                f.write(f"{eid}, " + ", ".join(str(int(n)) for n in row) + "\n")

        # ---- sets ----
        _nset(f, "COLTOP", mesh.column_top_nodes)
        _nset(f, "CONCBOT", mesh.concrete_bottom_nodes)
        _nset(f, "FOOTPRINT", mesh.footprint_nodes)
        _nset(f, "ANCHORCONC", sorted(set(anchor_concrete)))

        # ---- materials and sections ----
        cs, ps = model.column_steel, model.plate_steel
        _material(f, "COLSTEEL", cs.E, cs.nu, cs.plastic_curve())
        _material(f, "PLATESTEEL", ps.E, ps.nu, ps.plastic_curve())
        _material(f, "CONCRETE", c.E, c.nu)
        f.write("*SOLID SECTION, ELSET=COLUMN, MATERIAL=COLSTEEL\n")
        f.write("*SOLID SECTION, ELSET=PLATE, MATERIAL=PLATESTEEL\n")
        f.write("*SOLID SECTION, ELSET=CONCRETE, MATERIAL=CONCRETE\n")
        if "STIFFENER" in mesh.parts:
            ss = model.stiffener_steel or ps
            _material(f, "STIFFSTEEL", ss.E, ss.nu, ss.plastic_curve())
            f.write("*SOLID SECTION, ELSET=STIFFENER, MATERIAL=STIFFSTEEL\n")

        # ---- contact plate / concrete ----
        f.write("*SURFACE, NAME=SPLATE, TYPE=ELEMENT\n")
        for e in mesh.plate_bottom_elements:
            f.write(f"{int(e)}, {FACE_BOTTOM}\n")
        f.write("*SURFACE, NAME=SCONC, TYPE=ELEMENT\n")
        for e in mesh.concrete_top_elements:
            f.write(f"{int(e)}, {FACE_TOP}\n")
        K = model.contact.stiffness or 10.0 * c.E / 25.0
        f.write("*CONTACT PAIR, INTERACTION=SI1, TYPE=SURFACE TO SURFACE\nSPLATE, SCONC\n")
        f.write("*SURFACE INTERACTION, NAME=SI1\n")
        f.write("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR\n")
        f.write(f"{K:.6e}, {model.contact.tension:.6e}\n")
        # Friction only matters when there is shear to transfer; without it the contact
        # is frictionless, which keeps the system symmetric and converges faster.
        # With welded plate washers the rods are designed for the whole shear (DG1 does
        # not add friction to rod bearing), so the contact is left frictionless.
        if model.contact.mu > 0 and (loads.Vx or loads.Vy) and not model.anchor.welded_washers:
            f.write(f"*FRICTION\n{model.contact.mu:.4e}, {K / 10:.6e}\n")

        # ---- anchors ----
        # The washer reference node follows the area-weighted mean translation of the
        # plate nodes under the washer, so the rod force is spread over the washer area.
        f.write("*EQUATION\n")
        # A second node per rod follows the plate bottom under the washer: the lateral
        # springs act there, so they resist the slip of the plate on the grout and not
        # the sway of its top face when the plate tilts.
        down = mesh.plate_node_count - mesh.plate_node_count // (mesh.settings.plate_layers + 1)
        tied = list(zip(anchor_ref, mesh.washer_nodes, mesh.washer_weights)) + [
            (base, wn - down, ww)
            for base, wn, ww in zip(anchor_base, mesh.washer_nodes, mesh.washer_weights)]
        for ref, wn, ww in tied:
            for dof in (1, 2, 3):
                terms = [(ref, dof, -1.0)] + [(int(n), dof, float(w)) for n, w in zip(wn, ww)]
                f.write(f"{len(terms)}\n")
                for i in range(0, len(terms), 4):
                    f.write(", ".join(f"{n}, {d}, {c:.8e}" for n, d, c in terms[i:i + 4]) + "\n")
        for name, ids in (("RODAX", spring_axial), ("RODX", spring_x), ("RODY", spring_y)):
            f.write(f"*ELEMENT, TYPE=SPRING2, ELSET={name}\n")
            # Node order (plate, ground): with it ccx 2.21 evaluates the tabulated law
            # with a positive elongation when the plate lifts.
            # The lateral springs join the plate bottom to the concrete surface next to
            # the rod, so they follow the block when it deforms.
            pairs = (zip(anchor_ground, anchor_ref) if name == "RODAX"
                     else zip(anchor_concrete, anchor_base))
            for eid, (g, r) in zip(ids, pairs):
                f.write(f"{eid}, {r}, {g}\n")
        X = 1000.0  # mm, range of the tabulated law
        f.write("*SPRING, ELSET=RODAX, NONLINEAR\n3, 3\n")
        f.write(f"{-ks.compression * X:.6e}, {-X:.6e}\n0., 0.\n{ks.axial * X:.6e}, {X:.6e}\n")
        # Rods in oversized holes do not take shear (DG1): friction does. The lateral
        # springs are then only a weak restraint against rigid-body sliding. With plate
        # washers welded to the plate the rods are engaged with their bending stiffness.
        f.write(f"*SPRING, ELSET=RODX\n1, 1\n{k_lat:.6e}\n")
        f.write(f"*SPRING, ELSET=RODY\n2, 2\n{k_lat:.6e}\n")

        # ---- load introduction ----
        f.write(f"*RIGID BODY, NSET=COLTOP, REF NODE={load_ref}, ROT NODE={load_rot}\n")

        # ---- boundary conditions ----
        f.write("*BOUNDARY\nCONCBOT, 1, 3\nANCHORGND, 1, 3\n")

        # ---- steps ----
        # The axial compression is applied first (the whole plate bears on the concrete)
        # and the moments and shears afterwards, so that the contact zone shrinks
        # gradually instead of having to be found in the first increment.
        h = top_z  # lever arm from the plate base to the load node
        Mx_top = loads.Mx + loads.Vy * h
        My_top = loads.My - loads.Vx * h
        axial = [(load_ref, 3, -loads.P)] if loads.P else []
        rest = [(load_ref, 1, loads.Vx), (load_ref, 2, loads.Vy), (load_rot, 1, Mx_top),
                (load_rot, 2, My_top)]
        rest = [r for r in rest if r[2]]
        steps = [axial, rest] if loads.P > 0 and rest else [axial + rest]
        for k, cloads in enumerate(steps):
            last = k == len(steps) - 1
            first, largest = (initial_increment, 0.2) if last else (1.0, 1.0)
            f.write(f"*STEP, INC={increments}\n*STATIC\n{first:.4e}, 1., 1e-6, {largest:.4e}\n")
            f.write("*CLOAD\n")
            for node, dof, value in cloads:
                f.write(f"{node}, {dof}, {value:.8e}\n")
            f.write("*NODE FILE, FREQUENCY=100000\nU\n*EL FILE, FREQUENCY=100000\nS, PEEQ\n"
                    "*CONTACT FILE, FREQUENCY=100000\nCSTR\n")
            for nset, key in (("ANCHORGND", "RF"), ("ANCHORREF", "U"), ("ANCHORBASE", "U"),
                              ("ANCHORCONC", "U"), ("CONCBOT", "RF"),
                              ("LOADNODES", "U")):
                f.write(f"*NODE PRINT, NSET={nset}, FREQUENCY=100000\n{key}\n")
            f.write("*END STEP\n")

    return InpNumbering(load_ref, load_rot, anchor_ref, anchor_ground, spring_axial,
                        steps=len(steps), anchor_base=anchor_base,
                        anchor_concrete=anchor_concrete, lateral_stiffness=k_lat)
