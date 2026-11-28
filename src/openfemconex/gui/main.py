# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Main window: ribbon by stage, project tree, 3D view, properties and solver log."""

from __future__ import annotations

import re
import shutil
import sys
from html import escape
from pathlib import Path

from openconex.report.builder import fmt
from openconex.units import Kind
from PySide6.QtCore import QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openfemconex import __version__
from openfemconex.checks import EDITIONS
from openfemconex.gui.connection_picker import ConnectionPicker, type_icon, type_title
from openfemconex.gui.help import HelpDialog, about, topics
from openfemconex.gui.icons import app_icon, icon
from openfemconex.gui.library import ColumnPanel, MaterialsDialog, SectionsDialog
from openfemconex.gui.panels import (
    HAIRPIN_FIELDS,
    LUG_FIELDS,
    PEDESTAL_FIELDS,
    SECTIONS,
    STIFFENER_FIELDS,
    AnalysisPanel,
    AnchorTable,
    BlockForm,
    FormPanel,
    LoadsPanel,
    unit_presets,
)
from openfemconex.gui.progress import SolveProgress
from openfemconex.gui.ribbon import STYLE as RIBBON_STYLE
from openfemconex.gui.ribbon import Ribbon
from openfemconex.gui.state import ProjectState
from openfemconex.gui.theme import apply_theme, settings
from openfemconex.gui.through_bolt_panel import ThroughBoltEditor
from openfemconex.gui.viewer import FIELDS, Viewer
from openfemconex.gui.worker import SolveWorker
from openfemconex.i18n import LANGUAGES, language, set_language, tr
from openfemconex.report import check_title
from openfemconex.runner import CcxError, find_ccx
from openfemconex.through_bolt_project import combinations as tb_combinations
from openfemconex.through_bolt_project import summary as tb_summary
from openfemconex.units import display_units

EDITION_LABELS = {"current": "AISC 360-22 / ACI 318-19", "dg1-2ed": "DG1 2nd ed. (360-05 / 318-08)"}
_LATEX = [(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)"), (r"\\sqrt\{([^{}]*)\}", r"√(\1)"),
          (r"\\left|\\right|\\,|\\ ", " "), (r"\\phi", "φ"), (r"\\psi", "ψ"), (r"\\mu", "μ"),
          (r"\\pi", "π"), (r"\\theta", "θ"), (r"\\Omega", "Ω"), (r"\\varepsilon", "ε"),
          (r"\\lambda", "λ"), (r"\\le", "≤"), (r"\\ge", "≥"), (r"\\min", "min"),
          (r"\\max", "max"), (r"\\sin", "sin"), (r"[{}]", ""), (r"\\", "")]


def plain_math(latex: str) -> str:
    """Readable text for a LaTeX fragment (the full report uses MathML)."""
    text = re.sub(r"\\text\{([^{}]*)\}", r"\1", latex)
    text = re.sub(r"([_^])\{([^{}]*)\}", r"\1\2", text)
    for _ in range(3):
        text = re.sub(_LATEX[0][0], _LATEX[0][1], text)
    for pattern, repl in _LATEX[1:]:
        text = re.sub(pattern, repl, text)
    return re.sub(r"\s+", " ", text).strip()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.dark = settings().value("dark", False, type=bool)
        self.state = ProjectState()
        self.tb = ThroughBoltEditor(self.state)
        self.mode = "base_plate"
        """Type of the connection being edited: ``base_plate`` or ``through_bolt``."""
        self.worker: SolveWorker | None = None
        self._view = "model"
        self._edges = False
        self._current_combo: str | None = None
        self.setWindowIcon(app_icon())
        self.resize(1500, 920)

        self.viewer = Viewer()
        self.viewer.options_changed.connect(lambda: self._refresh_view())
        self.loads = LoadsPanel(self.state)
        self.central = QStackedWidget()
        self.central.addWidget(self.viewer)
        self.central.addWidget(self.loads)
        self.central.addWidget(self.tb.combinations)
        self.setCentralWidget(self.central)

        self._build_status()  # first: the other parts may report through it
        self._build_docks()
        self._build_ribbon()
        self._build_tb_ribbon()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self._refresh_view)
        self.solve_progress = SolveProgress(self)
        self.solve_progress.cancel_requested.connect(self.stop)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(500)
        self._progress_timer.timeout.connect(self._poll_progress)

        self.state.changed.connect(self._on_changed)
        self.state.results_changed.connect(self._on_results)
        self.state.loaded.connect(self._on_loaded)
        self.state.connections_changed.connect(self._fill_tree)
        self.tb.changed.connect(self._show_tb_view)
        self.tb.results_changed.connect(self._on_tb_results)
        self._on_loaded()
        self._on_changed()
        self._on_results()
        apply_theme(self.dark)
        self.viewer.set_dark(self.dark)
        self.ribbon.setStyleSheet(RIBBON_STYLE)
        self.tb_ribbon.setStyleSheet(RIBBON_STYLE)

    # ------------------------------------------------------------------ construction
    def _build_docks(self) -> None:
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._tree_clicked)
        left = QDockWidget(tr("Proyecto"), self)
        left.setObjectName("dockProject")
        left.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left)

        self.properties = QStackedWidget()
        self.forms: dict[str, FormPanel] = {}
        self.pages: dict[str, QWidget] = {}
        self.anchor_table = AnchorTable(self.state)
        self.pedestal_form = BlockForm(self.state, "pedestal", "Refuerzo del pedestal",
                                       PEDESTAL_FIELDS)
        self.stiffener_form = BlockForm(self.state, "stiffeners", "Rigidizadores",
                                        STIFFENER_FIELDS)
        self.cjp = QCheckBox(tr("Penetración completa (CJP)"))
        self.cjp.setToolTip(tr("Soldadura columna-placa de penetración completa: la resistencia "
                               "es la del metal base de la pared de la columna (AISC Tabla J2.5) "
                               "y no se usa el tamaño del filete"))
        self.cjp.toggled.connect(
            lambda on: self.state.set_ext("column_weld", "cjp" if on else None))
        self.state.loaded.connect(self._sync_cjp)
        additions = {"Anclajes": self.anchor_table}
        self.column_panel = ColumnPanel(self.state)
        for name, fields in SECTIONS.items():
            page = QWidget()
            box = QVBoxLayout(page)
            box.setContentsMargins(0, 0, 0, 0)
            if name == "Columna":
                box.addWidget(self.column_panel)
            else:
                self.forms[name] = FormPanel(self.state, name, fields)
                box.addWidget(self.forms[name])
                if name == "Soldadura":
                    self.forms[name].form.addRow("", self.cjp)
            if name in additions:
                box.addWidget(additions[name], 1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages[name] = scroll
            self.properties.addWidget(scroll)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.addWidget(self.stiffener_form)
        box.addStretch(1)
        scroll.setWidget(holder)
        self.pages["Rigidizadores"] = scroll
        self.properties.addWidget(scroll)
        self.lug_form = BlockForm(self.state, "shear_lug", "Llave de cortante", LUG_FIELDS,
                                  section="base_plate")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.addWidget(self.lug_form)
        box.addStretch(1)
        scroll.setWidget(holder)
        self.pages["Llave de cortante"] = scroll
        self.properties.addWidget(scroll)
        note = QLabel(tr(
            "Las barras longitudinales a menos de 0.5·hef de los anclajes en tracción y "
            "desarrolladas sobre el cono trabajan como refuerzo de anclaje a tracción; los "
            "estribos superiores, como refuerzo de anclaje a cortante (ACI 318-19 §17.5.2.1). "
            "Si cumplen, reemplazan al arrancamiento del concreto. Requiere las dimensiones del "
            "pedestal (Geometría › Concreto)."))
        note.setWordWrap(True)
        self.hairpin_form = BlockForm(self.state, "hairpins", "Horquillas en U", HAIRPIN_FIELDS)
        hairpin_note = QLabel(tr(
            "Horquillas en U invertida sobre cada anclaje, con sus dos patas a cada lado del "
            "anclaje. Cuentan como refuerzo de anclaje a tracción si las patas quedan a menos "
            "de 0.5·hef y se desarrollan sobre y bajo el cono (ACI 318-19 §17.5.2.1). No "
            "requieren pedestal."))
        hairpin_note.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.addWidget(self.pedestal_form)
        box.addWidget(note)
        box.addSpacing(12)
        box.addWidget(self.hairpin_form)
        box.addWidget(hairpin_note)
        box.addStretch(1)
        scroll.setWidget(holder)
        self.pages["Refuerzo del pedestal"] = scroll
        self.properties.addWidget(scroll)
        self.analysis_panel = AnalysisPanel(self.state)
        self.properties.addWidget(self.analysis_panel)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.properties.addWidget(self.detail)
        for page in self.tb.pages.values():
            self.properties.addWidget(page)
        self.properties.addWidget(self.tb.trace)
        right = QDockWidget(tr("Propiedades"), self)
        right.setObjectName("dockProperties")
        right.setWidget(self.properties)
        right.setMinimumWidth(360)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
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
        self.bottom = QTabWidget()
        self.bottom.addTab(self.log, tr("Registro del solver"))
        self.bottom.addTab(self.checks, tr("Verificaciones"))
        self.anchor_forces = QTableWidget(0, 9)
        self.anchor_forces.setHorizontalHeaderLabels([tr(h) for h in (
            "Combinación", "Anclaje", "x", "y", "Axial", "Cortante Vx", "Cortante Vy",
            "Cortante total", "Levantamiento")])
        self.anchor_forces.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.anchor_forces.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bottom.addTab(self.anchor_forces, tr("Fuerzas en anclajes"))
        self.bottom.addTab(self.tb.checks, tr("Verificaciones"))
        bottom = QDockWidget(tr("Resultados"), self)
        bottom.setObjectName("dockBottom")
        bottom.setWidget(self.bottom)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom)
        self.resizeDocks([left, right], [270, 400], Qt.Orientation.Horizontal)
        self.resizeDocks([bottom], [250], Qt.Orientation.Vertical)

    def _build_ribbon(self) -> None:
        self.ribbon = Ribbon()
        self.ribbons = QStackedWidget()
        self.ribbons.addWidget(self.ribbon)
        self.ribbons.setSizePolicy(self.ribbon.sizePolicy())
        self.setMenuWidget(self.ribbons)

        tab = self.ribbon.add_tab("Proyecto")
        g = tab("Archivo")
        g.add_button("Nuevo", icon("new"), self.new_project)
        g.add_button("Abrir", icon("open"), self.open_project)
        g.add_button("Guardar", icon("save"), self.save_project)
        g.add_button("Guardar como", icon("save"), self.save_project_as)
        self._connections_group(tab)
        g = tab("Unidades y normas")
        self.units_box = QComboBox()
        self.units_box.addItems(unit_presets())
        self.units_box.textActivated.connect(self.state.set_units)
        g.add_widget("Unidades de presentación", self.units_box)
        self.edition_box = QComboBox()
        for key in EDITIONS:
            self.edition_box.addItem(EDITION_LABELS[key], key)
        self.edition_box.activated.connect(
            lambda i: self.state.set_setting("edition", self.edition_box.itemData(i)))
        g.add_widget("Normas", self.edition_box)

        g = tab("Apariencia")
        self.language_box = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_box.addItem(name, code)
        self.language_box.setCurrentIndex(self.language_box.findData(language()))
        self.language_box.activated.connect(
            lambda i: self.change_language(self.language_box.itemData(i)))
        g.add_widget("Idioma", self.language_box)
        self.theme_box = QComboBox()
        self.theme_box.addItem(tr("Claro"), False)
        self.theme_box.addItem(tr("Oscuro"), True)
        self.theme_box.setCurrentIndex(1 if self.dark else 0)
        self.theme_box.activated.connect(lambda i: self.set_dark(self.theme_box.itemData(i)))
        g.add_widget("Tema", self.theme_box)

        tab = self.ribbon.add_tab("Geometría")
        g = tab("Componentes")
        for name, pic in (("Columna", "column"), ("Placa", "plate"), ("Anclajes", "anchor"),
                          ("Concreto", "concrete"), ("Soldadura", "weld"),
                          ("Refuerzo del pedestal", "rebar"), ("Rigidizadores", "stiffener"),
                          ("Llave de cortante", "lug")):
            g.add_button(name, icon(pic), lambda n=name: self.show_section(n))
        g = tab("Biblioteca")
        g.add_button("Perfiles", icon("sections"), self.edit_sections,
                     "Perfiles W armados de placas, guardados con el proyecto")
        g.add_button("Materiales", icon("materials"), self.edit_materials,
                     "Aceros y grados de anclaje, con la ley constitutiva del modelo FEM")
        g = tab("Vista")
        g.add_button("Modelo", icon("view"), lambda: self.show_model(False))
        g.add_button("Malla", icon("mesh"), lambda: self.show_model(True))

        tab = self.ribbon.add_tab("Cargas")
        g = tab("Cargas")
        g.add_button("Casos", icon("load"), lambda: self.loads.cases.setFocus())
        g.add_button("Combinaciones", icon("combo"), lambda: self.loads.combos.setFocus())
        g.add_button("Editar combinaciones", icon("table"), self.loads.open_editor,
                     "Combinaciones propias con sus factores, o copia editable de las de "
                     "ASCE 7")

        tab = self.ribbon.add_tab("Análisis")
        g = tab("Malla")
        g.add_button("Ajustes", icon("table"), self.show_analysis_settings)
        g.add_button("Generar malla", icon("mesh"), lambda: self.show_model(True))
        g = tab("CalculiX")
        self.solve_button = g.add_button("Resolver", icon("play"), self.solve,
                                         "Resuelve las combinaciones marcadas en Cargas")
        self.stop_button = g.add_button("Detener", icon("stop"), self.stop)
        self.stop_button.setEnabled(False)
        g.add_button("Avance", icon("table"), self.show_progress,
                     "Muestra el avance detallado de CalculiX")
        g = tab("Resultados")
        self.combo_box = QComboBox()
        self.combo_box.setMinimumWidth(130)
        self.combo_box.textActivated.connect(self.show_results)
        g.add_widget("Combinación", self.combo_box)
        self.field_box = QComboBox()
        for name in FIELDS:
            self.field_box.addItem(tr(name), name)
        self.field_box.activated.connect(lambda _: self.show_results())
        g.add_widget("Resultado", self.field_box)
        self.scale_box = QDoubleSpinBox()
        self.scale_box.setRange(0.0, 500.0)
        self.scale_box.setValue(20.0)
        self.scale_box.setPrefix("× ")
        self.scale_box.editingFinished.connect(lambda: self.show_results())
        g.add_widget("Deformada", self.scale_box)

        tab = self.ribbon.add_tab("Verificación")
        g = tab("Verificaciones")
        g.add_button("Resumen", icon("check"), self.show_checks)
        g.add_button("Ver en 3D", icon("results"), lambda: self.show_results())

        tab = self.ribbon.add_tab("Reporte")
        g = tab("Memoria de cálculo")
        g.add_button("Generar", icon("report"), self.generate_report)
        g.add_button("Abrir", icon("browser"), self.open_report,
                     "Abre el reporte completo en el navegador")
        g.add_button("Exportar PDF", icon("pdf"), self.export_pdf)
        g.add_button("Exportar Word", icon("report"), self.export_docx,
                     "Memoria editable en Word (.docx)")
        g = tab("Identificación")
        g.add_button("Ficha", icon("info"), lambda: self.show_section("Ficha"),
                     "Proyecto, conexión, ingeniero y revisión que encabezan el reporte")
        tab = self.ribbon.add_tab("Ayuda")
        g = tab("Ayuda")
        g.add_button("Manual", icon("help"), self.show_help,
                     "Manual de uso, verificaciones y validación")
        g.add_button("Acerca de", icon("info"), lambda: about(self))
        self.ribbon.tab_changed.connect(self._ribbon_tab)
        self.ribbon.select("Geometría")

    def _connections_group(self, tab) -> None:
        g = tab("Conexiones")
        g.add_button("Agregar conexión", icon("new"), self.add_connection,
                     "Agrega al proyecto una conexión de otro tipo, elegido con su imagen")
        g.add_button("Quitar conexión", icon("stop"), self.remove_connection,
                     "Quita del proyecto la conexión seleccionada")

    def _build_tb_ribbon(self) -> None:
        """Ribbon of a through-bolt connection: the same stages, its own panels."""
        self.tb_ribbon = Ribbon()
        self.ribbons.addWidget(self.tb_ribbon)
        tab = self.tb_ribbon.add_tab("Proyecto")
        g = tab("Archivo")
        g.add_button("Nuevo", icon("new"), self.new_project)
        g.add_button("Abrir", icon("open"), self.open_project)
        g.add_button("Guardar", icon("save"), self.save_project)
        g.add_button("Guardar como", icon("save"), self.save_project_as)
        self._connections_group(tab)
        g = tab("Unidades y normas")
        self.tb_units_box = QComboBox()
        self.tb_units_box.addItems(unit_presets())
        self.tb_units_box.textActivated.connect(self.state.set_units)
        g.add_widget("Unidades de presentación", self.tb_units_box)
        self.tb_edition_box = QComboBox()
        for key in EDITIONS:
            self.tb_edition_box.addItem(EDITION_LABELS[key], key)
        self.tb_edition_box.activated.connect(
            lambda i: self.state.set_setting("edition", self.tb_edition_box.itemData(i)))
        g.add_widget("Normas", self.tb_edition_box)

        tab = self.tb_ribbon.add_tab("Geometría")
        g = tab("Componentes")
        for name, pic in (("Viga", "column"), ("Placa de extremo", "plate"),
                          ("Placa posterior", "plate"), ("Muro o columna", "concrete"),
                          ("Viga opuesta", "column"), ("Cortante", "lug")):
            g.add_button(name, icon(pic), lambda n=name: self.show_tb_page(n))
        g = tab("Vista")
        g.add_button("Modelo", icon("view"), self._show_tb_view)

        tab = self.tb_ribbon.add_tab("Cargas")
        g = tab("Cargas")
        g.add_button("Casos", icon("load"), lambda: (
            self.central.setCurrentWidget(self.tb.combinations),
            self.tb.combinations.cases.setFocus()))
        g.add_button("Combinaciones", icon("combo"), lambda: (
            self.central.setCurrentWidget(self.tb.combinations),
            self.tb.combinations.combos.setFocus()))
        g.add_button("Editar combinaciones", icon("table"),
                     lambda: self.tb.combinations.open_editor(),
                     "Combinaciones propias con sus factores, o copia editable de las de "
                     "ASCE 7")

        tab = self.tb_ribbon.add_tab("Análisis")
        g = tab("Malla")
        g.add_button("Ajustes", icon("table"), self.show_analysis_settings,
                     "Tamaño de malla, malla rápida, capas, hilos de CalculiX y límite de "
                     "deformación plástica (los mismos de la placa base)")
        g = tab("CalculiX")
        self.tb_solve_button = g.add_button(
            "Resolver", icon("play"), self.solve_tb,
            "Calcula las verificaciones analíticas y resuelve con CalculiX las combinaciones "
            "marcadas en Cargas: placas sobre el concreto, pernos sin adherencia y soldaduras")
        self.tb_stop_button = g.add_button("Detener", icon("stop"), self.stop_tb)
        self.tb_stop_button.setEnabled(False)
        g.add_button("Avance", icon("table"), self.show_progress,
                     "Muestra el avance detallado de CalculiX")
        g = tab("Resultados")
        self.tb_fem_box = QComboBox()
        self.tb_fem_box.setMinimumWidth(170)
        self.tb_fem_box.textActivated.connect(self.show_tb_fem)
        g.add_widget("Combinación", self.tb_fem_box)
        self.tb_field_box = QComboBox()
        for name in FIELDS:
            self.tb_field_box.addItem(tr(name), name)
        # the plate on the far face: back plate or end plate of the opposite beam
        self.tb_field_box.addItem(tr("Presión de contacto en la cara opuesta"),
                                  "Presión de contacto|far")
        self.tb_field_box.activated.connect(lambda _: self.show_tb_fem())
        g.add_widget("Resultado", self.tb_field_box)

        tab = self.tb_ribbon.add_tab("Verificación")
        g = tab("Verificaciones")
        g.add_button("Resumen", icon("check"), self.show_tb_checks)

        tab = self.tb_ribbon.add_tab("Reporte")
        g = tab("Memoria de cálculo")
        g.add_button("Generar", icon("report"), self.generate_tb_report)
        g.add_button("Abrir", icon("browser"), self.open_tb_report,
                     "Abre el reporte completo en el navegador")
        g.add_button("Exportar PDF", icon("pdf"), self.export_tb_pdf)
        g.add_button("Exportar Word", icon("report"), self.export_tb_docx,
                     "Reporte editable en Word (.docx), con los mismos gráficos")
        g = tab("Identificación")
        g.add_button("Ficha", icon("info"), lambda: self.show_tb_page("Identificación"),
                     "Nombre de la conexión; el proyecto, cliente e ingeniero son los del "
                     "proyecto")
        tab = self.tb_ribbon.add_tab("Ayuda")
        g = tab("Ayuda")
        g.add_button("Pernos pasantes", icon("help"), lambda: self.show_help(self._tb_topic()),
                     "Camino de cargas, esquemas de cortante y verificaciones de esta "
                     "conexión")
        g.add_button("Manual", icon("help"), self.show_help)
        g.add_button("Acerca de", icon("info"), lambda: about(self))
        self.tb_ribbon.tab_changed.connect(self._tb_ribbon_tab)

    # ------------------------------------------------------------------ connections
    def set_mode(self, mode: str, index: int = -1) -> None:
        """Edit the base plate (``base_plate``) or connection ``index`` of the list."""
        self.mode = mode
        through = mode == "through_bolt"
        self.ribbons.setCurrentWidget(self.tb_ribbon if through else self.ribbon)
        self.viewer.dims.setVisible(not through)
        self.viewer.numbers.setVisible(not through)
        self.analysis_panel.set_base_plate(not through)
        for w, on in ((self.log, True), (self.checks, not through),
                      (self.anchor_forces, not through), (self.tb.checks, through)):
            self.bottom.setTabVisible(self.bottom.indexOf(w), on)
        if through:
            self.tb.set_index(index)
            self._view = "tb"
            self.central.setCurrentWidget(self.viewer)
            current = self.tb_ribbon.current()
            self._tb_ribbon_tab(current)
            self._show_tb_view(reset=True)
        else:
            self._view = "model"
            self._ribbon_tab(self.ribbon.current())
        self._update_status()
        QTimer.singleShot(0, self._fill_tree)  # not inside the click on the tree

    def add_connection(self) -> None:
        disabled = {"base_plate": "El proyecto ya tiene una placa base (una por proyecto en "
                                  "esta versión)"} if self.state.has_base_plate else {}
        picker = ConnectionPicker(self, disabled=disabled)
        if not picker.exec() or not picker.selected:
            return
        index = self.state.add_connection(picker.selected)
        if picker.selected == "base_plate":
            self.set_mode("base_plate")
        else:
            self.set_mode("through_bolt", index)
            self.tb_ribbon.select("Geometría")

    def remove_connection(self) -> None:
        index = self.tb.index if self.mode == "through_bolt" else -1
        name = (self.tb.data.get("name", "") if index >= 0 else tr("Placa base"))
        answer = QMessageBox.question(self, tr("Quitar conexión"),
                                      tr("¿Quitar la conexión {name} del proyecto?", name=name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.state.remove_connection(index)
        except ValueError as exc:
            QMessageBox.information(self, tr("Quitar conexión"), str(exc))
            return
        self._select_first()

    def _select_first(self) -> None:
        if self.state.has_base_plate:
            self.set_mode("base_plate")
        elif self.state.connections():
            self.set_mode("through_bolt", 0)

    def show_tb_page(self, name: str) -> None:
        self.properties.setCurrentWidget(self.tb.pages[name])
        if self.central.currentWidget() is not self.viewer:
            self.central.setCurrentWidget(self.viewer)

    def _tb_ribbon_tab(self, name: str) -> None:
        if self.mode != "through_bolt":
            return
        if name == "Cargas":
            self.central.setCurrentWidget(self.tb.combinations)
        else:
            self.central.setCurrentWidget(self.viewer)
        if name in ("Geometría", "Proyecto"):
            if self.properties.currentWidget() not in self.tb.pages.values():
                self.properties.setCurrentWidget(self.tb.pages["Viga"])
        elif name == "Análisis":
            self.properties.setCurrentWidget(self.analysis_panel)
            self.bottom.setCurrentWidget(self.log)
        elif name in ("Verificación", "Reporte"):
            self.show_tb_checks()

    def _show_tb_view(self, reset: bool = False) -> None:
        if self.mode != "through_bolt" or self.tb.index < 0:
            return
        self._view = "tb"
        self._update_status()
        try:
            conn = self.tb.connection()
        except Exception:
            return
        self.viewer.show_through_bolt(conn, reset=reset)

    def calculate_tb(self) -> None:
        if self.tb.calculate():
            self.tb_ribbon.select("Verificación")
            self.show_tb_checks()
        else:
            QMessageBox.warning(self, tr("Calcular"), tr("No se pudo calcular: {error}",
                                                          error=self.tb.error))

    def show_tb_checks(self) -> None:
        self.bottom.setCurrentWidget(self.tb.checks)
        self.properties.setCurrentWidget(self.tb.trace)
        if self.tb.checks.rowCount() and not self.tb.checks.selectedItems():
            self.tb.checks.selectRow(0)

    def _on_tb_results(self) -> None:
        current = self.tb_fem_box.currentText()
        labels = [label for label, _ in self.tb.fem_sides()]
        self.tb_fem_box.clear()
        self.tb_fem_box.addItems(labels)
        if current in labels:
            self.tb_fem_box.setCurrentText(current)
        self._update_status()
        self._fill_tree()

    def solve_tb(self) -> None:
        """Analytic checks of every combination, then CalculiX for the checked ones."""
        from openfemconex.checks import EDITIONS as EDS
        from openfemconex.gui.through_bolt_panel import FemWorker
        from openfemconex.model import MeshSettings
        from openfemconex.through_bolt_project import combinations

        if getattr(self, "tb_worker", None) is not None:
            return
        if not self.tb.calculate():
            QMessageBox.warning(self, tr("Resolver"), tr("No se pudo calcular: {error}",
                                                          error=self.tb.error))
            return
        self.show_tb_checks()
        try:
            find_ccx(self.state.settings.ccx)
        except CcxError as exc:
            QMessageBox.warning(self, "CalculiX", tr(
                "Verificaciones analíticas listas; el modelo CalculiX no se resolvió: "
                "{error}", error=exc))
            return
        chosen = set(self.tb.combinations.selected())
        combos = [c for c in combinations(self.tb.data, self.state.units) if c.name in chosen]
        if not combos:
            QMessageBox.information(self, tr("Resolver"), tr(
                "Verificaciones analíticas listas. Marque en Cargas las combinaciones que "
                "se resuelven con CalculiX."))
            return
        st = self.state.settings
        mesh = MeshSettings(size_fine=st.size, plate_layers=st.layers, fast=st.fast)
        worker = FemWorker(self.tb.connection(), combos, self.tb.fem_dir(),
                           EDS.get(st.edition, EDS["current"]), st.ccx, st.fast, st.threads,
                           settings=mesh, strain_limit=st.strain_limit)
        worker.stage.connect(self._tb_stage)
        worker.started_combo.connect(self._tb_combo_started)
        worker.combo_done.connect(self._tb_combo_done)
        worker.combo_failed.connect(self._tb_combo_failed)
        worker.cancelled.connect(self._cancelled)
        worker.finished.connect(self._tb_solve_finished)
        self.tb_worker = worker
        self._cancelled_run = False
        self.tb_solve_button.setEnabled(False)
        self.tb_stop_button.setEnabled(True)
        self.bottom.setCurrentWidget(self.log)
        self.log.appendPlainText(tr("{n} combinaciones con CalculiX ({mesh}, {t} hilos). "
                                    "Salida: {out}", n=len(combos), t=st.threads,
                                    out=self.tb.fem_dir(),
                                    mesh=tr("malla rápida") if st.fast else tr("malla normal")))
        axial = any(c.P > 0 or c.P2 > 0 for c in combos)  # then two load steps
        self.solve_progress.start(len(combos), 0, 0, st.threads, steps=2 if axial else 1)
        self.progress.setValue(0)
        self.progress.show()
        self._progress_timer.start()
        worker.start()

    def _tb_stage(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("")
        self.solve_progress.stage(text)

    def _tb_combo_started(self, name: str, sta: str) -> None:
        self.log.appendPlainText(tr("{name}: resolviendo con CalculiX…", name=name))
        self.solve_progress.combo_started(name, Path(sta))

    def _tb_combo_done(self, name: str, sides: list) -> None:
        units = self.state.units
        self.tb.attach_fem(name, sides)
        res = sides[0].results if sides else None
        checks = [c for s in sides for c in s.checks if c.applicable]
        worst = max(checks, key=lambda r: r.ratio, default=None)
        if res is None:
            summary = f"{name}: " + tr("sin carga")
        else:
            summary = (
                f"{name}: " + (tr("convergió") if res.converged else
                               tr("NO convergió ({pct} % de la carga)",
                                  pct=f"{100 * res.load_fraction:.0f}"))
                + tr(" en {s} s. Tracción total en pernos {t}, compresión {c}.",
                     s=f"{sum(s.results.solver.get('seconds', 0) for s in sides):.0f}",
                     t=fmt(res.anchor_tension_total, Kind.FORCE, units),
                     c=fmt(res.bearing_force, Kind.FORCE, units))
                + (tr(" Gobierna {check}: {ratio}.", check=check_title(worst),
                      ratio=f"{worst.ratio:.2f}") if worst else ""))
        self.log.appendPlainText(summary)
        self.solve_progress.combo_finished(summary)

    def _tb_combo_failed(self, name: str, msg: str) -> None:
        text = tr("{name}: no se pudo resolver: {error}", name=name, error=msg)
        self.log.appendPlainText(text)
        self.solve_progress.combo_finished(text)

    def stop_tb(self) -> None:
        if getattr(self, "tb_worker", None) is not None:
            self.tb_worker.cancel.set()
            self.log.appendPlainText(tr("Deteniendo CalculiX…"))

    def _tb_solve_finished(self) -> None:
        self.tb_worker = None
        self.solve_progress.finished(self._cancelled_run)
        self._progress_timer.stop()
        self.tb_solve_button.setEnabled(True)
        self.tb_stop_button.setEnabled(False)
        self.progress.hide()
        self._update_status()
        if self.tb.fem_sides():
            self.tb_ribbon.select("Análisis")
            self.show_tb_fem(self.tb.fem_sides()[0][0])
            self.show_tb_checks()

    def show_tb_fem(self, label: str | None = None) -> None:
        sides = dict(self.tb.fem_sides())
        label = label or self.tb_fem_box.currentText()
        side = sides.get(label)
        if side is None or side.vtu is None or not side.vtu.exists():
            return
        self.tb_fem_box.setCurrentText(label)
        self.central.setCurrentWidget(self.viewer)
        self._view = "tb_fem"
        units = self.state.units
        sample = fmt(1000.0, Kind.FORCE, units, 6).split()
        field, _sep, face = str(self.tb_field_box.currentData()).partition("|")
        if face == "far" and side.model.far is None and side.model.opposite is None:
            face = ""  # rigid far face: nothing to show there
        self.viewer.show_results(side.vtu, side.model, side.results, field, 20.0,
                                 unit_force=float(sample[0]) / 1000.0, force_label=sample[-1],
                                 reset=True, face=face or "front")

    def _tb_topic(self) -> int:
        for i, (_, text) in enumerate(topics()):
            if "openfemconex.through_bolt" in text:
                return i
        return 0

    def _tb_report_ready(self) -> bool:
        if not self.tb.results or self.tb.stale:
            if not self.tb.calculate():
                QMessageBox.warning(self, tr("Reporte"), tr("No se pudo calcular: {error}",
                                                             error=self.tb.error))
                return False
        return True

    def _tb_report_dir(self) -> Path:
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(self.tb.data.get("name", "conexion")))
        folder = self.state.output_dir() / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _tb_picture(self, folder: Path) -> str:
        """3D picture of the connection for the report; its base URL, or "" without one."""
        if self.viewer.plotter is None:
            return ""
        self._show_tb_view(reset=True)
        try:
            self.viewer.screenshot(folder / "conexion.png")
        except Exception:  # no OpenGL context: the report goes without the picture
            return ""
        return QUrl.fromLocalFile(str(folder)).toString() + "/"

    def _tb_fem_figures(self, folder: Path) -> dict:
        """Figures of the CalculiX models (model, mesh, stresses, strains, displacements
        and contact pressure on both plates) rendered into ``folder``."""
        from openfemconex.scenes import render_through_bolt_figures

        sides = [s for _, s in self.tb.fem_sides()]
        if not sides:
            return {}
        if self.viewer.plotter is None:
            self.log.appendPlainText(tr("Reporte sin gráficos: el visor 3D (OpenGL) no está "
                                        "disponible."))
            return {}
        self.status_label.setText(tr("Generando los gráficos del reporte…"))
        QApplication.processEvents()
        sample = fmt(1000.0, Kind.FORCE, self.state.units, 6).split()
        conn = self.tb.connection()
        far = (tr("placa de extremo de la viga 2") if conn.opposite is not None
               else tr("placa posterior"))
        errors: list[str] = []
        figures = render_through_bolt_figures(
            folder, sides, far_caption=far, unit_force=float(sample[0]) / 1000.0,
            force_label=sample[-1], errors=errors)
        for error in errors:
            self.log.appendPlainText(tr("No se pudieron generar los gráficos del reporte: "
                                        "{error}", error=error))
        return figures

    def _tb_figures(self, folder: Path) -> tuple[bool, dict]:
        """Render the 3D picture and the FEM figures into ``folder``: (picture made,
        FEM figures)."""
        picture = bool(self._tb_picture(folder))
        return picture, self._tb_fem_figures(folder)

    def _tb_report(self, folder: Path) -> str:
        """HTML for the PDF: images by absolute file URL (QTextDocument)."""
        picture, figures = self._tb_figures(folder)
        base = QUrl.fromLocalFile(str(folder.resolve())).toString() + "/"
        return self.tb.report_html(figure_base=base, fem_figures=figures, picture=picture)

    def generate_tb_report(self) -> Path | None:
        if not self._tb_report_ready():
            return None
        folder = self._tb_report_dir()
        picture, figures = self._tb_figures(folder)
        # the HTML names its images relative to its own folder, so that a browser finds
        # them and the folder can be moved or sent; the help diagrams are copied there
        help_dir = folder / "esquemas"
        help_dir.mkdir(exist_ok=True)
        for png in Path(self.tb.help_dir()).glob("*.png"):
            shutil.copy2(png, help_dir / png.name)
        html = self.tb.report_html(figure_base="", help_figures="esquemas",
                                   fem_figures=figures, picture=picture)
        path = folder / "reporte.html"
        path.write_text(html, encoding="utf-8")
        self.status_label.setText(tr("Reporte escrito en {path}", path=path))
        return path

    def open_tb_report(self) -> None:
        path = self.generate_tb_report()
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def export_tb_docx(self, path: str | None = None) -> Path | None:
        if not self._tb_report_ready():
            return None
        folder = self._tb_report_dir()
        if not path:
            default = str(folder / "reporte.docx")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar Word"), default,
                                                  "Word (*.docx)")
        if not path:
            return None
        picture, figures = self._tb_figures(folder)
        out = self.tb.report_docx(Path(path), folder, fem_figures=figures, picture=picture)
        self.log.appendPlainText(tr("Word escrito en {path}", path=out))
        self.status_label.setText(tr("Word escrito en {path}", path=out))
        return out

    def export_tb_pdf(self, path: str | None = None) -> Path | None:
        if not self._tb_report_ready():
            return None
        folder = self._tb_report_dir()
        if not path:
            default = str(folder / "reporte.pdf")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar PDF"), default, "PDF (*.pdf)")
        if not path:
            return None
        html = self._tb_report(folder)
        html = html.replace("<details>", "<details open>")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        document = QTextDocument()
        document.setHtml(html.replace('width="470"', 'width="330"')
                         .replace('width="940"', 'width="660"'))
        document.print_(printer)
        self.status_label.setText(tr("PDF escrito en {path}", path=path))
        return Path(path)

    # ------------------------------------------------------------------ appearance and help
    def set_dark(self, dark: bool) -> None:
        self.dark = bool(dark)
        apply_theme(self.dark)
        self.viewer.set_dark(self.dark)
        self.ribbon.setStyleSheet(RIBBON_STYLE)  # re-resolve the palette() colours
        settings().setValue("dark", self.dark)
        self._update_status()
        self._fill_tree()
        if self.mode == "through_bolt":
            self._show_tb_view()
        elif self._view == "results":
            self.show_results()
        else:
            self._refresh_view()

    def change_language(self, code: str) -> None:
        if code == language():
            return
        settings().setValue("language", code)
        if not self._confirm_discard():
            self.language_box.setCurrentIndex(self.language_box.findData(language()))
            return
        # the window is built again in the new language, on the same project
        args = [sys.executable, "-m", "openfemconex.gui.main"]
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        if self.state.path is not None:
            args.append(str(self.state.path))
        self.state.dirty = False
        QProcess.startDetached(args[0], args[1:])
        self.close()

    def show_help(self, topic: int = 0) -> None:
        HelpDialog(self, topic).exec()

    def _build_status(self) -> None:
        self.status_label = QLabel()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.progress)

    # ------------------------------------------------------------------ state updates
    def _on_loaded(self) -> None:
        units = str(self.state.get("info", "units", "SI_kN_m"))
        edition = self.state.settings.edition
        for units_box, edition_box in ((self.units_box, self.edition_box),
                                       (self.tb_units_box, self.tb_edition_box)):
            units_box.setCurrentText(units)
            edition_box.setCurrentIndex(max(0, edition_box.findData(edition)))
        self.log.clear()
        self._current_combo = None
        self._view = "model"
        if self.mode == "through_bolt" and 0 <= self.tb.index < len(self.state.connections()):
            self.set_mode("through_bolt", self.tb.index)  # same project, new units
        elif self.mode == "through_bolt" or not self.state.has_base_plate:
            self._select_first()

    def _on_changed(self) -> None:
        self.setWindowTitle(self.state.title())
        self._update_status()
        self._fill_tree()
        if self._view == "model":
            self._refresh_timer.start()

    def _on_results(self) -> None:
        names = list(self.state.reports)
        current = self.combo_box.currentText()
        self.combo_box.clear()
        self.combo_box.addItems(names)
        if current in names:
            self.combo_box.setCurrentText(current)
        self._fill_checks()
        self._fill_anchor_forces()
        self._fill_tree()
        self._update_status()

    def _update_status(self) -> None:
        st = self.state
        if self.mode == "through_bolt":
            text, color = self.tb.status()
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"color: {color};" if color else "")
            self.solve_button.setEnabled(False)
            return
        if not st.valid:
            text, color = tr("Datos no válidos: {error}", error=st.error), "#d03040"
        elif st.stale:
            text, color = tr("Los resultados están desactualizados: cambió la geometría, las "
                             "cargas o los ajustes. Vuelva a resolver."), "#d08020"
        elif st.reports:
            worst = max((r for rep in st.reports.values() for r in rep.fem_checks),
                        key=lambda r: r.ratio / r.ratio_limit, default=None)
            ok = all(r.status.value != "ng" for rep in st.reports.values()
                     for r in rep.fem_checks)
            text = tr("Cumple" if ok else "No cumple") + (
                ". " + tr("Gobierna: {check}, ratio {ratio} ({combo})", check=check_title(worst),
                          ratio=f"{worst.ratio:.2f}", combo=worst.combo) if worst else "")
            color = "#2e9e4f" if ok else "#d03040"
        else:
            text, color = tr("Listo. Sin resultados: use Análisis › Resolver."), ""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};" if color else "")
        self.solve_button.setEnabled(st.valid and self.worker is None)

    def _fill_tree(self) -> None:
        st = self.state
        self.tree.clear()
        top = QTreeWidgetItem([f"{tr('Proyecto')}: {st.get('info', 'name', '')}"])
        top.setData(0, Qt.ItemDataRole.UserRole, ("info", ""))
        self.tree.addTopLevelItem(top)
        if st.has_base_plate:
            root = QTreeWidgetItem(top, [tr("Placa base")])
            root.setIcon(0, type_icon("base_plate"))
            root.setData(0, Qt.ItemDataRole.UserRole, ("connection", -1))
            self._fill_base_plate(root)
            root.setExpanded(self.mode == "base_plate")
            if self.mode == "base_plate":
                self._bold(root)
        for i, conn in enumerate(st.connections()):
            self._fill_tb(top, i, conn)
        top.setExpanded(True)

    @staticmethod
    def _bold(item: QTreeWidgetItem) -> None:
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

    def _fill_tb(self, top: QTreeWidgetItem, index: int, conn: dict) -> None:
        current = self.mode == "through_bolt" and self.tb.index == index
        item = QTreeWidgetItem(top, [f"{conn.get('name', '?')} · {type_title(conn['type'])}"])
        item.setIcon(0, type_icon(conn["type"]))
        item.setToolTip(0, tb_summary(conn))
        item.setData(0, Qt.ItemDataRole.UserRole, ("connection", index))
        if current:
            self._bold(item)
        geometry = QTreeWidgetItem(item, [tr("Geometría") + ": " + tb_summary(conn)])
        pages = ["Viga", "Placa de extremo",
                 "Viga opuesta" if conn.get("opposite") else "Placa posterior",
                 "Muro o columna", "Cortante"]
        for name in pages:
            child = QTreeWidgetItem(geometry, [tr(name)])
            child.setData(0, Qt.ItemDataRole.UserRole, ("tb_page", (index, name)))
        loads = QTreeWidgetItem(item, [tr("Combinaciones")])
        loads.setData(0, Qt.ItemDataRole.UserRole, ("tb_loads", index))
        results = self.tb.results if current else []
        try:
            names = [c.name for c in tb_combinations(conn, self.state.units)]
        except Exception:  # the cases are being edited
            names = []
        for name in names:
            res = next((r for r in results if r.combo.name == name), None)
            if res is None or res.worst is None:
                text, color = tr("sin calcular"), "#888888"
            else:
                text = tr("ratio máx. {ratio}", ratio=f"{res.worst.ratio:.2f}") + (
                    tr(" (desactualizado)") if self.tb.stale else "")
                color = "#2e9e4f" if res.ok else "#d03040"
            child = QTreeWidgetItem(loads, [f"{name}: {text}"])
            child.setForeground(0, QColor(color))
            child.setData(0, Qt.ItemDataRole.UserRole, ("tb_checks", index))
        item.setExpanded(current)

    def _fill_base_plate(self, root: QTreeWidgetItem) -> None:
        st = self.state
        geometry = QTreeWidgetItem(root, [tr("Geometría")])
        bp = st.data.get("base_plate", {})
        summary = {
            "Columna": (tr("cruciforme {main} + {cross}", main=st.column_label(),
                           cross=st.ext("column").get("cross", "?"))
                        if (st.ext("column") or {}).get("type") == "cruciform"
                        else st.column_label()),
            "Placa": " × ".join(str(bp.get(k, "?")) for k in ("N", "B", "tp")),
            "Anclajes": (f"{len(st.ext('anchors'))} {tr('por coordenadas')}" if st.ext("anchors")
                         else tr("{n} de {d}", n=2 * int(bp.get("rods_per_side", 2)),
                                 d=bp.get("rod_diameter", "?"))),
            "Concreto": f"f'c = {bp.get('fc', '?')}",
            "Soldadura": ("CJP" if st.ext("column_weld") == "cjp"
                          else str(bp.get("flange_weld", tr("filete mínimo")))),
            "Refuerzo del pedestal": ", ".join(filter(None, [
                tr("{n} barras de {d}", n=st.ext("pedestal").get("bars", "?"),
                   d=st.ext("pedestal").get("bar_diameter", "?"))
                if st.ext("pedestal") else "",
                tr("horquillas en U") if st.ext("hairpins") else ""])) or tr("ninguno"),
            "Rigidizadores": (tr(str(st.ext("stiffeners").get("layout")))
                              if st.ext("stiffeners") else tr("ninguno")),
            "Llave de cortante": (tr(str(bp["shear_lug"].get("direction", "strong")))
                                  if bp.get("shear_lug") else tr("ninguno")),
        }
        for name, text in summary.items():
            item = QTreeWidgetItem(geometry, [f"{tr(name)}: {text}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("section", name))
        loads = QTreeWidgetItem(root, [tr("Cargas")])
        loads.setData(0, Qt.ItemDataRole.UserRole, ("loads", ""))
        for case in st.data.get("cases", []):
            item = QTreeWidgetItem(loads, [f"{case.get('name')} ({case.get('type')})"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("loads", ""))
        analysis = QTreeWidgetItem(root, [tr("Combinaciones")])
        if st.valid:
            for combo, _ in st.study().combinations():
                rep = st.reports.get(combo.name)
                if rep is None:
                    text, color = tr("sin resolver"), "#888888"
                elif not rep.results.converged:
                    text, color = tr("no convergió"), "#d03040"
                else:
                    worst = max((r.ratio / r.ratio_limit for r in rep.fem_checks), default=0.0)
                    ok = all(r.status.value != "ng" for r in rep.fem_checks)
                    text = (tr("ratio máx. {ratio}", ratio=f"{worst:.2f}")
                            + (tr(" (desactualizado)") if st.stale else ""))
                    color = "#2e9e4f" if ok else "#d03040"
                item = QTreeWidgetItem(analysis, [f"{combo.name}: {text}"])
                item.setForeground(0, QColor(color))
                item.setData(0, Qt.ItemDataRole.UserRole, ("combo", combo.name))
        for i in range(root.childCount()):
            root.child(i).setExpanded(True)

    def _fill_checks(self) -> None:
        self.checks.setRowCount(0)
        if not self.state.valid:
            return
        units = display_units(self.state.project.info)
        self._check_rows = []
        for name, rep in self.state.reports.items():
            for r in rep.fem_checks:
                row = self.checks.rowCount()
                self.checks.insertRow(row)
                ok = r.status.value != "ng"
                state = tr({"ok": "Cumple", "ng": "No cumple"}.get(r.status.value, "No rige"))
                cells = [name, check_title(r), fmt(r.demand, r.kind, units),
                         fmt(r.capacity, r.kind, units),
                         f"{r.ratio:.2f}" if r.applicable else "—", state, r.clause]
                for c, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if c in (2, 3, 4):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                              | Qt.AlignmentFlag.AlignVCenter)
                    if c in (4, 5):
                        item.setForeground(QColor("#888888" if not r.applicable else
                                                  "#2e9e4f" if ok else "#d03040"))
                    self.checks.setItem(row, c, item)
                self._check_rows.append((name, r))

    def _fill_anchor_forces(self) -> None:
        """Axial force (tension +) and shear of every anchor, per combination."""
        table = self.anchor_forces
        table.setRowCount(0)
        if not self.state.valid:
            return
        units = display_units(self.state.project.info)
        F, L = Kind.FORCE, Kind.LENGTH
        for name, rep in self.state.reports.items():
            for i, a in enumerate(rep.results.anchors, start=1):
                row = table.rowCount()
                table.insertRow(row)
                cells = [name, str(i), fmt(a.x, L, units), fmt(a.y, L, units),
                         fmt(a.tension, F, units), fmt(a.Vx, F, units), fmt(a.Vy, F, units),
                         fmt((a.Vx**2 + a.Vy**2) ** 0.5, F, units),
                         fmt(a.uplift, Kind.THICKNESS, units, 3)]
                for c, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if c >= 2:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                              | Qt.AlignmentFlag.AlignVCenter)
                    table.setItem(row, c, item)

    # ------------------------------------------------------------------ navigation
    def _ribbon_tab(self, name: str) -> None:
        self.central.setCurrentWidget(self.loads if name == "Cargas" else self.viewer)
        if name == "Geometría":
            if self.properties.currentWidget() not in self.pages.values():
                self.properties.setCurrentWidget(self.pages["Columna"])
            self.show_model(self._edges)
        elif name == "Análisis":
            self.properties.setCurrentWidget(self.analysis_panel)
            self.bottom.setCurrentWidget(self.log)
        elif name in ("Verificación", "Reporte"):
            self.show_checks()

    def _tree_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, name = data
        if kind == "connection":
            if name < 0:
                if self.mode != "base_plate":
                    self.set_mode("base_plate")
            elif self.mode != "through_bolt" or self.tb.index != name:
                self.set_mode("through_bolt", name)
            return
        if kind.startswith("tb_"):
            index = name[0] if kind == "tb_page" else name
            if self.mode != "through_bolt" or self.tb.index != index:
                self.set_mode("through_bolt", index)
            if kind == "tb_page":
                self.tb_ribbon.select("Geometría")
                self.show_tb_page(name[1])
            elif kind == "tb_loads":
                self.tb_ribbon.select("Cargas")
            else:
                self.tb_ribbon.select("Verificación")
            return
        if kind == "info":
            if self.mode == "through_bolt":
                self.show_tb_page("Identificación")
            else:
                self.show_section("Ficha")
            return
        if self.mode != "base_plate":
            self.set_mode("base_plate")
        if kind == "section":
            self.ribbon.select("Geometría")
            self.show_section(name)
        elif kind == "loads":
            self.ribbon.select("Cargas")
        elif kind == "combo" and name in self.state.reports:
            self.ribbon.select("Análisis")
            self.show_results(name)

    def show_section(self, name: str) -> None:
        self.properties.setCurrentWidget(self.pages[name])

    def _sync_cjp(self) -> None:
        self.cjp.blockSignals(True)
        self.cjp.setChecked(self.state.ext("column_weld") == "cjp")
        self.cjp.blockSignals(False)

    def edit_sections(self) -> None:
        SectionsDialog(self.state, self).exec()

    def edit_materials(self) -> None:
        MaterialsDialog(self.state, self).exec()

    def show_analysis_settings(self) -> None:
        self.properties.setCurrentWidget(self.analysis_panel)

    def show_checks(self) -> None:
        self.bottom.setCurrentWidget(self.checks)
        self.properties.setCurrentWidget(self.detail)
        if self.checks.rowCount() and not self.checks.selectedItems():
            self.checks.selectRow(0)
        elif not self.checks.rowCount():
            self.detail.setHtml(tr("<p>No hay verificaciones todavía. Resuelva el modelo en la "
                                   "pestaña Análisis.</p>"))

    # ------------------------------------------------------------------ 3D
    def _ensure_mesh(self) -> bool:
        st = self.state
        if not st.valid:
            return False
        if st.mesh is None:
            try:
                st.mesh = st.study().mesh(st.model)
            except Exception as exc:
                self.log.appendPlainText(tr("No se pudo mallar: {error}", error=exc))
                self.status_label.setText(tr("No se pudo mallar: {error}", error=exc))
                return False
            m = st.mesh
            self.analysis_panel.info.setText(
                tr("Malla actual: {nodes} nodos y {elements} hexaedros (tamaño fino {size}).",
                   nodes=len(m.nodes), elements=m.element_count,
                   size=fmt(m.settings.size_fine, Kind.THICKNESS, st.units, 3)))
            if m.settings.fast:
                self.analysis_panel.info.setText(self.analysis_panel.info.text() + " "
                                                 + tr("Malla rápida."))
        return True

    def show_model(self, edges: bool = False) -> None:
        self._view, self._edges = "model", edges
        self._refresh_view(reset=True)

    def _refresh_view(self, reset: bool = False) -> None:
        if self._view != "model" or not self._ensure_mesh():
            return
        st = self.state
        self.viewer.show_model(st.model, st.mesh, self._edges, reset=reset,
                               length=st.study().length_text,
                               numbers=bool(st.extras.anchors))

    def show_results(self, combo: str | None = None) -> None:
        st = self.state
        name = combo or self.combo_box.currentText() or self._current_combo
        if not name or name not in st.reports:
            return
        vtu = st.output_dir() / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', name)}.vtu"
        if not vtu.exists() or st.model is None:
            return
        first = self._view != "results"
        self._view, self._current_combo = "results", name
        self.combo_box.setCurrentText(name)
        self.central.setCurrentWidget(self.viewer)
        units = display_units(st.project.info)
        sample = fmt(1000.0, Kind.FORCE, units, 6).split()
        self.viewer.show_results(vtu, st.model, st.reports[name].results,
                                 self.field_box.currentData(), self.scale_box.value(),
                                 unit_force=float(sample[0]) / 1000.0, force_label=sample[-1],
                                 reset=first)

    # ------------------------------------------------------------------ analysis
    def solve(self) -> None:
        st = self.state
        if self.worker is not None or not self._ensure_mesh():
            return
        try:
            find_ccx(st.settings.ccx)
        except CcxError as exc:
            QMessageBox.warning(self, "CalculiX", str(exc))
            return
        selected = set(self.loads.selected())
        combos = [(c, ld) for c, ld in st.study().combinations() if c.name in selected]
        if not combos:
            QMessageBox.information(self, tr("Resolver"),
                                    tr("Marque al menos una combinación en la pestaña Cargas."))
            return
        out = st.output_dir()
        out.mkdir(parents=True, exist_ok=True)
        st.clear_results()
        self.bottom.setCurrentWidget(self.log)
        self.log.appendPlainText(
            tr("Malla: {nodes} nodos, {elements} hexaedros. Salida: {out}",
               nodes=len(st.mesh.nodes), elements=st.mesh.element_count, out=out))
        self.worker = SolveWorker(st.study(), combos, out, st.model, st.mesh)
        self.worker.started_combo.connect(self._combo_started)
        self.worker.combo_done.connect(self._combo_done)
        self.worker.combo_failed.connect(
            lambda n, msg: self.log.appendPlainText(tr("{name}: falló. {msg}", name=n, msg=msg)))
        self.worker.combo_warning.connect(
            lambda n, msg: self.log.appendPlainText(tr("Aviso: {msg}", msg=msg)))
        self.worker.cancelled.connect(self._cancelled)
        self.worker.stage.connect(lambda _n, text: self.solve_progress.stage(text))
        self.worker.combo_failed.connect(
            lambda n, msg: self.solve_progress.combo_finished(
                tr("{name}: falló. {msg}", name=n, msg=msg)))
        self.worker.finished.connect(self._solve_finished)
        self._cancelled_run = False
        self._done, self._total = 0, len(combos)
        self.solve_progress.start(len(combos), st.mesh.element_count, len(st.mesh.nodes),
                                  st.settings.threads)
        self.progress.setValue(0)
        self.progress.show()
        self.stop_button.setEnabled(True)
        self.solve_button.setEnabled(False)
        self._progress_timer.start()
        self.worker.start()

    def stop(self) -> None:
        if getattr(self, "tb_worker", None) is not None:
            self.stop_tb()
        if self.worker is not None:
            self.worker.cancel.set()
            self.log.appendPlainText(tr("Deteniendo CalculiX…"))

    def _cancelled(self) -> None:
        self._cancelled_run = True
        self.log.appendPlainText(tr("Análisis detenido."))

    def show_progress(self) -> None:
        self.solve_progress.show()
        self.solve_progress.raise_()

    def _combo_started(self, name: str) -> None:
        self._running = name
        self.log.appendPlainText(tr("{name}: resolviendo con CalculiX…", name=name))
        sta = self.state.output_dir() / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', name)}.sta"
        self.solve_progress.combo_started(name, sta)

    def _poll_progress(self) -> None:
        if self.worker is None and getattr(self, "tb_worker", None) is None:
            return
        if not self.solve_progress.isVisible():
            self.solve_progress.poll()
        self.progress.setValue(int(100 * self.solve_progress.overall()))

    def _combo_done(self, name: str, report: object) -> None:
        self._done += 1
        res = report.results
        units = display_units(self.state.project.info)
        worst = max(report.fem_checks, key=lambda r: r.ratio / r.ratio_limit, default=None)
        summary = (
            f"{name}: " + (tr("convergió") if res.converged else
                           tr("NO convergió ({pct} % de la carga)",
                              pct=f"{100 * res.load_fraction:.0f}"))
            + tr(" en {s} s. Tracción total en anclajes {t}, compresión {c}, equilibrio {e} %.",
                 s=f"{res.solver.get('seconds', 0):.0f}",
                 t=fmt(res.anchor_tension_total, Kind.FORCE, units),
                 c=fmt(res.bearing_force, Kind.FORCE, units),
                 e=f"{100 * res.equilibrium_error:.2f}")
            + (tr(" Gobierna {check}: {ratio}.", check=check_title(worst),
                  ratio=f"{worst.ratio:.2f}") if worst else ""))
        if self.state.mesh is not None and self.state.mesh.settings.fast:
            summary += " " + tr("(malla rápida)")
        self.log.appendPlainText(summary)
        self.solve_progress.combo_finished(summary)
        self.state.set_report(name, report)
        self.show_results(name)

    def _solve_finished(self) -> None:
        self.solve_progress.finished(self._cancelled_run)
        self._progress_timer.stop()
        self.progress.hide()
        self.worker = None
        self._running = None
        self.stop_button.setEnabled(False)
        self._update_status()

    # ------------------------------------------------------------------ checks and report
    def _check_selected(self) -> None:
        rows = {i.row() for i in self.checks.selectedItems()}
        if not rows or not self.state.valid:
            return
        name, r = self._check_rows[min(rows)]
        units = display_units(self.state.project.info)
        lines = "".join(
            f"<tr><td>{escape(plain_math(s.symbol))}</td>"
            f"<td>{escape(plain_math(s.expression))}</td>"
            f"<td align='right'>{escape(fmt(s.value, s.kind, units))}</td></tr>" for s in r.steps)
        ok = r.status.value != "ng"
        verdict = (tr("cumple") if ok else tr("no cumple")) if r.applicable else tr("no rige")
        color = ("#2e9e4f" if ok else "#d03040") if r.applicable else "#888888"
        why = ""
        if not r.applicable and r.id.startswith("anchor.reinforcement"):
            why = ("<p>" + escape(tr(
                "No rige: ninguna barra del pedestal está a menos de 0.5·hef de un anclaje en "
                "tracción; rige el arrancamiento del concreto.")) + "</p>")
        tips = ""
        rep = self.state.reports.get(name)
        if rep is not None and r.id in rep.advice and r.applicable:
            tips = ("<h4>" + tr("Recomendaciones") + "</h4><ul>"
                    + "".join(f"<li>{escape(a)}</li>" for a in rep.advice[r.id]) + "</ul>"
                    + "<p><small>" + escape(tr(
                        "Cambios posibles para que cumpla, uno a la vez; los valores son "
                        "estimaciones: vuelva a resolver después de cambiar los datos."))
                    + "</small></p>")
        self.detail.setHtml(
            f"<h3>{escape(check_title(r))}</h3><p>"
            + escape(tr("Combinación {name}. Referencia: {clause}.", name=name, clause=r.clause))
            + "</p><p>" + tr("Demanda {d}, capacidad {c}, ratio <b>{r}</b>:",
                             d=escape(fmt(r.demand, r.kind, units)),
                             c=escape(fmt(r.capacity, r.kind, units)), r=f"{r.ratio:.2f}")
            + f" <span style='color:{color}'>{verdict}</span>.</p>" + why + tips
            +
            f"<table cellspacing='0' cellpadding='4' border='1'><tr><th>{tr('Símbolo')}</th>"
            f"<th>{tr('Expresión')}</th><th>{tr('Valor')}</th></tr>{lines}</table>"
            "<p><small>" + tr("El reporte completo muestra las fórmulas con notación matemática.")
            + "</small></p>")

    def _report_html(self, traces: bool = True, figure_base: str = "") -> str | None:
        st = self.state
        if not st.reports or not st.valid:
            QMessageBox.information(self, tr("Reporte"), tr("Primero resuelva el modelo."))
            return None
        reports = list(st.reports.values())
        figures = self._report_figures(reports)
        return st.study().report_html(reports, st.model, st.mesh, traces=traces,
                                      figures=figures, figure_base=figure_base)

    def _report_figures(self, reports: list) -> dict:
        """Figures of the report; why they are missing goes to the solver log."""
        st = self.state
        if self.viewer.plotter is None:
            self.log.appendPlainText(tr("Reporte sin gráficos: el visor 3D (OpenGL) no está "
                                        "disponible."))
            return {}
        if not self._ensure_mesh():
            return {}
        self.status_label.setText(tr("Generando los gráficos del reporte…"))
        QApplication.processEvents()
        study = st.study()
        figures = study.figures(st.output_dir(), reports, st.model, st.mesh)
        for error in study.figure_errors:
            self.log.appendPlainText(tr("No se pudieron generar los gráficos del reporte: "
                                        "{error}", error=error))
        return figures

    def generate_report(self) -> Path | None:
        html = self._report_html()
        if html is None:
            return None
        path = self.state.output_dir() / "reporte.html"
        path.write_text(html, encoding="utf-8")
        self.log.appendPlainText(tr("Reporte escrito en {path}", path=path))
        self.status_label.setText(tr("Reporte escrito en {path}", path=path))
        return path

    def open_report(self) -> None:
        path = self.generate_report()
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def export_docx(self, path: str | None = None) -> Path | None:
        st = self.state
        if not st.reports or not st.valid:
            QMessageBox.information(self, tr("Reporte"), tr("Primero resuelva el modelo."))
            return None
        if not path:
            default = str(st.output_dir() / "reporte.docx")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar Word"), default,
                                                  "Word (*.docx)")
        if not path:
            return None
        reports = list(st.reports.values())
        figures = self._report_figures(reports)
        out = st.study().report_docx(Path(path), reports, st.model, st.mesh, figures,
                                     st.output_dir())
        self.log.appendPlainText(tr("Word escrito en {path}", path=out))
        self.status_label.setText(tr("Word escrito en {path}", path=out))
        return out

    def export_pdf(self, path: str | None = None) -> Path | None:
        # a file URL: a Windows path (C:\\...) is not a valid image source for QTextDocument
        base = QUrl.fromLocalFile(str(self.state.output_dir())).toString() + "/"
        html = self._report_html(traces=False, figure_base=base)
        if html is None:
            return None
        if not path:
            default = str(self.state.output_dir() / "reporte.pdf")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar PDF"), default, "PDF (*.pdf)")
        if not path:
            return None
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        document = QTextDocument()
        document.setHtml(html.replace('width="470"', 'width="330"')
                         .replace('width="940"', 'width="660"'))
        document.print_(printer)
        self.log.appendPlainText(tr("PDF escrito en {path}", path=path))
        return Path(path)

    # ------------------------------------------------------------------ files
    def _confirm_discard(self) -> bool:
        if not self.state.dirty:
            return True
        answer = QMessageBox.question(
            self, tr("Cambios sin guardar"),
            tr("El proyecto tiene cambios sin guardar. ¿Descartarlos?"),
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return answer == QMessageBox.StandardButton.Discard

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        picker = ConnectionPicker(self, title="Nuevo proyecto")
        if not picker.exec() or not picker.selected:
            return
        self.tb.index = -1
        self.state.new(picker.selected)
        self._select_first()

    def open_project(self, path: str | None = None) -> None:
        if not path:
            if not self._confirm_discard():
                return
            path, _ = QFileDialog.getOpenFileName(self, tr("Abrir proyecto"), "",
                                                  tr("Proyecto OpenConex (*.ocnx *.json)"))
        if not path:
            return
        try:
            self.state.open(path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Abrir proyecto"),
                                 tr("No se pudo abrir {path}:\n{error}", path=path, error=exc))
            return
        self.tb.index = -1
        self._select_first()
        (self.tb_ribbon if self.mode == "through_bolt" else self.ribbon).select("Geometría")

    def save_project(self) -> None:
        if self.state.path is None:
            self.save_project_as()
        else:
            self.state.save()

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar proyecto"), "",
                                              tr("Proyecto OpenConex (*.ocnx)"))
        if path:
            self.state.save(path if path.endswith(".ocnx") else path + ".ocnx")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.worker is not None:
            self.worker.cancel.set()
            self.worker.wait(5000)
        if getattr(self, "tb_worker", None) is not None:
            self.tb_worker.cancel.set()
            self.tb_worker.wait(5000)
        if not self._confirm_discard():
            event.ignore()
            return
        self.viewer.close_plotter()
        event.accept()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    set_language(str(settings().value("language", "es")))
    app.setApplicationName("OpenFEMConex")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    if len(argv) > 1 and Path(argv[1]).exists():
        window.open_project(argv[1])
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
