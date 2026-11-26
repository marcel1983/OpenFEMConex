# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""The open project and what has been computed for it."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from openconex.core.materials import BOLTS, STEELS
from openconex.io.project import FORMAT_VERSION, Project, WSectionInput
from PySide6.QtCore import QObject, Signal

from openfemconex import __version__
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

    # ---------------------------------------------------------------- libraries
    def steel_names(self) -> list[str]:
        """Built-in steels and the ones defined in the project."""
        return list(STEELS) + [m["name"] for m in self.data.get("materials", [])
                               if m.get("name") not in STEELS]

    def rod_names(self) -> list[str]:
        own = [b["name"] for b in self.data.get("bolts", []) if b.get("name") not in BOLTS]
        return [n for n in BOLTS if "F1554" in n] + own

    def custom_sections(self) -> dict[str, dict[str, Any]]:
        """Custom W-shapes of the project by label."""
        out = {}
        for sec in self.data.get("sections", []):
            if sec.get("type") == "W":
                try:
                    out[WSectionInput.model_validate(sec).label()] = sec
                except Exception:  # an invalid entry is reported by the validation
                    continue
        return out

    def column_label(self) -> str:
        col = self.get("base_plate", "column", "")
        if isinstance(col, dict):
            try:
                return WSectionInput.model_validate(col).label()
            except Exception:
                return str(col.get("name", ""))
        return str(col)

    def column_grade(self) -> str:
        col = self.get("base_plate", "column", "")
        if isinstance(col, dict):
            return str(col.get("grade", ""))
        return str(self.get("base_plate", "column_grade", "ASTM A992"))

    def set_column(self, label: str, grade: str | None = None) -> None:
        """Column by label: a custom section of the project or the AISC catalog."""
        grade = grade or self.column_grade()
        custom = self.custom_sections().get(label)
        bp = self.data.setdefault("base_plate", {})
        if custom is not None:
            bp["column"] = {**copy.deepcopy(custom), "grade": grade}
        else:
            bp["column"] = label
            bp["column_grade"] = grade
        self._touch()

    def set_library(self, materials: list[dict[str, Any]], laws: dict[str, Any],
                    bolts: list[dict[str, Any]], renames: dict[str, str]) -> None:
        """Replace the project steels, their FEM laws and the rod grades.

        ``renames`` maps old to new material names; references follow the new name.
        """
        self._rename_grades(renames)
        for key, value in (("materials", materials), ("bolts", bolts)):
            if value:
                self.data[key] = copy.deepcopy(value)
            else:
                self.data.pop(key, None)
        ext = self.data.setdefault(KEY, {})
        if laws:
            ext["materials"] = copy.deepcopy(laws)
        else:
            ext.pop("materials", None)
        if not ext:
            del self.data[KEY]
        self._touch()

    def _rename_grades(self, renames: dict[str, str]) -> None:
        if not renames:
            return
        bp = self.data.get("base_plate", {})
        blocks = [bp, bp.get("shear_lug") or {}, self.data.get(KEY, {}).get("stiffeners") or {}]
        if isinstance(bp.get("column"), dict):
            blocks.append(bp["column"])
        blocks += self.data.get("sections", [])
        for block in blocks:
            for key in ("grade", "column_grade", "plate_grade", "rod_grade"):
                if block.get(key) in renames:
                    block[key] = renames[block[key]]

    def set_sections(self, sections: list[dict[str, Any]], renames: dict[str, str],
                     use: str | None = None) -> None:
        """Replace the custom sections; ``use`` makes one of them the column."""
        if sections:
            self.data["sections"] = copy.deepcopy(sections)
        else:
            self.data.pop("sections", None)
        labels = {WSectionInput.model_validate(s).label(): s for s in sections
                  if s.get("type") == "W"}
        bp = self.data.setdefault("base_plate", {})
        current = self.column_label()
        target = use or renames.get(current, current)
        if target in labels and (use or isinstance(bp.get("column"), dict)):
            bp["column"] = copy.deepcopy(labels[target])
        cross = (self.data.get(KEY) or {}).get("column")
        if cross and cross.get("cross") in renames:
            cross["cross"] = renames[cross["cross"]]
        self._touch()

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        if cases != self.data.get("cases"):
            self.data["cases"] = cases
            self._touch()

    def set_combinations(self, include_code: bool, custom: list[dict[str, Any]]) -> None:
        """Generated ASCE 7 combinations on or off, and the user's own combinations."""
        combos = self.data.setdefault("combinations", {})
        before = copy.deepcopy(combos)
        combos["include_code"] = include_code
        if include_code:
            del combos["include_code"]  # the default
        if custom:
            combos["custom"] = copy.deepcopy(custom)
        else:
            combos.pop("custom", None)
        if combos != before:
            self._touch()

    def set_methods(self, methods: list[str]) -> None:
        combos = self.data.setdefault("combinations", {})
        if combos.get("methods") != methods:
            combos["methods"] = methods
            self._touch()

    def set_setting(self, name: str, value: Any) -> None:
        if getattr(self.settings, name) != value:
            setattr(self.settings, name, value)
            self.mark_stale(mesh=name in ("size", "layers", "fast"))
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
        return f"{name}{' *' if self.dirty else ''} — OpenFEMConex {__version__}"
