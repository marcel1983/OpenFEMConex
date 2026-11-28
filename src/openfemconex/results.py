# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Readers for the CalculiX .dat and .frd files and the result summary."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from openfemconex.inp import InpNumbering
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel, Loads, SectionKind

__all__ = ["AnchorForce", "Results", "WeldPoint", "read_dat", "read_dat_history", "read_frd",
           "summarize",
           "stiffener_weld_forces", "von_mises", "weld_forces"]


# --------------------------------------------------------------------------- .dat
def read_dat(path: str | Path) -> dict[str, dict[int, np.ndarray]]:
    """Last printed table of each ``kind/SET`` in the .dat file.

    Keys look like ``"forces/ANCHORGND"``, ``"displacements/ANCHORREF"`` or
    ``"total force/CONCBOT"`` (the totals are stored under node id 0).
    """
    out: dict[str, dict[int, np.ndarray]] = {}
    current: dict[int, np.ndarray] | None = None
    total = False
    for line in Path(path).read_text().splitlines():
        text = line.strip()
        if " for set " in line:
            kind = text.split("(")[0].strip()
            name = text.split(" for set ")[1].split()[0]
            total = kind.startswith("total")
            current = out[f"{kind}/{name}"] = {}
            continue
        if not text or current is None:
            continue
        parts = text.split()
        try:
            if total:
                current[0] = np.array([float(p) for p in parts])
            else:
                current[int(parts[0])] = np.array([float(p) for p in parts[1:]])
        except ValueError:
            current = None
    return out


def read_dat_history(path: str | Path, key: str) -> list[tuple[float, dict[int, np.ndarray]]]:
    """Every printed table of ``key`` (``kind/SET``, as in read_dat) with its time:
    [(time, {node: values})], in the order of the file (the increments)."""
    out: list[tuple[float, dict[int, np.ndarray]]] = []
    current: dict[int, np.ndarray] | None = None
    for line in Path(path).read_text().splitlines():
        text = line.strip()
        if " for set " in line:
            kind = text.split("(")[0].strip()
            name = text.split(" for set ")[1].split()[0]
            current = None
            if f"{kind}/{name}" == key:
                time = float(text.rsplit("time", 1)[1]) if "time" in text else 0.0
                current = {}
                out.append((time, current))
            continue
        if not text or current is None:
            continue
        parts = text.split()
        try:
            current[int(parts[0])] = np.array([float(v) for v in parts[1:]])
        except ValueError:
            current = None
    return out


# --------------------------------------------------------------------------- .frd
def read_frd(path: str | Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Last nodal result block of each name: ``name -> (node ids, values[n, ncomp])``."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    name: str | None = None
    ids: list[int] = []
    rows: list[list[float]] = []
    with Path(path).open(errors="replace") as f:
        for line in f:
            key = line[:3]
            if key == " -4":
                name, ids, rows = line.split()[1], [], []
            elif key == " -1" and name is not None:
                ids.append(int(line[3:13]))
                body = line[13:].rstrip("\n")
                rows.append([float(body[i:i + 12]) for i in range(0, len(body), 12)])
            elif key == " -3" and name is not None:
                out[name] = (np.asarray(ids), np.asarray(rows))
                name = None
    return out


def von_mises(s: np.ndarray) -> np.ndarray:
    """Von Mises stress from rows ``SXX SYY SZZ SXY SYZ SZX``."""
    sx, sy, sz, sxy, syz, szx = s.T
    return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
                   + 3.0 * (sxy**2 + syz**2 + szx**2))


# --------------------------------------------------------------------------- summary
@dataclass(frozen=True)
class AnchorForce:
    x: float
    y: float
    tension: float
    """Axial force, positive in tension [N]."""
    Vx: float
    """Shear the rod applies to the plate [N]."""
    Vy: float
    uplift: float
    """Vertical displacement of the plate at the washer [mm]."""


@dataclass(frozen=True)
class WeldPoint:
    """Force per unit length that the column wall delivers to the weld at one station."""

    wall: str
    """``flange+``, ``flange-``, ``web``, ``wall_x+``, ``wall_y-``, ``pipe``..."""
    x: float
    y: float
    thickness: float
    normal: float
    """Force per unit length normal to the plate, positive in tension [N/mm]."""
    shear: float
    """Resultant in-plane shear per unit length [N/mm]."""


def weld_forces(model: BasePlateModel, mesh: Mesh, stress_ids: np.ndarray,
                stress: np.ndarray) -> list[WeldPoint]:
    """Forces per unit length along the column walls, just above the plate.

    The nodal stresses of the first column level are averaged over each footprint
    quad and integrated through the wall thickness in stations along each wall.
    """
    if not len(mesh.weld_quads):
        return []
    table = np.zeros((int(max(stress_ids.max(), mesh.weld_quads.max())) + 1, 6))
    table[stress_ids] = stress
    sq = table[mesh.weld_quads].mean(axis=1)  # (m, 6): SXX SYY SZZ SXY SYZ SZX
    xy = mesh.weld_quad_xy - np.array([model.ex, model.ey])
    s = model.section
    step = 1.5 * (mesh.settings.size_wall or mesh.settings.size_fine or 10.0)
    wall = np.empty(len(xy), dtype=object)
    station = np.zeros(len(xy))
    thick = np.zeros(len(xy))
    if s.kind is SectionKind.HSS_ROUND:
        r = s.d / 2 - s.t / 2
        wall[:] = "pipe"
        station = np.arctan2(xy[:, 1], xy[:, 0]) * r
        thick[:] = s.t
    elif s.kind is SectionKind.CRUCIFORM:
        for i, (x, y) in enumerate(xy):
            sx, sy = "+" if x >= 0 else "-", "+" if y >= 0 else "-"
            if abs(x) > s.d / 2 - s.tf:
                wall[i], station[i], thick[i] = "flange" + sx, y, s.tf
            elif abs(y) > s.d2 / 2 - s.tf2:
                wall[i], station[i], thick[i] = "cross_flange" + sy, x, s.tf2
            elif abs(y) <= s.tw / 2:
                wall[i], station[i], thick[i] = "web", x, s.tw
            else:
                wall[i], station[i], thick[i] = "cross_web" + sy, y, s.tw2
    else:
        tf = s.tf if s.kind is SectionKind.I else s.t
        tw = s.tw if s.kind is SectionKind.I else s.t
        names = ("flange", "web") if s.kind is SectionKind.I else ("wall_x", "wall_y")
        in_flange = np.abs(xy[:, 0]) > s.d / 2 - tf
        sign_x = np.where(xy[:, 0] >= 0, "+", "-")
        sign_y = np.where(xy[:, 1] >= 0, "+", "-")
        for i in range(len(xy)):
            if in_flange[i]:
                wall[i], station[i], thick[i] = names[0] + sign_x[i], xy[i, 1], tf
            elif s.kind is SectionKind.I:
                wall[i], station[i], thick[i] = "web", xy[i, 0], tw
            else:
                wall[i], station[i], thick[i] = names[1] + sign_y[i], xy[i, 0], tw
    area = mesh.weld_quad_area
    out = []
    for name in sorted(set(wall)):
        sel = wall == name
        bins = np.round(station[sel] / step).astype(int)
        for b in np.unique(bins):
            k = np.nonzero(sel)[0][bins == b]
            a = area[k].sum()
            length = a / thick[k[0]]
            fz = (sq[k, 2] * area[k]).sum() / length
            fx = (sq[k, 5] * area[k]).sum() / length
            fy = (sq[k, 4] * area[k]).sum() / length
            c = (mesh.weld_quad_xy[k] * area[k, None]).sum(axis=0) / a
            out.append(WeldPoint(name, float(c[0]), float(c[1]), float(thick[k[0]]),
                                 float(fz), float(np.hypot(fx, fy))))
    return out


def stiffener_weld_forces(model: BasePlateModel, mesh: Mesh, stress_ids: np.ndarray,
                           stress: np.ndarray) -> list[WeldPoint]:
    """Forces per unit length in the welds of each stiffener.

    ``base k``: along the weld to the base plate, from the stresses of the first
    level above the plate. ``vertical k``: along the weld to the column, from the
    stresses one element away from the column face, level by level.
    """
    if not len(mesh.stiffener_quads):
        return []
    top = int(max(stress_ids.max(), mesh.stiffener_quads.max(),
                  max(r.max() for r in mesh.stiffener_root_nodes if r.size)))
    table = np.zeros((top + 1, 6))
    table[stress_ids] = stress
    out: list[WeldPoint] = []
    step = 1.5 * (mesh.settings.size_wall or mesh.settings.size_fine or 10.0)
    for k, sf in enumerate(model.stiffeners):
        ts = sf.thickness
        sel = np.nonzero(mesh.stiffener_quad_index == k)[0]
        if len(sel):
            sq = table[mesh.stiffener_quads[sel]].mean(axis=1)
            xy = mesh.stiffener_quad_xy[sel]
            area = mesh.stiffener_quad_area[sel]
            r = (xy - np.array(sf.origin)) @ np.array(sf.direction)
            bins = np.floor(r / step).astype(int)
            for b in np.unique(bins):
                i = bins == b
                length = area[i].sum() / ts
                fz = (sq[i, 2] * area[i]).sum() / length
                fx = (sq[i, 5] * area[i]).sum() / length
                fy = (sq[i, 4] * area[i]).sum() / length
                c = (xy[i] * area[i, None]).sum(axis=0) / area[i].sum()
                out.append(WeldPoint(f"base {k + 1}", float(c[0]), float(c[1]), ts, float(fz),
                                     float(np.hypot(fx, fy))))
        roots = mesh.stiffener_root_nodes[k] if k < len(mesh.stiffener_root_nodes) else None
        if roots is not None and roots.size:
            d = np.array([sf.direction[0], sf.direction[1], 0.0])
            for m in range(1, roots.shape[0]):
                sxx, syy, szz, sxy, syz, szx = table[roots[m]].mean(axis=0)
                tensor = np.array([[sxx, sxy, szx], [sxy, syy, syz], [szx, syz, szz]])
                traction = tensor @ d
                normal = float(traction @ d)
                shear = float(np.linalg.norm(traction - normal * d))
                out.append(WeldPoint(f"vertical {k + 1}", float(sf.origin[0]),
                                     float(sf.origin[1]), ts, normal * ts, shear * ts))
    return out


@dataclass
class Results:
    load: str
    converged: bool
    load_fraction: float
    """Fraction of the moments and shears reached (1.0 when the analysis completed)."""
    applied: dict[str, float]
    anchors: list[AnchorForce]
    anchor_tension_total: float
    bearing_force: float
    """Compression resultant on the concrete, from the reactions of the block [N]."""
    bearing_centroid: tuple[float, float]
    friction: tuple[float, float]
    """Shear (x, y) the plate transfers to the concrete by friction [N]."""
    bearing_pressure_max: float
    bearing_pressure_mean: float
    """Compression resultant divided by the area in contact [MPa]."""
    bearing_area: float
    bearing_length_x: float
    """Extent of the contact zone measured along x from the compressed edge [mm]."""
    plate_von_mises_max: float
    plate_peeq_max: float
    plate_peeq_element: float
    """Largest element-mean equivalent plastic strain in the plate (less mesh sensitive)."""
    column_von_mises_max: float
    column_peeq_max: float
    column_top_displacement: tuple[float, float, float]
    equilibrium_error: float
    """|bearing − ΣT − P| / max(|P|, bearing) (vertical equilibrium)."""
    moment_error: float
    """Relative error of the moment about y from anchors and bearing."""
    lug_shear: tuple[float, float] = (0.0, 0.0)
    """Shear (x, y) the plate transfers to the concrete through the shear lug [N]."""
    weld: list[WeldPoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    """Notes from the pre-analysis diagnostics (see openfemconex.diagnostics)."""
    stiffener_weld: list[WeldPoint] = field(default_factory=list)
    stiffener_von_mises_max: float = 0.0
    stiffener_peeq_element: float = 0.0
    mesh: dict[str, int] = field(default_factory=dict)
    solver: dict[str, float] = field(default_factory=dict)
    far_bearing_force: float = 0.0
    """Compression of the far plate on the far face of the block [N] (with a far plate)."""
    far_bearing_centroid: tuple[float, float] = (0.0, 0.0)
    far_pressure_max: float = 0.0
    far_von_mises_max: float = 0.0
    far_peeq_element: float = 0.0
    far_weld: list[WeldPoint] = field(default_factory=list)
    """Weld of the opposite column (with one)."""
    far_column_top_displacement: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Of the opposite column, in global axes."""
    flange_von_mises_max: float = 0.0
    """Of the column flanges, when the block is a steel column (moment end plate)."""
    flange_peeq_element: float = 0.0
    column_von_mises: dict[str, float] = field(default_factory=dict)
    """Of a steel column: largest von Mises stress of each of its regions (``flange``,
    ``web``, ``continuity``, ``doubler``)."""
    column_peeq_element: dict[str, float] = field(default_factory=dict)
    """Of a steel column: largest element-mean PEEQ of each of its regions."""

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))


def summarize(base: str | Path, model: BasePlateModel, mesh: Mesh, numbering: InpNumbering,
              loads: Loads, *, converged: bool = True,
              fractions: tuple[float, float] = (1.0, 1.0),
              seconds: float = 0.0) -> Results:
    base = Path(base)
    dat = read_dat(base.with_suffix(".dat"))
    frd = read_frd(base.with_suffix(".frd"))

    rf = dat["forces/ANCHORGND"]
    u = dat["displacements/ANCHORREF"]
    ub = dat.get("displacements/ANCHORBASE", {})
    uc = dat.get("displacements/ANCHORCONC", {})
    k_lat = numbering.lateral_stiffness
    anchors = []
    if model.free_nuts:
        # the rod ends are free: its force from the law and the elongation
        from openfemconex.inp import anchor_stiffness, rod_force

        ks = anchor_stiffness(model)
        ug = dat["displacements/ANCHORGND"]
    for i, (a, g, r) in enumerate(zip(model.anchors, numbering.anchor_ground,
                                      numbering.anchor_ref)):
        if model.free_nuts:
            tension = rod_force(model, ks, float(u[r][2] - ug[g][2]))
        else:
            # The reaction at the fixed end is opposite to the force the rod applies to it.
            tension = -rf[g][2]
        vx = vy = 0.0
        if numbering.anchor_base:
            # shear on the plate: the lateral spring resists its slip over the concrete
            slip = ub[numbering.anchor_base[i]] - uc[numbering.anchor_concrete[i]]
            vx, vy = -k_lat * float(slip[0]), -k_lat * float(slip[1])
        anchors.append(AnchorForce(a.x, a.y, tension=tension, Vx=vx, Vy=vy,
                                   uplift=float(u[r][2])))
    T = sum(a.tension for a in anchors)
    lug_shear = (0.0, 0.0)
    if numbering.lug_nodes:
        ul = dat["displacements/LUGNODES"]
        slip = ul[numbering.lug_nodes[0]] - ul[numbering.lug_nodes[1]]
        active = {"strong": (True, False), "weak": (False, True),
                  "both": (True, True)}[model.lug.direction]
        lug_shear = tuple(-numbering.lug_stiffness * float(slip[i]) if active[i] else 0.0
                          for i in (0, 1))
    # Compression on the concrete and its line of action, from the reactions at the
    # fixed base of the block taken to the contact plane (z = 0).
    base = dat["forces/FLANGEHELD" if model.flange is not None else "forces/CONCBOT"]
    bid = np.fromiter(base, dtype=int)
    brf = np.array([base[i] for i in bid])
    bxyz = mesh.nodes[bid - 1]
    C = float(brf[:, 2].sum())
    # moment about y of the block reactions, about the plate centre at z = 0
    M_base = float((bxyz[:, 0] * brf[:, 2] - bxyz[:, 2] * brf[:, 0]).sum())
    if C > 0:
        centroid = (float((bxyz[:, 0] * brf[:, 2] - bxyz[:, 2] * brf[:, 0]).sum() / C),
                    float((bxyz[:, 1] * brf[:, 2] - bxyz[:, 2] * brf[:, 1]).sum() / C))
    else:
        centroid = (0.0, 0.0)

    # Contact pressure on the plate bottom (slave surface of the pair).
    ids, cv = frd["CONTACT"]
    press = np.zeros(max(int(ids.max()), len(mesh.nodes)) + 1)
    press[ids] = cv[:, 3]
    pb = mesh.plate_bottom_nodes
    p = press[pb]
    area = mesh.plate_bottom_area
    xy = mesh.nodes[pb - 1, :2]
    far: dict = {}
    if model.free_nuts:
        # the block is not held under the plate: the compression comes from the contact
        # pressure
        forces = p * area
        C = float(forces.sum())
        M_base = float((xy[:, 0] * forces).sum())
        centroid = ((float((xy[:, 0] * forces).sum() / C), float((xy[:, 1] * forces).sum() / C))
                    if C > 0 else (0.0, 0.0))
        brf = np.zeros((1, 3))
    if model.two_faces:
        fp = press[mesh.far_top_nodes] * mesh.far_top_area
        fxy = mesh.nodes[mesh.far_top_nodes - 1, :2]
        Cf = float(fp.sum())
        far = {"far_bearing_force": Cf,
               "far_bearing_centroid": ((float((fxy[:, 0] * fp).sum() / Cf),
                                         float((fxy[:, 1] * fp).sum() / Cf)) if Cf > 0
                                        else (0.0, 0.0)),
               "far_pressure_max": float(press[mesh.far_top_nodes].max(initial=0.0))}
    in_contact = p > max(1e-3, 0.01 * p.max(initial=0.0))
    A = float(area[in_contact].sum())
    if in_contact.any():
        side = 1.0 if centroid[0] >= 0 else -1.0
        xs = xy[in_contact, 0] * side
        Y = float(model.N / 2 - xs.min())
    else:
        Y = 0.0

    sid, sv = frd["STRESS"]
    vm = von_mises(sv)
    pid, pv = frd["PE"]
    solid_s, solid_p = sid <= len(mesh.nodes), pid <= len(mesh.nodes)
    sid, sv, vm, pid, pv = sid[solid_s], sv[solid_s], vm[solid_s], pid[solid_p], pv[solid_p]
    plate_s, plate_p = sid <= mesh.plate_node_count, pid <= mesh.plate_node_count
    col_s = (sid > mesh.plate_node_count) & (sid <= mesh.plate_node_count
                                             + _column_node_count(mesh))
    col_p = (pid > mesh.plate_node_count) & (pid <= mesh.plate_node_count
                                             + _column_node_count(mesh))
    # Skip the column top, where the rigid body introduces the load.
    ztop = mesh.nodes[:, 2].max()
    col_s &= mesh.nodes[sid - 1, 2] < ztop - 0.25 * model.Lc
    col_p &= mesh.nodes[pid - 1, 2] < ztop - 0.25 * model.Lc

    peeq = np.zeros(len(mesh.nodes) + 1)
    peeq[pid] = pv[:, 0]
    peeq_element = float(peeq[mesh.parts["PLATE"]].mean(axis=1).max())
    weld = weld_forces(model, mesh, sid, sv)
    stiff = {}
    if "STIFFENER" in mesh.parts:
        conn = mesh.parts["STIFFENER"]
        vm_table = np.zeros(len(mesh.nodes) + 1)
        vm_table[sid] = vm
        stiff = {"stiffener_weld": stiffener_weld_forces(model, mesh, sid, sv),
                 "stiffener_von_mises_max": float(vm_table[conn].max()),
                 "stiffener_peeq_element": float(peeq[conn].mean(axis=1).max())}
    far_part = "FARPLATE" if "FARPLATE" in mesh.parts else "PLATE2"
    if far_part in mesh.parts:
        conn = mesh.parts[far_part]
        vm_table = np.zeros(len(mesh.nodes) + 1)
        vm_table[sid] = vm
        far.update(far_von_mises_max=float(vm_table[conn].max()),
                   far_peeq_element=float(peeq[conn].mean(axis=1).max()))
    if model.flange is not None:
        conn = mesh.parts["CONCRETE"]
        vm_table = np.zeros(len(mesh.nodes) + 1)
        vm_table[sid] = vm
        regions = mesh.column_regions or {"flange": np.arange(len(conn))}
        vms = {k: float(vm_table[conn[i]].max()) for k, i in regions.items() if len(i)}
        peeqs = {k: float(peeq[conn[i]].mean(axis=1).max()) for k, i in regions.items()
                 if len(i)}
        far.update(flange_von_mises_max=vms.get("flange", 0.0),
                   flange_peeq_element=peeqs.get("flange", 0.0),
                   column_von_mises=vms, column_peeq_element=peeqs)
    if model.opposite is not None:
        # the stresses of the mirror image: the normal one keeps its sign
        far["far_weld"] = weld_forces(model.opposite, mesh.opposite, sid, sv)
        t2 = dat["displacements/LOADNODES2"][numbering.load_ref2]
        far["far_column_top_displacement"] = (float(t2[0]), float(t2[1]), float(t2[2]))

    top = dat["displacements/LOADNODES"][numbering.load_ref]
    P = loads.P * fractions[0]
    My = loads.My * fractions[1]
    scale = max(abs(P), abs(C), 1.0)
    # Moment about y at the plate base: compression at +x gives a positive moment.
    # The rod shears act at the contact plane, so they add no moment about it.
    M_fem = M_base - sum(a.x * a.tension for a in anchors)
    # couple of the lug shear over the depth it is transferred
    M_fem -= lug_shear[0] * numbering.lug_offset
    # relative to the moment itself, to the moment of the shear at the column top, or
    # to 1 % of P·N when there is (almost) none
    V_lever = math.hypot(loads.Vx, loads.Vy) * fractions[1] * (model.tp + model.Lc)
    m_scale = max(abs(My), abs(M_fem), V_lever, 0.01 * max(abs(P), abs(C), T) * model.N, 1.0)
    return Results(
        load=loads.name, converged=converged, load_fraction=fractions[1],
        applied={"P": loads.P, "Vx": loads.Vx, "Vy": loads.Vy, "Mx": loads.Mx, "My": loads.My},
        anchors=anchors, anchor_tension_total=float(T),
        bearing_force=C,
        # shear through the contact: what reaches the block minus what the rods bring
        friction=(float(-brf[:, 0].sum() + sum(a.Vx for a in anchors) + lug_shear[0]),
                  float(-brf[:, 1].sum() + sum(a.Vy for a in anchors) + lug_shear[1])),
        lug_shear=(float(lug_shear[0]), float(lug_shear[1])),
        bearing_centroid=(float(centroid[0]), float(centroid[1])),
        bearing_pressure_max=float(p.max(initial=0.0)),
        bearing_pressure_mean=C / A if A else 0.0, bearing_area=A, bearing_length_x=Y,
        plate_von_mises_max=float(vm[plate_s].max()), plate_peeq_max=float(pv[plate_p].max()),
        plate_peeq_element=peeq_element, weld=weld, **stiff, **far,
        column_von_mises_max=float(vm[col_s].max()), column_peeq_max=float(pv[col_p].max()),
        column_top_displacement=(float(top[0]), float(top[1]), float(top[2])),
        equilibrium_error=abs(C - T - P) / scale,
        moment_error=abs(M_fem - My) / m_scale,
        mesh={"nodes": len(mesh.nodes), "elements": mesh.element_count,
              **{k.lower(): len(v) for k, v in mesh.parts.items()}},
        solver={"seconds": seconds},
    )


def _column_node_count(mesh: Mesh) -> int:
    return int(mesh.column_top_nodes.max()) - mesh.plate_node_count
