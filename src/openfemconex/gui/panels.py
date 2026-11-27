# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Property panels: geometry forms, load cases, combinations and analysis settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openconex.core.materials import BOLTS
from openconex.core.shapes import aisc_shapes
from openconex.report.builder import fmt
from openconex.units import PRESETS, Kind, to_internal
from PySide6.QtCore import Qt
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

from openfemconex.gui.loads import CaseColumn, LoadsEditor, LoadsSource
from openfemconex.gui.state import ProjectState
from openfemconex.i18n import tr
from openfemconex.units import convert_text, with_unit

STRESS_KEYS = {"fc", "fy", "Fy", "Fu", "E", "Fnt", "Fnv_N", "Fnv_X", "hardening"}
"""Keys of stress values; every other quantity typed in a form is a length."""
FORCE_KEYS = {"P", "V", "V_weak", "column_V", "column_P"}
MOMENT_KEYS = {"M", "M_weak"}


def key_kind(key: str) -> Kind:
    if key in STRESS_KEYS:
        return Kind.STRESS
    if key in FORCE_KEYS:
        return Kind.FORCE
    if key in MOMENT_KEYS:
        return Kind.MOMENT
    return Kind.LENGTH


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
    "Ficha": [
        Field("name", "Proyecto", section="info"),
        Field("number", "Número de proyecto", section="info"),
        Field("client", "Cliente", section="info"),
        Field("connection", "Nombre de la conexión", section="openfemconex",
              tip="Por ejemplo: Placa base PB-1, eje A-3"),
        Field("engineer", "Ingeniero", section="info"),
        Field("revision", "Revisión", section="info"),
        Field("date", "Fecha", section="info", tip="Vacío: la fecha del día del reporte"),
    ],
    "Columna": [
        Field("column", "Perfil AISC", "choice", tip="W, M, S, HP, HSS y Pipe del catálogo AISC"),
        Field("column_grade", "Acero", "steel"),
    ],
    "Placa": [
        Field("N", "Largo N (dirección del peralte)"),
        Field("B", "Ancho B"),
        Field("tp", "Espesor tp"),
        Field("plate_grade", "Acero", "steel"),
    ],
    "Anclajes": [
        Field("rod_diameter", "Diámetro"),
        Field("rod_grade", "Grado", "rod"),
        Field("rods_per_side", "Anclajes por lado", "int"),
        Field("rows_weak_axis", "Filas frente al eje débil", "bool", section="openfemconex",
              tip="Sin marcar: las dos filas en x = ±f, frente a los patines (eje fuerte). "
                  "Marcada: las filas en y = ±f, frente al eje débil, con los anclajes por lado "
                  "repartidos a lo largo de N"),
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
        Field("grout_pad", "Cortante de anclajes a través del mortero", "bool",
              tip="ACI 17.7.1.2.1: con mortero bajo la placa la resistencia del acero a "
                  "cortante se multiplica por 0.80"),
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
        self.form = form
        layout.addLayout(form)
        layout.addStretch(1)
        for field in fields:
            widget = self._make(field)
            widget.setToolTip(tr(field.tip))
            self.widgets[field.key] = widget
            form.addRow(tr(field.label), widget)
        state.loaded.connect(self.refresh)
        state.changed.connect(self.update_choices)
        self.refresh()

    def _choices(self, f: Field) -> list[str]:
        if f.kind == "steel":
            return self.state.steel_names()
        if f.kind == "rod":
            return self.state.rod_names()
        return list(f.options)

    def update_choices(self) -> None:
        """Refill the material lists, which follow the project library."""
        for f in self.fields:
            if f.kind in ("steel", "rod"):
                box = self.widgets[f.key]
                names = self._choices(f)
                if [box.itemText(i) for i in range(box.count())] != names:
                    current = box.currentText()
                    box.blockSignals(True)
                    box.clear()
                    box.addItems(names)
                    box.setCurrentIndex(max(0, box.findText(current)))
                    box.blockSignals(False)

    def _make(self, f: Field) -> QWidget:
        if f.kind in ("choice", "steel", "rod"):
            box = QComboBox()
            if f.key == "column":
                box.setEditable(True)
                box.addItems(column_labels())
                box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                completer = box.completer()
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            else:
                box.addItems(self._choices(f))
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
        if f.section == "base_plate":
            edit.setPlaceholderText(tr("valor con unidad, p. ej. 22 in o 560 mm"))
        edit.editingFinished.connect(lambda f=f, e=edit: self._commit(f, e.text().strip()))
        return edit

    def _commit(self, f: Field, value: Any) -> None:
        if not self._loading:
            if isinstance(value, str) and f.section == "base_plate" and f.kind == "text":
                # a bare number is taken in the project units (mm or in, MPa, ...)
                value = with_unit(value, key_kind(f.key), self.state.units)
            self.state.set(f.section, f.key, value)

    def refresh(self) -> None:
        self._loading = True
        try:
            defaults = {"column_grade": "ASTM A992", "plate_grade": "ASTM A572 Gr. 50",
                        "rod_grade": "ASTM F1554 Gr. 36", "rods_per_side": 2, "A2_over_A1": 1.0,
                        "cracked": True, "friction_mu": 0.4, "electrode": "E70XX",
                        "grout_pad": True,
                        "grout": "1.5 in"}
            self.update_choices()
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


class BasePlateLoads(LoadsSource):
    """The cases and combinations of the base plate, in the OpenConex project."""

    columns = tuple(CaseColumn(k, label, key_kind(k)) for k, label in CASE_COLUMNS[2:])
    methods = ("LRFD", "ASD")
    result_heads = ("P", "V", "M")

    def __init__(self, state: ProjectState) -> None:
        self.state = state

    @property
    def units(self):
        return self.state.units

    def cases(self) -> list[dict[str, Any]]:
        return list(self.state.data.get("cases", []))

    def options(self) -> dict[str, Any]:
        return dict(self.state.data.get("combinations", {}))

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        self.state.set_cases(cases)

    def set_combinations(self, include_code: bool, custom: list[dict[str, Any]]) -> None:
        self.state.set_combinations(include_code, custom)

    def set_methods(self, methods: list[str]) -> None:
        self.state.set_methods(methods)

    def set_option(self, key: str, value: Any) -> None:
        self.state.set_combination_option(key, value)

    def combinations(self):
        if not self.state.valid:
            raise ValueError(self.state.error)
        out = []
        for combo, loads in self.state.study().combinations():
            shear = (loads.Vx**2 + loads.Vy**2) ** 0.5
            moment = (loads.Mx**2 + loads.My**2) ** 0.5
            out.append((combo, [(loads.P, Kind.FORCE), (shear, Kind.FORCE),
                                (moment, Kind.MOMENT)]))
        return out


class LoadsPanel(LoadsEditor):
    """Load cases and combinations of the base plate (the shared Loads tab)."""

    def __init__(self, state: ProjectState) -> None:
        super().__init__(BasePlateLoads(state))
        self.state = state
        state.loaded.connect(self.load_cases)
        state.changed.connect(self.load_combos)
        self.refresh()


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
        self.size.setSpecialValueText(tr("automático"))
        self.size.setToolTip(tr("Tamaño de elemento junto a la columna y los agujeros. Automático: "
                                "el menor espesor entre la pared de la columna y la placa."))
        self.size.valueChanged.connect(self._size_changed)
        state.loaded.connect(self._size_units)
        self._size_units()
        self.fast = QCheckBox(tr("Malla rápida (prioriza el tiempo de solución)"))
        self.fast.setToolTip(tr(
            "Sigue siendo automática, con elementos de unas dos veces el tamaño normal en la "
            "placa y tres capas en su espesor. En los ejemplos tardó entre un quinto y la mitad "
            "del tiempo (más ahorro cuanto más grande el modelo); anclajes y aplastamiento "
            "cambian menos de 3 %, la soldadura hasta 10 % por debajo. Útil para tantear; para "
            "la memoria final use la malla normal."))
        self.fast.toggled.connect(self._fast_toggled)
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
        form.addRow("", self.fast)
        form.addRow(tr("Capas en el espesor de la placa"), self.layers)
        form.addRow(tr("Hilos de CalculiX"), self.threads)
        form.addRow(tr("Tuercas de nivelación"), self.nuts)
        self._form = form
        form.addRow(tr("Límite de deformación plástica"), self.strain)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        layout.addStretch(1)

    def set_base_plate(self, on: bool) -> None:
        """Options of the base plate only (leveling nuts) shown or not."""
        self._form.setRowVisible(self.nuts, on)
        self.info.setVisible(on)  # the mesh of the base plate

    def _size_units(self) -> None:
        """The fine size in the project length unit (mm or in)."""
        unit = self.state.units.thickness
        factor = to_internal(1.0, unit, Kind.LENGTH)
        self._factor = factor
        self.size.blockSignals(True)
        self.size.setSuffix(f" {unit}")
        self.size.setDecimals(1 if factor < 2 else 3)
        self.size.setSingleStep(1.0 if factor < 2 else 0.0625)
        self.size.setRange(0.0, 100.0 / factor)
        self.size.setValue((self.state.settings.size or 0.0) / factor)
        self.size.blockSignals(False)

    def _size_changed(self, value: float) -> None:
        self.state.set_setting("size", value * self._factor or None)

    def _fast_toggled(self, on: bool) -> None:
        self.state.set_setting("fast", on)
        self.layers.setEnabled(not on)


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
                 fields: list[BlockField], section: str | None = None) -> None:
        super().__init__()
        self.state, self.block, self.fields = state, block, fields
        self.section = section
        """Project section holding the block (e.g. ``base_plate``); None = the
        OpenFEMConex additions."""
        self._loading = False
        self.widgets: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox(tr(title))
        bold = self.enabled.font()
        bold.setBold(True)
        self.enabled.setFont(bold)  # a style sheet here would freeze the text colour
        self.enabled.toggled.connect(self._commit)
        layout.addWidget(self.enabled)
        form = QFormLayout()
        layout.addLayout(form)
        for f in fields:
            w: QWidget
            if f.kind in ("choice", "steel"):
                w = QComboBox()
                for option in (state.steel_names() if f.kind == "steel" else f.options):
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
        state.changed.connect(self._update_choices)
        self.refresh()

    def _update_choices(self) -> None:
        for f in self.fields:
            if f.kind != "steel":
                continue
            box = self.widgets[f.key]
            names = self.state.steel_names()
            if [box.itemData(i) for i in range(box.count())] != names:
                current = box.currentData()
                box.blockSignals(True)
                box.clear()
                for name in names:
                    box.addItem(name, name)
                box.setCurrentIndex(max(0, box.findData(current)))
                box.blockSignals(False)

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
                out[f.key] = with_unit(w.text(), key_kind(f.key), self.state.units)
        return out

    def _commit(self, *_: object) -> None:
        for w in self.widgets.values():
            w.setEnabled(self.enabled.isChecked())
        if not self._loading:
            value = self.values() if self.enabled.isChecked() else None
            if value is not None:
                # keep the keys of the block that this form does not edit
                current = (self.state.get(self.section, self.block, None) if self.section
                           else self.state.ext(self.block)) or {}
                known = {f.key for f in self.fields}
                value = {**{k: v for k, v in current.items() if k not in known}, **value}
            if self.section:
                self.state.set(self.section, self.block, value)
            else:
                self.state.set_ext(self.block, value)

    def refresh(self) -> None:
        self._loading = True
        try:
            data = (self.state.get(self.section, self.block, None) if self.section
                    else self.state.ext(self.block))
            self.enabled.setChecked(bool(data))
            data = data or {}
            for f in self.fields:
                default = (convert_text(f.default, self.state.units) if f.kind == "text"
                           and isinstance(f.default, str) else f.default)
                value = data.get(f.key, default)
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
    BlockField("hook", "Terminación arriba", "90", "choice", ("90", "180", "recta"),
               tip="Gancho estándar de 90° o de 180°, o barra recta"),
    BlockField("tie_diameter", "Diámetro de estribo", "10 mm"),
    BlockField("tie_spacing", "Separación de estribos", "150 mm"),
    BlockField("tie_legs", "Ramas por estribo", 2, "int"),
    BlockField("top_ties", "Estribos superiores que toman cortante", 2, "int",
               tip="Estribos cerca del tope que encierran los anclajes"),
    BlockField("height", "Altura del pedestal", "1 m",
               tip="El cortante suma V·h al momento en la base del pedestal"),
]

LUG_FIELDS = [
    BlockField("direction", "Dirección del cortante que resiste", "strong", "choice",
               ("strong", "weak", "both"),
               tip="Eje fuerte: cortante a lo largo de N (la llave va a lo largo de B). "
                   "Ambas: llave en cruz"),
    BlockField("width", "Ancho de la llave", "200 mm"),
    BlockField("embedment", "Empotramiento bajo el mortero", "75 mm"),
    BlockField("thickness", "Espesor", "32 mm"),
    BlockField("weld", "Filete a la placa (ambas caras)", "8 mm"),
    BlockField("grade", "Acero", "ASTM A36", "steel"),
]

HAIRPIN_FIELDS = [
    BlockField("count", "Horquillas por anclaje", 1, "int"),
    BlockField("diameter", "Diámetro de barra", "16 mm"),
    BlockField("fy", "fy del refuerzo", "420 MPa"),
    BlockField("offset", "Distancia del anclaje a cada pata", "75 mm",
               tip="Debe ser menor que 0.5·hef para que cuente"),
    BlockField("leg_length", "Largo de cada pata", "600 mm"),
    BlockField("cover", "Recubrimiento sobre el doblez", "50 mm"),
]

STIFFENER_FIELDS = [
    BlockField("layout", "Disposición", "alma", "choice",
               ("alma", "alma y bordes", "bordes", "radial"),
               tip="Perfiles W: en línea con el alma, solo en los bordes de los patines o "
                   "ambos. Cruciformes: en línea con las dos almas. Tubos rectangulares: al "
                   "centro de cada cara, junto a las esquinas (bordes), ambos, o en diagonal "
                   "en las esquinas (radial). Tubos circulares: radial"),
    BlockField("count", "Cantidad (radial)", 8, "int",
               tip="Tubos circulares: rigidizadores alrededor. Tubos rectangulares: 4 en las "
                   "esquinas, o 8 con uno más al centro de cada cara"),
    BlockField("length", "Largo desde la cara de la columna", "120 mm"),
    BlockField("height", "Alto junto a la columna", "250 mm"),
    BlockField("end_height", "Alto en el extremo libre", "25 mm"),
    BlockField("thickness", "Espesor", "12 mm"),
    BlockField("grade", "Acero", "ASTM A36", "steel"),
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
        bold = self.enabled.font()
        bold.setBold(True)
        self.enabled.setFont(bold)  # a style sheet here would freeze the text colour
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
            out.append([with_unit(c.text() if c else "0", Kind.LENGTH, self.state.units)
                        for c in cells])
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
            u = self.state.units
            self._fill([[fmt(a.x, Kind.LENGTH, u, 5), fmt(a.y, Kind.LENGTH, u, 5)]
                        for a in self.state.model.anchors])
        self._commit()

    def _commit(self, *_: object) -> None:
        if not self._loading:
            self.state.set_ext("anchors", self.rows() if self.enabled.isChecked() else None)

    def _add(self) -> None:
        rows = self.rows()
        zero = f"0 {self.state.units.length}"
        rows.append([zero, zero])
        self._fill(rows)
        self._commit()

    def _remove(self) -> None:
        row = self.table.currentRow()
        rows = self.rows()
        if 0 <= row < len(rows) and len(rows) > 2:
            del rows[row]
            self._fill(rows)
            self._commit()
