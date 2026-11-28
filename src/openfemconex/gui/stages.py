# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Ribbon stages shared by every connection type: Cargas, Análisis and Reporte.

Every connection type gets the same tabs with the same commands in the same
place; only what each command does is its own. A new type fills a
:class:`StageActions` and calls :func:`add_loads_tab`, :func:`add_analysis_tab` and
:func:`add_report_tab` (see ``docs/conexiones.md``):

* Cargas: load cases, the combinations built from them and the editor of
  combinations (``gui.loads.LoadsEditor`` with a ``LoadsSource`` of the type).
* Análisis: mesh and solver settings (the shared ``AnalysisPanel``), the green
  "Resolver" button that runs the analytical checks and CalculiX, "Detener" and
  the detailed CalculiX progress (``gui.progress.SolveProgress``).
* Reporte: generate, open, PDF and Word, and the identification card.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QPushButton, QToolButton

from openfemconex.gui.icons import icon
from openfemconex.gui.ribbon import Ribbon, RibbonGroup
from openfemconex.i18n import tr

SOLVE_STYLE = """
QToolButton#solveButton, QPushButton#solveButton {
    background: #2e7d32; color: white; font-weight: bold;
    border: 1px solid #1b5e20; border-radius: 4px; padding: 3px 10px;
}
QToolButton#solveButton:hover, QPushButton#solveButton:hover { background: #388e3c; }
QToolButton#solveButton:pressed, QPushButton#solveButton:pressed { background: #1b5e20; }
QToolButton#solveButton:disabled, QPushButton#solveButton:disabled {
    background: palette(midlight); color: palette(mid); border-color: palette(mid);
}
"""
"""The green "Resolver" button, the same in the ribbon and in the Análisis panel."""

SOLVE_TIP = ("Calcula las verificaciones analíticas y resuelve con CalculiX las "
             "combinaciones marcadas en Cargas")


def make_green(button: QToolButton | QPushButton) -> QToolButton | QPushButton:
    button.setObjectName("solveButton")
    button.setStyleSheet(SOLVE_STYLE)
    return button


def solve_push_button(text: str = "Resolver") -> QPushButton:
    """The green "Resolver" button of the Análisis panel."""
    button = QPushButton(icon("play"), tr(text))
    button.setMinimumHeight(34)
    return make_green(button)


@dataclass
class StageActions:
    """What the commands of the shared stages do for one connection type."""

    cases: Callable[[], None]
    combinations: Callable[[], None]
    edit_combinations: Callable[[], None]
    settings: Callable[[], None]
    solve: Callable[[], None]
    stop: Callable[[], None]
    progress: Callable[[], None]
    generate: Callable[[], None]
    open_report: Callable[[], None]
    pdf: Callable[[], None]
    docx: Callable[[], None]
    ficha: Callable[[], None]
    mesh: Callable[[], None] | None = None
    """"Generar malla", for types that can show the mesh before solving."""
    solve_tip: str = SOLVE_TIP
    settings_tip: str = ("Tamaño de malla, malla rápida, capas, hilos de CalculiX y límite de "
                         "deformación plástica")
    ficha_tip: str = "Proyecto, conexión, ingeniero y revisión que encabezan el reporte"


@dataclass
class AnalysisButtons:
    solve: QToolButton
    stop: QToolButton
    results: RibbonGroup
    """The "Resultados" group, for the type's own result selectors."""


def add_loads_tab(ribbon: Ribbon, a: StageActions) -> None:
    g = ribbon.add_tab("Cargas")("Cargas")
    g.add_button("Casos", icon("load"), a.cases)
    g.add_button("Combinaciones", icon("combo"), a.combinations)
    g.add_button("Editar combinaciones", icon("table"), a.edit_combinations,
                 "Combinaciones propias con sus factores, o copia editable de las de ASCE 7")


def add_analysis_tab(ribbon: Ribbon, a: StageActions) -> AnalysisButtons:
    tab = ribbon.add_tab("Análisis")
    g = tab("Malla")
    g.add_button("Ajustes", icon("table"), a.settings, a.settings_tip)
    if a.mesh is not None:
        g.add_button("Generar malla", icon("mesh"), a.mesh)
    g = tab("CalculiX")
    solve = make_green(g.add_button("Resolver", icon("play"), a.solve, a.solve_tip))
    stop = g.add_button("Detener", icon("stop"), a.stop)
    stop.setEnabled(False)
    g.add_button("Avance", icon("table"), a.progress, "Muestra el avance detallado de CalculiX")
    return AnalysisButtons(solve, stop, tab("Resultados"))


def add_report_tab(ribbon: Ribbon, a: StageActions) -> None:
    tab = ribbon.add_tab("Reporte")
    g = tab("Memoria de cálculo")
    g.add_button("Generar", icon("report"), a.generate)
    g.add_button("Abrir", icon("browser"), a.open_report,
                 "Abre el reporte completo en el navegador")
    g.add_button("Exportar PDF", icon("pdf"), a.pdf)
    g.add_button("Exportar Word", icon("report"), a.docx,
                 "Reporte editable en Word (.docx), con los mismos gráficos")
    g = tab("Identificación")
    g.add_button("Ficha", icon("info"), a.ficha, a.ficha_tip)
