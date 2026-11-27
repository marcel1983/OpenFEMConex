# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Export mesh and nodal results to a VTK unstructured grid (.vtu, ASCII).

The file opens in ParaView and with ``pyvista.read``; the C3D8 node order is
the VTK hexahedron order.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from openfemconex.mesh import Mesh
from openfemconex.results import read_frd, von_mises

__all__ = ["PARTS", "write_vtu"]

PARTS = {"PLATE": 1, "COLUMN": 2, "CONCRETE": 3, "STIFFENER": 4}
# the far plate and the opposite column are shown as plate, column and stiffener
PARTS.update(FARPLATE=1, PLATE2=1, COLUMN2=2, STIFFENER2=4)


def _array(f, name: str, data: np.ndarray, fmt: str, kind: str = "Float64",
           components: int | None = None) -> None:
    data = np.atleast_2d(data.T).T
    f.write(f'<DataArray type="{kind}" Name="{name}" '
            f'NumberOfComponents="{components or data.shape[1]}" '
            'format="ascii">\n')
    np.savetxt(f, data, fmt=fmt)
    f.write("</DataArray>\n")


def write_vtu(path: str | Path, mesh: Mesh, frd: str | Path | None = None) -> Path:
    path = Path(path)
    n = len(mesh.nodes)
    conn = np.vstack(list(mesh.parts.values())) - 1
    part = np.concatenate([np.full(len(c), PARTS[k]) for k, c in mesh.parts.items()])
    fields: dict[str, np.ndarray] = {}
    if frd is not None:
        blocks = read_frd(frd)

        def nodal(name: str) -> np.ndarray:
            ids, values = blocks[name]
            keep = ids <= n
            out = np.zeros((n, values.shape[1]))
            out[ids[keep] - 1] = values[keep]
            return out

        fields["U"] = nodal("DISP")[:, :3]
        fields["von_Mises"] = von_mises(nodal("STRESS"))
        fields["PEEQ"] = nodal("PE")[:, 0]
        fields["CPRESS"] = nodal("CONTACT")[:, 3]
    with path.open("w") as f:
        f.write('<?xml version="1.0"?>\n<VTKFile type="UnstructuredGrid" version="0.1" '
                'byte_order="LittleEndian">\n<UnstructuredGrid>\n')
        f.write(f'<Piece NumberOfPoints="{n}" NumberOfCells="{len(conn)}">\n<Points>\n')
        _array(f, "Points", mesh.nodes, "%.6f")
        f.write("</Points>\n<Cells>\n")
        _array(f, "connectivity", conn, "%d", "Int64", components=1)
        _array(f, "offsets", 8 * np.arange(1, len(conn) + 1), "%d", "Int64")
        _array(f, "types", np.full(len(conn), 12), "%d", "UInt8")
        f.write("</Cells>\n<CellData>\n")
        _array(f, "part", part, "%d", "Int32")
        f.write("</CellData>\n<PointData>\n")
        for name, data in fields.items():
            _array(f, name, data, "%.6e")
        f.write("</PointData>\n</Piece>\n</UnstructuredGrid>\n</VTKFile>\n")
    return path
