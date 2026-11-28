# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""The main-window part of the moment end-plate connection.

A mixin of :class:`openfemconex.gui.main.MainWindow`: its ribbon (the same stages as
the other connection types), the pages of data in the Properties dock, the 3D view,
the analytic calculation behind "Resolver", the report and its branch of the
project tree. The window keeps one :class:`EndPlateEditor` in ``self.ep`` and edits
it while ``self.mode`` is ``moment_end_plate``.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from openconex.report.builder import fmt
from openconex.units import Kind
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QComboBox, QFileDialog, QMessageBox, QTreeWidgetItem

from openfemconex import end_plate_project as epp
from openfemconex.gui.connection_picker import type_icon, type_title
from openfemconex.gui.help import about, topics
from openfemconex.gui.icons import icon
from openfemconex.gui.ribbon import Ribbon
from openfemconex.gui.stages import (
    StageActions,
    add_analysis_tab,
    add_loads_tab,
    add_report_tab,
)
from openfemconex.gui.viewer import FIELDS
from openfemconex.i18n import tr
from openfemconex.runner import CcxError, find_ccx

MODE = epp.TYPE
"""``MainWindow.mode`` while an end-plate connection is edited."""

GEOMETRY_PAGES = (("Viga", "column"), ("Columna", "column"), ("Placa de extremo", "plate"),
                  ("Pernos", "anchor"), ("Soldaduras", "weld"),
                  ("Rigidización de la columna", "stiffener"), ("Diseño sísmico", "check"))


class EndPlateWindow:
    """Ribbon, pages, view, calculation, report and tree of the end-plate connection."""

    # ------------------------------------------------------------------ construction
    def _build_ep_ribbon(self) -> None:
        self.ep_ribbon = Ribbon()
        self.ribbons.addWidget(self.ep_ribbon)
        tab = self.ep_ribbon.add_tab("Proyecto")
        g = tab("Archivo")
        g.add_button("Nuevo", icon("new"), self.new_project)
        g.add_button("Abrir", icon("open"), self.open_project)
        g.add_button("Guardar", icon("save"), self.save_project)
        g.add_button("Guardar como", icon("save"), self.save_project_as)
        self._connections_group(tab)
        g = tab("Unidades y normas")
        from openfemconex.gui.panels import unit_presets

        self.ep_units_box = QComboBox()
        self.ep_units_box.addItems(unit_presets())
        self.ep_units_box.textActivated.connect(self.state.set_units)
        g.add_widget("Unidades de presentación", self.ep_units_box)

        tab = self.ep_ribbon.add_tab("Geometría")
        g = tab("Componentes")
        for name, pic in GEOMETRY_PAGES:
            g.add_button(name, icon(pic), lambda n=name: self.show_ep_page(n))
        g = tab("Vista")
        g.add_button("Modelo", icon("view"), lambda: self._show_ep_view(reset=True))

        actions = StageActions(
            cases=lambda: (self.central.setCurrentWidget(self.ep.combinations),
                           self.ep.combinations.cases.setFocus()),
            combinations=lambda: (self.central.setCurrentWidget(self.ep.combinations),
                                  self.ep.combinations.combos.setFocus()),
            edit_combinations=lambda: self.ep.combinations.open_editor(),
            settings=self.show_analysis_settings,
            solve=self.solve_ep, stop=self.stop_ep, progress=self.show_progress,
            generate=self.generate_ep_report, open_report=self.open_ep_report,
            pdf=self.export_ep_pdf, docx=self.export_ep_docx,
            ficha=lambda: self.show_ep_page("Identificación"),
            settings_tip="Tamaño de malla, malla rápida, capas, hilos de CalculiX y límite de "
                         "deformación plástica (los mismos de la placa base)",
            solve_tip="Calcula las verificaciones de AISC 360-22, las Guías de Diseño 16 y 4 "
                      "y, si es sísmica, AISC 358-22 para todas las combinaciones, y resuelve "
                      "con CalculiX las combinaciones marcadas en Cargas: placa, pernos "
                      "pretensados, ala de la columna y soldaduras",
            ficha_tip="Nombre de la conexión; el proyecto, cliente e ingeniero son los del "
                      "proyecto")
        add_loads_tab(self.ep_ribbon, actions)
        buttons = add_analysis_tab(self.ep_ribbon, actions)
        self.ep_solve_button, self.ep_stop_button = buttons.solve, buttons.stop
        g = buttons.results
        self.ep_fem_box = QComboBox()
        self.ep_fem_box.setMinimumWidth(170)
        self.ep_fem_box.textActivated.connect(self.show_ep_fem)
        g.add_widget("Combinación", self.ep_fem_box)
        self.ep_field_box = QComboBox()
        for name in FIELDS:
            self.ep_field_box.addItem(tr(name), name)
        self.ep_field_box.activated.connect(lambda _: self.show_ep_fem())
        g.add_widget("Resultado", self.ep_field_box)
        tab = self.ep_ribbon.add_tab("Verificación")
        g = tab("Verificaciones")
        g.add_button("Resumen", icon("check"), self.show_ep_checks)
        add_report_tab(self.ep_ribbon, actions)
        tab = self.ep_ribbon.add_tab("Ayuda")
        g = tab("Ayuda")
        g.add_button("Placa de extremo", icon("help"), lambda: self.show_help(self._ep_topic()),
                     "Configuraciones, camino de las fuerzas y estados límite de esta "
                     "conexión")
        g.add_button("Manual", icon("help"), self.show_help)
        g.add_button("Acerca de", icon("info"), lambda: about(self))
        self.ep_ribbon.tab_changed.connect(self._ep_ribbon_tab)

    def _add_ep_widgets(self) -> None:
        """The pages and the trace in the Properties dock, the checks in the bottom one."""
        for page in self.ep.pages.values():
            self.properties.addWidget(page)
        self.properties.addWidget(self.ep.trace)
        self.bottom.addTab(self.ep.checks, tr("Verificaciones"))

    # ------------------------------------------------------------------ pages and view
    def show_ep_page(self, name: str) -> None:
        self.properties.setCurrentWidget(self.ep.pages[name])
        if self.central.currentWidget() is not self.viewer:
            self.central.setCurrentWidget(self.viewer)

    def _ep_ribbon_tab(self, name: str) -> None:
        if self.mode != MODE:
            return
        self.central.setCurrentWidget(self.ep.combinations if name == "Cargas"
                                      else self.viewer)
        if name in ("Geometría", "Proyecto"):
            if self.properties.currentWidget() not in self.ep.pages.values():
                self.properties.setCurrentWidget(self.ep.pages["Placa de extremo"])
        elif name == "Análisis":
            self.properties.setCurrentWidget(self.analysis_panel)
            self.bottom.setCurrentWidget(self.log)
        elif name in ("Verificación", "Reporte"):
            self.show_ep_checks()

    def _show_ep_view(self, reset: bool = False) -> None:
        if self.mode != MODE or self.ep.index < 0:
            return
        self._view = "ep"
        self._update_status()
        try:
            mc = self.ep.connection()
        except Exception:
            return
        self.viewer.show_end_plate(mc, reset=reset)

    def show_ep_checks(self) -> None:
        self.bottom.setCurrentWidget(self.ep.checks)
        self.properties.setCurrentWidget(self.ep.trace)
        if self.ep.checks.rowCount() and not self.ep.checks.selectedItems():
            self.ep.checks.selectRow(0)

    def _on_ep_results(self) -> None:
        current = self.ep_fem_box.currentText()
        labels = [label for label, _ in self.ep.fem_sides()]
        self.ep_fem_box.clear()
        self.ep_fem_box.addItems(labels)
        if current in labels:
            self.ep_fem_box.setCurrentText(current)
        self._update_status()
        self._fill_tree()

    def show_ep_fem(self, label: str | None = None) -> None:
        """Results of the CalculiX model of one combination in the 3D view."""
        sides = dict(self.ep.fem_sides())
        label = label or self.ep_fem_box.currentText()
        side = sides.get(label)
        if side is None or side.vtu is None or not side.vtu.exists():
            return
        self.ep_fem_box.setCurrentText(label)
        self.central.setCurrentWidget(self.viewer)
        self._view = "ep_fem"
        sample = fmt(1000.0, Kind.FORCE, self.state.units, 6).split()
        self.viewer.show_results(side.vtu, side.model, side.results,
                                 str(self.ep_field_box.currentData()), 20.0,
                                 unit_force=float(sample[0]) / 1000.0, force_label=sample[-1],
                                 reset=True, face="front")

    def _ep_topic(self) -> int:
        for i, (_, text) in enumerate(topics()):
            if "openfemconex.end_plate_project" in text:
                return i
        return 0

    # ------------------------------------------------------------------ calculation
    def solve_ep(self) -> None:
        """Analytic checks of every combination (and the AISC 358 block), then CalculiX
        for the combinations checked in Cargas."""
        from openfemconex import end_plate_fem as epf
        from openfemconex.checks import EDITIONS
        from openfemconex.gui.through_bolt_panel import FemWorker
        from openfemconex.model import MeshSettings

        if getattr(self, "ep_worker", None) is not None:
            return
        if not self.ep.calculate():
            QMessageBox.warning(self, tr("Resolver"), tr("No se pudo calcular: {error}",
                                                          error=self.ep.error))
            return
        n = len([r for r in self.ep.results if r.combo.name != epp.SEISMIC_COMBO])
        self.log.appendPlainText(tr("Placa de extremo: {n} combinaciones calculadas.", n=n))
        self.show_ep_checks()
        try:
            find_ccx(self.state.settings.ccx)
        except CcxError as exc:
            QMessageBox.warning(self, "CalculiX", tr(
                "Verificaciones analíticas listas; el modelo CalculiX no se resolvió: "
                "{error}", error=exc))
            return
        chosen = set(self.ep.combinations.selected())
        combos = [c for c in self.ep.combination_list() if c.name in chosen]
        if not combos:
            self.ep_ribbon.select("Verificación")
            QMessageBox.information(self, tr("Resolver"), tr(
                "Verificaciones analíticas listas. Marque en Cargas las combinaciones que "
                "se resuelven con CalculiX."))
            return
        st = self.state.settings
        mesh = MeshSettings(size_fine=st.size, plate_layers=st.layers, fast=st.fast)
        worker = FemWorker(self.ep.connection(), combos, self.ep.fem_dir(),
                           EDITIONS["current"], st.ccx, st.fast, st.threads,
                           settings=mesh, strain_limit=st.strain_limit,
                           solver=epf.solve_combination)
        worker.stage.connect(self._tb_stage)
        worker.started_combo.connect(self._tb_combo_started)
        worker.combo_done.connect(self._ep_combo_done)
        worker.combo_failed.connect(self._tb_combo_failed)
        worker.cancelled.connect(self._cancelled)
        worker.finished.connect(self._ep_solve_finished)
        self.ep_worker = worker
        self._cancelled_run = False
        self.ep_solve_button.setEnabled(False)
        self.ep_stop_button.setEnabled(True)
        self._sync_panel()
        self.bottom.setCurrentWidget(self.log)
        self.log.appendPlainText(tr("{n} combinaciones con CalculiX ({mesh}, {t} hilos). "
                                    "Salida: {out}", n=len(combos), t=st.threads,
                                    out=self.ep.fem_dir(),
                                    mesh=tr("malla rápida") if st.fast else tr("malla normal")))
        axial = any(c.P > 0 for c in combos)  # then two load steps
        self.solve_progress.start(len(combos), 0, 0, st.threads, steps=2 if axial else 1)
        self.progress.setValue(0)
        self.progress.show()
        self._progress_timer.start()
        worker.start()

    def _ep_combo_done(self, name: str, sides: list) -> None:
        self._tb_combo_done(name, sides, self.ep)

    def stop_ep(self) -> None:
        if getattr(self, "ep_worker", None) is not None:
            self.ep_worker.cancel.set()
            self.log.appendPlainText(tr("Deteniendo CalculiX…"))

    def _ep_solve_finished(self) -> None:
        self.ep_worker = None
        self.solve_progress.finished(self._cancelled_run)
        self._progress_timer.stop()
        self.ep_solve_button.setEnabled(True)
        self.ep_stop_button.setEnabled(False)
        self._sync_panel()
        self.progress.hide()
        self._update_status()
        if self.ep.fem_sides():
            self.ep_ribbon.select("Análisis")
            self.show_ep_fem(self.ep.fem_sides()[0][0])
            self.show_ep_checks()

    # ------------------------------------------------------------------ report
    def _ep_report_ready(self) -> bool:
        if not self.ep.results or self.ep.stale:
            if not self.ep.calculate():
                QMessageBox.warning(self, tr("Reporte"), tr("No se pudo calcular: {error}",
                                                             error=self.ep.error))
                return False
        return True

    def _ep_report_dir(self) -> Path:
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(self.ep.data.get("name", "conexion")))
        folder = self.state.output_dir() / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _ep_picture(self, folder: Path) -> bool:
        if self.viewer.plotter is None:
            return False
        self._show_ep_view(reset=True)
        try:
            self.viewer.screenshot(folder / "conexion.png")
        except Exception:  # no OpenGL context: the report goes without the picture
            return False
        return True

    def _ep_fem_figures(self, folder: Path) -> dict:
        """Figures of the CalculiX models (model, mesh, stresses, strains, displacements
        and contact pressure) rendered into ``folder``."""
        from PySide6.QtWidgets import QApplication

        from openfemconex.scenes import render_through_bolt_figures

        sides = [s for _, s in self.ep.fem_sides()]
        if not sides:
            return {}
        if self.viewer.plotter is None:
            self.log.appendPlainText(tr("Reporte sin gráficos: el visor 3D (OpenGL) no está "
                                        "disponible."))
            return {}
        self.status_label.setText(tr("Generando los gráficos del reporte…"))
        QApplication.processEvents()
        sample = fmt(1000.0, Kind.FORCE, self.state.units, 6).split()
        errors: list[str] = []
        figures = render_through_bolt_figures(folder, sides, unit_force=float(sample[0]) / 1000.0,
                                              force_label=sample[-1], errors=errors)
        for error in errors:
            self.log.appendPlainText(tr("No se pudieron generar los gráficos del reporte: "
                                        "{error}", error=error))
        return figures

    def generate_ep_report(self) -> Path | None:
        if not self._ep_report_ready():
            return None
        folder = self._ep_report_dir()
        picture = self._ep_picture(folder)
        figures = self._ep_fem_figures(folder)
        help_dir = folder / "esquemas"
        help_dir.mkdir(exist_ok=True)
        for png in Path(self.ep.help_dir()).glob("placa_extremo_*.png"):
            shutil.copy2(png, help_dir / png.name)
        html = self.ep.report_html(figure_base="", help_figures="esquemas", picture=picture,
                                   fem_figures=figures)
        path = folder / "reporte.html"
        path.write_text(html, encoding="utf-8")
        self.status_label.setText(tr("Reporte escrito en {path}", path=path))
        return path

    def open_ep_report(self) -> None:
        path = self.generate_ep_report()
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def export_ep_docx(self, path: str | None = None) -> Path | None:
        if not self._ep_report_ready():
            return None
        folder = self._ep_report_dir()
        if not path:
            default = str(folder / "reporte.docx")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar Word"), default,
                                                  "Word (*.docx)")
        if not path:
            return None
        picture = self._ep_picture(folder)
        out = self.ep.report_docx(Path(path), folder, picture=picture,
                                  fem_figures=self._ep_fem_figures(folder))
        self.log.appendPlainText(tr("Word escrito en {path}", path=out))
        self.status_label.setText(tr("Word escrito en {path}", path=out))
        return out

    def export_ep_pdf(self, path: str | None = None) -> Path | None:
        if not self._ep_report_ready():
            return None
        folder = self._ep_report_dir()
        if not path:
            default = str(folder / "reporte.pdf")
            path, _ = QFileDialog.getSaveFileName(self, tr("Exportar PDF"), default, "PDF (*.pdf)")
        if not path:
            return None
        picture = self._ep_picture(folder)
        base = QUrl.fromLocalFile(str(folder.resolve())).toString() + "/"
        html = self.ep.report_html(figure_base=base, picture=picture,
                                   fem_figures=self._ep_fem_figures(folder))
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

    # ------------------------------------------------------------------ project tree
    def _fill_ep(self, top: QTreeWidgetItem, index: int, conn: dict) -> None:
        current = self.mode == MODE and self.ep.index == index
        item = QTreeWidgetItem(top, [f"{conn.get('name', '?')} · {type_title(conn['type'])}"])
        item.setIcon(0, type_icon(conn["type"]))
        item.setToolTip(0, epp.summary(conn))
        item.setData(0, Qt.ItemDataRole.UserRole, ("connection", index))
        if current:
            self._bold(item)
        geometry = QTreeWidgetItem(item, [tr("Geometría") + ": " + epp.summary(conn)])
        for name, _ in GEOMETRY_PAGES:
            if name == "Diseño sísmico" and not conn.get("seismic"):
                continue
            child = QTreeWidgetItem(geometry, [tr(name)])
            child.setData(0, Qt.ItemDataRole.UserRole, ("ep_page", (index, name)))
        loads = QTreeWidgetItem(item, [tr("Combinaciones")])
        loads.setData(0, Qt.ItemDataRole.UserRole, ("ep_loads", index))
        results = self.ep.results if current else []
        try:
            names = [c.name for c in epp.combinations(conn, self.state.units)]
        except Exception:  # the cases are being edited
            names = []
        if conn.get("seismic"):
            names.append(epp.SEISMIC_COMBO)
        for name in names:
            res = next((r for r in results if r.combo.name == name), None)
            if res is None or res.worst is None:
                text, color = tr("sin calcular"), "#888888"
            else:
                text = tr("ratio máx. {ratio}", ratio=f"{res.worst.ratio:.2f}") + (
                    tr(" (desactualizado)") if self.ep.stale else "")
                color = "#2e9e4f" if res.ok else "#d03040"
            child = QTreeWidgetItem(loads, [f"{name}: {text}"])
            child.setForeground(0, QColor(color))
            child.setData(0, Qt.ItemDataRole.UserRole, ("ep_checks", index))
        item.setExpanded(current)

    def _ep_tree_clicked(self, kind: str, name) -> None:
        index = name[0] if kind == "ep_page" else name
        if self.mode != MODE or self.ep.index != index:
            self.set_mode(MODE, index)
        if kind == "ep_page":
            self.ep_ribbon.select("Geometría")
            self.show_ep_page(name[1])
        elif kind == "ep_loads":
            self.ep_ribbon.select("Cargas")
        else:
            self.ep_ribbon.select("Verificación")
