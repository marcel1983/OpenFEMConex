# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""The Loads tab shared by every connection type.

Load cases (service loads with a type D, L, W, E...) in an editable table, the
ASCE 7-22 combinations generated from them, the user's own combinations (edited in
:class:`~openfemconex.gui.combos.CombinationsDialog`) and the list of combinations to
solve. What changes between connection types is their forces and where the data is
kept, which a :class:`LoadsSource` gives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openconex.core.loads import LoadCombination, LoadType
from openconex.units import Kind, UnitSystem, format_value
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openfemconex.i18n import tr
from openfemconex.load_cases import code_combinations, combination_text
from openfemconex.units import with_unit

__all__ = ["CaseColumn", "LoadsEditor", "LoadsSource"]


@dataclass(frozen=True)
class CaseColumn:
    key: str
    label: str
    kind: Kind = Kind.FORCE


class LoadsSource:
    """Where the cases and combinations of one connection live (override)."""

    columns: tuple[CaseColumn, ...] = ()
    """Forces of a case, after its name and type."""
    methods: tuple[str, ...] = ("LRFD", "ASD")
    """Design methods the checks of the connection support."""
    result_heads: tuple[str, ...] = ()
    """Columns of the factored forces in the list of combinations."""

    @property
    def units(self) -> UnitSystem:
        raise NotImplementedError

    def cases(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def options(self) -> dict[str, Any]:
        raise NotImplementedError

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def set_combinations(self, include_code: bool, custom: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def set_methods(self, methods: list[str]) -> None:
        raise NotImplementedError

    def set_option(self, key: str, value: Any) -> None:
        """One option of the combinations (``SDS``, ``rho``, ``omega0``); None removes it."""
        raise NotImplementedError

    def combinations(self) -> list[tuple[LoadCombination, list[tuple[float, Kind]]]]:
        """Every combination with its factored forces (``result_heads``); raises when
        the data are not valid."""
        raise NotImplementedError

    def hidden(self) -> set[str]:
        """Case columns not used now (e.g. the opposite beam when there is none)."""
        return set()

    def code_combinations(self) -> list[LoadCombination]:
        """The generated ASCE 7 combinations, whether included or not."""
        return code_combinations(self.cases(), self.options(), self.methods)


class LoadsEditor(QWidget):
    """Cases table, combination options and the list of combinations to solve."""

    selection_changed = Signal()

    def __init__(self, source: LoadsSource, intro: str = "") -> None:
        super().__init__()
        self.source = source
        self._loading = False
        layout = QVBoxLayout(self)
        if intro:
            text = QLabel(tr(intro))
            text.setWordWrap(True)
            layout.addWidget(text)
        layout.addWidget(QLabel(tr("<b>Casos de carga</b> (valores con unidad, p. ej. 100 kip)")))
        self.columns = (("name", "Caso"), ("type", "Tipo"),
                        *[(c.key, c.label) for c in source.columns])
        self.cases = QTableWidget(0, len(self.columns))
        self.cases.setHorizontalHeaderLabels([tr(label) for _, label in self.columns])
        self.cases.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cases.itemChanged.connect(self._cases_edited)
        layout.addWidget(self.cases, 2)
        row = QHBoxLayout()
        add, remove = QPushButton(tr("Agregar caso")), QPushButton(tr("Quitar caso"))
        add.clicked.connect(self._add_case)
        remove.clicked.connect(self._remove_case)
        for w in (add, remove):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(QLabel(tr("Combinaciones ASCE 7:")))
        self.method_boxes: dict[str, QCheckBox] = {}
        for m in ("LRFD", "ASD"):
            box = QCheckBox(m)
            box.setVisible(m in source.methods)
            box.setEnabled(len(source.methods) > 1)
            box.toggled.connect(self._methods_edited)
            row.addWidget(box)
            self.method_boxes[m] = box
        self.lrfd, self.asd = self.method_boxes["LRFD"], self.method_boxes["ASD"]
        # seismic combinations of ASCE 7 §2.3.6 / §2.4.5: they need S_DS (and E cases)
        self.seismic: dict[str, QLineEdit] = {}
        for key, label, tip in (
                ("SDS", "S<sub>DS</sub>", "Aceleración espectral de diseño de periodo corto: "
                 "con casos E genera las combinaciones sísmicas de ASCE 7 (vacío: sin ellas)"),
                ("rho", "ρ", "Factor de redundancia (1.0 por omisión)"),
                ("omega0", "Ω<sub>0</sub>", "Sobrerresistencia: agrega las combinaciones "
                 "con Ω0 (vacío: sin ellas)")):
            row.addWidget(QLabel(label))
            edit = QLineEdit()
            edit.setMaximumWidth(56)
            edit.setToolTip(tr(tip))
            edit.editingFinished.connect(lambda k=key: self._seismic_edited(k))
            row.addWidget(edit)
            self.seismic[key] = edit
        self.edit_combos = QPushButton(tr("Editar combinaciones…"))
        self.edit_combos.setToolTip(tr("Combinaciones propias con sus factores, o copia "
                                       "editable de las de ASCE 7"))
        self.edit_combos.clicked.connect(self.open_editor)
        row.addWidget(self.edit_combos)
        layout.addLayout(row)
        layout.addWidget(QLabel(tr("<b>Combinaciones</b> (marque las que se resuelven)")))
        self.combos = QTableWidget(0, 3 + len(source.result_heads))
        self.combos.setHorizontalHeaderLabels([tr("Combinación"), tr("Método"), tr("Factores"),
                                               *[tr(h) for h in source.result_heads]])
        self.combos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.combos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.combos.itemChanged.connect(lambda _: self.selection_changed.emit())
        layout.addWidget(self.combos, 3)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #d03040;")
        layout.addWidget(self.error)
        self._unchecked: set[str] = set()
        self._editing = False

    def refresh(self) -> None:
        if not self._editing:  # the table is not rebuilt under the cell being edited
            self.load_cases()
        self.load_combos()

    # -- cases
    def load_cases(self) -> None:
        self._loading = True
        try:
            cases = self.source.cases()
            # replaced cell widgets are only deleted later by the event loop: hide them
            # now so that they never show behind the new ones
            for old in self.cases.findChildren(QComboBox):
                old.hide()
                old.deleteLater()
            self.cases.setRowCount(0)
            self.cases.setRowCount(len(cases))
            for r, case in enumerate(cases):
                for c, (key, _) in enumerate(self.columns):
                    if key == "type":
                        box = QComboBox()
                        box.addItems([t.value for t in LoadType])
                        box.setCurrentText(str(case.get("type", "D")))
                        box.currentTextChanged.connect(lambda _: self._cases_edited())
                        self.cases.setCellWidget(r, c, box)
                    else:
                        value = case.get(key, "")
                        self.cases.setItem(r, c, QTableWidgetItem(
                            "" if value is None else str(value)))
            hidden = self.source.hidden()
            for c, (key, _) in enumerate(self.columns):
                self.cases.setColumnHidden(c, key in hidden)
            opts = self.source.options()
            methods = opts.get("methods", ["LRFD"])
            for m, box in self.method_boxes.items():
                box.setChecked(m in methods)
            for key, edit in self.seismic.items():
                value = opts.get(key)
                edit.setText("" if value is None or (key == "rho" and value == 1.0)
                             else f"{value:g}")
            self._unchecked.clear()
        finally:
            self._loading = False

    def _kind(self, key: str) -> Kind:
        return next(c.kind for c in self.source.columns if c.key == key)

    def _read_cases(self) -> list[dict[str, Any]]:
        out = []
        old = self.source.cases()
        for r in range(self.cases.rowCount()):
            # keep what the table does not show (e.g. the forces of a hidden column)
            case: dict[str, Any] = dict(old[r]) if r < len(old) else {}
            for c, (key, _) in enumerate(self.columns):
                if key == "type":
                    case[key] = self.cases.cellWidget(r, c).currentText()
                    continue
                if self.cases.isColumnHidden(c):
                    continue
                item = self.cases.item(r, c)
                text = item.text().strip() if item else ""
                if text:
                    case[key] = (text if key == "name"
                                 else with_unit(text, self._kind(key), self.source.units))
                else:
                    case.pop(key, None)
            out.append(case)
        return out

    def _cases_edited(self, *_: object) -> None:
        if not self._loading:
            self._editing = True
            try:
                self.source.set_cases(self._read_cases())
            finally:
                self._editing = False

    def _add_case(self) -> None:
        cases = self._read_cases()
        names = {c.get("name") for c in cases}
        name = next(n for n in ("D", "L", "W", "S", "E", *[f"C{i}" for i in range(1, 99)])
                    if n not in names)
        kind = name if name in {t.value for t in LoadType} else "L"
        u = self.source.units
        new = {"name": name, "type": kind}
        for col in self.source.columns[:2]:
            new[col.key] = f"0 {u.force if col.kind is Kind.FORCE else u.moment}"
        cases.append(new)
        self.source.set_cases(cases)
        self.load_cases()

    def _remove_case(self) -> None:
        row = self.cases.currentRow()
        cases = self._read_cases()
        if 0 <= row < len(cases) and len(cases) > 1:
            del cases[row]
            self.source.set_cases(cases)
            self.load_cases()

    def _methods_edited(self) -> None:
        if not self._loading:
            methods = [m for m, box in self.method_boxes.items()
                       if box.isChecked() and m in self.source.methods]
            self.source.set_methods(methods or [self.source.methods[0]])

    def _seismic_edited(self, key: str) -> None:
        if self._loading:
            return
        text = self.seismic[key].text().strip().replace(",", ".")
        try:
            value = float(text) if text else None
        except ValueError:
            self.error.setText(tr("valor no válido: {text}", text=text))
            return
        if key == "rho" and value == 1.0:
            value = None
        if self.source.options().get(key) != value:
            self.source.set_option(key, value)

    # -- combinations
    def load_combos(self) -> None:
        for r in range(self.combos.rowCount()):
            item = self.combos.item(r, 0)
            if item is not None and item.checkState() == Qt.CheckState.Unchecked:
                self._unchecked.add(item.text())
            elif item is not None:
                self._unchecked.discard(item.text())
        self.combos.blockSignals(True)
        try:
            self.combos.setRowCount(0)
            try:
                rows = self.source.combinations()
                self.error.setText("")
            except Exception as exc:  # the cases are being edited
                self.error.setText(str(exc).strip().splitlines()[0] if str(exc).strip()
                                   else type(exc).__name__)
                return
            units = self.source.units
            for combo, values in rows:
                r = self.combos.rowCount()
                self.combos.insertRow(r)
                name = QTableWidgetItem(combo.name)
                name.setFlags(name.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                name.setCheckState(Qt.CheckState.Unchecked if combo.name in self._unchecked
                                   else Qt.CheckState.Checked)
                name.setToolTip(combo.source)
                factors = QTableWidgetItem(combination_text(combo.factors))
                factors.setToolTip(combo.source)
                cells = [name, QTableWidgetItem(combo.method.value), factors,
                         *[QTableWidgetItem(format_value(v, kind, units)) for v, kind in values]]
                for c, cell in enumerate(cells):
                    self.combos.setItem(r, c, cell)
        finally:
            self.combos.blockSignals(False)
        self.selection_changed.emit()

    def open_editor(self) -> None:
        from openfemconex.gui.combos import CombinationsDialog

        CombinationsDialog(self.source, self).exec()
        self.load_combos()

    def selected(self) -> list[str]:
        return [self.combos.item(r, 0).text() for r in range(self.combos.rowCount())
                if self.combos.item(r, 0).checkState() == Qt.CheckState.Checked]
