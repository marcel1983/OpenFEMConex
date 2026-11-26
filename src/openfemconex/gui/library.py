# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Section and material libraries of the project: editors and previews."""

from __future__ import annotations

import copy
import math
from typing import Any

from openconex.core.materials import BOLTS, STEELS
from openconex.core.shapes import aisc_shapes
from openconex.io.project import WSectionInput
from openconex.report.builder import fmt
from openconex.units import Kind, UnitSystem, from_internal, parse
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from openfemconex.extras import LAWS, law_from_dict
from openfemconex.gui.state import ProjectState
from openfemconex.i18n import tr
from openfemconex.model import Section, SectionKind
from openfemconex.units import convert_data, convert_text

I_TYPES = ("W", "M", "S", "HP")
STEEL_COLOR = QColor("#5b7fb0")
CURVE_COLOR = QColor("#e07a1f")
LAW_LABELS = {"bilineal": "Bilineal (endurecimiento lineal)",
              "elastoplastica": "Elastoplástica perfecta",
              "trilineal": "Trilineal (escalón de fluencia y endurecimiento hasta Fu)",
              "tabla": "Tabla de puntos"}
DEFAULT_LAW = {"law": "bilineal", "nu": 0.3}


def i_shape_labels() -> list[str]:
    db = aisc_shapes()
    out: list[str] = []
    for t in I_TYPES:
        out += db.labels(t)
    return out


def _units(state: ProjectState) -> UnitSystem:
    return state.units


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def w_properties(d: float, bf: float, tf: float, tw: float) -> dict[str, float]:
    """Gross properties of a doubly symmetric I-shape made of three plates (no fillets)."""
    h = d - 2 * tf
    A = 2 * bf * tf + h * tw
    Ix = (bf * d**3 - (bf - tw) * h**3) / 12
    Iy = (2 * tf * bf**3 + h * tw**3) / 12
    return {"A": A, "Ix": Ix, "Iy": Iy, "Sx": 2 * Ix / d, "Sy": 2 * Iy / bf,
            "Zx": bf * tf * (d - tf) + tw * h**2 / 4, "Zy": tf * bf**2 / 2 + h * tw**2 / 4,
            "rx": math.sqrt(Ix / A), "ry": math.sqrt(Iy / A),
            "J": (2 * bf * tf**3 + (d - tf) * tw**3) / 3}


def _nice(step: float) -> float:
    """1, 2 or 5 times a power of ten, at least ``step``."""
    if step <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(step))
    return next(m * power for m in (1, 2, 5, 10) if m * power >= step)


# ---------------------------------------------------------------------- previews
class SectionPreview(QWidget):
    """Plan of a column section to scale, with its main dimensions."""

    def __init__(self) -> None:
        super().__init__()
        self.section: Section | None = None
        self.message = ""
        self.setMinimumSize(220, 200)

    def show_section(self, section: Section | None, message: str = "") -> None:
        self.section, self.message = section, message
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))
        text = pal.color(QPalette.ColorRole.Text)
        s = self.section
        if s is None:
            p.setPen(text)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       self.message or tr("sin sección"))
            return
        width = max(s.d, s.bf2 if s.kind is SectionKind.CRUCIFORM else 0.0)
        height = max(s.bf, s.d2)
        margin = 28
        scale = min((self.width() - 2 * margin) / width, (self.height() - 2 * margin) / height)
        cx, cy = self.width() / 2, self.height() / 2

        def pt(x: float, y: float) -> QPointF:
            return QPointF(cx + x * scale, cy - y * scale)

        p.setPen(QPen(STEEL_COLOR.darker(140), 1))
        p.setBrush(STEEL_COLOR)
        if s.kind in (SectionKind.I, SectionKind.CRUCIFORM):
            for x0, y0, x1, y1 in s.boxes():
                p.drawRect(QRectF(pt(x0, y1), pt(x1, y0)))
        elif s.kind is SectionKind.HSS_ROUND:
            path = QPainterPath()
            r, ri = s.d / 2 * scale, (s.d / 2 - s.t) * scale
            path.addEllipse(QPointF(cx, cy), r, r)
            path.addEllipse(QPointF(cx, cy), ri, ri)
            p.drawPath(path)
        else:
            path = QPainterPath()
            path.addRect(QRectF(pt(-s.d / 2, s.bf / 2), pt(s.d / 2, -s.bf / 2)))
            path.addRect(QRectF(pt(-s.d / 2 + s.t, s.bf / 2 - s.t),
                                pt(s.d / 2 - s.t, -s.bf / 2 + s.t)))
            p.drawPath(path)
        p.setPen(text)
        p.drawText(QRectF(0, self.height() - 22, self.width(), 20),
                   Qt.AlignmentFlag.AlignCenter, s.name)
        p.drawText(QRectF(4, 2, 60, 18), Qt.AlignmentFlag.AlignLeft, "x →")


class CurveWidget(QWidget):
    """Engineering view of a constitutive law: stress against total strain."""

    def __init__(self) -> None:
        super().__init__()
        self.points: list[tuple[float, float]] = []
        self.units: UnitSystem | None = None
        self.Fy = self.Fu = 0.0
        self.message = ""
        self.setMinimumSize(320, 220)

    def show_curve(self, E: float, plastic: list[tuple[float, float]], Fy: float, Fu: float,
                   units: UnitSystem, message: str = "") -> None:
        """``plastic`` holds (stress, plastic strain) points as CalculiX reads them."""
        self.units, self.Fy, self.Fu, self.message = units, Fy, Fu, message
        self.points = [(0.0, 0.0)]
        if plastic and E > 0:
            self.points += [(e + s / E, s) for s, e in plastic]
            last_s, last_e = plastic[-1]
            self.points.append((last_e + last_s / E + 0.03, last_s))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))
        text = pal.color(QPalette.ColorRole.Text)
        grid = pal.color(QPalette.ColorRole.Mid)
        p.setPen(text)
        if len(self.points) < 2 or self.units is None:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       self.message or tr("sin curva"))
            return
        left, right, top, bottom = 64, 16, 16, 40
        w, h = self.width() - left - right, self.height() - top - bottom
        emax = max(e for e, _ in self.points)
        smax = max(max(s for _, s in self.points), self.Fu) * 1.1
        unit = self.units.stress

        def pt(e: float, s: float) -> QPointF:
            return QPointF(left + e / emax * w, top + h - s / smax * h)

        factor = from_internal(1.0, Kind.STRESS, unit)
        s_step = _nice(smax * factor / 5) / factor
        e_step = _nice(emax / 5)
        k = 1
        while k * s_step < smax:
            s = k * s_step
            p.setPen(QPen(grid, 1, Qt.PenStyle.DotLine))
            p.drawLine(pt(0, s), pt(emax, s))
            p.setPen(text)
            p.drawText(QRectF(0, pt(0, s).y() - 8, left - 6, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{s * factor:g}")
            k += 1
        k = 1
        while k * e_step < emax:
            e = k * e_step
            p.setPen(QPen(grid, 1, Qt.PenStyle.DotLine))
            p.drawLine(pt(e, 0), pt(e, smax))
            p.setPen(text)
            p.drawText(QRectF(pt(e, 0).x() - 30, top + h + 2, 60, 16),
                       Qt.AlignmentFlag.AlignCenter, f"{e:g}")
            k += 1
        for value, label in ((self.Fy, "Fy"), (self.Fu, "Fu")):
            if value > 0:
                p.setPen(QPen(grid, 1, Qt.PenStyle.DashLine))
                p.drawLine(pt(0, value), pt(emax, value))
                p.setPen(text)
                p.drawText(pt(emax, value) + QPointF(-24, -3), label)
        p.setPen(QPen(text, 1))
        p.drawLine(pt(0, 0), pt(emax, 0))
        p.drawLine(pt(0, 0), pt(0, smax))
        p.drawText(QRectF(left, self.height() - 18, w, 16), Qt.AlignmentFlag.AlignCenter,
                   tr("deformación unitaria total"))
        p.save()
        p.translate(12, top + h / 2)
        p.rotate(-90)
        p.drawText(QRectF(-h / 2, -10, h, 20), Qt.AlignmentFlag.AlignCenter,
                   tr("esfuerzo") + f" [{unit}]")
        p.restore()
        pen = QPen(CURVE_COLOR, 2.5)
        p.setPen(pen)
        path = QPainterPath(pt(*self.points[0]))
        for e, s in self.points[1:]:
            path.lineTo(pt(e, s))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


# ---------------------------------------------------------------------- sections
SECTION_FIELDS = (("name", "Nombre"), ("d", "Peralte d"), ("bf", "Ancho de patín bf"),
                  ("tf", "Espesor de patín tf"), ("tw", "Espesor de alma tw"),
                  ("k_des", "Distancia k de diseño (opcional)"))


class SectionsDialog(QDialog):
    """Custom W-shapes built from plates, saved with the project."""

    def __init__(self, state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Perfiles armados"))
        self.resize(860, 560)
        self.state = state
        self.units = _units(state)
        self.sections = [copy.deepcopy(s) for s in state.data.get("sections", [])]
        self.renames: dict[str, str] = {}
        self.use: str | None = None
        self._loading = False

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._load)
        buttons = QHBoxLayout()
        for text, slot in (("Nuevo", self._new), ("Duplicar", self._duplicate),
                           ("Eliminar", self._delete)):
            b = QPushButton(tr(text))
            b.clicked.connect(slot)
            buttons.addWidget(b)
        catalog = QHBoxLayout()
        self.catalog = QComboBox()
        self.catalog.setEditable(True)
        self.catalog.addItems(i_shape_labels())
        self.catalog.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.catalog.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.catalog.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        copy_button = QPushButton(tr("Copiar del catálogo"))
        copy_button.setToolTip(tr("Crea un perfil armado con las dimensiones de un perfil AISC"))
        copy_button.clicked.connect(self._from_catalog)
        catalog.addWidget(self.catalog, 1)
        catalog.addWidget(copy_button)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel(tr("Perfiles del proyecto")))
        lv.addWidget(self.list, 1)
        lv.addLayout(buttons)
        lv.addLayout(catalog)

        self.edits: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for key, label in SECTION_FIELDS:
            e = QLineEdit()
            if key != "name":
                e.setPlaceholderText(tr("valor con unidad, p. ej. 22 in o 560 mm"))
            e.editingFinished.connect(self._edited)
            self.edits[key] = e
            form.addRow(tr(label), e)
        self.grade = QComboBox()
        self.grade.addItems(state.steel_names())
        self.grade.activated.connect(self._edited)
        form.addRow(tr("Acero"), self.grade)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #d03040;")
        self.props = QLabel()
        self.props.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview = SectionPreview()
        use = QPushButton(tr("Usar como columna"))
        use.clicked.connect(self._use)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(form)
        rv.addWidget(self.error)
        row = QHBoxLayout()
        row.addWidget(self.preview, 1)
        row.addWidget(self.props)
        rv.addLayout(row, 1)
        rv.addWidget(use)
        self.form_widget = right

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([300, 560])
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        note = QLabel(tr("Perfiles I doblemente simétricos formados por tres placas soldadas, sin "
                         "radios de acuerdo. Se guardan con el proyecto y aparecen en la lista de "
                         "perfiles de la columna y del perfil cruzado de una cruciforme."))
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(split, 1)
        layout.addWidget(box)
        self._fill()

    # -- list
    def _w_rows(self) -> list[int]:
        return [i for i, s in enumerate(self.sections) if s.get("type") == "W"]

    def _label(self, sec: dict[str, Any]) -> str:
        try:
            return WSectionInput.model_validate(sec).label()
        except Exception:
            return str(sec.get("name", "?"))

    def _fill(self, select: int | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for i in self._w_rows():
            item = QListWidgetItem(self._label(self.sections[i]))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(select if select is not None else 0)
        else:
            self._load(-1)

    def _current(self) -> dict[str, Any] | None:
        item = self.list.currentItem()
        return None if item is None else self.sections[item.data(Qt.ItemDataRole.UserRole)]

    def _load(self, _row: int) -> None:
        sec = self._current()
        self.form_widget.setEnabled(sec is not None)
        self._loading = True
        try:
            for key, e in self.edits.items():
                e.setText(_text((sec or {}).get(key, "")))
            if sec is not None:
                index = self.grade.findText(str(sec.get("grade", "")))
                self.grade.setCurrentIndex(max(0, index))
        finally:
            self._loading = False
        self._update_preview()

    def _unique(self, base: str) -> str:
        names = {self._label(s) for s in self.sections}
        name, k = base, 2
        while name in names:
            name, k = f"{base} ({k})", k + 1
        return name

    def _add(self, sec: dict[str, Any]) -> None:
        self.sections.append(sec)
        self._fill(len(self._w_rows()) - 1)

    def _new(self) -> None:
        dims = convert_data({"d": "450 mm", "bf": "300 mm", "tf": "22 mm", "tw": "12 mm"},
                            self.units)
        self._add({"type": "W", "name": self._unique(tr("Perfil armado")), **dims,
                   "grade": "ASTM A572 Gr. 50"})

    def _duplicate(self) -> None:
        sec = self._current()
        if sec is not None:
            self._add({**copy.deepcopy(sec), "name": self._unique(self._label(sec))})

    def _delete(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        label = item.text()
        if label == self.state.column_label():
            QMessageBox.warning(self, tr("Perfiles armados"),
                                tr("El perfil es la columna del proyecto: elija otra columna "
                                   "antes de eliminarlo."))
            return
        del self.sections[item.data(Qt.ItemDataRole.UserRole)]
        self._fill()

    def _from_catalog(self) -> None:
        label = self.catalog.currentText().strip()
        try:
            p = aisc_shapes().get(label).properties
        except Exception:
            return
        u = self.units.thickness
        values = {k: f"{from_internal(p[k], Kind.THICKNESS, u):.4g} {u}"
                  for k in ("d", "bf", "tf", "tw")}
        self._add({"type": "W", "name": self._unique(label + " " + tr("armado")), **values,
                   "grade": "ASTM A992"})

    # -- editing
    def _edited(self, *_: object) -> None:
        if self._loading:
            return
        sec = self._current()
        if sec is None:
            return
        old = self._label(sec)
        for key, e in self.edits.items():
            value = e.text().strip()
            if value:
                sec[key] = value
            else:
                sec.pop(key, None)
        sec["grade"] = self.grade.currentText()
        new = self._label(sec)
        if new != old:
            first = next((k for k, v in self.renames.items() if v == old), old)
            self.renames[first] = new
            self.list.currentItem().setText(new)
        self._update_preview()

    def _section(self, sec: dict[str, Any]) -> tuple[Section | None, str]:
        try:
            w = WSectionInput.model_validate(sec)
            dims = [parse(str(getattr(w, k)), Kind.LENGTH, self.units)
                    for k in ("d", "bf", "tf", "tw")]
        except Exception as exc:
            return None, str(exc).splitlines()[0]
        d, bf, tf, tw = dims
        if min(dims) <= 0:
            return None, tr("las dimensiones deben ser positivas")
        if 2 * tf >= d:
            return None, tr("los patines son más gruesos que el peralte")
        if tw >= bf:
            return None, tr("el alma es más gruesa que el ancho del patín")
        return Section(SectionKind.I, d=d, bf=bf, tf=tf, tw=tw, name=w.label()), ""

    def _update_preview(self) -> None:
        sec = self._current()
        section, error = self._section(sec) if sec is not None else (None, "")
        self.error.setText(error)
        self.preview.show_section(section, error)
        if section is None:
            self.props.setText("")
            return
        props = w_properties(section.d, section.bf, section.tf, section.tw)
        u = self.units
        kinds = {"A": Kind.AREA, "Ix": Kind.MOMENT_OF_INERTIA, "Iy": Kind.MOMENT_OF_INERTIA,
                 "Sx": Kind.SECTION_MODULUS, "Sy": Kind.SECTION_MODULUS,
                 "Zx": Kind.SECTION_MODULUS, "Zy": Kind.SECTION_MODULUS,
                 "rx": Kind.THICKNESS, "ry": Kind.THICKNESS, "J": Kind.MOMENT_OF_INERTIA}
        rows = "".join(f"<tr><td>{k}</td><td align='right'>{fmt(v, kinds[k], u)}</td></tr>"
                       for k, v in props.items())
        slender = section.bf / (2 * section.tf)
        web = (section.d - 2 * section.tf) / section.tw
        self.props.setText(
            f"<table cellspacing=4>{rows}<tr><td>bf/2tf</td><td align='right'>{slender:.2f}"
            f"</td></tr><tr><td>h/tw</td><td align='right'>{web:.1f}</td></tr></table>"
            "<p><small>" + tr("eje x: fuerte (a lo largo de d)") + "</small></p>")

    def _use(self) -> None:
        sec = self._current()
        if sec is not None and self._section(sec)[0] is not None:
            self.use = self._label(sec)
            self._accept()

    def _accept(self) -> None:
        labels = [self._label(s) for s in self.sections]
        if len(set(labels)) != len(labels):
            QMessageBox.warning(self, tr("Perfiles armados"),
                                tr("Hay perfiles con el mismo nombre."))
            return
        for sec in self.sections:
            if sec.get("type") == "W" and self._section(sec)[0] is None:
                QMessageBox.warning(self, tr("Perfiles armados"),
                                    tr("Corrija el perfil {name}: {error}",
                                       name=self._label(sec), error=self._section(sec)[1]))
                return
        self.state.set_sections(self.sections, self.renames, self.use)
        self.accept()


# ---------------------------------------------------------------------- materials
STEEL_FIELDS = (("name", "Nombre"), ("Fy", "Fy, fluencia mínima"), ("Fu", "Fu, resistencia a "
                                                                          "tracción"),
                ("E", "E, módulo de elasticidad"))
BOLT_FIELDS = (("name", "Nombre"), ("Fu", "Fu, resistencia a tracción"),
               ("Fy", "Fy, fluencia (opcional)"), ("Fnt", "Fnt, tracción nominal"),
               ("Fnv_N", "Fnv, cortante con rosca en el plano"),
               ("Fnv_X", "Fnv, cortante sin rosca en el plano"))


class MaterialsDialog(QDialog):
    """Steels and anchor rod grades: built-in library and project materials."""

    def __init__(self, state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Materiales"))
        self.resize(940, 640)
        self.state = state
        self.units = _units(state)
        self.materials = [copy.deepcopy(m) for m in state.data.get("materials", [])]
        self.laws: dict[str, dict[str, Any]] = copy.deepcopy(
            (state.data.get("openfemconex") or {}).get("materials") or {})
        self.bolts = [copy.deepcopy(b) for b in state.data.get("bolts", [])]
        self.renames: dict[str, str] = {}
        self._loading = False
        tabs = QTabWidget()
        tabs.addTab(self._steel_tab(), tr("Aceros"))
        tabs.addTab(self._bolt_tab(), tr("Anclajes"))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(box)
        self._fill_steels()
        self._fill_bolts()

    # -- steels
    def _steel_tab(self) -> QWidget:
        self.steel_list = QListWidget()
        self.steel_list.currentRowChanged.connect(self._load_steel)
        buttons = QHBoxLayout()
        for text, slot in (("Nuevo", self._new_steel), ("Duplicar", self._duplicate_steel),
                           ("Eliminar", self._delete_steel)):
            b = QPushButton(tr(text))
            b.clicked.connect(slot)
            buttons.addWidget(b)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.steel_list, 1)
        lv.addLayout(buttons)

        form = QFormLayout()
        self.steel_edits: dict[str, QLineEdit] = {}
        for key, label in STEEL_FIELDS:
            e = QLineEdit()
            e.editingFinished.connect(self._steel_edited)
            self.steel_edits[key] = e
            form.addRow(tr(label), e)
        self.nu = QDoubleSpinBox()
        self.nu.setRange(0.0, 0.49)
        self.nu.setDecimals(3)
        self.nu.setSingleStep(0.01)
        self.nu.valueChanged.connect(self._steel_edited)
        form.addRow(tr("ν, coeficiente de Poisson"), self.nu)
        self.law = QComboBox()
        for key in LAWS:
            self.law.addItem(tr(LAW_LABELS[key]), key)
        self.law.activated.connect(self._steel_edited)
        form.addRow(tr("Ley constitutiva (FEM)"), self.law)
        self.hardening = QLineEdit()
        self.hardening.setPlaceholderText("E/1000")
        self.hardening.editingFinished.connect(self._steel_edited)
        form.addRow(tr("Módulo de endurecimiento H"), self.hardening)
        self.eps_sh = QDoubleSpinBox()
        self.eps_u = QDoubleSpinBox()
        for spin, value in ((self.eps_sh, 0.015), (self.eps_u, 0.15)):
            spin.setRange(0.0, 1.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.005)
            spin.setValue(value)
            spin.valueChanged.connect(self._steel_edited)
        form.addRow(tr("εp al final del escalón de fluencia"), self.eps_sh)
        self.eps_u_label = tr("εp última (en Fu para la trilineal)")
        form.addRow(self.eps_u_label, self.eps_u)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([tr("Esfuerzo"), tr("Deformación plástica")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(120)
        self.table.itemChanged.connect(self._steel_edited)
        table_buttons = QHBoxLayout()
        for text, slot in (("Agregar punto", self._add_point), ("Quitar punto", self._del_point)):
            b = QPushButton(tr(text))
            b.clicked.connect(slot)
            table_buttons.addWidget(b)
        self.table_box = QWidget()
        tb = QVBoxLayout(self.table_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.addWidget(QLabel(tr("Puntos (esfuerzo verdadero, deformación plástica); el primero "
                               "es la fluencia con deformación plástica 0")))
        tb.addWidget(self.table)
        tb.addLayout(table_buttons)
        self.steel_info = QLabel()
        self.steel_info.setWordWrap(True)
        self.steel_error = QLabel()
        self.steel_error.setWordWrap(True)
        self.steel_error.setStyleSheet("color: #d03040;")
        self.curve = CurveWidget()
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(self.steel_info)
        rv.addLayout(form)
        rv.addWidget(self.table_box)
        rv.addWidget(self.steel_error)
        rv.addWidget(self.curve, 1)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([280, 660])
        return split

    def _steel_names(self) -> list[tuple[str, bool]]:
        """(name, built-in) of every steel."""
        return ([(n, True) for n in STEELS]
                + [(m["name"], False) for m in self.materials])

    def _fill_steels(self, select: str | None = None) -> None:
        self.steel_list.blockSignals(True)
        self.steel_list.clear()
        row = 0
        for i, (name, builtin) in enumerate(self._steel_names()):
            item = QListWidgetItem(name + (f"  ({tr('biblioteca')})" if builtin else ""))
            item.setData(Qt.ItemDataRole.UserRole, (name, builtin))
            self.steel_list.addItem(item)
            if name == select:
                row = i
        self.steel_list.blockSignals(False)
        self.steel_list.setCurrentRow(row)

    def _steel(self) -> tuple[str, bool, dict[str, Any]]:
        """Name, built-in flag and the editable data of the selected steel."""
        item = self.steel_list.currentItem()
        name, builtin = item.data(Qt.ItemDataRole.UserRole)
        if builtin:
            g = STEELS[name]
            data = {"name": name, "Fy": fmt(g.Fy, Kind.STRESS, self.units, 4),
                    "Fu": fmt(g.Fu, Kind.STRESS, self.units, 4),
                    "E": fmt(g.E, Kind.STRESS, self.units, 5)}
            return name, True, data
        return name, False, next(m for m in self.materials if m["name"] == name)

    def _load_steel(self, _row: int = 0) -> None:
        if self.steel_list.currentItem() is None:
            return
        name, builtin, data = self._steel()
        law = {**DEFAULT_LAW, **self.laws.get(name, {})}
        self._loading = True
        try:
            for key, e in self.steel_edits.items():
                e.setText(_text(data.get(key, "29000 ksi" if key == "E" else "")))
                e.setReadOnly(builtin)
            self.nu.setValue(float(law.get("nu", 0.3)))
            self.law.setCurrentIndex(max(0, self.law.findData(law.get("law", "bilineal"))))
            self.hardening.setText(_text(law.get("hardening", "")))
            self.eps_sh.setValue(float(law.get("eps_sh", 0.015)))
            self.eps_u.setValue(float(law.get("eps_u", 0.15)))
            self.table.setRowCount(0)
            for sv, ev in law.get("table", []):
                self._append_row(str(sv), str(ev))
        finally:
            self._loading = False
        self.steel_info.setText(
            tr("Material de la biblioteca AISC: sus resistencias son fijas; la ley del modelo "
               "de elementos finitos sí se puede cambiar.") if builtin else
            tr("Material del proyecto: todas sus propiedades se pueden editar."))
        self._show_law_fields()
        self._update_curve()

    def _append_row(self, stress: str, strain: str) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(stress))
        self.table.setItem(r, 1, QTableWidgetItem(strain))

    def _add_point(self) -> None:
        self._loading = True
        try:
            if self.table.rowCount() == 0:
                fy = self.steel_edits["Fy"].text() or convert_text("250 MPa", self.units)
                self._append_row(fy, "0")
            else:
                last = self.table.item(self.table.rowCount() - 1, 0)
                strain = self.table.item(self.table.rowCount() - 1, 1)
                e = float(strain.text()) if strain and strain.text() else 0.0
                self._append_row(last.text() if last else "", f"{e + 0.05:g}")
        finally:
            self._loading = False
        self._steel_edited()

    def _del_point(self) -> None:
        r = self.table.currentRow()
        if r < 0:
            r = self.table.rowCount() - 1
        if r >= 0:
            self.table.removeRow(r)
            self._steel_edited()

    def _show_law_fields(self) -> None:
        law = self.law.currentData()
        self.hardening.setEnabled(law == "bilineal")
        self.eps_sh.setEnabled(law == "trilineal")
        self.eps_u.setEnabled(law in ("bilineal", "trilineal"))
        self.table_box.setVisible(law == "tabla")

    def _law_data(self) -> dict[str, Any]:
        law = self.law.currentData()
        out: dict[str, Any] = {"law": law, "nu": round(self.nu.value(), 4)}
        if law == "bilineal" and self.hardening.text().strip():
            out["hardening"] = self.hardening.text().strip()
        if law == "trilineal":
            out["eps_sh"] = round(self.eps_sh.value(), 6)
        if law in ("bilineal", "trilineal"):
            out["eps_u"] = round(self.eps_u.value(), 6)
        if law == "tabla":
            rows = []
            for r in range(self.table.rowCount()):
                s, e = self.table.item(r, 0), self.table.item(r, 1)
                if s and e and s.text().strip() and e.text().strip():
                    try:
                        rows.append([s.text().strip(), float(e.text().replace(",", "."))])
                    except ValueError:
                        rows.append([s.text().strip(), e.text().strip()])
            out["table"] = rows
        return out

    def _steel_edited(self, *_: object) -> None:
        if self._loading or self.steel_list.currentItem() is None:
            return
        name, builtin, data = self._steel()
        if not builtin:
            for key, e in self.steel_edits.items():
                value = e.text().strip()
                if value:
                    data[key] = value
            new = data["name"]
            if new != name:
                others = [n for n in STEELS] + [m["name"] for m in self.materials
                                                if m is not data]
                if new in others:
                    data["name"] = name
                    self.steel_edits["name"].setText(name)
                else:
                    first = next((k for k, v in self.renames.items() if v == name), name)
                    self.renames[first] = new
                    if name in self.laws:
                        self.laws[new] = self.laws.pop(name)
                    self.steel_list.currentItem().setData(Qt.ItemDataRole.UserRole, (new, False))
                    self.steel_list.currentItem().setText(new)
                    name = new
        law = self._law_data()
        if law == DEFAULT_LAW:
            self.laws.pop(name, None)
        else:
            self.laws[name] = law
        self._show_law_fields()
        self._update_curve()

    def _parse_steel(self, name: str) -> tuple[float, float, float]:
        if name in STEELS:
            g = STEELS[name]
            return g.Fy, g.Fu, g.E
        data = next(m for m in self.materials if m["name"] == name)
        values = [parse(str(data.get(k, "29000 ksi")), Kind.STRESS, self.units)
                  for k in ("Fy", "Fu", "E")]
        Fy, Fu, E = values
        if min(values) <= 0:
            raise ValueError(tr("Fy, Fu y E deben ser positivos"))
        if Fu < Fy:
            raise ValueError(tr("Fu debe ser al menos Fy"))
        return Fy, Fu, E

    def _update_curve(self) -> None:
        if self.steel_list.currentItem() is None:
            return
        name = self.steel_list.currentItem().data(Qt.ItemDataRole.UserRole)[0]
        try:
            Fy, Fu, E = self._parse_steel(name)
            law = law_from_dict({**DEFAULT_LAW, **self.laws.get(name, {})},
                                lambda v: parse(str(v), Kind.STRESS, self.units))
            law.check(Fy, Fu)
            plastic = list(law.curve(Fy, Fu, E))
            error = ""
        except Exception as exc:
            Fy = Fu = E = 0.0
            plastic, error = [], str(exc).splitlines()[0]
        self.steel_error.setText(error)
        self.curve.show_curve(E, plastic, Fy, Fu, self.units, error)

    def _new_steel(self) -> None:
        name = self._unique_steel(tr("Acero nuevo"))
        self.materials.append({"name": name, **convert_data(
            {"Fy": "250 MPa", "Fu": "400 MPa", "E": "200000 MPa"}, self.units)})
        self._fill_steels(name)

    def _duplicate_steel(self) -> None:
        if self.steel_list.currentItem() is None:
            return
        name, _builtin, data = self._steel()
        new = self._unique_steel(name + " " + tr("copia"))
        self.materials.append({**copy.deepcopy(data), "name": new})
        if name in self.laws:
            self.laws[new] = copy.deepcopy(self.laws[name])
        self._fill_steels(new)

    def _delete_steel(self) -> None:
        if self.steel_list.currentItem() is None:
            return
        name, builtin, _ = self._steel()
        if builtin:
            self.laws.pop(name, None)
            self._load_steel()
            return
        used = self._used_steels()
        if name in used:
            QMessageBox.warning(self, tr("Materiales"),
                                tr("El acero {name} está en uso en el proyecto.", name=name))
            return
        self.materials = [m for m in self.materials if m["name"] != name]
        self.laws.pop(name, None)
        self._fill_steels()

    def _used_steels(self) -> set[str]:
        bp = self.state.data.get("base_plate", {})
        used = {bp.get("column_grade"), bp.get("plate_grade"),
                (bp.get("shear_lug") or {}).get("grade"),
                ((self.state.data.get("openfemconex") or {}).get("stiffeners") or {}).get("grade")}
        if isinstance(bp.get("column"), dict):
            used.add(bp["column"].get("grade"))
        used |= {s.get("grade") for s in self.state.data.get("sections", [])}
        renamed = {self.renames.get(n, n) for n in used if n}
        return renamed

    def _unique_steel(self, base: str) -> str:
        names = {n for n, _ in self._steel_names()}
        name, k = base, 2
        while name in names:
            name, k = f"{base} ({k})", k + 1
        return name

    # -- anchor rod grades
    def _bolt_tab(self) -> QWidget:
        self.bolt_list = QListWidget()
        self.bolt_list.currentRowChanged.connect(self._load_bolt)
        buttons = QHBoxLayout()
        for text, slot in (("Nuevo", self._new_bolt), ("Duplicar", self._duplicate_bolt),
                           ("Eliminar", self._delete_bolt)):
            b = QPushButton(tr(text))
            b.clicked.connect(slot)
            buttons.addWidget(b)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.bolt_list, 1)
        lv.addLayout(buttons)
        form = QFormLayout()
        self.bolt_edits: dict[str, QLineEdit] = {}
        for key, label in BOLT_FIELDS:
            e = QLineEdit()
            e.editingFinished.connect(self._bolt_edited)
            self.bolt_edits[key] = e
            form.addRow(tr(label), e)
        self.bolt_info = QLabel()
        self.bolt_info.setWordWrap(True)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(self.bolt_info)
        rv.addLayout(form)
        note = QLabel(tr("En el modelo de elementos finitos los anclajes son resortes elásticos "
                         "que solo trabajan a tracción (y a compresión con tuercas de "
                         "nivelación); sus resistencias se usan en las verificaciones de AISC "
                         "y ACI."))
        note.setWordWrap(True)
        rv.addWidget(note)
        rv.addStretch(1)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([280, 660])
        return split

    def _bolt_names(self) -> list[tuple[str, bool]]:
        return ([(n, True) for n in BOLTS if "F1554" in n]
                + [(b["name"], False) for b in self.bolts])

    def _fill_bolts(self, select: str | None = None) -> None:
        self.bolt_list.blockSignals(True)
        self.bolt_list.clear()
        row = 0
        for i, (name, builtin) in enumerate(self._bolt_names()):
            item = QListWidgetItem(name + (f"  ({tr('biblioteca')})" if builtin else ""))
            item.setData(Qt.ItemDataRole.UserRole, (name, builtin))
            self.bolt_list.addItem(item)
            if name == select:
                row = i
        self.bolt_list.blockSignals(False)
        self.bolt_list.setCurrentRow(row)

    def _bolt(self) -> tuple[str, bool, dict[str, Any]]:
        name, builtin = self.bolt_list.currentItem().data(Qt.ItemDataRole.UserRole)
        if builtin:
            g = BOLTS[name]
            data = {"name": name}
            for key in ("Fu", "Fy", "Fnt", "Fnv_N", "Fnv_X"):
                value = getattr(g, key)
                if value is not None:
                    data[key] = fmt(value, Kind.STRESS, self.units, 4)
            return name, True, data
        return name, False, next(b for b in self.bolts if b["name"] == name)

    def _load_bolt(self, _row: int = 0) -> None:
        if self.bolt_list.currentItem() is None:
            return
        _name, builtin, data = self._bolt()
        self._loading = True
        try:
            for key, e in self.bolt_edits.items():
                e.setText(_text(data.get(key, "")))
                e.setReadOnly(builtin)
        finally:
            self._loading = False
        self.bolt_info.setText(tr("Grado de la biblioteca AISC (Tabla J3.2), solo lectura.")
                               if builtin else tr("Grado del proyecto."))

    def _bolt_edited(self) -> None:
        if self._loading or self.bolt_list.currentItem() is None:
            return
        name, builtin, data = self._bolt()
        if builtin:
            return
        for key, e in self.bolt_edits.items():
            value = e.text().strip()
            if value:
                data[key] = value
            else:
                data.pop(key, None)
        new = data.get("name", name)
        if new != name:
            others = [n for n in BOLTS] + [b["name"] for b in self.bolts if b is not data]
            if new in others or not new:
                data["name"] = name
                self.bolt_edits["name"].setText(name)
            else:
                first = next((k for k, v in self.renames.items() if v == name), name)
                self.renames[first] = new
                self.bolt_list.currentItem().setData(Qt.ItemDataRole.UserRole, (new, False))
                self.bolt_list.currentItem().setText(new)

    def _new_bolt(self) -> None:
        name = self._unique_bolt(tr("Grado nuevo"))
        self.bolts.append({"name": name, **convert_data(
            {"Fu": "58 ksi", "Fy": "36 ksi", "Fnt": "43.5 ksi", "Fnv_N": "23.2 ksi",
             "Fnv_X": "29 ksi"}, self.units)})
        self._fill_bolts(name)

    def _duplicate_bolt(self) -> None:
        if self.bolt_list.currentItem() is None:
            return
        name, _builtin, data = self._bolt()
        new = self._unique_bolt(name + " " + tr("copia"))
        self.bolts.append({**copy.deepcopy(data), "name": new})
        self._fill_bolts(new)

    def _delete_bolt(self) -> None:
        if self.bolt_list.currentItem() is None:
            return
        name, builtin, _ = self._bolt()
        if builtin:
            return
        if self.renames.get(self.state.get("base_plate", "rod_grade"),
                            self.state.get("base_plate", "rod_grade")) == name:
            QMessageBox.warning(self, tr("Materiales"),
                                tr("El grado {name} está en uso en el proyecto.", name=name))
            return
        self.bolts = [b for b in self.bolts if b["name"] != name]
        self._fill_bolts()

    def _unique_bolt(self, base: str) -> str:
        names = {n for n, _ in self._bolt_names()}
        name, k = base, 2
        while name in names:
            name, k = f"{base} ({k})", k + 1
        return name

    # -- accept
    def _accept(self) -> None:
        for m in self.materials:
            try:
                self._parse_steel(m["name"])
                law = law_from_dict({**DEFAULT_LAW, **self.laws.get(m["name"], {})},
                                    lambda v: parse(str(v), Kind.STRESS, self.units))
                law.check(*self._parse_steel(m["name"])[:2])
            except Exception as exc:
                QMessageBox.warning(self, tr("Materiales"),
                                    tr("Corrija el material {name}: {error}", name=m["name"],
                                       error=str(exc).splitlines()[0]))
                return
        for name, law in self.laws.items():
            if name in STEELS:
                try:
                    law_from_dict(law, lambda v: parse(str(v), Kind.STRESS, self.units)).check(
                        STEELS[name].Fy, STEELS[name].Fu)
                except Exception as exc:
                    QMessageBox.warning(self, tr("Materiales"),
                                        tr("Corrija el material {name}: {error}", name=name,
                                           error=str(exc).splitlines()[0]))
                    return
        for b in self.bolts:
            try:
                for key in ("Fu", "Fnt", "Fnv_N", "Fnv_X"):
                    if parse(str(b[key]), Kind.STRESS, self.units) <= 0:
                        raise ValueError(key)
            except Exception as exc:
                QMessageBox.warning(self, tr("Materiales"),
                                    tr("Corrija el grado {name}: falta o no es válido {error}",
                                       name=b["name"], error=str(exc).splitlines()[0]))
                return
        self.state.set_library(self.materials, self.laws, self.bolts, self.renames)
        self.accept()


# ---------------------------------------------------------------------- column panel
class ColumnPanel(QWidget):
    """The column: catalog or built-up shape, steel, single or cruciform, and a preview."""

    def __init__(self, state: ProjectState) -> None:
        super().__init__()
        self.state = state
        self._loading = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{tr('Columna')}</b>"))
        form = QFormLayout()
        layout.addLayout(form)
        self.kind = QComboBox()
        self.kind.addItem(tr("Perfil simple"), "single")
        self.kind.addItem(tr("Cruciforme (perfil W + perfil cruzado en dos T)"), "cruciform")
        self.kind.setToolTip(tr("Cruciforme: un segundo perfil I cortado por el alma y soldado a "
                                "las dos caras del alma del principal; sus patines quedan a lo "
                                "largo del eje y"))
        self.kind.activated.connect(self._commit_kind)
        form.addRow(tr("Tipo"), self.kind)
        self.shape = self._shape_box()
        self.shape.setToolTip(tr("W, M, S, HP, HSS y Pipe del catálogo AISC, o un perfil armado "
                                 "del proyecto"))
        self.shape.textActivated.connect(self._commit_shape)
        form.addRow(tr("Perfil"), self.shape)
        self.grade = QComboBox()
        self.grade.textActivated.connect(self._commit_grade)
        form.addRow(tr("Acero"), self.grade)
        self.cross = self._shape_box()
        self.cross.setToolTip(tr("Perfil I del catálogo o armado; sus patines deben caber entre "
                                 "los patines del perfil principal"))
        self.cross.textActivated.connect(self._commit_kind)
        self.cross_label = QLabel(tr("Perfil cruzado"))
        form.addRow(self.cross_label, self.cross)
        buttons = QHBoxLayout()
        sections = QPushButton(tr("Perfiles armados…"))
        sections.clicked.connect(self.edit_sections)
        materials = QPushButton(tr("Materiales…"))
        materials.clicked.connect(self.edit_materials)
        buttons.addWidget(sections)
        buttons.addWidget(materials)
        layout.addLayout(buttons)
        self.preview = SectionPreview()
        layout.addWidget(self.preview, 1)
        self.props = QLabel()
        self.props.setWordWrap(True)
        layout.addWidget(self.props)
        state.loaded.connect(self.refresh)
        state.changed.connect(self.refresh)
        self.refresh()

    def _shape_box(self) -> QComboBox:
        box = QComboBox()
        box.setEditable(True)
        box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        box.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        box.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        return box

    def _fill(self, box: QComboBox, labels: list[str], current: str) -> None:
        if [box.itemText(i) for i in range(box.count())] != labels:
            box.blockSignals(True)
            box.clear()
            box.addItems(labels)
            box.blockSignals(False)
        box.setCurrentText(current)

    def refresh(self) -> None:
        self._loading = True
        try:
            st = self.state
            from openfemconex.gui.panels import column_labels
            custom = list(st.custom_sections())
            self._fill(self.shape, custom + list(column_labels()), st.column_label())
            self._fill(self.grade, st.steel_names(), st.column_grade())
            self.grade.setCurrentIndex(max(0, self.grade.findText(st.column_grade())))
            cross = (st.ext("column") or {})
            cruciform = cross.get("type") == "cruciform"
            self.kind.setCurrentIndex(1 if cruciform else 0)
            self._fill(self.cross, custom + i_shape_labels(), str(cross.get("cross", "")))
            self.cross.setVisible(cruciform)
            self.cross_label.setVisible(cruciform)
        finally:
            self._loading = False
        model = self.state.model
        if model is not None:
            self.preview.show_section(model.section)
            from openfemconex.diagnostics import column_capacity
            cap = column_capacity(model)
            u = _units(self.state)
            self.props.setText(tr("A = {a}; Mp eje fuerte = {mpy}; Mp eje débil = {mpx}",
                                  a=fmt(cap["A"], Kind.AREA, u),
                                  mpy=fmt(cap["Mpy"], Kind.MOMENT, u),
                                  mpx=fmt(cap["Mpx"], Kind.MOMENT, u)))
        else:
            self.preview.show_section(None, self.state.error)
            self.props.setText("")

    def _commit_shape(self, text: str) -> None:
        if not self._loading and text.strip() and text.strip() != self.state.column_label():
            self.state.set_column(text.strip())

    def _commit_grade(self, text: str) -> None:
        if not self._loading and text != self.state.column_grade():
            self.state.set_column(self.state.column_label(), text)

    def _commit_kind(self, *_: object) -> None:
        if self._loading:
            return
        if self.kind.currentData() == "cruciform":
            cross = self.cross.currentText().strip() or self.state.column_label()
            self.state.set_ext("column", {"type": "cruciform", "cross": cross})
        else:
            self.state.set_ext("column", None)

    def edit_sections(self) -> None:
        SectionsDialog(self.state, self).exec()

    def edit_materials(self) -> None:
        MaterialsDialog(self.state, self).exec()
