# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""The open project and what has been computed for it."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from openconex.io.project import FORMAT_VERSION, Project
from PySide6.QtCore import QObject, Signal

from openfemconex.extras import KEY, Extras, parse_extras, split_data
from openfemconex.i18n import tr
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.report import ComboReport
from openfemconex.study import Settings, Study

TEMPLATE: dict[str, Any] = {
    "format_version": FORMAT_VERSION,
    "info": {"name": "Placa base", "number": "", "client": "", "engineer": "", "revision": "0",
             "language": "es", "units": "SI_kN_m"},
    "base_plate": {
        "column": "W12X96", "N": "560 mm", "B": "560 mm", "tp": "50 mm",
        "plate_grade": "ASTM A36", "fc": "28 MPa", "A2_over_A1": 1.0, "grout": "40 mm",
        "rod_diameter": "1.5 in", "rod_grade": "ASTM F1554 Gr. 36", "rods_per_side": 2,
        "f": "220 mm", "rod_spacing": "300 mm", "hef": "450 mm", "cracked": True,
    },
    "cases": [
        {"name": "D", "type": "D", "P": "450 kN", "M": "110 kN*m"},
        {"name": "L", "type": "L", "P": "700 kN", "M": "170 kN*m"},
    ],
    "combinations": {"methods": ["LRFD"]},
}


class ProjectState(QObject):
    """Project data as an editable JSON tree, validated through OpenConex on every change."""

    changed = Signal()
    """The project data changed (and was validated again)."""
    results_changed = Signal()
    loaded = Signal()
    """Another project replaced the current one."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.path: Path | None = None
        self.dirty = False
        self.data: dict[str, Any] = {}
        self.project: Project | None = None
        self.extras = Extras()
        self.model: BasePlateModel | None = None
        self.error = ""
        self.mesh: Mesh | None = None
        self.reports: dict[str, ComboReport] = {}
        self.stale = False
        """True when the results no longer match the project data."""
        self._tmp: tempfile.TemporaryDirectory | None = None
        self.new()

    # ---------------------------------------------------------------- files
    def new(self) -> None:
        self._replace(copy.deepcopy(TEMPLATE), None)

    def open(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if "base_plate" not in data:
            raise ValueError("el archivo no contiene una placa base")
        self._replace(data, Path(path))

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("falta el nombre del archivo")
        target.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        self.path, self.dirty = target, False
        self.changed.emit()
        return target

    def _replace(self, data: dict[str, Any], path: Path | None) -> None:
        self.data, self.path, self.dirty = data, path, False
        self.mesh, self.reports, self.stale = None, {}, False
        self._validate()
        self.loaded.emit()
        self.changed.emit()
        self.results_changed.emit()

    # ---------------------------------------------------------------- editing
    def get(self, section: str, key: str, default: Any = "") -> Any:
        return self.data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set one field; an empty text removes it so the OpenConex default applies."""
        block = self.data.setdefault(section, {})
        if value == "" or value is None:
            if key not in block:
                return
            del block[key]
        elif block.get(key) == value:
            return
        else:
            block[key] = value
        self._touch()

    def ext(self, block: str) -> Any:
        """One block of the OpenFEMConex additions (``anchors``, ``pedestal``, ``stiffeners``)."""
        return self.data.get(KEY, {}).get(block)

    def set_ext(self, block: str, value: Any) -> None:
        """Replace a block of the additions; None removes it."""
        ext = self.data.setdefault(KEY, {})
        if value is None:
            if block not in ext:
                return
            del ext[block]
        elif ext.get(block) == value:
            return
        else:
            ext[block] = copy.deepcopy(value)
        if not ext:
            del self.data[KEY]
        self._touch()

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        if cases != self.data.get("cases"):
            self.data["cases"] = cases
            self._touch()

    def set_methods(self, methods: list[str]) -> None:
        combos = self.data.setdefault("combinations", {})
        if combos.get("methods") != methods:
            combos["methods"] = methods
            self._touch()

    def set_setting(self, name: str, value: Any) -> None:
        if getattr(self.settings, name) != value:
            setattr(self.settings, name, value)
            self.mark_stale(mesh=name in ("size", "layers"))
            self.changed.emit()

    def _touch(self) -> None:
        self.dirty = True
        self._validate()
        self.mark_stale(mesh=True)
        self.changed.emit()

    def mark_stale(self, mesh: bool = False) -> None:
        if mesh:
            self.mesh = None
        if self.reports and not self.stale:
            self.stale = True
            self.results_changed.emit()

    def _validate(self) -> None:
        try:
            base, ext = split_data(self.data)
            self.project = Project.model_validate(base)
            self.extras = parse_extras(self.project, ext)
            self.model = self.study().model()
            self.project.load_combinations()
            self.error = ""
        except Exception as exc:
            self.project = self.model = None
            first = str(exc).strip().splitlines()
            self.error = " ".join(line.strip() for line in first[:3]) or type(exc).__name__

    # ---------------------------------------------------------------- analysis
    def study(self) -> Study:
        if self.project is None:
            raise ValueError(self.error or tr("proyecto no válido"))
        return Study(self.project, self.settings, self.extras)

    @property
    def valid(self) -> bool:
        return self.project is not None and self.model is not None

    def output_dir(self) -> Path:
        if self.path is not None:
            return self.path.with_name(self.path.stem + "_fem")
        if self._tmp is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="openfemconex_")
        return Path(self._tmp.name)

    def set_report(self, name: str, report: ComboReport) -> None:
        self.reports[name] = report
        self.stale = False
        self.results_changed.emit()

    def clear_results(self) -> None:
        self.reports, self.stale = {}, False
        self.results_changed.emit()

    def title(self) -> str:
        name = self.path.name if self.path else tr("sin título")
        return f"{name}{' *' if self.dirty else ''} — OpenFEMConex"
