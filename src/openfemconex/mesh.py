# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Hexahedral mesh of the base plate model.

The plate plan (rectangle with anchor holes, plate-washer rings and the column
footprint) is meshed once in 2D with Gmsh using quadrilaterals. That quad mesh
is extruded here into hexahedra: through the plate thickness, and then only the
column footprint upwards along the column. Plate and column therefore share
the nodes on the welded footprint (conforming mesh). The concrete block is a
separate structured hexahedral grid below the plate, in contact with it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from openfemconex.model import BasePlateModel, MeshSettings, SectionKind

__all__ = ["Mesh", "MeshError", "build_mesh", "distorted_elements", "plan_mesh"]

# C3D8 faces (Abaqus/CalculiX numbering): S1 = nodes 1-2-3-4 (bottom), S2 = 5-8 (top).
FACE_BOTTOM = "S1"
FACE_TOP = "S2"


@dataclass
class PlanMesh:
    """2D quad mesh of the plate plan at z = 0."""

    xy: np.ndarray
    """(n, 2) node coordinates."""
    quads: np.ndarray
    """(m, 4) zero-based node indices, counter-clockwise seen from +z."""
    region: np.ndarray
    """(m,) region of each quad: -1 plate, -2 column footprint, k >= 0 washer ring of
    anchor k, -10 - k stiffener k."""


@dataclass
class Mesh:
    nodes: np.ndarray
    """(n, 3) coordinates; node id = row + 1."""
    parts: dict[str, np.ndarray]
    """Element connectivity (one-based node ids) of PLATE, COLUMN and CONCRETE."""
    first_element: dict[str, int]
    """Id of the first element of each part (consecutive numbering)."""
    plate_bottom_elements: np.ndarray
    concrete_top_elements: np.ndarray
    washer_nodes: list[np.ndarray]
    """Plate top nodes under each plate washer."""
    washer_weights: list[np.ndarray]
    """Normalised tributary area of each washer node (sums to 1 per anchor)."""
    column_top_nodes: np.ndarray
    concrete_bottom_nodes: np.ndarray
    plate_bottom_nodes: np.ndarray
    plate_bottom_area: np.ndarray
    """Tributary area of each plate bottom node (same order as ``plate_bottom_nodes``)."""
    footprint_nodes: np.ndarray
    plate_node_count: int = 0
    """Plate nodes are ids 1..plate_node_count."""
    weld_quads: np.ndarray = field(default_factory=lambda: np.zeros((0, 4), dtype=int))
    """Column footprint quads as node ids of the first column level above the plate."""
    weld_quad_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    weld_quad_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    stiffener_quads: np.ndarray = field(default_factory=lambda: np.zeros((0, 4), dtype=int))
    """Stiffener plan quads as node ids of the first level above the plate."""
    stiffener_quad_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    stiffener_quad_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    stiffener_quad_index: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    """Stiffener each of those quads belongs to."""
    stiffener_root_nodes: list[np.ndarray] = field(default_factory=list)
    """Per stiffener, (levels, n) node ids one element away from the column face."""
    stiffener_levels: np.ndarray = field(default_factory=lambda: np.zeros(0))
    """Heights above the plate of the stiffener levels at the column face [mm]."""
    """Nodes on the plate top shared with the column (welded footprint)."""
    settings: MeshSettings = field(default_factory=MeshSettings)
    far_top_elements: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    """Far plate elements whose top face (z = -H) touches the block."""
    concrete_bottom_elements: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    """Block elements whose bottom face is the far face (z = -H)."""
    far_washer_nodes: list[np.ndarray] = field(default_factory=list)
    """Far plate outer-face nodes under the nut of each rod."""
    far_washer_weights: list[np.ndarray] = field(default_factory=list)
    far_top_nodes: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    far_top_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    concrete_end_nodes: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    """Block nodes at its ends x = ±N/2, held when there is a far plate."""
    opposite: Mesh | None = None
    """With an opposite column: its plate and column, in this mesh's numbering (parts
    PLATE, COLUMN, STIFFENER mean PLATE2, COLUMN2, STIFFENER2 here)."""

    @property
    def element_count(self) -> int:
        return sum(len(c) for c in self.parts.values())

    def element_ids(self, part: str) -> np.ndarray:
        return self.first_element[part] + np.arange(len(self.parts[part]))


def _section_surfaces(occ, model: BasePlateModel) -> list[tuple[int, int]]:
    s, x0, y0 = model.section, model.ex, model.ey
    if s.kind is SectionKind.I:
        d2, b2, tf, tw2 = s.d / 2, s.bf / 2, s.tf, s.tw / 2
        pts = [(-d2, -b2), (-d2, b2), (-d2 + tf, b2), (-d2 + tf, tw2), (d2 - tf, tw2),
               (d2 - tf, b2), (d2, b2), (d2, -b2), (d2 - tf, -b2), (d2 - tf, -tw2),
               (-d2 + tf, -tw2), (-d2 + tf, -b2)]
        ptags = [occ.addPoint(x0 + x, y0 + y, 0) for x, y in pts]
        lines = [occ.addLine(ptags[i], ptags[(i + 1) % len(ptags)]) for i in range(len(ptags))]
        return [(2, occ.addPlaneSurface([occ.addCurveLoop(lines)]))]
    if s.kind is SectionKind.CRUCIFORM:
        rects = [(2, occ.addRectangle(x0 + a, y0 + b, 0, c - a, e - b))
                 for a, b, c, e in s.boxes()]
        fused, _ = occ.fuse(rects[:1], rects[1:])
        return fused
    if s.kind is SectionKind.HSS_RECT:
        outer = occ.addRectangle(x0 - s.d / 2, y0 - s.bf / 2, 0, s.d, s.bf)
        inner = occ.addRectangle(x0 - s.d / 2 + s.t, y0 - s.bf / 2 + s.t, 0,
                                 s.d - 2 * s.t, s.bf - 2 * s.t)
    else:
        r = s.d / 2
        outer = occ.addDisk(x0, y0, 0, r, r)
        inner = occ.addDisk(x0, y0, 0, r - s.t, r - s.t)
    out, _ = occ.cut([(2, outer)], [(2, inner)])
    return out


def plan_mesh(model: BasePlateModel, settings: MeshSettings) -> PlanMesh:
    """Quad mesh of the plate plan with Gmsh (OpenCASCADE kernel)."""
    import gmsh

    st = settings
    gmsh.initialize(interruptible=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("plan")
        occ = gmsh.model.occ
        rect = occ.addRectangle(-model.N / 2, -model.B / 2, 0, model.N, model.B)
        section = _section_surfaces(occ, model)
        rw, rh = model.anchor.washer / 2, model.anchor.hole / 2
        rings, cutters = [], []
        for a in model.anchors:
            w = occ.addDisk(a.x, a.y, 0, rw, rw)
            h = occ.addDisk(a.x, a.y, 0, rh, rh)
            ring, _ = occ.cut([(2, w)], [(2, h)])
            rings.append(ring[0])
            cutters.append((2, occ.addDisk(a.x, a.y, 0, rw, rw)))
        body, _ = occ.cut([(2, rect)], cutters)
        stiffs = []
        for sf in model.stiffeners:
            pts = [occ.addPoint(x, y, 0) for x, y in sf.corners()]
            loop = occ.addCurveLoop([occ.addLine(pts[i], pts[(i + 1) % 4]) for i in range(4)])
            stiffs.append((2, occ.addPlaneSurface([loop])))
        tools = section + rings + stiffs
        _, omap = occ.fragment(body, tools)
        occ.synchronize()

        n_body, n_sec, n_ring = len(body), len(section), len(rings)
        column_surfs = {t for m in omap[n_body:n_body + n_sec] for _, t in m}
        ring_surfs: dict[int, int] = {}
        for k, m in enumerate(omap[n_body + n_sec:n_body + n_sec + n_ring]):
            for _, t in m:
                ring_surfs[t] = k
        # the part of each stiffener rectangle inside the column wall stays column
        stiff_surfs: dict[int, int] = {}
        for k, m in enumerate(omap[n_body + n_sec + n_ring:]):
            for _, t in m:
                if t not in column_surfs:
                    stiff_surfs[t] = k

        curves = gmsh.model.getBoundary(
            [(2, t) for t in column_surfs | set(ring_surfs) | set(stiff_surfs)],
            combined=False, oriented=False)
        fld = gmsh.model.mesh.field
        f1 = fld.add("Distance")
        fld.setNumbers(f1, "CurvesList", sorted({abs(t) for _, t in curves}))
        fld.setNumber(f1, "Sampling", 200)
        f2 = fld.add("Threshold")
        fld.setNumber(f2, "InField", f1)
        fld.setNumber(f2, "SizeMin", st.size_fine)
        fld.setNumber(f2, "SizeMax", st.size_coarse)
        fld.setNumber(f2, "DistMin", st.size_fine)
        fld.setNumber(f2, "DistMax", 0.25 * max(model.N, model.B))
        # Column walls and stiffeners: size limited by their thickness (wall_size).
        wall = st.wall_size(model)
        walls = gmsh.model.getBoundary([(2, t) for t in column_surfs | set(stiff_surfs)],
                                       combined=False, oriented=False)
        f3 = fld.add("Distance")
        fld.setNumbers(f3, "CurvesList", sorted({abs(t) for _, t in walls}))
        fld.setNumber(f3, "Sampling", 400)
        f4 = fld.add("Threshold")
        fld.setNumber(f4, "InField", f3)
        fld.setNumber(f4, "SizeMin", wall)
        fld.setNumber(f4, "SizeMax", st.size_coarse)
        fld.setNumber(f4, "DistMin", wall)
        fld.setNumber(f4, "DistMax", max(0.25 * max(model.N, model.B), 4 * st.size_fine))
        f5 = fld.add("Min")
        fld.setNumbers(f5, "FieldsList", [f2, f4])
        fld.setAsBackgroundMesh(f5)
        for opt, val in (("Mesh.MeshSizeFromPoints", 0), ("Mesh.MeshSizeFromCurvature", 0),
                         ("Mesh.MeshSizeExtendFromBoundary", 0), ("Mesh.Algorithm", 8),
                         ("Mesh.RecombineAll", 1), ("Mesh.RecombinationAlgorithm", 1)):
            gmsh.option.setNumber(opt, val)
        gmsh.model.mesh.generate(2)
        if _has_triangles():
            # Fall back to the all-quad subdivision, with doubled sizes to keep the count.
            gmsh.model.mesh.clear()
            fld.setNumber(f2, "SizeMin", 2 * st.size_fine)
            fld.setNumber(f2, "SizeMax", 2 * st.size_coarse)
            fld.setNumber(f4, "SizeMin", 2 * wall)
            fld.setNumber(f4, "SizeMax", 2 * st.size_coarse)
            gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 1)
            gmsh.model.mesh.generate(2)

        tags, coords, _ = gmsh.model.mesh.getNodes()
        xyz = coords.reshape(-1, 3)
        index = {int(t): i for i, t in enumerate(tags)}
        quads, region = [], []
        for _, s in gmsh.model.getEntities(2):
            etypes, _, enodes = gmsh.model.mesh.getElements(2, s)
            reg = (-2 if s in column_surfs else -10 - stiff_surfs[s] if s in stiff_surfs
                   else ring_surfs.get(s, -1))
            for et, nodes in zip(etypes, enodes):
                if et != 3:
                    raise RuntimeError("the plan mesh is not all quadrilaterals")
                for q in nodes.reshape(-1, 4):
                    quads.append([index[int(n)] for n in q])
                    region.append(reg)
    finally:
        gmsh.finalize()

    used = np.unique(np.asarray(quads))
    remap = -np.ones(len(xyz), dtype=int)
    remap[used] = np.arange(len(used))
    q = remap[np.asarray(quads)]
    xy = xyz[used, :2]
    # orient counter-clockwise seen from +z
    p = xy[q]
    area2 = ((p[:, 0, 0] * p[:, 1, 1] - p[:, 1, 0] * p[:, 0, 1])
             + (p[:, 1, 0] * p[:, 2, 1] - p[:, 2, 0] * p[:, 1, 1])
             + (p[:, 2, 0] * p[:, 3, 1] - p[:, 3, 0] * p[:, 2, 1])
             + (p[:, 3, 0] * p[:, 0, 1] - p[:, 0, 0] * p[:, 3, 1]))
    flip = area2 < 0
    q[flip] = q[flip][:, ::-1]
    return PlanMesh(xy=xy, quads=q, region=np.asarray(region))


def _has_triangles() -> bool:
    import gmsh

    etypes, _, _ = gmsh.model.mesh.getElements(2)
    return 2 in list(etypes)


def _quad_areas(xy: np.ndarray, quads: np.ndarray) -> np.ndarray:
    p = xy[quads]
    d1 = p[:, 2] - p[:, 0]
    d2 = p[:, 3] - p[:, 1]
    return 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])


def _graded(H: float, n: int, power: float = 1.6) -> np.ndarray:
    """Ascending z from -H to 0, finer near the top."""
    s = np.linspace(0.0, 1.0, n + 1)
    return -H * (1.0 - s) ** power


def _graded_both(H: float, n: int) -> np.ndarray:
    """Ascending z from -H to 0, finer near both faces (cosine spacing)."""
    s = np.linspace(0.0, 1.0, n + 1)
    return -H * (0.5 + 0.5 * np.cos(np.pi * s))


def _lines(lo: float, hi: float, size: float, breaks: list[float]) -> np.ndarray:
    """Grid lines from lo to hi about ``size`` apart that also pass through ``breaks``."""
    pts = sorted({lo, hi, *[b for b in breaks if lo < b < hi]})
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:], strict=True):
        n = max(1, math.ceil((b - a) / size - 1e-9))
        out += list(np.linspace(a, b, n + 1)[1:])
    out = np.array(out)
    keep = np.concatenate([[True], np.diff(out) > 0.2 * size])
    keep[-1] = True
    return out[keep]


def _far_plate(model: BasePlateModel, st: MeshSettings, first_node: int):
    """Structured hexahedral grid of the far plate under the block, z from -H - t to -H.

    Returns its nodes, elements (one-based ids from ``first_node``), the elements of its
    top layer, the outer-face nodes and weights under each nut, and the top-face nodes
    with their tributary areas.
    """
    f, H = model.far, model.concrete.H
    r = model.anchor.washer / 2
    size = min(st.size_coarse, max(model.anchor.washer / 2, 5.0))
    gx = _lines(-f.height / 2, f.height / 2, size,
                [v for a in model.anchors for v in (a.x - r, a.x + r)])
    gy = _lines(-f.width / 2, f.width / 2, size,
                [v for a in model.anchors for v in (a.y - r, a.y + r)])
    layers = max(2, st.plate_layers - 1)
    gz = np.linspace(-H - f.thickness, -H, layers + 1)
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    nodes = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    ny, nz = len(gy), len(gz)

    def fid(i, j, k):
        return first_node + (np.asarray(i) * ny + np.asarray(j)) * nz + np.asarray(k)

    I, J, K = np.meshgrid(np.arange(len(gx) - 1), np.arange(ny - 1), np.arange(nz - 1),
                          indexing="ij")
    I, J, K = I.ravel(), J.ravel(), K.ravel()
    elems = np.column_stack([
        fid(I, J, K), fid(I + 1, J, K), fid(I + 1, J + 1, K), fid(I, J + 1, K),
        fid(I, J, K + 1), fid(I + 1, J, K + 1), fid(I + 1, J + 1, K + 1),
        fid(I, J + 1, K + 1)])
    top = np.nonzero(K == nz - 2)[0]
    # tributary areas of a face grid
    wx = np.zeros(len(gx))
    wx[:-1] += np.diff(gx) / 2
    wx[1:] += np.diff(gx) / 2
    wy = np.zeros(ny)
    wy[:-1] += np.diff(gy) / 2
    wy[1:] += np.diff(gy) / 2
    gi, gj = np.meshgrid(np.arange(len(gx)), np.arange(ny), indexing="ij")
    gi, gj = gi.ravel(), gj.ravel()
    area = wx[gi] * wy[gj]
    washer_nodes, washer_weights = [], []
    for a in model.anchors:
        sel = (np.abs(gx[gi] - a.x) <= r + 1e-6) & (np.abs(gy[gj] - a.y) <= r + 1e-6)
        if sel.sum() < 4:
            sel = np.argsort(np.hypot(gx[gi] - a.x, gy[gj] - a.y))[:4]
        washer_nodes.append(fid(gi[sel], gj[sel], 0))
        w = area[sel]
        washer_weights.append(w / w.sum())
    return (nodes, elems, top, washer_nodes, washer_weights, fid(gi, gj, nz - 1), area)


def _column_levels(length: float, first: float, growth: float = 1.3,
                   max_ratio: float = 5.0, uniform: float = 0.0) -> np.ndarray:
    """Heights along the column: fine next to the plate, growing geometrically.

    The first ``uniform`` millimetres (the stiffener height) are divided evenly so
    that a level falls exactly at that height.
    """
    sizes, h, total = [], first, 0.0
    if uniform > 0:
        n = max(3, math.ceil(uniform / first))
        sizes = [uniform / n] * n
        total, h = uniform, uniform / n
    while total + h < length:
        sizes.append(h)
        total += h
        h = min(h * growth, first * max_ratio)
    sizes.append(length - total)
    if len(sizes) > 1 and sizes[-1] < 0.5 * sizes[-2]:
        sizes[-2] += sizes.pop()
    return np.concatenate([[0.0], np.cumsum(sizes)])


# Natural coordinates of the C3D8 nodes.
_XI = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=float)


def distorted_elements(nodes: np.ndarray, conn: np.ndarray) -> np.ndarray:
    """Rows of ``conn`` whose Jacobian is not positive at some integration point.

    CalculiX evaluates it at the 2 × 2 × 2 Gauss points and stops with "nonpositive
    jacobian determinant" when one is negative (an inverted or folded hexahedron).
    """
    p = nodes[conn - 1]  # (m, 8, 3)
    bad = np.zeros(len(conn), dtype=bool)
    g = 1 / np.sqrt(3)
    for gp in np.array(np.meshgrid([-g, g], [-g, g], [-g, g])).T.reshape(-1, 3):
        # derivatives of the trilinear shape functions at the point, (8, 3)
        f = 1 + _XI * gp
        dn = np.column_stack([_XI[:, 0] * f[:, 1] * f[:, 2], _XI[:, 1] * f[:, 0] * f[:, 2],
                              _XI[:, 2] * f[:, 0] * f[:, 1]]) / 8
        jac = np.einsum("ki,mkj->mij", dn, p)  # (m, 3, 3)
        bad |= np.linalg.det(jac) <= 0
    return np.nonzero(bad)[0]


class MeshError(ValueError):
    pass


def build_mesh(model: BasePlateModel, settings: MeshSettings | None = None) -> Mesh:
    """Hexahedral mesh of the model.

    A fast mesh that comes out with distorted elements is built again finer, down to
    the normal automatic sizes.
    """
    settings = settings or MeshSettings()
    if not settings.fast:
        return _build_mesh(model, settings)
    for factor in (settings.fast_factor, 1.5, 1.25):
        try:
            return _build_mesh(model, replace(settings, fast_factor=factor))
        except MeshError:
            continue
    return _build_mesh(model, replace(settings, fast=False))


def _build_mesh(model: BasePlateModel, settings: MeshSettings) -> Mesh:
    model.validate()
    st = settings.resolved(model)
    plan = plan_mesh(model, st)
    xy, quads = plan.xy, plan.quads
    n2 = len(xy)

    # --- plate: layers through the thickness --------------------------------
    L = st.plate_layers
    zp = np.linspace(0.0, model.tp, L + 1)
    nodes = [np.column_stack([xy, np.full(n2, z)]) for z in zp]

    def pid(k: int, i):
        return k * n2 + np.asarray(i) + 1

    plate = np.vstack([np.hstack([pid(k, quads), pid(k + 1, quads)]) for k in range(L)])

    # --- column and stiffeners: footprint quads extruded upwards ----------------
    # The stiffeners share the column levels up to their height; away from the column
    # face each level is scaled down to follow the sloping top edge.
    cq = quads[plan.region == -2]
    cnodes = np.unique(cq)
    stiff_sel = plan.region <= -10
    sq = quads[stiff_sel]
    sq_index = -10 - plan.region[stiff_sel]
    hs = max((sf.height for sf in model.stiffeners), default=0.0) if len(sq) else 0.0
    zc = model.tp + _column_levels(model.Lc, st.column_size, uniform=hs)
    Mc = len(zc) - 1
    Ms = int(np.argmin(np.abs(zc - model.tp - hs))) if hs else 0
    snodes = np.setdiff1d(np.unique(sq), cnodes) if len(sq) else np.zeros(0, dtype=int)
    scale = np.ones(n2)
    for k, sf in enumerate(model.stiffeners):
        mine = np.setdiff1d(np.unique(sq[sq_index == k]), cnodes)
        r = (xy[mine] - np.array(sf.origin)) @ np.array(sf.direction)
        scale[mine] = sf.height_at(r) / hs
    ids = np.zeros((Mc + 1, n2), dtype=int)
    ids[0] = pid(L, np.arange(n2))
    next_id = (L + 1) * n2 + 1
    for m in range(1, Mc + 1):
        members = np.concatenate([cnodes, snodes]) if m <= Ms else cnodes
        ids[m, members] = next_id + np.arange(len(members))
        next_id += len(members)
        z = model.tp + (zc[m] - model.tp) * scale[members]
        nodes.append(np.column_stack([xy[members], z]))

    def cid(m: int, i):
        return ids[m, np.asarray(i)]

    column = np.vstack([np.hstack([cid(m, cq), cid(m + 1, cq)]) for m in range(Mc)])
    column_top = cid(Mc, cnodes)
    stiffener = (np.vstack([np.hstack([cid(m, sq), cid(m + 1, sq)]) for m in range(Ms)])
                 if Ms else np.zeros((0, 8), dtype=int))
    in_column = np.zeros(n2, dtype=bool)
    in_column[cnodes] = True
    roots = []
    for k in range(len(model.stiffeners) if Ms else 0):
        mine = sq[sq_index == k]
        touching = mine[in_column[mine].sum(axis=1) >= 2]
        far = np.setdiff1d(np.unique(touching), cnodes)
        roots.append(ids[:Ms + 1][:, far])

    # --- concrete: structured grid -------------------------------------------
    c = model.concrete
    base_k = next_id - 1
    nx = max(4, math.ceil(c.N / st.concrete_size))
    ny = max(4, math.ceil(c.B / st.concrete_size))
    gx = np.linspace(-c.N / 2, c.N / 2, nx + 1)
    gy = np.linspace(-c.B / 2, c.B / 2, ny + 1)
    gz = (_graded_both(c.H, st.concrete_layers + 4) if model.two_faces
          else _graded(c.H, st.concrete_layers))
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    nodes.append(np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]))

    def kid(i, j, k):
        return base_k + (np.asarray(i) * (ny + 1) + np.asarray(j)) * (len(gz)) + np.asarray(k) + 1

    I, J, K = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(len(gz) - 1), indexing="ij")
    I, J, K = I.ravel(), J.ravel(), K.ravel()
    concrete = np.column_stack([
        kid(I, J, K), kid(I + 1, J, K), kid(I + 1, J + 1, K), kid(I, J + 1, K),
        kid(I, J, K + 1), kid(I + 1, J, K + 1), kid(I + 1, J + 1, K + 1), kid(I, J + 1, K + 1)])
    conc_top = np.nonzero(K == len(gz) - 2)[0]
    gi, gj = np.meshgrid(np.arange(nx + 1), np.arange(ny + 1), indexing="ij")
    conc_bottom = kid(gi.ravel(), gj.ravel(), 0)
    far = None
    first_far = base_k + 1 + len(X.ravel())
    if model.far is not None:
        far = _far_plate(model, st, first_far)
        nodes.append(far[0])
    sub = sub_nodes = None
    if model.opposite is not None:
        # the opposite plate and column: meshed as a base plate of their own and
        # mirrored about the far face (z -> -H - z)
        sub = _build_mesh(replace(model.opposite, concrete=c, anchors=model.anchors),
                          settings)
        ns = int(sub.parts["CONCRETE"].min()) - 1
        sub_nodes = sub.nodes[:ns].copy()
        sub_nodes[:, 2] = -c.H - sub_nodes[:, 2]
        nodes.append(sub_nodes)
    if model.two_faces:
        ei, ej, ek = np.meshgrid([0, nx], np.arange(ny + 1), np.arange(len(gz)), indexing="ij")
        conc_ends = kid(ei.ravel(), ej.ravel(), ek.ravel())

    # --- numbering and sets ------------------------------------------------------
    parts = {"PLATE": plate, "COLUMN": column}
    if len(stiffener):
        parts["STIFFENER"] = stiffener
    parts["CONCRETE"] = concrete
    if far is not None:
        parts["FARPLATE"] = far[1]
    off = first_far - 1  # node offset of the opposite column
    if sub is not None:
        # mirrored: the top and bottom faces of each hexahedron swap
        for name in ("PLATE", "COLUMN", "STIFFENER"):
            if name in sub.parts:
                parts[name + "2"] = sub.parts[name][:, [4, 5, 6, 7, 0, 1, 2, 3]] + off
    first, count = {}, 1
    for name, conn in parts.items():
        first[name] = count
        count += len(conn)
    m2 = len(quads)
    area = _quad_areas(xy, quads)
    washer_nodes, washer_weights = [], []
    for k in range(len(model.anchors)):
        sel = plan.region == k
        w = np.zeros(n2)
        for j in range(4):
            np.add.at(w, quads[sel, j], area[sel] / 4)
        idx = np.nonzero(w)[0]
        washer_nodes.append(pid(L, idx))
        washer_weights.append(w[idx] / w[idx].sum())
    nodal_area = np.zeros(n2)
    for j in range(4):
        np.add.at(nodal_area, quads[:, j], area / 4)

    all_nodes = np.vstack(nodes)
    opposite = None
    if sub is not None:
        def e_off(name):
            return first[name + "2"] - sub.first_element[name]

        opposite = replace(
            sub, nodes=all_nodes,
            parts={k: parts[k + "2"] for k in ("PLATE", "COLUMN", "STIFFENER")
                   if k + "2" in parts},
            first_element={k: first[k + "2"] for k in ("PLATE", "COLUMN", "STIFFENER")
                           if k + "2" in parts},
            plate_bottom_elements=sub.plate_bottom_elements + e_off("PLATE"),
            concrete_top_elements=np.zeros(0, dtype=int),
            washer_nodes=[w + off for w in sub.washer_nodes],
            column_top_nodes=sub.column_top_nodes + off,
            concrete_bottom_nodes=np.zeros(0, dtype=int),
            plate_bottom_nodes=sub.plate_bottom_nodes + off,
            footprint_nodes=sub.footprint_nodes + off,
            weld_quads=sub.weld_quads + off,
            stiffener_quads=sub.stiffener_quads + off if len(sub.stiffener_quads)
            else sub.stiffener_quads,
            stiffener_root_nodes=[r + off for r in sub.stiffener_root_nodes])
    for name, conn in parts.items():
        bad = distorted_elements(all_nodes, conn)
        if len(bad):
            raise MeshError(
                f"the mesh has {len(bad)} distorted elements in {name} (first: element "
                f"{first[name] + int(bad[0])}); use a smaller mesh size")
    return Mesh(
        nodes=all_nodes,
        parts=parts,
        first_element=first,
        plate_bottom_elements=first["PLATE"] + np.arange(m2),
        concrete_top_elements=first["CONCRETE"] + conc_top,
        washer_nodes=washer_nodes,
        washer_weights=washer_weights,
        column_top_nodes=column_top,
        concrete_bottom_nodes=conc_bottom,
        plate_bottom_nodes=np.arange(n2) + 1,
        plate_bottom_area=nodal_area,
        footprint_nodes=pid(L, cnodes),
        plate_node_count=(L + 1) * n2,
        weld_quads=cid(1, cq), weld_quad_xy=xy[cq].mean(axis=1),
        weld_quad_area=area[plan.region == -2],
        stiffener_quads=cid(1, sq) if Ms else np.zeros((0, 4), dtype=int),
        stiffener_quad_xy=xy[sq].mean(axis=1) if Ms else np.zeros((0, 2)),
        stiffener_quad_area=area[stiff_sel], stiffener_quad_index=sq_index,
        stiffener_root_nodes=roots, stiffener_levels=zc[:Ms + 1] - model.tp,
        settings=st,
        **({} if far is None else dict(
            far_top_elements=first["FARPLATE"] + far[2],
            far_washer_nodes=far[3], far_washer_weights=far[4], far_top_nodes=far[5],
            far_top_area=far[6])),
        # the opposite plate: its face on the block is the top face of its first layer
        # (mirrored) and its nuts are on its outer face, where its washers were
        **({} if opposite is None else dict(
            far_top_elements=opposite.plate_bottom_elements,
            far_washer_nodes=opposite.washer_nodes, far_washer_weights=sub.washer_weights,
            far_top_nodes=opposite.plate_bottom_nodes, far_top_area=sub.plate_bottom_area,
            opposite=opposite)),
        **({} if not model.two_faces else dict(
            concrete_bottom_elements=first["CONCRETE"] + np.nonzero(K == 0)[0],
            concrete_end_nodes=conc_ends)),
    )
