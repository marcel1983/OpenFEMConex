# SPDX-License-Identifier: AGPL-3.0-or-later
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
  compression is applied in a first step and moments and shears in a second one;
* with a far plate or an opposite column (through-bolts) the rods end at nuts on that
  plate, which bears on the far face of the block (node-to-surface contact), and the
  block is held at its ends instead of its base.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import numpy as np

from openfemconex.mesh import FACE_BOTTOM, FACE_TOP, Mesh
from openfemconex.model import BasePlateModel, Loads

__all__ = ["AnchorStiffness", "InpNumbering", "anchor_stiffness", "rod_force",
           "write_inp"]


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


def rod_force(model: BasePlateModel, ks: AnchorStiffness, elongation: float) -> float:
    """Axial force of a rod with free nuts from its elongation: the spring law plus,
    for a pretensioned bolt, the pretension applied as a pair of forces."""
    T0 = model.flange.pretension if model.flange is not None else 0.0
    d = elongation
    return T0 + (ks.axial * d if d > 0 else ks.compression * d)


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
    lug_nodes: tuple[int, ...] = ()
    """Plate-side and concrete-side reference nodes of the shear lug."""
    lug_stiffness: float = 0.0
    far_springs: tuple[int, ...] = ()
    """Lateral springs (x then y) of the far plate nuts, with a far plate."""
    lug_offset: float = 0.0
    """Height of the plate-side lug nodes above the concrete-side ones [mm]: the lug
    transfers its shear across this offset, as the real lug does over its depth."""
    load_ref2: int = 0
    """Load nodes of the opposite column (0 without one)."""
    load_rot2: int = 0


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
              *, increments: int = 200, initial_increment: float = 0.05,
              knee: bool = False, min_increment: float = 1e-6, max_increment: float = 0.2,
              history: bool = False) -> InpNumbering:
    """Write the CalculiX input deck. With ``history`` the load nodes and the rods are
    printed to the .dat file at every increment (a load-deformation curve); otherwise
    only at the end of each step."""
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
    # Rods in oversized holes take shear only with welded washers, or when there is no
    # compression to give friction (net uplift with shear, no lug): then the plate slides
    # in the holes until the rods bear (DG1). Otherwise friction carries it and the
    # springs are only a weak restraint against rigid-body sliding.
    no_friction = (loads.P <= 0 and (loads.Vx or loads.Vy) and model.lug is None
                   and not model.anchor.friction_only)
    k_lat = (ks.lateral if model.anchor.welded_washers or no_friction
             else 1e-3 * ks.lateral)
    lug_nodes: tuple[int, ...] = ()
    lug_plate: list[int] = []
    lug_conc: list[int] = []
    k_lug = 0.0
    if model.lug is not None:
        lug = model.lug
        # plate bottom and concrete surface nodes over the lug footprint (a cross for
        # "both"); at least the nearest few, whatever the mesh size
        half = (lug.width / 2, max(lug.thickness, 2 * (mesh.settings.size_fine or 10.0)) / 2)
        boxes = {"strong": [(half[1], half[0])], "weak": [(half[0], half[1])],
                 "both": [(half[1], half[0]), (half[0], half[1])]}[lug.direction]

        def inside(ids):
            xy = mesh.nodes[ids - 1, :2] - np.array([model.ex, model.ey])
            sel = np.zeros(len(ids), dtype=bool)
            for hx, hy in boxes:
                sel |= (np.abs(xy[:, 0]) <= hx) & (np.abs(xy[:, 1]) <= hy)
            if sel.sum() < 3:
                sel = np.argsort(np.hypot(xy[:, 0], xy[:, 1]))[:3]
            return [int(n) for n in ids[sel]]

        # one layer away from the contact surfaces: nodes of a contact pair are best
        # kept out of the equations
        n2 = len(mesh.plate_bottom_nodes)
        lug_plate = inside(mesh.plate_bottom_nodes + n2)
        below = mesh.nodes[conc - 1, 2]
        level = below[below < -1e-6].max()
        lug_conc = inside(conc[np.abs(below - level) < 1e-6])
        lug_nodes = (nn + 3 + 3 * na, nn + 4 + 3 * na)
        # bearing on the concrete over the embedded face: very stiff compared with
        # the plate sliding on the grout
        k_lug = model.concrete.E * lug.width
    c = model.concrete
    top_z = model.tp + model.Lc
    opp = model.opposite
    load_ref2, load_rot2 = (nn + 5 + 3 * na, nn + 6 + 3 * na) if opp is not None else (0, 0)
    loads2 = (loads.opposite or Loads()) if opp is not None else None

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
        if opp is not None:
            z2 = -c.H - opp.tp - opp.Lc
            f.write("*NODE, NSET=LOADNODES2\n")
            f.write(f"{load_ref2}, {opp.ex:.6f}, {opp.ey:.6f}, {z2:.6f}\n")
            f.write(f"{load_rot2}, {opp.ex:.6f}, {opp.ey:.6f}, {z2:.6f}\n")
        f.write("*NODE, NSET=ANCHORREF\n")
        for nid, a in zip(anchor_ref, model.anchors):
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, {model.tp:.6f}\n")
        f.write("*NODE, NSET=ANCHORBASE\n")
        for nid, a in zip(anchor_base, model.anchors):
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, 0.\n")
        f.write("*NODE, NSET=ANCHORGND\n")
        far = model.far
        for nid, a in zip(anchor_ground, model.anchors):
            # Coincident with the washer node: springs between separated nodes that act
            # on one translation would add a spurious couple to the model. With a far
            # plate the node is its nut, on the same line along z.
            z = (-c.H - far.thickness if far is not None else -c.H - opp.tp if opp is not None
                 else -c.H if model.flange is not None else model.tp)
            f.write(f"{nid}, {a.x:.6f}, {a.y:.6f}, {z:.6f}\n")

        # ---- solid elements ----
        for part, conn in mesh.parts.items():
            f.write(f"*ELEMENT, TYPE=C3D8I, ELSET={part}\n")
            for eid, row in zip(mesh.element_ids(part), conn):
                f.write(f"{eid}, " + ", ".join(str(int(n)) for n in row) + "\n")

        # ---- sets ----
        _nset(f, "COLTOP", mesh.column_top_nodes)
        _nset(f, "CONCBOT", mesh.concrete_bottom_nodes)
        if model.two_faces:
            _nset(f, "CONCENDS", mesh.concrete_end_nodes)
        if model.flange is not None:
            _nset(f, "FLANGEHELD", mesh.flange_held_nodes)
        if opp is not None:
            _nset(f, "COLTOP2", mesh.opposite.column_top_nodes)
        _nset(f, "FOOTPRINT", mesh.footprint_nodes)
        _nset(f, "ANCHORCONC", sorted(set(anchor_concrete)))

        # ---- materials and sections ----
        cs, ps = model.column_steel, model.plate_steel
        _material(f, "COLSTEEL", cs.E, cs.nu, cs.plastic_curve())
        _material(f, "PLATESTEEL", ps.E, ps.nu, ps.plastic_curve())
        if model.flange is not None:
            fs = model.flange.steel
            _material(f, "CONCRETE", fs.E, fs.nu, fs.plastic_curve())
        else:
            _material(f, "CONCRETE", c.E, c.nu)
        f.write("*SOLID SECTION, ELSET=COLUMN, MATERIAL=COLSTEEL\n")
        f.write("*SOLID SECTION, ELSET=PLATE, MATERIAL=PLATESTEEL\n")
        f.write("*SOLID SECTION, ELSET=CONCRETE, MATERIAL=CONCRETE\n")
        if far is not None:
            _material(f, "FARSTEEL", far.steel.E, far.steel.nu, far.steel.plastic_curve())
            f.write("*SOLID SECTION, ELSET=FARPLATE, MATERIAL=FARSTEEL\n")
        if "STIFFENER" in mesh.parts:
            ss = model.stiffener_steel or ps
            _material(f, "STIFFSTEEL", ss.E, ss.nu, ss.plastic_curve())
            f.write("*SOLID SECTION, ELSET=STIFFENER, MATERIAL=STIFFSTEEL\n")
        if opp is not None:
            for part, st in (("PLATE2", opp.plate_steel), ("COLUMN2", opp.column_steel),
                             ("STIFFENER2", opp.stiffener_steel or opp.plate_steel)):
                if part in mesh.parts:
                    _material(f, part + "STEEL", st.E, st.nu, st.plastic_curve())
                    f.write(f"*SOLID SECTION, ELSET={part}, MATERIAL={part}STEEL\n")

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
        # not add friction to rod bearing), so the contact is left frictionless. With a
        # shear lug friction stays: it keeps the plate stable while the lug engages, and
        # the lug is checked for the whole shear anyway.
        if model.contact.mu > 0 and (loads.Vx or loads.Vy) and not model.anchor.welded_washers:
            f.write(f"*FRICTION\n{model.contact.mu:.4e}, {K / 10:.6e}\n")
        if model.two_faces:
            # the far plate bears on the far face of the block, frictionless. Node to
            # surface: with surface to surface the contact status of the plate, which
            # starts touching with no pressure, chatters and Newton stalls.
            f.write("*SURFACE, NAME=SFAR, TYPE=ELEMENT\n")
            for e in mesh.far_top_elements:
                f.write(f"{int(e)}, {FACE_TOP}\n")
            f.write("*SURFACE, NAME=SCONCB, TYPE=ELEMENT\n")
            for e in mesh.concrete_bottom_elements:
                f.write(f"{int(e)}, {FACE_BOTTOM}\n")
            f.write("*CONTACT PAIR, INTERACTION=SI2, TYPE=NODE TO SURFACE\nSFAR, SCONCB\n")
            f.write("*SURFACE INTERACTION, NAME=SI2\n")
            f.write("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR\n")
            f.write(f"{K:.6e}, {model.contact.tension:.6e}\n")
            # an opposite column carries its own shear through friction like the first
            if (opp is not None and opp.contact.mu > 0 and (loads2.Vx or loads2.Vy)
                    and not model.anchor.welded_washers):
                f.write(f"*FRICTION\n{opp.contact.mu:.4e}, {K / 10:.6e}\n")

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
        if model.free_nuts:
            # the nut on the far plate (or on the column flange): its node follows the
            # face under it
            tied += list(zip(anchor_ground, mesh.far_washer_nodes, mesh.far_washer_weights))
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
        # Tension-only law. With ``knee`` the stiffness changes in steps of ten over
        # 0.005 mm on each side of zero: it stops Newton from chattering when a rod
        # starts to work under moment, but it hinders pure uplift, so it is the retry.
        kt, kc, width = ks.axial, ks.compression, 0.005
        if knee and kc < 0.01 * kt:
            f_neg = -0.01 * kt * width
            f_pos = 0.1 * kt * width
            f.write(f"{f_neg - kc * (X - width):.6e}, {-X:.6e}\n{f_neg:.6e}, {-width:.6e}\n"
                    f"0., 0.\n{f_pos:.6e}, {width:.6e}\n"
                    f"{f_pos + kt * (X - width):.6e}, {X:.6e}\n")
        else:
            f.write(f"{-kc * X:.6e}, {-X:.6e}\n0., 0.\n{kt * X:.6e}, {X:.6e}\n")
        f.write(f"*SPRING, ELSET=RODX\n1, 1\n{k_lat:.6e}\n")
        f.write(f"*SPRING, ELSET=RODY\n2, 2\n{k_lat:.6e}\n")
        far_springs: tuple[int, ...] = ()
        if model.two_faces:
            # weak lateral restraint of the far plate (it has no friction): each nut to
            # the nearest node of the far face of the block. The rods bearing on the
            # grout carry the shear of an opposite column: then they are not weak.
            cb = conc[np.abs(mesh.nodes[conc - 1, 2] + c.H) < 1e-6]
            cxy = mesh.nodes[cb - 1, :2]
            near = [int(cb[np.argmin(np.hypot(cxy[:, 0] - a.x, cxy[:, 1] - a.y))])
                    for a in model.anchors]
            start = ne + 1 + 3 * na + 2
            far_springs = tuple(start + i for i in range(2 * na))
            k_weak = (ks.lateral if opp is not None and model.anchor.welded_washers
                      else 1e-3 * ks.lateral)
            for k, (dof, name) in enumerate(((1, "FARX"), (2, "FARY"))):
                f.write(f"*ELEMENT, TYPE=SPRING2, ELSET={name}\n")
                for i, (g, cn) in enumerate(zip(anchor_ground, near)):
                    f.write(f"{far_springs[k * na + i]}, {g}, {cn}\n")
                f.write(f"*SPRING, ELSET={name}\n{dof}, {dof}\n{k_weak:.6e}\n")

        # ---- shear lug ----
        if lug_nodes:
            f.write("*NODE, NSET=LUGNODES\n")
            f.write(f"{lug_nodes[0]}, {model.ex:.6f}, {model.ey:.6f}, 0.\n")
            f.write(f"{lug_nodes[1]}, {model.ex:.6f}, {model.ey:.6f}, 0.\n")
            f.write("*EQUATION\n")
            for ref, ids in ((lug_nodes[0], lug_plate), (lug_nodes[1], lug_conc)):
                for dof in (1, 2, 3):
                    terms = [(ref, dof, -1.0)] + [(int(n), dof, 1.0 / len(ids)) for n in ids]
                    f.write(f"{len(terms)}\n")
                    for i in range(0, len(terms), 4):
                        f.write(", ".join(f"{n}, {d}, {c:.8e}" for n, d, c in terms[i:i + 4])
                                + "\n")
            dofs = {"strong": (1,), "weak": (2,), "both": (1, 2)}[model.lug.direction]
            for k, dof in enumerate(dofs):
                f.write(f"*ELEMENT, TYPE=SPRING2, ELSET=LUG{dof}\n")
                f.write(f"{ne + 1 + 3 * na + k}, {lug_nodes[0]}, {lug_nodes[1]}\n")
                f.write(f"*SPRING, ELSET=LUG{dof}\n{dof}, {dof}\n{k_lug:.6e}\n")

        # ---- load introduction ----
        f.write(f"*RIGID BODY, NSET=COLTOP, REF NODE={load_ref}, ROT NODE={load_rot}\n")
        if opp is not None:
            f.write(f"*RIGID BODY, NSET=COLTOP2, REF NODE={load_ref2}, ROT NODE={load_rot2}\n")

        # ---- boundary conditions ----
        if model.flange is not None:
            f.write("*BOUNDARY\nFLANGEHELD, 1, 3\n")
        elif not model.two_faces:
            f.write("*BOUNDARY\nCONCBOT, 1, 3\nANCHORGND, 1, 3\n")
        else:
            f.write("*BOUNDARY\nCONCENDS, 1, 3\n")

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
        if opp is not None:
            # the opposite column in its own axes, mirrored about the block: forces keep
            # x and y and flip z, moments flip x and y
            h2 = opp.tp + opp.Lc
            axial += [(load_ref2, 3, loads2.P)] if loads2.P else []
            rest += [(load_ref2, 1, loads2.Vx), (load_ref2, 2, loads2.Vy),
                     (load_rot2, 1, -(loads2.Mx + loads2.Vy * h2)),
                     (load_rot2, 2, -(loads2.My - loads2.Vx * h2))]
        rest = [r for r in rest if r[2]]
        T0 = model.flange.pretension if model.flange is not None else 0.0
        if T0 > 0:
            # Bolt pretension: a pair of forces T0 on the plate under each washer and on
            # the flange under each nut, in a first step; the tension-only spring adds
            # its force when the joint opens (T0 + kt·δ, the force of a pretensioned
            # bolt once the plies separate). Forces on the mesh nodes, with the washer
            # weights: a dependent node of an *EQUATION takes no load.
            for wn, ww, fwn, fww in zip(mesh.washer_nodes, mesh.washer_weights,
                                        mesh.far_washer_nodes, mesh.far_washer_weights):
                axial += [(int(n), 3, -T0 * float(w)) for n, w in zip(wn, ww)]
                axial += [(int(n), 3, T0 * float(w)) for n, w in zip(fwn, fww)]
        steps = ([axial, rest] if (loads.P > 0 or (loads2 is not None and loads2.P > 0)
                                   or T0 > 0) and rest else [axial + rest])
        for k, cloads in enumerate(steps):
            last = k == len(steps) - 1
            first, largest = ((min(initial_increment, max_increment), max_increment) if last
                              else (1.0, 1.0))
            f.write(f"*STEP, INC={increments}\n*STATIC\n{first:.4e}, 1., {min_increment:.1e}, "
                    f"{largest:.4e}\n")
            f.write("*CLOAD\n")
            for node, dof, value in cloads:
                f.write(f"{node}, {dof}, {value:.8e}\n")
            f.write("*NODE FILE, FREQUENCY=100000\nU\n*EL FILE, FREQUENCY=100000\nS, PEEQ\n"
                    "*CONTACT FILE, FREQUENCY=100000\nCSTR\n")
            prints = [("ANCHORGND", "RF"), ("ANCHORREF", "U"), ("ANCHORBASE", "U"),
                      ("ANCHORCONC", "U"), ("CONCBOT", "RF"), ("LOADNODES", "U")]
            if lug_nodes:
                prints.append(("LUGNODES", "U"))
            if model.two_faces:
                prints += [("ANCHORGND", "U"), ("CONCENDS", "RF")]
            elif model.flange is not None:
                prints += [("ANCHORGND", "U"), ("FLANGEHELD", "RF")]
            if opp is not None:
                prints.append(("LOADNODES2", "U"))
            for nset, key in prints:
                # every increment: if the step stops early the last converged state is
                # still in the .dat file
                every = ", FREQUENCY=1" if history else ""
                f.write(f"*NODE PRINT, NSET={nset}{every}\n{key}\n")
            f.write("*END STEP\n")

    return InpNumbering(load_ref, load_rot, anchor_ref, anchor_ground, spring_axial,
                        steps=len(steps), anchor_base=anchor_base,
                        anchor_concrete=anchor_concrete, lateral_stiffness=k_lat,
                        lug_nodes=lug_nodes, lug_stiffness=k_lug, far_springs=far_springs,
                        lug_offset=(float(mesh.nodes[np.array(lug_plate) - 1, 2].mean()
                                          - mesh.nodes[np.array(lug_conc) - 1, 2].mean())
                                    if lug_nodes else 0.0),
                        load_ref2=load_ref2, load_rot2=load_rot2)
