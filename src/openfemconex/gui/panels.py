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
from openfemconex.i18n import tr

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
        heading = QLabel(f"<b>{tr(title)}</b>")
        layout.addWidget(heading)
        form = QFormLayout()
        layout.addLayout(form)
        layout.addStretch(1)
        for field in fields:
            widget = self._make(field)
            widget.setToolTip(tr(field.tip))
            self.widgets[field.key] = widget
            form.addRow(tr(field.label), widget)
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
        edit.setPlaceholderText(tr("valor con unidad, p. ej. 22 in o 560 mm"))
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
        layout.addWidget(QLabel(tr("<b>Casos de carga</b> (valores con unidad, p. ej. 100 kip)")))
        self.cases = QTableWidget(0, len(CASE_COLUMNS))
        self.cases.setHorizontalHeaderLabels([tr(label) for _, label in CASE_COLUMNS])
        self.cases.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cases.itemChanged.connect(self._cases_edited)
        layout.addWidget(self.cases, 2)
        row = QHBoxLayout()
        add, remove = QPushButton(tr("Agregar caso")), QPushButton(tr("Quitar caso"))
        add.clicked.connect(self._add_case)
        remove.clicked.connect(self._remove_case)
        self.lrfd, self.asd = QCheckBox("LRFD"), QCheckBox("ASD")
        self.lrfd.toggled.connect(self._methods_edited)
        self.asd.toggled.connect(self._methods_edited)
        for w in (add, remove):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(QLabel(tr("Combinaciones ASCE 7:")))
        row.addWidget(self.lrfd)
        row.addWidget(self.asd)
        layout.addLayout(row)
        layout.addWidget(QLabel(tr("<b>Combinaciones</b> (marque las que se resuelven)")))
        self.combos = QTableWidget(0, 5)
        self.combos.setHorizontalHeaderLabels([tr("Combinación"), tr("Método"), "P", "V", "M"])
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
        layout.addWidget(QLabel(tr("<b>Ajustes de malla y análisis</b>")))
        form = QFormLayout()
        layout.addLayout(form)
        self.size = QDoubleSpinBox()
        self.size.setRange(0.0, 100.0)
        self.size.setSuffix(" mm")
        self.size.setSpecialValueText(tr("automático"))
        self.size.setToolTip(tr("Tamaño de elemento junto a la columna y los agujeros. Automático: "
                                "el menor espesor entre la pared de la columna y la placa."))
        self.size.valueChanged.connect(lambda v: state.set_setting("size", v or None))
        self.layers = QSpinBox()
        self.layers.setRange(3, 8)
        self.layers.setValue(state.settings.layers)
        self.layers.valueChanged.connect(lambda v: state.set_setting("layers", v))
        self.threads = QSpinBox()
        self.threads.setRange(1, 64)
        self.threads.setValue(state.settings.threads)
        self.threads.valueChanged.connect(lambda v: state.set_setting("threads", v))
        self.nuts = QCheckBox(tr("Los anclajes también toman compresión"))
        self.nuts.toggled.connect(lambda on: state.set_setting("leveling_nuts", on))
        self.strain = QDoubleSpinBox()
        self.strain.setRange(0.1, 20.0)
        self.strain.setSuffix(" %")
        self.strain.setValue(100 * state.settings.strain_limit)
        self.strain.valueChanged.connect(lambda v: state.set_setting("strain_limit", v / 100))
        form.addRow(tr("Tamaño fino de malla"), self.size)
        form.addRow(tr("Capas en el espesor de la placa"), self.layers)
        form.addRow(tr("Hilos de CalculiX"), self.threads)
        form.addRow(tr("Tuercas de nivelación"), self.nuts)
        form.addRow(tr("Límite de deformación plástica"), self.strain)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        layout.addStretch(1)


def unit_presets() -> list[str]:
    return list(PRESETS)


@dataclass(frozen=True)
class BlockField:
    key: str
    label: str
    default: Any
    kind: str = "text"
    options: tuple[str, ...] = ()
    tip: str = ""


class BlockForm(QWidget):
    """An optional block of the OpenFEMConex additions: a switch and its fields."""

    def __init__(self, state: ProjectState, block: str, title: str,
                 fields: list[BlockField]) -> None:
        super().__init__()
        self.state, self.block, self.fields = state, block, fields
        self._loading = False
        self.widgets: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox(tr(title))
        self.enabled.setStyleSheet("font-weight: bold;")
        self.enabled.toggled.connect(self._commit)
        layout.addWidget(self.enabled)
        form = QFormLayout()
        layout.addLayout(form)
        for f in fields:
            w: QWidget
            if f.kind == "choice":
                w = QComboBox()
                for option in f.options:
                    w.addItem(tr(option), option)
                w.textActivated.connect(self._commit)
            elif f.kind == "int":
                w = QSpinBox()
                w.setRange(1, 99)
                w.valueChanged.connect(self._commit)
            elif f.kind == "bool":
                w = QCheckBox()
                w.toggled.connect(self._commit)
            else:
                w = QLineEdit()
                w.editingFinished.connect(self._commit)
            w.setToolTip(tr(f.tip))
            self.widgets[f.key] = w
            form.addRow(tr(f.label), w)
        state.loaded.connect(self.refresh)
        self.refresh()

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in self.fields:
            w = self.widgets[f.key]
            if isinstance(w, QComboBox):
                out[f.key] = w.currentData()
            elif isinstance(w, QSpinBox):
                out[f.key] = w.value()
            elif isinstance(w, QCheckBox):
                out[f.key] = w.isChecked()
            elif w.text().strip():
                out[f.key] = w.text().strip()
        return out

    def _commit(self, *_: object) -> None:
        for w in self.widgets.values():
            w.setEnabled(self.enabled.isChecked())
        if not self._loading:
            self.state.set_ext(self.block, self.values() if self.enabled.isChecked() else None)

    def refresh(self) -> None:
        self._loading = True
        try:
            data = self.state.ext(self.block)
            self.enabled.setChecked(bool(data))
            data = data or {}
            for f in self.fields:
                value = data.get(f.key, f.default)
                w = self.widgets[f.key]
                if isinstance(w, QComboBox):
                    w.setCurrentIndex(max(0, w.findData(str(value))))
                elif isinstance(w, QSpinBox):
                    w.setValue(int(value))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(value))
                else:
                    w.setText("" if value is None else str(value))
                w.setEnabled(self.enabled.isChecked())
        finally:
            self._loading = False


PEDESTAL_FIELDS = [
    BlockField("bars", "Barras longitudinales", 8, "int",
               tip="Se reparten por igual en el perímetro"),
    BlockField("bar_diameter", "Diámetro de barra", "25 mm"),
    BlockField("fy", "fy del refuerzo", "420 MPa"),
    BlockField("cover", "Recubrimiento libre a estribos", "40 mm"),
    BlockField("hooked", "Barras con gancho arriba", True, "bool"),
    BlockField("tie_diameter", "Diámetro de estribo", "10 mm"),
    BlockField("tie_spacing", "Separación de estribos", "150 mm"),
    BlockField("tie_legs", "Ramas por estribo", 2, "int"),
    BlockField("top_ties", "Estribos superiores que toman cortante", 2, "int",
               tip="Estribos cerca del tope que encierran los anclajes"),
    BlockField("height", "Altura del pedestal", "1 m",
               tip="El cortante suma V·h al momento en la base del pedestal"),
]

STIFFENER_FIELDS = [
    BlockField("layout", "Disposición", "alma", "choice", ("alma", "alma y bordes", "radial"),
               tip="Perfiles W: en línea con el alma o tres por patín. Tubos: radial"),
    BlockField("count", "Cantidad (radial)", 8, "int"),
    BlockField("length", "Largo desde la cara de la columna", "120 mm"),
    BlockField("height", "Alto junto a la columna", "250 mm"),
    BlockField("end_height", "Alto en el extremo libre", "25 mm"),
    BlockField("thickness", "Espesor", "12 mm"),
    BlockField("grade", "Acero", "ASTM A36", "choice", tuple(STEELS)),
    BlockField("weld", "Tamaño del filete", "", tip="Vacío: mínimo de la Tabla J2.4"),
]


class AnchorTable(QWidget):
    """Anchor rods at free coordinates, from the plate centre."""

    def __init__(self, state: ProjectState) -> None:
        super().__init__()
        self.state = state
        self._loading = False
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox(tr("Posiciones por coordenadas"))
        self.enabled.setStyleSheet("font-weight: bold;")
        self.enabled.setToolTip(tr("x a lo largo del peralte de la columna, y a lo largo del "
                                   "patín, desde el centro de la placa"))
        self.enabled.toggled.connect(self._toggled)
        layout.addWidget(self.enabled)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["x", "y"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._commit)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        self.add_button, self.remove_button = QPushButton(tr("Agregar")), QPushButton(tr("Quitar"))
        self.add_button.clicked.connect(self._add)
        self.remove_button.clicked.connect(self._remove)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        layout.addLayout(row)
        state.loaded.connect(self.refresh)
        self.refresh()

    def _fill(self, rows: list[list[str]]) -> None:
        self._loading = True
        try:
            self.table.setRowCount(len(rows))
            for r, (x, y) in enumerate(rows):
                self.table.setItem(r, 0, QTableWidgetItem(str(x)))
                self.table.setItem(r, 1, QTableWidgetItem(str(y)))
        finally:
            self._loading = False

    def rows(self) -> list[list[str]]:
        out = []
        for r in range(self.table.rowCount()):
            cells = [self.table.item(r, c) for c in (0, 1)]
            out.append([c.text().strip() if c else "0" for c in cells])
        return out

    def refresh(self) -> None:
        data = self.state.ext("anchors")
        self._loading = True
        self.enabled.setChecked(bool(data))
        self._loading = False
        self._fill(data or [])
        self._enable()

    def _enable(self) -> None:
        for w in (self.table, self.add_button, self.remove_button):
            w.setEnabled(self.enabled.isChecked())

    def _toggled(self, on: bool) -> None:
        self._enable()
        if self._loading:
            return
        if on and not self.table.rowCount() and self.state.model is not None:
            # start from the current pattern so that points are only moved or added
            self._fill([[f"{a.x:.1f} mm", f"{a.y:.1f} mm"] for a in self.state.model.anchors])
        self._commit()

    def _commit(self, *_: object) -> None:
        if not self._loading:
            self.state.set_ext("anchors", self.rows() if self.enabled.isChecked() else None)

    def _add(self) -> None:
        rows = self.rows()
        rows.append(["0 mm", "0 mm"])
        self._fill(rows)
        self._commit()

    def _remove(self) -> None:
        row = self.table.currentRow()
        rows = self.rows()
        if 0 <= row < len(rows) and len(rows) > 2:
            del rows[row]
            self._fill(rows)
            self._commit()
