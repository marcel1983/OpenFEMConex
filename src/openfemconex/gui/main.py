# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Main window: ribbon by stage, project tree, 3D view, properties and solver log."""

from __future__ import annotations

import re
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
from openfemconex.gui.help import HelpDialog, about
from openfemconex.gui.icons import app_icon, icon
from openfemconex.gui.panels import (
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
from openfemconex.gui.ribbon import STYLE as RIBBON_STYLE
from openfemconex.gui.ribbon import Ribbon
from openfemconex.gui.state import ProjectState
from openfemconex.gui.theme import apply_theme, settings
from openfemconex.gui.viewer import FIELDS, Viewer
from openfemconex.gui.worker import SolveWorker
from openfemconex.i18n import LANGUAGES, language, set_language, tr
from openfemconex.report import check_title
from openfemconex.runner import CcxError, find_ccx

EDITION_LABELS = {"current": "AISC 360-22 / ACI 318-19", "dg1-2ed": "DG1 2nd ed. (360-05 / 318-08)"}
_LATEX = [(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)"), (r"\\sqrt\{([^{}]*)\}", r"√(\1)"),
          (r"\\left|\\right|\\,|\\ ", " "), (r"\\phi", "φ"), (r"\\psi", "ψ"), (r"\\mu", "μ"),
          (r"\\pi", "π"), (r"\\theta", "θ"), (r"\\Omega", "Ω"), (r"\\varepsilon", "ε"),
          (r"\\lambda", "λ"), (r"\\le", "≤"), (r"\\ge", "≥"), (r"\\min", "min"),
          (r"\\max", "max"), (r"\\sin", "sin"), (r"[{}]", ""), (r"\\", "")]


def plain_math(latex: str) -> str:
    """Readable text for a LaTeX fragment (the full report uses MathML)."""
    text = re.sub(r"([_^])\{([^{}]*)\}", r"\1\2", latex)
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
        self.worker: SolveWorker | None = None
        self._view = "model"
        self._edges = False
        self._current_combo: str | None = None
        self.setWindowIcon(app_icon())
        self.resize(1500, 920)

        self.viewer = Viewer()
        self.loads = LoadsPanel(self.state)
        self.central = QStackedWidget()
        self.central.addWidget(self.viewer)
        self.central.addWidget(self.loads)
        self.setCentralWidget(self.central)

        self._build_docks()
        self._build_ribbon()
        self._build_status()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self._refresh_view)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(500)
        self._progress_timer.timeout.connect(self._poll_progress)

        self.state.changed.connect(self._on_changed)
        self.state.results_changed.connect(self._on_results)
        self.state.loaded.connect(self._on_loaded)
        self._on_loaded()
        self._on_changed()
        self._on_results()
        apply_theme(self.dark)
        self.viewer.set_dark(self.dark)

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
        additions = {"Anclajes": self.anchor_table}
        for name, fields in SECTIONS.items():
            self.forms[name] = FormPanel(self.state, name, fields)
            page = QWidget()
            box = QVBoxLayout(page)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(self.forms[name])
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.addWidget(self.pedestal_form)
        box.addWidget(note)
        box.addStretch(1)
        scroll.setWidget(holder)
        self.pages["Refuerzo del pedestal"] = scroll
        self.properties.addWidget(scroll)
        self.analysis_panel = AnalysisPanel(self.state)
        self.properties.addWidget(self.analysis_panel)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.properties.addWidget(self.detail)
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
        bottom = QDockWidget(tr("Resultados"), self)
        bottom.setObjectName("dockBottom")
        bottom.setWidget(self.bottom)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom)
        self.resizeDocks([left, right], [270, 400], Qt.Orientation.Horizontal)
        self.resizeDocks([bottom], [250], Qt.Orientation.Vertical)

    def _build_ribbon(self) -> None:
        self.ribbon = Ribbon()
        self.setMenuWidget(self.ribbon)

        tab = self.ribbon.add_tab("Proyecto")
        g = tab("Archivo")
        g.add_button("Nuevo", icon("new"), self.new_project)
        g.add_button("Abrir", icon("open"), self.open_project)
        g.add_button("Guardar", icon("save"), self.save_project)
        g.add_button("Guardar como", icon("save"), self.save_project_as)
        g = tab("Unidades y normas")
        self.units_box = QComboBox()
        self.units_box.addItems(unit_presets())
        self.units_box.textActivated.connect(lambda t: self.state.set("info", "units", t))
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
        g = tab("Vista")
        g.add_button("Modelo", icon("view"), lambda: self.show_model(False))
        g.add_button("Malla", icon("mesh"), lambda: self.show_model(True))

        tab = self.ribbon.add_tab("Cargas")
        g = tab("Cargas")
        g.add_button("Casos", icon("load"), lambda: self.loads.cases.setFocus())
        g.add_button("Combinaciones", icon("combo"), lambda: self.loads.combos.setFocus())

        tab = self.ribbon.add_tab("Análisis")
        g = tab("Malla")
        g.add_button("Ajustes", icon("table"), self.show_analysis_settings)
        g.add_button("Generar malla", icon("mesh"), lambda: self.show_model(True))
        g = tab("CalculiX")
        self.solve_button = g.add_button("Resolver", icon("play"), self.solve,
                                         "Resuelve las combinaciones marcadas en Cargas")
        self.stop_button = g.add_button("Detener", icon("stop"), self.stop)
        self.stop_button.setEnabled(False)
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
        tab = self.ribbon.add_tab("Ayuda")
        g = tab("Ayuda")
        g.add_button("Manual", icon("help"), self.show_help,
                     "Manual de uso, verificaciones y validación")
        g.add_button("Acerca de", icon("info"), lambda: about(self))
        self.ribbon.tab_changed.connect(self._ribbon_tab)
        self.ribbon.select("Geometría")

    # ------------------------------------------------------------------ appearance and help
    def set_dark(self, dark: bool) -> None:
        self.dark = bool(dark)
        apply_theme(self.dark)
        self.viewer.set_dark(self.dark)
        self.ribbon.setStyleSheet(RIBBON_STYLE)  # re-resolve the palette() colours
        settings().setValue("dark", self.dark)
        self._update_status()
        self._fill_tree()
        if self._view == "results":
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
        self.units_box.setCurrentText(str(self.state.get("info", "units", "SI_kN_m")))
        self.edition_box.setCurrentIndex(max(0, self.edition_box.findData(
            self.state.settings.edition)))
        self.log.clear()
        self._current_combo = None
        self._view = "model"

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
        root = QTreeWidgetItem([str(st.get("info", "name", "Proyecto"))])
        self.tree.addTopLevelItem(root)
        geometry = QTreeWidgetItem(root, [tr("Geometría")])
        bp = st.data.get("base_plate", {})
        summary = {
            "Columna": str(bp.get("column", "")),
            "Placa": " × ".join(str(bp.get(k, "?")) for k in ("N", "B", "tp")),
            "Anclajes": (f"{len(st.ext('anchors'))} {tr('por coordenadas')}" if st.ext("anchors")
                         else tr("{n} de {d}", n=2 * int(bp.get("rods_per_side", 2)),
                                 d=bp.get("rod_diameter", "?"))),
            "Concreto": f"f'c = {bp.get('fc', '?')}",
            "Soldadura": str(bp.get("flange_weld", tr("filete mínimo"))),
            "Refuerzo del pedestal": (
                tr("{n} barras de {d}", n=st.ext("pedestal").get("bars", "?"),
                   d=st.ext("pedestal").get("bar_diameter", "?"))
                if st.ext("pedestal") else tr("ninguno")),
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
        self.tree.expandAll()

    def _fill_checks(self) -> None:
        self.checks.setRowCount(0)
        if not self.state.valid:
            return
        units = self.state.project.info.unit_system()
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
        units = self.state.project.info.unit_system()
        F, L = Kind.FORCE, Kind.LENGTH
        for name, rep in self.state.reports.items():
            for i, a in enumerate(rep.results.anchors, start=1):
                row = table.rowCount()
                table.insertRow(row)
                cells = [name, str(i), fmt(a.x, L, units), fmt(a.y, L, units),
                         fmt(a.tension, F, units), fmt(a.Vx, F, units), fmt(a.Vy, F, units),
                         fmt((a.Vx**2 + a.Vy**2) ** 0.5, F, units), f"{a.uplift:.3f} mm"]
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

    def show_analysis_settings(self) -> None:
        self.properties.setCurrentWidget(self.analysis_panel)

    def show_checks(self) -> None:
        self.bottom.setCurrentWidget(self.checks)
        self.properties.setCurrentWidget(self.detail)
        if self.checks.rowCount() and not self.checks.selectedItems():
            self.checks.selectRow(0)
        elif not self.checks.rowCount():
            self.detail.setHtml("<p>No hay verificaciones todavía. Resuelva el modelo en la "
                                "pestaña Análisis.</p>")

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
                tr("Malla actual: {nodes} nodos y {elements} hexaedros (tamaño fino {size} mm).",
                   nodes=len(m.nodes), elements=m.element_count,
                   size=f"{m.settings.size_fine:.1f}"))
        return True

    def show_model(self, edges: bool = False) -> None:
        self._view, self._edges = "model", edges
        self._refresh_view(reset=True)

    def _refresh_view(self, reset: bool = False) -> None:
        if self._view != "model" or not self._ensure_mesh():
            return
        self.viewer.show_model(self.state.model, self.state.mesh, self._edges, reset=reset)

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
        units = st.project.info.unit_system()
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
        self.worker.cancelled.connect(
            lambda: self.log.appendPlainText(tr("Análisis detenido.")))
        self.worker.finished.connect(self._solve_finished)
        self._done, self._total = 0, len(combos)
        self.progress.setValue(0)
        self.progress.show()
        self.stop_button.setEnabled(True)
        self.solve_button.setEnabled(False)
        self._progress_timer.start()
        self.worker.start()

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.cancel.set()

    def _combo_started(self, name: str) -> None:
        self._running = name
        self.log.appendPlainText(tr("{name}: resolviendo con CalculiX…", name=name))

    def _poll_progress(self) -> None:
        name = getattr(self, "_running", None)
        if not name or self.worker is None:
            return
        sta = self.state.output_dir() / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', name)}.sta"
        fraction = 0.0
        if sta.exists():
            lines = [ln.split() for ln in sta.read_text(errors="replace").splitlines()]
            rows = [p for p in lines if len(p) == 7 and p[0].isdigit() and not p[2].endswith("U")]
            if rows:
                step, step_time = int(rows[-1][0]), float(rows[-1][5])
                fraction = (0.1 if step == 1 else 0.1 + 0.9 * step_time) if any(
                    int(r[0]) > 1 for r in rows) or step > 1 else 0.1 * step_time
        self.progress.setValue(int(100 * (self._done + fraction) / max(self._total, 1)))

    def _combo_done(self, name: str, report: object) -> None:
        self._done += 1
        res = report.results
        units = self.state.project.info.unit_system()
        worst = max(report.fem_checks, key=lambda r: r.ratio / r.ratio_limit, default=None)
        self.log.appendPlainText(
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
        self.state.set_report(name, report)
        self.show_results(name)

    def _solve_finished(self) -> None:
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
        units = self.state.project.info.unit_system()
        lines = "".join(
            f"<tr><td>{escape(plain_math(s.symbol))}</td>"
            f"<td>{escape(plain_math(s.expression))}</td>"
            f"<td align='right'>{escape(fmt(s.value, s.kind, units))}</td></tr>" for s in r.steps)
        ok = r.status.value != "ng"
        self.detail.setHtml(
            f"<h3>{escape(check_title(r))}</h3><p>"
            + escape(tr("Combinación {name}. Referencia: {clause}.", name=name, clause=r.clause))
            + "</p><p>" + tr("Demanda {d}, capacidad {c}, ratio <b>{r}</b>:",
                             d=escape(fmt(r.demand, r.kind, units)),
                             c=escape(fmt(r.capacity, r.kind, units)), r=f"{r.ratio:.2f}")
            + f" <span style='color:{'#2e9e4f' if ok else '#d03040'}'>"
            f"{tr('cumple') if ok else tr('no cumple')}</span>.</p>"
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
        figures = {}
        if self.viewer.plotter is not None and self._ensure_mesh():
            self.status_label.setText(tr("Generando los gráficos del reporte…"))
            QApplication.processEvents()
            figures = st.study().figures(st.output_dir(), reports, st.model, st.mesh)
        return st.study().report_html(reports, st.model, st.mesh, traces=traces,
                                      figures=figures, figure_base=figure_base)

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

    def export_pdf(self, path: str | None = None) -> Path | None:
        html = self._report_html(traces=False, figure_base=str(self.state.output_dir()) + "/")
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
        document.setHtml(html.replace('width="470"', 'width="330"'))
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
        if self._confirm_discard():
            self.state.new()

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
        self.ribbon.select("Geometría")

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
