# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Property panels: geometry forms, load cases, combinations and analysis settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openconex.core.loads import LoadType
from openconex.core.materials import BOLTS, STEELS
from openconex.core.shapes import aisc_shapes
from openconex.units import PRESETS, Kind, format_value
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openfemconex.gui.state import ProjectState

COLUMN_TYPES = ("W", "M", "S", "HP", "HSS", "PIPE")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"
    """text (quantity or free text), choice, int, float, bool."""
    options: tuple[str, ...] = ()
    tip: str = ""
    section: str = "base_plate"


def column_labels() -> tuple[str, ...]:
    db = aisc_shapes()
    out: list[str] = []
    for shape_type in COLUMN_TYPES:
        out += db.labels(shape_type)
    return tuple(out)


ROD_GRADES = tuple(n for n in BOLTS if "F1554" in n)

SECTIONS: dict[str, list[Field]] = {
    "Columna": [
        Field("column", "Perfil AISC", "choice", tip="W, M, S, HP, HSS y Pipe del catálogo AISC"),
        Field("column_grade", "Acero", "choice", tuple(STEELS)),
    ],
    "Placa": [
        Field("N", "Largo N (dirección del peralte)"),
        Field("B", "Ancho B"),
        Field("tp", "Espesor tp"),
        Field("plate_grade", "Acero", "choice", tuple(STEELS)),
    ],
    "Anclajes": [
        Field("rod_diameter", "Diámetro"),
        Field("rod_grade", "Grado", "choice", ROD_GRADES),
        Field("rods_per_side", "Anclajes por lado", "int"),
        Field("f", "Distancia f del eje a cada fila"),
        Field("rod_spacing", "Separación entre los extremos de la fila"),
        Field("hef", "Empotramiento hef"),
        Field("washer_thickness", "Arandelas soldadas, espesor",
              tip="Vacío: sin arandelas soldadas y el cortante va por fricción"),
    ],
    "Concreto": [
        Field("fc", "Resistencia f'c"),
        Field("A2_over_A1", "Relación A2/A1", "float"),
        Field("pedestal_N", "Pedestal, largo", tip="Vacío: concreto sin bordes cercanos"),
        Field("pedestal_B", "Pedestal, ancho"),
        Field("grout", "Espesor de mortero"),
        Field("cracked", "Concreto fisurado", "bool"),
        Field("friction_mu", "Fricción μ (verificación)", "float"),
    ],
    "Soldadura": [
        Field("flange_weld", "Tamaño del filete", tip="Vacío: filete mínimo de la Tabla J2.4"),
        Field("electrode", "Electrodo", "choice", ("E70XX", "E80XX")),
    ],
}


class FormPanel(QWidget):
    """A form bound to fields of the project; edits go to the state when committed."""

    def __init__(self, state: ProjectState, title: str, fields: list[Field]) -> None:
        super().__init__()
        self.state = state
        self.fields = fields
        self.widgets: dict[str, QWidget] = {}
        self._loading = False
        layout = QVBoxLayout(self)
        heading = QLabel(f"<b>{title}</b>")
        layout.addWidget(heading)
        form = QFormLayout()
        layout.addLayout(form)
        layout.addStretch(1)
        for field in fields:
            widget = self._make(field)
            widget.setToolTip(field.tip)
            self.widgets[field.key] = widget
            form.addRow(field.label, widget)
        state.loaded.connect(self.refresh)
        self.refresh()

    def _make(self, f: Field) -> QWidget:
        if f.kind == "choice":
            box = QComboBox()
            if f.key == "column":
                box.setEditable(True)
                box.addItems(column_labels())
                box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                completer = box.completer()
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            else:
                box.addItems(f.options)
            box.textActivated.connect(lambda text, f=f: self._commit(f, text))
            return box
        if f.kind == "bool":
            check = QCheckBox()
            check.toggled.connect(lambda on, f=f: self._commit(f, on))
            return check
        if f.kind == "int":
            spin = QSpinBox()
            spin.setRange(1, 12)
            spin.valueChanged.connect(lambda v, f=f: self._commit(f, v))
            return spin
        if f.kind == "float":
            dspin = QDoubleSpinBox()
            dspin.setRange(0.0, 100.0)
            dspin.setDecimals(2)
            dspin.setSingleStep(0.05)
            dspin.valueChanged.connect(lambda v, f=f: self._commit(f, round(v, 4)))
            return dspin
        edit = QLineEdit()
        edit.setPlaceholderText("valor con unidad, p. ej. 22 in o 560 mm")
        edit.editingFinished.connect(lambda f=f, e=edit: self._commit(f, e.text().strip()))
        return edit

    def _commit(self, f: Field, value: Any) -> None:
        if not self._loading:
            self.state.set(f.section, f.key, value)

    def refresh(self) -> None:
        self._loading = True
        try:
            defaults = {"column_grade": "ASTM A992", "plate_grade": "ASTM A572 Gr. 50",
                        "rod_grade": "ASTM F1554 Gr. 36", "rods_per_side": 2, "A2_over_A1": 1.0,
                        "cracked": True, "friction_mu": 0.4, "electrode": "E70XX",
                        "grout": "1.5 in"}
            for f in self.fields:
                value = self.state.get(f.section, f.key, defaults.get(f.key, ""))
                w = self.widgets[f.key]
                if isinstance(w, QComboBox):
                    if w.isEditable():
                        w.setCurrentText(str(value))
                    else:
                        w.setCurrentIndex(max(0, w.findText(str(value))))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(value))
                elif isinstance(w, QSpinBox):
                    w.setValue(int(value))
                elif isinstance(w, QDoubleSpinBox):
                    w.setValue(float(value))
                elif isinstance(w, QLineEdit):
                    w.setText(str(value))
        finally:
            self._loading = False


CASE_COLUMNS = (("name", "Caso"), ("type", "Tipo"), ("P", "P (compresión +)"), ("V", "V"),
                ("M", "M (eje fuerte)"), ("V_weak", "V eje débil"), ("M_weak", "M eje débil"))


class LoadsPanel(QWidget):
    """Editable table of load cases and the list of combinations to solve."""

    selection_changed = Signal()

    def __init__(self, state: ProjectState) -> None:
        super().__init__()
        self.state = state
        self._loading = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Casos de carga</b> (valores con unidad, p. ej. 100 kip)"))
        self.cases = QTableWidget(0, len(CASE_COLUMNS))
        self.cases.setHorizontalHeaderLabels([label for _, label in CASE_COLUMNS])
        self.cases.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cases.itemChanged.connect(self._cases_edited)
        layout.addWidget(self.cases, 2)
        row = QHBoxLayout()
        add, remove = QPushButton("Agregar caso"), QPushButton("Quitar caso")
        add.clicked.connect(self._add_case)
        remove.clicked.connect(self._remove_case)
        self.lrfd, self.asd = QCheckBox("LRFD"), QCheckBox("ASD")
        self.lrfd.toggled.connect(self._methods_edited)
        self.asd.toggled.connect(self._methods_edited)
        for w in (add, remove):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(QLabel("Combinaciones ASCE 7:"))
        row.addWidget(self.lrfd)
        row.addWidget(self.asd)
        layout.addLayout(row)
        layout.addWidget(QLabel("<b>Combinaciones</b> (marque las que se resuelven)"))
        self.combos = QTableWidget(0, 5)
        self.combos.setHorizontalHeaderLabels(["Combinación", "Método", "P", "V", "M"])
        self.combos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.combos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.combos.itemChanged.connect(lambda _: self.selection_changed.emit())
        layout.addWidget(self.combos, 3)
        self._unchecked: set[str] = set()
        state.loaded.connect(self._load_cases)
        state.changed.connect(self._load_combos)
        self._load_cases()
        self._load_combos()

    # -- cases
    def _load_cases(self) -> None:
        self._loading = True
        try:
            cases = self.state.data.get("cases", [])
            self.cases.setRowCount(len(cases))
            for r, case in enumerate(cases):
                for c, (key, _) in enumerate(CASE_COLUMNS):
                    if key == "type":
                        box = QComboBox()
                        box.addItems([t.value for t in LoadType])
                        box.setCurrentText(str(case.get("type", "D")))
                        box.currentTextChanged.connect(lambda _: self._cases_edited())
                        self.cases.setCellWidget(r, c, box)
                    else:
                        self.cases.setItem(r, c, QTableWidgetItem(str(case.get(key, ""))))
            methods = self.state.data.get("combinations", {}).get("methods", ["LRFD"])
            self.lrfd.setChecked("LRFD" in methods)
            self.asd.setChecked("ASD" in methods)
            self._unchecked.clear()
        finally:
            self._loading = False

    def _read_cases(self) -> list[dict[str, Any]]:
        out = []
        for r in range(self.cases.rowCount()):
            case: dict[str, Any] = {}
            for c, (key, _) in enumerate(CASE_COLUMNS):
                if key == "type":
                    case[key] = self.cases.cellWidget(r, c).currentText()
                else:
                    item = self.cases.item(r, c)
                    text = item.text().strip() if item else ""
                    if text:
                        case[key] = text
            out.append(case)
        return out

    def _cases_edited(self, *_: object) -> None:
        if not self._loading:
            self.state.set_cases(self._read_cases())

    def _add_case(self) -> None:
        cases = self._read_cases()
        names = {c.get("name") for c in cases}
        name = next(n for n in ("D", "L", "W", "S", "E", *[f"C{i}" for i in range(1, 99)])
                    if n not in names)
        kind = name if name in {t.value for t in LoadType} else "L"
        cases.append({"name": name, "type": kind, "P": "0 kN", "M": "0 kN*m"})
        self.state.set_cases(cases)
        self._load_cases()

    def _remove_case(self) -> None:
        row = self.cases.currentRow()
        cases = self._read_cases()
        if 0 <= row < len(cases) and len(cases) > 1:
            del cases[row]
            self.state.set_cases(cases)
            self._load_cases()

    def _methods_edited(self) -> None:
        if not self._loading:
            methods = [m for m, box in (("LRFD", self.lrfd), ("ASD", self.asd))
                       if box.isChecked()]
            self.state.set_methods(methods or ["LRFD"])

    # -- combinations
    def _load_combos(self) -> None:
        for r in range(self.combos.rowCount()):
            item = self.combos.item(r, 0)
            if item is not None and item.checkState() == Qt.CheckState.Unchecked:
                self._unchecked.add(item.text())
            elif item is not None:
                self._unchecked.discard(item.text())
        self.combos.blockSignals(True)
        try:
            self.combos.setRowCount(0)
            if not self.state.valid:
                return
            units = self.state.project.info.unit_system()
            for combo, loads in self.state.study().combinations():
                r = self.combos.rowCount()
                self.combos.insertRow(r)
                name = QTableWidgetItem(combo.name)
                name.setFlags(name.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                name.setCheckState(Qt.CheckState.Unchecked if combo.name in self._unchecked
                                   else Qt.CheckState.Checked)
                name.setToolTip(combo.source)
                shear = (loads.Vx**2 + loads.Vy**2) ** 0.5
                moment = (loads.Mx**2 + loads.My**2) ** 0.5
                cells = [name, QTableWidgetItem(combo.method.value),
                         QTableWidgetItem(format_value(loads.P, Kind.FORCE, units)),
                         QTableWidgetItem(format_value(shear, Kind.FORCE, units)),
                         QTableWidgetItem(format_value(moment, Kind.MOMENT, units))]
                for c, cell in enumerate(cells):
                    self.combos.setItem(r, c, cell)
        finally:
            self.combos.blockSignals(False)
        self.selection_changed.emit()

    def selected(self) -> list[str]:
        return [self.combos.item(r, 0).text() for r in range(self.combos.rowCount())
                if self.combos.item(r, 0).checkState() == Qt.CheckState.Checked]


class AnalysisPanel(QWidget):
    """Mesh and solver settings."""

    def __init__(self, state: ProjectState) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Ajustes de malla y análisis</b>"))
        form = QFormLayout()
        layout.addLayout(form)
        self.size = QDoubleSpinBox()
        self.size.setRange(0.0, 100.0)
        self.size.setSuffix(" mm")
        self.size.setSpecialValueText("automático")
        self.size.setToolTip("Tamaño de elemento junto a la columna y los agujeros. Automático: "
                             "el menor espesor entre la pared de la columna y la placa.")
        self.size.valueChanged.connect(lambda v: state.set_setting("size", v or None))
        self.layers = QSpinBox()
        self.layers.setRange(3, 8)
        self.layers.setValue(state.settings.layers)
        self.layers.valueChanged.connect(lambda v: state.set_setting("layers", v))
        self.threads = QSpinBox()
        self.threads.setRange(1, 64)
        self.threads.setValue(state.settings.threads)
        self.threads.valueChanged.connect(lambda v: state.set_setting("threads", v))
        self.nuts = QCheckBox("Los anclajes también toman compresión")
        self.nuts.toggled.connect(lambda on: state.set_setting("leveling_nuts", on))
        self.strain = QDoubleSpinBox()
        self.strain.setRange(0.1, 20.0)
        self.strain.setSuffix(" %")
        self.strain.setValue(100 * state.settings.strain_limit)
        self.strain.valueChanged.connect(lambda v: state.set_setting("strain_limit", v / 100))
        form.addRow("Tamaño fino de malla", self.size)
        form.addRow("Capas en el espesor de la placa", self.layers)
        form.addRow("Hilos de CalculiX", self.threads)
        form.addRow("Tuercas de nivelación", self.nuts)
        form.addRow("Límite de deformación plástica", self.strain)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        layout.addStretch(1)


def unit_presets() -> list[str]:
    return list(PRESETS)
