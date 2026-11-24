# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Readers for the CalculiX .dat and .frd files and the result summary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from openfemconex.inp import InpNumbering
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel, Loads, SectionKind

__all__ = ["AnchorForce", "Results", "WeldPoint", "read_dat", "read_frd", "summarize",
           "von_mises", "weld_forces"]


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
    step = 1.5 * (mesh.settings.size_fine or 10.0)
    wall = np.empty(len(xy), dtype=object)
    station = np.zeros(len(xy))
    thick = np.zeros(len(xy))
    if s.kind is SectionKind.HSS_ROUND:
        r = s.d / 2 - s.t / 2
        wall[:] = "pipe"
        station = np.arctan2(xy[:, 1], xy[:, 0]) * r
        thick[:] = s.t
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
    weld: list[WeldPoint] = field(default_factory=list)
    mesh: dict[str, int] = field(default_factory=dict)
    solver: dict[str, float] = field(default_factory=dict)

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
    for i, (a, g, r) in enumerate(zip(model.anchors, numbering.anchor_ground,
                                      numbering.anchor_ref)):
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
    # Compression on the concrete and its line of action, from the reactions at the
    # fixed base of the block taken to the contact plane (z = 0).
    base = dat["forces/CONCBOT"]
    bid = np.fromiter(base, dtype=int)
    brf = np.array([base[i] for i in bid])
    bxyz = mesh.nodes[bid - 1]
    C = float(brf[:, 2].sum())
    if C > 0:
        centroid = (float((bxyz[:, 0] * brf[:, 2] - bxyz[:, 2] * brf[:, 0]).sum() / C),
                    float((bxyz[:, 1] * brf[:, 2] - bxyz[:, 2] * brf[:, 1]).sum() / C))
    else:
        centroid = (0.0, 0.0)

    # Contact pressure on the plate bottom (slave surface of the pair).
    ids, cv = frd["CONTACT"]
    press = np.zeros(int(ids.max()) + 1)
    press[ids] = cv[:, 3]
    pb = mesh.plate_bottom_nodes
    p = press[pb]
    area = mesh.plate_bottom_area
    xy = mesh.nodes[pb - 1, :2]
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

    top = dat["displacements/LOADNODES"][numbering.load_ref]
    P = loads.P * fractions[0]
    My = loads.My * fractions[1]
    scale = max(abs(P), abs(C), 1.0)
    # Moment about y at the plate base: compression at +x gives a positive moment.
    # The rod shears act at the contact plane, so they add no moment about it.
    M_fem = centroid[0] * C - sum(a.x * a.tension for a in anchors)
    m_scale = max(abs(My), abs(M_fem), 1.0)
    return Results(
        load=loads.name, converged=converged, load_fraction=fractions[1],
        applied={"P": loads.P, "Vx": loads.Vx, "Vy": loads.Vy, "Mx": loads.Mx, "My": loads.My},
        anchors=anchors, anchor_tension_total=float(T),
        bearing_force=C,
        # shear through the contact: what reaches the block minus what the rods bring
        friction=(float(-brf[:, 0].sum() + sum(a.Vx for a in anchors)),
                  float(-brf[:, 1].sum() + sum(a.Vy for a in anchors))),
        bearing_centroid=(float(centroid[0]), float(centroid[1])),
        bearing_pressure_max=float(p.max(initial=0.0)),
        bearing_pressure_mean=C / A if A else 0.0, bearing_area=A, bearing_length_x=Y,
        plate_von_mises_max=float(vm[plate_s].max()), plate_peeq_max=float(pv[plate_p].max()),
        plate_peeq_element=peeq_element, weld=weld,
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
