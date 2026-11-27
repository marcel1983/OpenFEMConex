# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Panels of a through-bolt connection: data forms, combinations, checks and traces.

The main window places these widgets in its own docks when a through-bolt
connection is selected in the project tree; the 3D view is the shared viewer.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from html import escape
from typing import Any

from openconex.core.materials import BOLTS, STEELS
from openconex.core.shapes import aisc_shapes
from openconex.report.builder import fmt
from openconex.units import Kind
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from openfemconex import through_bolt_project as tbp
from openfemconex.gui.loads import CaseColumn, LoadsEditor, LoadsSource
from openfemconex.gui.state import ProjectState
from openfemconex.i18n import tr
from openfemconex.report import check_title
from openfemconex.units import with_unit

STRESS = {"fc", "fy", "grout_fc"}
FORCE = {"axial"}


@dataclass(frozen=True)
class TBField:
    path: tuple[str, ...]
    label: str
    kind: str = "text"
    """text (quantity), name, choice, beam, steel, bolt, bool, float."""
    options: tuple[tuple[str, str], ...] = ()
    """choice: (value, label) pairs."""
    tip: str = ""

    @property
    def key(self) -> str:
        return self.path[-1]

    def quantity_kind(self) -> Kind:
        if self.key in STRESS:
            return Kind.STRESS
        if self.key in FORCE:
            return Kind.FORCE
        if self.key == "thickness" and self.path[0] != "member":
            return Kind.THICKNESS
        return Kind.LENGTH


EP = ("end_plate",)
BP = ("back_plate",)
MB = ("member",)
SH = ("shear",)
PAGES: dict[str, list[TBField]] = {
    "Identificación": [
        TBField(("name",), "Nombre de la conexión", "name",
                tip="Por ejemplo: PP-1, muro eje 3"),
    ],
    "Viga": [
        TBField(("beam",), "Perfil", "beam", tip="Perfiles W, M, S y HP del catálogo AISC"),
        TBField(("beam_grade",), "Acero", "steel"),
    ],
    "Placa de extremo": [
        TBField(EP + ("layout",), "Disposición", "choice",
                tuple((k.value, v) for k, v in tbp.LAYOUTS.items())),
        TBField(EP + ("width",), "Ancho bp"),
        TBField(EP + ("thickness",), "Espesor tp"),
        TBField(EP + ("grade",), "Acero", "steel"),
        TBField(EP + ("bolt_diameter",), "Diámetro de los pernos"),
        TBField(EP + ("bolt_grade",), "Grado de los pernos", "bolt"),
        TBField(EP + ("gage",), "Gramil g"),
        TBField(EP + ("pf",), "pf (fila interior a la cara del patín)"),
        TBField(EP + ("pb",), "pb (entre filas interiores)",
                tip="Solo para las disposiciones con dos filas entre los patines"),
        TBField(EP + ("pf_o",), "pf,o (fila exterior al patín)",
                tip="Placas extendidas"),
        TBField(EP + ("pext",), "Extensión pext", tip="Placas extendidas"),
        TBField(EP + ("web_weld",), "Filete del alma",
                tip="Vacío: soldadura de penetración completa"),
        TBField(EP + ("flange_weld",), "Filete de los patines",
                tip="Vacío: soldadura de penetración completa"),
    ],
    "Placa posterior": [
        TBField(BP + ("width",), "Ancho"),
        TBField(BP + ("height",), "Alto", tip="Vacío: el alto de la placa de extremo + 50 mm"),
        TBField(BP + ("thickness",), "Espesor"),
        TBField(BP + ("grade",), "Acero", "steel"),
        TBField(BP + ("washer",), "Diámetro de arandela",
                tip="Vacío: el núcleo de apoyo es la placa misma"),
    ],
    "Muro o columna": [
        TBField(MB + ("kind",), "Tipo", "choice", (("wall", "Muro"), ("column", "Columna"))),
        TBField(MB + ("thickness",), "Espesor h (dirección de los pernos)"),
        TBField(MB + ("width",), "Ancho de la columna",
                tip="Solo columnas; un muro es continuo a los lados"),
        TBField(MB + ("fc",), "f'c"),
        TBField(MB + ("cover",), "Recubrimiento libre"),
        TBField(MB + ("vertical_diameter",), "Barras verticales, diámetro"),
        TBField(MB + ("vertical_spacing",), "Barras verticales, separación"),
        TBField(MB + ("horizontal_diameter",), "Barras horizontales, diámetro"),
        TBField(MB + ("horizontal_spacing",), "Barras horizontales, separación"),
        TBField(MB + ("fy",), "fy del refuerzo"),
        TBField(MB + ("cross_ties",), "Estribos que cruzan el espesor", "bool",
                tip="El puntal se revisa con βs = 0.75 en vez de 0.4"),
        TBField(MB + ("top",), "Distancia al extremo superior",
                tip="Vacío: el elemento continúa"),
        TBField(MB + ("bottom",), "Distancia al extremo inferior",
                tip="Vacío: el elemento continúa"),
        TBField(MB + ("axial",), "Carga axial (compresión +)"),
    ],
    "Viga opuesta": [
        TBField(("opposite", "beam"), "Perfil", "beam"),
        TBField(("opposite", "beam_grade"), "Acero", "steel"),
    ],
    "Cortante": [
        TBField(SH + ("type",), "Transferencia", "choice",
                (("friction", "Fricción"), ("grout", "Grout en las camisas"))),
        TBField(SH + ("mu",), "Coeficiente de fricción μ", "float"),
        TBField(SH + ("grout_length",), "Largo con grout ℓg"),
        TBField(SH + ("grout_fc",), "f'c del grout", tip="Vacío: el f'c del concreto"),
        TBField(SH + ("gap",), "Holgura g entre placa y grout"),
    ],
}
NOTES = {
    "Viga opuesta": "Con viga del otro lado, su placa de extremo es la placa posterior: "
                    "usa la misma placa y los mismos pernos que la viga 1 (filas, gramil y "
                    "diámetro).",
    "Cortante": "Fricción: el cortante pasa por la compresión de cada cara (solo la "
                "compresión permanente según ACI 318 §22.9). Grout: los pernos se apoyan "
                "en el grout de la camisa; vea la ayuda.",
    "Placa posterior": "Placa corrida en la cara opuesta; no se usa cuando hay viga "
                       "opuesta.",
}


def _get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(key, "")
    return node


def _beam_labels() -> list[str]:
    db = aisc_shapes()
    out: list[str] = []
    for t in ("W", "M", "S", "HP"):
        out += db.labels(t)
    return out


class TBForm(QWidget):
    """One page of fields of the current connection."""

    def __init__(self, editor: ThroughBoltEditor, title: str, fields: list[TBField]) -> None:
        super().__init__()
        self.editor = editor
        self.fields = fields
        self.widgets: dict[tuple[str, ...], QWidget] = {}
        self._loading = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{tr(title)}</b>"))
        self.toggle: QCheckBox | None = None
        if title == "Viga opuesta":
            self.toggle = QCheckBox(tr("Hay una viga del otro lado (conexión opuesta)"))
            self.toggle.toggled.connect(self._opposite_toggled)
            layout.addWidget(self.toggle)
        form = QFormLayout()
        layout.addLayout(form)
        for f in fields:
            w = self._make(f)
            w.setToolTip(tr(f.tip))
            self.widgets[f.path] = w
            form.addRow(tr(f.label), w)
        if title in NOTES:
            note = QLabel(tr(NOTES[title]))
            note.setWordWrap(True)
            note.setStyleSheet("color: palette(mid);")
            layout.addWidget(note)
        layout.addStretch(1)

    def _make(self, f: TBField) -> QWidget:
        if f.kind in ("choice", "steel", "bolt", "beam"):
            box = QComboBox()
            if f.kind == "choice":
                for value, label in f.options:
                    box.addItem(tr(label), value)
                box.activated.connect(lambda i, f=f, b=box: self._commit(f, b.itemData(i)))
                return box
            if f.kind == "beam":
                box.setEditable(True)
                box.addItems(_beam_labels())
                box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                completer = box.completer()
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            else:
                box.addItems(list(STEELS) if f.kind == "steel"
                             else [n for n in BOLTS if "F3125" in n])
            box.textActivated.connect(lambda text, f=f: self._commit(f, text))
            return box
        if f.kind == "bool":
            check = QCheckBox()
            check.toggled.connect(lambda on, f=f: self._commit(f, on))
            return check
        if f.kind == "float":
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.5)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.valueChanged.connect(lambda v, f=f: self._commit(f, round(v, 3)))
            return spin
        edit = QLineEdit()
        if f.kind == "text":
            edit.setPlaceholderText(tr("valor con unidad, p. ej. 1 in o 25 mm"))
        edit.editingFinished.connect(lambda f=f, e=edit: self._commit(f, e.text().strip()))
        return edit

    def _commit(self, f: TBField, value: Any) -> None:
        if self._loading:
            return
        if isinstance(value, str) and f.kind == "text":
            value = with_unit(value, f.quantity_kind(), self.editor.state.units)
        self.editor.update(f.path, value)

    def _opposite_toggled(self, on: bool) -> None:
        if not self._loading:
            self.editor.update(("opposite",), copy.deepcopy(tbp.OPPOSITE) if on else None)

    def refresh(self, data: dict[str, Any]) -> None:
        self._loading = True
        try:
            if self.toggle is not None:
                self.toggle.setChecked(bool(data.get("opposite")))
            for f in self.fields:
                value = _get(data, f.path)
                w = self.widgets[f.path]
                if self.toggle is not None:
                    w.setEnabled(bool(data.get("opposite")))
                if isinstance(w, QComboBox):
                    if f.kind == "choice":
                        w.setCurrentIndex(max(0, w.findData(value)))
                    elif w.isEditable():
                        w.setCurrentText(str(value))
                    else:
                        w.setCurrentIndex(max(0, w.findText(str(value))))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(value))
                elif isinstance(w, QDoubleSpinBox):
                    w.setValue(float(value or 0.0))
                elif isinstance(w, QLineEdit):
                    w.setText("" if value is None else str(value))
            self._enable(data)
        finally:
            self._loading = False

    def _enable(self, data: dict[str, Any]) -> None:
        shear = _get(data, SH + ("type",))
        column = _get(data, MB + ("kind",)) == "column"
        layout = _get(data, EP + ("layout",))
        extended = layout.startswith("extended")
        two_rows = layout not in ("flush_2", "extended_4", "extended_4_stiffened")
        rules = {
            SH + ("mu",): shear != "grout", SH + ("grout_length",): shear == "grout",
            SH + ("grout_fc",): shear == "grout", SH + ("gap",): shear == "grout",
            MB + ("width",): column, EP + ("pf_o",): extended, EP + ("pext",): extended,
            EP + ("pb",): two_rows,
        }
        for path, on in rules.items():
            if path in self.widgets:
                self.widgets[path].setEnabled(on)
        if self.fields[0].path[0] == "back_plate":
            for w in self.widgets.values():
                w.setEnabled(not data.get("opposite"))


class ThroughBoltLoads(LoadsSource):
    """Cases and combinations of the through-bolt connection being edited (LRFD)."""

    columns = (CaseColumn("V", "V"), CaseColumn("M", "M", Kind.MOMENT),
               CaseColumn("P", "P"), CaseColumn("V2", "V2"),
               CaseColumn("M2", "M2", Kind.MOMENT), CaseColumn("P2", "P2"))
    methods = tbp.METHODS
    result_heads = ("V", "M", "P", "V2", "M2", "P2")

    def __init__(self, editor: ThroughBoltEditor) -> None:
        self.editor = editor

    @property
    def units(self):
        return self.editor.state.units

    def cases(self) -> list[dict[str, Any]]:
        return list(self.editor.data.get("cases") or [])

    def options(self) -> dict[str, Any]:
        opts = self.editor.data.get("combinations")
        return dict(opts) if isinstance(opts, dict) else {}

    def set_cases(self, cases: list[dict[str, Any]]) -> None:
        self.editor.update(("cases",), cases)

    def set_combinations(self, include_code: bool, custom: list[dict[str, Any]]) -> None:
        opts = self.options()
        opts["include_code"] = include_code
        if custom:
            opts["custom"] = custom
        else:
            opts.pop("custom", None)
        self.editor.update(("combinations",), opts)

    def set_methods(self, methods: list[str]) -> None:
        opts = self.options()
        opts["methods"] = methods
        self.editor.update(("combinations",), opts)

    def set_option(self, key: str, value: Any) -> None:
        opts = self.options()
        if value is None:
            opts.pop(key, None)
        else:
            opts[key] = value
        self.editor.update(("combinations",), opts)

    def combinations(self):
        from openfemconex.load_cases import load_combinations

        data = self.editor.data
        combos = {c.name: c for c in load_combinations(data.get("cases") or [],
                                                       self.options(), self.methods)}
        out = []
        for c in tbp.combinations(data, self.units):
            values = [(getattr(c, k), Kind.MOMENT if k.startswith("M") else Kind.FORCE)
                      for k in self.result_heads]
            out.append((combos[c.name], values))
        return out

    def hidden(self) -> set[str]:
        return set() if self.editor.data.get("opposite") else {"V2", "M2", "P2"}


class TBLoadsPanel(LoadsEditor):
    """The Loads tab of a through-bolt connection."""

    def __init__(self, editor: ThroughBoltEditor) -> None:
        super().__init__(ThroughBoltLoads(editor), intro=(
            "Casos de carga de servicio en la cara del muro o columna, como en la placa base: "
            "las combinaciones ASCE 7 (LRFD) se generan de sus tipos y se pueden editar o "
            "agregar propias. V positivo hacia abajo, M positivo con tracción arriba, P "
            "positiva en compresión; V2, M2 y P2 son de la viga opuesta. Un número sin unidad "
            "se toma en las unidades del proyecto."))
        self.result_heads_hidden()

    def result_heads_hidden(self) -> None:
        opposite = bool(self.source.editor.data.get("opposite"))
        for col in (6, 7, 8):
            self.combos.setColumnHidden(col, not opposite)

    def refresh(self) -> None:
        super().refresh()
        self.result_heads_hidden()


class ThroughBoltEditor(QObject):
    """The widgets of the through-bolt connection selected in the project tree."""

    changed = Signal()
    """The data of the connection changed (the 3D view follows)."""
    results_changed = Signal()

    def __init__(self, state: ProjectState) -> None:
        super().__init__()
        self.state = state
        self.index = -1
        self.data: dict[str, Any] = {}
        self.results: list[tbp.ComboResult] = []
        self.error = ""
        self.stale = False
        self._edition = ""
        self.forms = {name: TBForm(self, name, fields) for name, fields in PAGES.items()}
        self.pages: dict[str, QScrollArea] = {}
        for name, form in self.forms.items():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(form)
            self.pages[name] = scroll
        self.combinations = TBLoadsPanel(self)
        self.checks = QTableWidget(0, 7)
        self.checks.setHorizontalHeaderLabels([tr(h, "column") for h in (
            "Combinación", "Verificación", "Demanda", "Capacidad", "Ratio", "Estado",
            "Referencia")])
        header = self.checks.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.checks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.checks.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.checks.itemSelectionChanged.connect(self._check_selected)
        self.trace = QTextBrowser()
        self._rows: list = []

    # ------------------------------------------------------------------ data
    def set_index(self, index: int) -> None:
        conns = self.state.connections()
        if not 0 <= index < len(conns):
            self.index, self.data = -1, {}
            return
        if index != self.index:
            self.results, self.stale = [], False
        self.index = index
        self.data = tbp.migrate(copy.deepcopy(conns[index]))
        self.refresh()

    def refresh(self) -> None:
        for form in self.forms.values():
            form.refresh(self.data)
        self.combinations.refresh()
        self._validate()
        self._fill_checks()

    def update(self, path: tuple[str, ...], value: Any) -> None:
        node = self.data
        for key in path[:-1]:
            if not isinstance(node.get(key), dict):
                node[key] = {}
            node = node[key]
        if value == "" and path[-1] not in ("name",):
            value = ""
        if node.get(path[-1]) == value:
            return
        node[path[-1]] = value
        self.state.set_connection(self.index, self.data)
        if self.results:
            self.stale = True
        self.refresh()
        self.changed.emit()
        self.results_changed.emit()

    def _validate(self) -> None:
        try:
            self.connection()
            tbp.combinations(self.data, self.state.units)
            self.error = ""
        except Exception as exc:
            self.error = str(exc).strip().splitlines()[0] if str(exc).strip() else \
                type(exc).__name__

    def connection(self):
        return tbp.build(self.data, self.state.units)

    # ------------------------------------------------------------------ checks
    def calculate(self, keep_fem: bool = False) -> bool:
        """Analytic checks; ``keep_fem`` keeps the CalculiX results of the same data."""
        fem = {r.combo.name: r.fem for r in self.results} if keep_fem and not self.stale \
            else {}
        try:
            self.results = tbp.run(self.data, self.state.units, self.state.settings.edition)
            for r in self.results:
                r.fem = fem.get(r.combo.name, [])
        except Exception as exc:
            self.error = str(exc)
            self.results = []
            self._fill_checks()
            self.results_changed.emit()
            return False
        self.error, self.stale = "", False
        self._edition = self.state.settings.edition
        self._fill_checks()
        self.results_changed.emit()
        return True

    def _fill_checks(self) -> None:
        table = self.checks
        table.setRowCount(0)
        self._rows = []
        units = self.state.units
        for res in self.results:
            for r in res.all_checks:
                row = table.rowCount()
                table.insertRow(row)
                ok = r.status.value != "ng"
                status = tr({"ok": "Cumple", "ng": "No cumple"}.get(r.status.value, "No rige"))
                cells = [r.combo, check_title(r), fmt(r.demand, r.kind, units),
                         fmt(r.capacity, r.kind, units),
                         f"{r.ratio:.2f}" if r.applicable else "—", status, r.clause]
                for c, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if c in (2, 3, 4):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                              | Qt.AlignmentFlag.AlignVCenter)
                    if c in (4, 5):
                        item.setForeground(QColor("#888888" if not r.applicable else
                                                  "#2e9e4f" if ok else "#d03040"))
                    table.setItem(row, c, item)
                self._rows.append(r)
        if not self._rows:
            self.trace.setHtml(tr("<p>Sin verificaciones todavía: use Análisis › Resolver.</p>"))

    def _check_selected(self) -> None:
        rows = self.checks.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._rows):
            return
        r = self._rows[rows[0].row()]
        from openfemconex.gui.main import plain_math

        units = self.state.units
        lines = "".join(
            f"<tr><td>{escape(plain_math(s.symbol))}</td>"
            f"<td>{escape(plain_math(s.expression))}</td>"
            f"<td align='right'>{escape(fmt(s.value, s.kind, units))}</td></tr>" for s in r.steps)
        ok = r.status.value != "ng"
        verdict = (tr("cumple") if ok else tr("no cumple")) if r.applicable else tr("no rige")
        color = ("#2e9e4f" if ok else "#d03040") if r.applicable else "#888888"
        self.trace.setHtml(
            f"<h3>{escape(check_title(r))}</h3><p>"
            + escape(tr("Combinación {name}. Referencia: {clause}.", name=r.combo,
                        clause=r.clause))
            + "</p><p>" + tr("Demanda {d}, capacidad {c}, ratio <b>{r}</b>:",
                             d=escape(fmt(r.demand, r.kind, units)),
                             c=escape(fmt(r.capacity, r.kind, units)), r=f"{r.ratio:.2f}")
            + f" <span style='color:{color}'>{verdict}</span>.</p>"
            f"<table cellspacing='0' cellpadding='4' border='1'><tr><th>{tr('Símbolo')}</th>"
            f"<th>{tr('Expresión')}</th><th>{tr('Valor')}</th></tr>{lines}</table>")

    def attach_fem(self, combo: str, sides: list) -> None:
        for r in self.results:
            if r.combo.name == combo:
                r.fem = sides
        self._fill_checks()
        self.results_changed.emit()

    def fem_sides(self) -> list:
        """(label, FemSide) of every solved beam."""
        return [(f"{r.combo.name} · {s.side}", s) for r in self.results for s in r.fem]

    def fem_dir(self):
        import re

        name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(self.data.get("name", "conexion")))
        return self.state.output_dir() / name / "fem"

    def status(self) -> tuple[str, str]:
        """Text and colour for the status bar."""
        if self.error:
            return tr("Datos no válidos: {error}", error=self.error), "#d03040"
        if self.stale or (self.results and self._edition != self.state.settings.edition):
            return tr("Los resultados están desactualizados: vuelva a calcular."), "#d08020"
        if self.results:
            ok = all(r.ok for r in self.results)
            worst = max((r.worst for r in self.results if r.worst), key=lambda c: c.ratio,
                        default=None)
            text = tr("Cumple" if ok else "No cumple")
            if worst is not None:
                text += ". " + tr("Gobierna: {check}, ratio {ratio} ({combo})",
                                  check=check_title(worst), ratio=f"{worst.ratio:.2f}",
                                  combo=worst.combo)
            return text, "#2e9e4f" if ok else "#d03040"
        return tr("Listo. Sin resultados: use Análisis › Resolver."), ""

    def report_html(self, figure_base: str = "", help_figures: bool = True,
                    fem_figures: dict | None = None, picture: bool = True) -> str:
        from importlib import resources

        folder = ""
        if help_figures:
            img = resources.files("openfemconex.help") / "img" / "es"
            folder = str(img)
        return tbp.report_html(self.data, self.results, self.state.units,
                               self.state.data.get("info", {}), self.state.settings.edition,
                               figures=folder, figure_base=figure_base,
                               fem_figures=fem_figures, picture=picture)


class FemWorker(QThread):
    """Solves the combinations of a through-bolt connection with CalculiX, one by one."""

    combo_done = Signal(str, object)
    combo_failed = Signal(str, str)
    stage = Signal(str)
    started_combo = Signal(str, str)
    """Name of a CalculiX run and its .sta file."""
    cancelled = Signal()

    def __init__(self, conn, combos: list, out, edition, ccx: str | None = None,
                 fast: bool = False, threads: int | None = None, settings=None,
                 strain_limit: float = 0.05) -> None:
        super().__init__()
        self.conn, self.combos, self.out, self.edition = conn, combos, out, edition
        self.ccx, self.fast, self.threads = ccx, fast, threads
        self.settings, self.strain_limit = settings, strain_limit
        self.cancel = threading.Event()

    def run(self) -> None:
        from openfemconex.runner import CcxCancelled
        from openfemconex.through_bolt_fem import solve_combination

        for combo in self.combos:
            if self.cancel.is_set():
                self.cancelled.emit()
                return
            try:
                sides = solve_combination(
                    self.conn, combo, self.out, ed=self.edition, ccx=self.ccx,
                    threads=self.threads, cancel=self.cancel, fast=self.fast,
                    settings=self.settings, strain_limit=self.strain_limit,
                    started=lambda name, sta: self.started_combo.emit(name, str(sta)),
                    progress=lambda text, n=combo.name: self.stage.emit(f"{n}: {text}"))
            except CcxCancelled:
                self.cancelled.emit()
                return
            except Exception as exc:
                self.combo_failed.emit(combo.name, f"{type(exc).__name__}: {exc}")
                continue
            self.combo_done.emit(combo.name, sides)
