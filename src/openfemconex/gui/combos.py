# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Editor of the load combinations: generated ASCE 7 ones and the user's own."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openfemconex.gui.state import ProjectState
from openfemconex.i18n import tr

METHODS = ("LRFD", "ASD")


def combination_text(factors: dict[str, float]) -> str:
    """1.2D + 1.6L."""
    parts = []
    for name, f in factors.items():
        if f == 0:
            continue
        sign = "−" if f < 0 else "+"
        parts.append((sign, f"{abs(f):g}{name}" if abs(f) != 1 else name))
    if not parts:
        return "0"
    text = ("−" if parts[0][0] == "−" else "") + parts[0][1]
    return text + "".join(f" {s} {t}" for s, t in parts[1:])


class CombinationsDialog(QDialog):
    """Own combinations as a table of factors, one column per load case."""

    def __init__(self, state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Combinaciones de carga"))
        self.resize(900, 520)
        self.state = state
        self.cases = [c.get("name", "") for c in state.data.get("cases", [])]
        options = state.data.get("combinations", {})
        self.custom: list[dict[str, Any]] = copy.deepcopy(options.get("custom", []))
        layout = QVBoxLayout(self)
        note = QLabel(tr("Las combinaciones ASCE 7 se generan solas a partir de los tipos de "
                         "caso. Para cambiar sus factores, cópielas como combinaciones propias "
                         "y desmarque las generadas. Un factor negativo invierte el caso; una "
                         "celda vacía o 0 lo omite."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.include = QCheckBox(tr("Incluir las combinaciones generadas de ASCE 7"))
        self.include.setChecked(options.get("include_code", True))
        layout.addWidget(self.include)
        self.table = QTableWidget(0, 3 + len(self.cases))
        self.table.setHorizontalHeaderLabels(
            [tr("Nombre"), tr("Método"), *self.cases, tr("Combinación")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.table.columnCount() - 1,
                                    QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._changed)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot, tip in (
                ("Agregar", self._add, ""),
                ("Duplicar", self._duplicate, ""),
                ("Quitar", self._remove, ""),
                ("Subir", lambda: self._move(-1), ""),
                ("Bajar", lambda: self._move(1), ""),
                ("Copiar las de ASCE 7", self._copy_code,
                 "Agrega las combinaciones generadas como combinaciones propias editables")):
            b = QPushButton(tr(text))
            if tip:
                b.setToolTip(tr(tip))
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #d03040;")
        layout.addWidget(self.error)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self._loading = False
        self._fill()

    # -- table
    def _fill(self, select: int | None = None) -> None:
        self._loading = True
        try:
            for old in self.table.findChildren(QComboBox):
                old.hide()
                old.deleteLater()
            self.table.setRowCount(len(self.custom))
            for r, combo in enumerate(self.custom):
                self.table.setItem(r, 0, QTableWidgetItem(combo.get("name", "")))
                method = QComboBox()
                method.addItems(METHODS)
                method.setCurrentText(str(combo.get("method", "LRFD")))
                method.currentTextChanged.connect(lambda _=None: self._changed())
                self.table.setCellWidget(r, 1, method)
                factors = combo.get("factors", {})
                for c, case in enumerate(self.cases):
                    f = factors.get(case)
                    item = QTableWidgetItem("" if not f else f"{f:g}")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, 2 + c, item)
                text = QTableWidgetItem(combination_text(factors))
                text.setFlags(text.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, 2 + len(self.cases), text)
        finally:
            self._loading = False
        if select is not None and 0 <= select < self.table.rowCount():
            self.table.selectRow(select)

    def _read(self) -> list[dict[str, Any]]:
        out = []
        for r in range(self.table.rowCount()):
            base = self.custom[r] if r < len(self.custom) else {}
            combo = {k: v for k, v in base.items() if k not in ("name", "method", "factors")}
            name = self.table.item(r, 0)
            combo["name"] = name.text().strip() if name else ""
            combo["method"] = self.table.cellWidget(r, 1).currentText()
            factors = {}
            for c, case in enumerate(self.cases):
                item = self.table.item(r, 2 + c)
                text = item.text().strip().replace(",", ".") if item else ""
                if text:
                    try:
                        value = float(text)
                    except ValueError as exc:
                        raise ValueError(tr("factor no válido en {name}, caso {case}: {text}",
                                            name=combo["name"], case=case,
                                            text=text)) from exc
                    if value:
                        factors[case] = value
            combo["factors"] = factors
            out.append(combo)
        return out

    def _changed(self, *_: object) -> None:
        if self._loading:
            return
        try:
            self.custom = self._read()
            self.error.setText("")
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self._loading = True
        try:
            for r, combo in enumerate(self.custom):
                self.table.item(r, 2 + len(self.cases)).setText(
                    combination_text(combo["factors"]))
        finally:
            self._loading = False

    def _unique(self, base: str) -> str:
        names = {c.get("name") for c in self.custom}
        if self.include.isChecked() and self.state.project is not None:
            names |= {c.name for c in self.state.project.load_combinations()
                      if c.source != "custom"}
        k, name = 1, base
        while name in names:
            k += 1
            name = f"{base}-{k}"
        return name

    def _add(self) -> None:
        self._changed()
        first = self.cases[0] if self.cases else "D"
        self.custom.append({"name": self._unique(tr("Comb")), "method": "LRFD",
                            "factors": {first: 1.0}})
        self._fill(len(self.custom) - 1)

    def _duplicate(self) -> None:
        self._changed()
        r = self.table.currentRow()
        if 0 <= r < len(self.custom):
            new = copy.deepcopy(self.custom[r])
            new["name"] = self._unique(new["name"])
            self.custom.insert(r + 1, new)
            self._fill(r + 1)

    def _remove(self) -> None:
        self._changed()
        r = self.table.currentRow()
        if 0 <= r < len(self.custom):
            del self.custom[r]
            self._fill(min(r, len(self.custom) - 1))

    def _move(self, step: int) -> None:
        self._changed()
        r = self.table.currentRow()
        t = r + step
        if 0 <= r < len(self.custom) and 0 <= t < len(self.custom):
            self.custom[r], self.custom[t] = self.custom[t], self.custom[r]
            self._fill(t)

    def _copy_code(self) -> None:
        """The generated combinations as editable ones; the generated ones are then off."""
        self._changed()
        if self.state.project is None:
            return
        names = {c.get("name") for c in self.custom}
        for combo in self.state.project.load_combinations():
            if combo.source == "custom" or combo.name in names:
                continue
            entry = {"name": combo.name, "method": combo.method.value,
                     "factors": dict(combo.factors), "source": combo.source}
            if combo.seismic:
                entry["seismic"] = True
            if combo.overstrength:
                entry["overstrength"] = True
            if combo.allowable_increase != 1.0:
                entry["allowable_increase"] = combo.allowable_increase
            self.custom.append(entry)
        self.include.setChecked(False)
        self._fill()

    # -- accept
    def _accept(self) -> None:
        try:
            custom = self._read()
        except ValueError as exc:
            QMessageBox.warning(self, tr("Combinaciones de carga"), str(exc))
            return
        names = [c["name"] for c in custom]
        problem = ""
        if any(not n for n in names):
            problem = tr("Cada combinación necesita un nombre.")
        elif len(set(names)) != len(names):
            problem = tr("Hay combinaciones con el mismo nombre.")
        elif any(not c["factors"] for c in custom):
            problem = tr("Cada combinación necesita al menos un factor distinto de cero.")
        elif not custom and not self.include.isChecked():
            problem = tr("Sin combinaciones: incluya las de ASCE 7 o defina alguna propia.")
        if problem:
            QMessageBox.warning(self, tr("Combinaciones de carga"), problem)
            return
        self.state.set_combinations(self.include.isChecked(), custom)
        self.accept()
