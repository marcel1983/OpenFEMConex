# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Panels of a moment end-plate connection: data forms, loads, checks and traces.

Built on the widgets of the through-bolt connection (same forms, loads editor,
checks table and trace); only the pages of data, the load columns and the
calculation are its own.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from openconex.core.materials import ELECTRODES
from openconex.units import Kind
from PySide6.QtCore import Signal

from openfemconex import end_plate_project as epp
from openfemconex.gui.loads import CaseColumn
from openfemconex.gui.through_bolt_panel import (
    FemWorker,
    TBField,
    TBForm,
    TBLoadsPanel,
    ThroughBoltEditor,
    ThroughBoltLoads,
    _get,
)

__all__ = ["EndPlateEditor", "EPField", "PAGES"]

FORCE = {"pretension", "gravity_shear", "column_axial", "column_shear"}
THICKNESS = {"thickness", "stiffener_thickness", "web_weld", "flange_weld",
             "weld_reinforcement", "continuity_plate", "continuity_plate_weld",
             "doubler_plate", "doubler_weld"}


@dataclass(frozen=True)
class EPField(TBField):
    def quantity_kind(self) -> Kind:
        if self.key in FORCE:
            return Kind.FORCE
        if self.key == "gravity_load":
            return Kind.FORCE_PER_LENGTH
        if self.key in THICKNESS:
            return Kind.THICKNESS
        return Kind.LENGTH


EP = ("end_plate",)
CS = ("column_side",)
SE = ("seismic",)
F = EPField
PAGES: dict[str, list[TBField]] = {
    "Identificación": [
        F(("name",), "Nombre de la conexión", "name", tip="Por ejemplo: PE-1, eje B-3"),
    ],
    "Viga": [
        F(("beam",), "Perfil", "beam", tip="Perfiles W, M, S y HP del catálogo AISC"),
        F(("beam_grade",), "Acero", "steel"),
        F(("span",), "Luz libre entre caras de columna",
          tip="Diseño sísmico (rótula plástica) y clasificación por rigidez"),
        F(("curve_connection_only",), "Curva M-θ solo de la conexión (sin la zona de panel)",
          "bool", tip="Sin marcar, la rotación de la curva incluye la distorsión de la zona "
                      "de panel de la columna; el reporte muestra las dos curvas"),
    ],
    "Columna": [
        F(("column",), "Perfil", "beam", tip="La viga se une al ala (eje fuerte)"),
        F(("column_grade",), "Acero", "steel"),
    ],
    "Placa de extremo": [
        F(EP + ("layout",), "Disposición", "choice",
          tuple((k.value, v) for k, v in epp.LAYOUTS.items())),
        F(EP + ("width",), "Ancho bp"),
        F(EP + ("thickness",), "Espesor tp"),
        F(EP + ("grade",), "Acero", "steel"),
        F(EP + ("gage",), "Gramil g"),
        F(EP + ("pf",), "pf,i (cara interior del ala a la primera fila)"),
        F(EP + ("pb",), "pb (paso entre filas)",
          tip="Disposiciones con dos o más filas dentro del ala, y entre las dos filas "
              "exteriores de la 8ES"),
        F(EP + ("pf_o",), "pf,o (cara exterior del ala a la fila exterior)",
          tip="Placas extendidas"),
        F(EP + ("pext",), "Extensión más allá del ala", tip="Placas extendidas"),
        F(EP + ("ps_o",), "ps,o (fila exterior al rigidizador)",
          tip="Al ras con rigidizador entre las filas"),
        F(EP + ("stiffener_thickness",), "Espesor del rigidizador entre filas",
          tip="Al ras con rigidizador entre las filas"),
        F(EP + ("ps",), "ps (fila al rigidizador)", tip="Al ras con rigidizador interior"),
        F(EP + ("symmetric",), "Mismo patrón en las dos alas (momento reversible)", "bool",
          tip="Sin marcar: solo dos pernos en el ala comprimida"),
    ],
    "Pernos": [
        F(EP + ("bolt_diameter",), "Diámetro"),
        F(EP + ("bolt_grade",), "Grado", "bolt"),
        F(EP + ("bolt_threads",), "Rosca", "choice",
          (("N", "Incluida en el plano de corte (N)"), ("X", "Excluida (X)"))),
        F(EP + ("snug_tight",), "Ajustados sin pretensión (snug-tight)", "bool",
          tip="La fuerza de pretensión de la acción de palanca es una fracción de la de "
              "la tabla J3.1"),
        F(EP + ("pretension",), "Pretensión Tb",
          tip="Vacío: la de la tabla J3.1 de AISC 360-22"),
    ],
    "Soldaduras": [
        F(("electrode",), "Electrodo", "choice", tuple((k, k) for k in ELECTRODES)),
        F(EP + ("flange_weld",), "Filete de las alas",
          tip="Vacío: soldadura de penetración completa"),
        F(EP + ("weld_reinforcement",), "Filete de refuerzo de la CJP",
          tip="Alas con penetración completa: N = tf + 2w en el alma de la columna"),
        F(EP + ("web_weld",), "Filete del alma (cada lado)",
          tip="Vacío: soldadura de penetración completa"),
    ],
    "Rigidización de la columna": [
        F(CS + ("continuity_plate",), "Espesor de las placas de continuidad",
          tip="Un par a la altura de cada ala de la viga; vacío: sin placas"),
        F(CS + ("continuity_plate_width",), "Ancho de cada placa",
          tip="Vacío: (bf − tw)/2 de la columna"),
        F(CS + ("continuity_plate_weld",), "Filete de las placas a las alas",
          tip="Vacío: penetración completa"),
        F(CS + ("doubler_plate",), "Espesor de la placa doble",
          tip="Vacío: sin placa doble"),
        F(CS + ("doubler_weld",), "Filete de la placa doble a las alas",
          tip="Vacío: penetración completa"),
        F(CS + ("two_sided",), "Vigas a ambos lados de la columna", "bool",
          tip="Revisa el pandeo del alma por compresión (§J10.5)"),
        F(CS + ("column_near_end",), "Cerca del extremo de la columna", "bool",
          tip="Fuerza del ala a menos de d de la columna de su extremo (§J10)"),
        F(CS + ("panel_zone",), "Revisar la zona de panel", "bool",
          tip="Con el cortante de piso Vc y la carga axial Pc de cada caso de carga"),
        F(CS + ("panel_zone_inelastic",), "Deformación de la zona de panel considerada",
          "bool", tip="En el análisis de estabilidad (§J10.6, Ec. J10-11 y J10-12)"),
    ],
    "Diseño sísmico": [
        F(SE + ("system",), "Sistema", "choice",
          (("smf", "Pórtico especial (SMF)"), ("imf", "Pórtico intermedio (IMF)"))),
        F(SE + ("gravity_load",), "Carga de gravedad factorada en la viga",
          tip="1.2D + f1 L + 0.15S, fuerza por longitud"),
        F(SE + ("gravity_shear",), "Cortante de gravedad adicional en la rótula"),
        F(SE + ("column_axial",), "Carga axial de la columna (compresión)",
          tip="Para la relación columna-viga"),
        F(SE + ("column_above",), "La columna sigue arriba del nudo", "bool"),
        F(SE + ("stiffener_thickness",), "Espesor del rigidizador de la extensión",
          tip="BSEEP (4ES y 8ES)"),
        F(SE + ("column_shear",), "Cortante de piso de la columna Vc",
          tip="Se resta del cortante de la zona de panel (SMF)"),
        F(SE + ("column_height_above",), "Altura al punto de inflexión arriba",
          tip="Proyecta los momentos de columna al eje de la viga (SMF)"),
        F(SE + ("column_height_below",), "Altura al punto de inflexión abajo"),
    ],
}
NOTES = {
    "Placa de extremo": "pf,i, pf,o y pb se miden desde las caras del ala de la viga, como "
                        "en las Guías de Diseño 4 y 16; vea los esquemas en la ayuda.",
    "Rigidización de la columna": "Con placas de continuidad, las revisiones del alma de la "
                                  "columna no aplican y la flexión del ala usa el mecanismo "
                                  "rigidizado.",
    "Diseño sísmico": "Conexión precalificada AISC 358-22 capítulo 6: 4E (BUEEP), 4ES y 8ES "
                      "(BSEEP). Usa la luz libre de la viga (página Viga). Es diseño por "
                      "capacidad: no depende de las combinaciones.",
}


class EPForm(TBForm):
    TOGGLES = {"Diseño sísmico": ("seismic", "Conexión sísmica precalificada (AISC 358)",
                                  epp.SEISMIC)}
    NOTES = NOTES

    def _enable(self, data: dict[str, Any]) -> None:
        layout = str(_get(data, EP + ("layout",)) or "")
        extended = layout.startswith("extended")
        pitch = layout not in ("flush_2", "extended_4", "extended_4_stiffened")
        cjp = not _get(data, EP + ("flange_weld",))
        rules = {
            EP + ("pf_o",): extended, EP + ("pext",): extended, EP + ("pb",): pitch,
            EP + ("ps_o",): layout == "flush_4_stiffened_between",
            EP + ("stiffener_thickness",): layout == "flush_4_stiffened_between",
            EP + ("ps",): layout == "flush_4_stiffened_inside",
            EP + ("pretension",): not _get(data, EP + ("snug_tight",)),
            EP + ("weld_reinforcement",): cjp,
            CS + ("panel_zone_inelastic",): bool(_get(data, CS + ("panel_zone",))),
        }
        seismic = bool(data.get("seismic"))
        bseep = layout in ("extended_4_stiffened", "extended_8_stiffened")
        if seismic:
            rules[SE + ("stiffener_thickness",)] = bseep
        for path, on in rules.items():
            if path in self.widgets:
                self.widgets[path].setEnabled(on)
        if self.toggle is not None:
            prequalified = bool(layout) and epp.prequalified(layout) is not None
            self.toggle.setEnabled(prequalified or seismic)


class EndPlateLoads(ThroughBoltLoads):
    """Cases and combinations of the end-plate connection being edited (LRFD or ASD)."""

    columns = (CaseColumn("V", "V"), CaseColumn("M", "M", Kind.MOMENT), CaseColumn("P", "P"),
               CaseColumn("Vc", "Vc"), CaseColumn("Pc", "Pc"))
    methods = epp.METHODS
    result_heads = ("V", "M", "P", "Vc", "Pc")

    def combinations(self):
        from openfemconex.load_cases import load_combinations

        data = self.editor.data
        combos = {c.name: c for c in load_combinations(data.get("cases") or [],
                                                       self.options(), self.methods)}
        out = []
        for c in epp.combinations(data, self.units):
            values = [(getattr(c, k), Kind.MOMENT if k.startswith("M") else Kind.FORCE)
                      for k in self.result_heads]
            out.append((combos[c.name], values))
        return out

    def hidden(self) -> set[str]:
        panel = bool(_get(self.editor.data, CS + ("panel_zone",)))
        return set() if panel else {"Vc", "Pc"}


class EPLoadsPanel(TBLoadsPanel):
    """The Loads tab of an end-plate connection."""

    def __init__(self, editor: EndPlateEditor) -> None:
        super(TBLoadsPanel, self).__init__(EndPlateLoads(editor), intro=(
            "Casos de carga de servicio de la viga en la cara de la columna: las "
            "combinaciones ASCE 7 (LRFD o ASD) se generan de sus tipos y se pueden editar o "
            "agregar propias. M positivo con tracción arriba, P positiva en compresión; Vc y "
            "Pc son el cortante de piso y la carga axial de la columna, solo para la zona de "
            "panel. Un número sin unidad se toma en las unidades del proyecto."))
        self.result_heads_hidden()

    def result_heads_hidden(self) -> None:
        panel = bool(_get(self.source.editor.data, CS + ("panel_zone",)))
        heads = [self.combos.horizontalHeaderItem(i).text()
                 for i in range(self.combos.columnCount())]
        for i, head in enumerate(heads):
            if head in ("Vc", "Pc"):
                self.combos.setColumnHidden(i, not panel)


class EndPlateEditor(ThroughBoltEditor):
    """The widgets of the end-plate connection selected in the project tree."""

    PAGES = PAGES
    FORM = EPForm
    LOADS = EPLoadsPanel

    def __init__(self, state) -> None:
        super().__init__(state)
        self.seismic: list = []
        self.curve = None
        """Moment-rotation curve (end_plate_fem.MomentRotation) of the last solution."""

    @staticmethod
    def load(data: dict[str, Any]) -> dict[str, Any]:
        return data

    def connection(self):
        return epp.build(self.data, self.state.units)

    def combination_list(self) -> list:
        return epp.combinations(self.data, self.state.units)

    def curve_panel_zone(self) -> bool:
        """Whether the moment-rotation curve includes the panel zone."""
        return not self.data.get("curve_connection_only")

    def span(self) -> float:
        """Beam span between column faces [mm]."""
        return epp._Reader(self.state.units).q(self.data.get("span"), Kind.LENGTH)

    def set_curve(self, curve) -> None:
        self.curve = curve
        self.results_changed.emit()

    def run(self) -> list:
        self.curve = None
        res = epp.run(self.data, self.state.units)
        self.seismic = res.seismic
        out = list(res.combos)
        if res.seismic:
            out.append(epp.ComboResult(epp.Combination(epp.SEISMIC_COMBO), res.seismic))
        return out

    def end_plate_results(self) -> epp.EndPlateResults:
        combos = [r for r in self.results if r.combo.name != epp.SEISMIC_COMBO]
        return epp.EndPlateResults(combos, self.seismic, self.curve)

    def _report_args(self) -> tuple:
        return (self.data, self.end_plate_results(), self.state.units,
                self.state.data.get("info", {}))

    def report_html(self, figure_base: str = "", help_figures: bool | str = True,
                    fem_figures: dict | None = None, picture: bool = True) -> str:
        folder = help_figures if isinstance(help_figures, str) else (
            self.help_dir() if help_figures else "")
        return epp.report_html(*self._report_args(), figures=folder, figure_base=figure_base,
                               picture=picture, fem_figures=fem_figures)

    def report_docx(self, path, figure_dir, fem_figures: dict | None = None,
                    picture: bool = True):
        return epp.report_docx(path, figure_dir, *self._report_args(),
                               figures=self.help_dir(), picture=picture,
                               fem_figures=fem_figures)

    def summary(self) -> str:
        return epp.summary(self.data)

    @staticmethod
    def new(name: str) -> dict[str, Any]:
        return copy.deepcopy(epp.new_connection(name))


class EndPlateFemWorker(FemWorker):
    """The CalculiX runs of an end-plate connection: the ticked combinations and then,
    always, the moment-rotation curve."""

    curve_done = Signal(object)
    curve_failed = Signal(str)

    def __init__(self, conn, combos: list, out, edition, *, span: float, all_combos: list,
                 panel_zone: bool = True, **kwargs) -> None:
        from openfemconex import end_plate_fem as epf

        super().__init__(conn, combos, out, edition, solver=epf.solve_combination, **kwargs)
        self.span, self.all_combos, self.panel_zone = span, all_combos, panel_zone

    def run(self) -> None:
        from openfemconex import end_plate_fem as epf
        from openfemconex.runner import CcxCancelled

        super().run()
        if self.cancel.is_set():
            return
        try:
            curve = epf.moment_rotation(
                self.conn, self.span, self.all_combos, self.out, ccx=self.ccx,
                threads=self.threads, cancel=self.cancel, fast=self.fast,
                settings=self.settings, panel_zone=self.panel_zone,
                started=lambda name, sta: self.started_combo.emit(name, str(sta)),
                progress=lambda text: self.stage.emit(f"{epf.CURVE}: {text}"))
        except CcxCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.curve_failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.curve_done.emit(curve)
