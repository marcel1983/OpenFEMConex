# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Moment end-plate connections (beam to column flange) saved in a project file.

An entry of ``openfemconex.connections`` with ``type`` ``moment_end_plate`` holds
the beam, the column, the end plate, the column stiffening, the optional AISC 358
seismic data and the load cases, as texts with units like the rest of the file.

The analytic checks are those of OpenConex (:mod:`openconex.connections.moment`):
end-plate yield lines and bolt forces with prying (AISC Design Guide 16, and
Design Guide 4 for the 8ES plate), the remaining limit states of AISC 360-22 on
the beam side, the column side (flange bending, web yielding, crippling and
buckling, continuity and doubler plates, panel zone) and, when the connection is
seismic, the prequalified BUEEP/BSEEP checks of AISC 358-22 Chapter 6 with AISC
341-22. This module maps the project data to that engine, runs every load
combination and writes the report; the CalculiX model and the moment-rotation
curve are added on top of these results.
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Any

from openconex.connections.moment.end_plate import (
    EXTENDED,
    FLUSH,
    STIFFENED_EXTENSION,
    EndPlate,
    EndPlateLayout,
)
from openconex.connections.moment.fr_moment import (
    FlangeDetail,
    MomentConnection,
    check_moment_connection,
)
from openconex.connections.moment.seismic import (
    Prequalified,
    Seismic,
    SeismicSystem,
    expected_ratios,
    nominal_depth,
    seismic_checks,
)
from openconex.core.checks import CheckResult
from openconex.core.loads import Method
from openconex.core.materials import BOLTS, ELECTRODES, STEELS
from openconex.core.model import BoltSpec, Threads
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, UnitSystem, parse, to_internal

__all__ = ["CASE_KEYS", "LAYOUTS", "METHODS", "TEMPLATE", "TYPE", "Combination",
           "ComboResult", "EndPlateResults", "build", "case_values", "combinations",
           "new_connection", "prequalified", "report_blocks", "report_docx", "report_html",
           "SEISMIC", "run", "summary"]

TYPE = "moment_end_plate"

LAYOUTS: dict[EndPlateLayout, str] = {
    EndPlateLayout.FLUSH_2: "Al ras, 1 fila por ala",
    EndPlateLayout.FLUSH_4: "Al ras, 2 filas por ala",
    EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN: "Al ras, 2 filas, rigidizador entre filas",
    EndPlateLayout.FLUSH_4_STIFFENED_INSIDE: "Al ras, 2 filas, rigidizador interior",
    EndPlateLayout.EXTENDED_4: "Extendida, 4 pernos (4E)",
    EndPlateLayout.EXTENDED_4_STIFFENED: "Extendida rigidizada, 4 pernos (4ES)",
    EndPlateLayout.EXTENDED_1_2: "Extendida multifila 1/2",
    EndPlateLayout.EXTENDED_1_3: "Extendida multifila 1/3",
    EndPlateLayout.EXTENDED_1_3_STIFFENED: "Extendida multifila 1/3 rigidizada",
    EndPlateLayout.EXTENDED_8_STIFFENED: "Extendida rigidizada, 8 pernos (8ES)",
}
"""Every end-plate layout of OpenConex, with its name in the program."""

PREQUALIFIED: dict[EndPlateLayout, Prequalified] = {
    EndPlateLayout.EXTENDED_4: Prequalified.BUEEP,
    EndPlateLayout.EXTENDED_4_STIFFENED: Prequalified.BSEEP,
    EndPlateLayout.EXTENDED_8_STIFFENED: Prequalified.BSEEP,
}
"""Layouts prequalified by AISC 358-22 Chapter 6 for seismic moment frames."""

CASE_KEYS = ("V", "M", "P", "Vc", "Pc")
"""Forces of a load case: beam shear, moment and axial force (positive in compression)
at the column face; story shear and axial force of the column (panel zone)."""

METHODS = ("LRFD", "ASD")
"""Design methods of the analytic checks (the seismic checks are LRFD)."""

SEISMIC_COMBO = "AISC 358"
"""Name of the capacity-design result block."""

TEMPLATE: dict[str, Any] = {
    "type": TYPE,
    "name": "Placa de extremo",
    "beam": "W21X55",
    "beam_grade": "ASTM A992",
    "column": "W14X109",
    "column_grade": "ASTM A992",
    "electrode": "E70XX",
    "span": "30 ft",
    "end_plate": {
        "layout": "extended_4", "bolt_diameter": "1 1/4 in", "bolt_grade": "ASTM F3125 Gr. A490",
        "bolt_threads": "N",
        "width": "9 in", "thickness": "1 1/4 in", "gage": "5 1/2 in", "pf": "2 in",
        "pf_o": "2 in", "pext": "3 5/8 in", "pb": "", "grade": "ASTM A572 Gr. 50",
        "flange_weld": "", "web_weld": "5/16 in", "weld_reinforcement": "5/16 in",
        "snug_tight": False, "symmetric": True,
    },
    "column_side": {
        "continuity_plate": "5/8 in", "continuity_plate_weld": "", "doubler_plate": "",
        "two_sided": False, "column_near_end": False, "panel_zone": False,
        "panel_zone_inelastic": False,
    },
    "seismic": None,
    "cases": [{"name": "U", "type": "D", "V": "40 kip", "M": "8039 kip*in"}],
    "combinations": {"methods": ["LRFD"], "include_code": False,
                     "custom": [{"name": "U", "method": "LRFD", "factors": {"U": 1.0}}]},
}
"""A new connection: AISC Design Guide 4 (2nd ed.) four-bolt extended Example A,
with its factored moment typed as one load case and 5/8 in. continuity plates (the
example uses 1/2 in. plates, thinner than the minimum of Design Guide 13 Eq. 4.3-3)."""

SEISMIC: dict[str, Any] = {
    "system": "smf", "gravity_load": "", "gravity_shear": "", "column_axial": "",
    "column_above": True, "stiffener_thickness": "", "column_shear": "",
    "column_height_above": "", "column_height_below": "",
}
"""Seismic block when the user switches it on (BUEEP for 4E, BSEEP for 4ES and 8ES)."""


def new_connection(name: str = "") -> dict[str, Any]:
    data = copy.deepcopy(TEMPLATE)
    if name:
        data["name"] = name
    return data


def prequalified(layout: EndPlateLayout | str) -> Prequalified | None:
    """AISC 358 connection of a layout, or ``None`` when it is not prequalified."""
    return PREQUALIFIED.get(EndPlateLayout(layout))


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


class _Reader:
    def __init__(self, units: UnitSystem) -> None:
        self.units = units

    def q(self, value: Any, kind: Kind = Kind.LENGTH, default: float | None = None) -> float:
        text = _text(value)
        if not text:
            if default is None:
                raise ValueError("falta un valor")
            return default
        return parse(text, kind, self.units)

    def need(self, block: dict[str, Any], key: str, label: str,
             kind: Kind = Kind.LENGTH) -> float:
        if not _text(block.get(key)):
            raise ValueError(f"falta {label}")
        return self.q(block.get(key), kind)


def _shape(name: str, grade: str, role: str):
    if grade not in STEELS:
        raise ValueError(f"acero desconocido: {grade}")
    try:
        row = aisc_shapes().get(name)
    except Exception as exc:
        raise ValueError(f"perfil no válido para la {role}: {name}") from exc
    if not row.label.upper().startswith(("W", "M", "S", "HP")):
        raise ValueError(f"la {role} debe ser un perfil I: {name}")
    return row, row.to_ishape(grade)


def _end_plate(e: dict[str, Any], r: _Reader) -> EndPlate:
    layout = EndPlateLayout(e.get("layout") or "extended_4")
    grade = e.get("grade") or "ASTM A572 Gr. 50"
    bolt_grade = e.get("bolt_grade") or "ASTM F3125 Gr. A325"
    if grade not in STEELS:
        raise ValueError(f"acero desconocido: {grade}")
    if bolt_grade not in BOLTS:
        raise ValueError(f"grado de perno desconocido: {bolt_grade}")
    steel = STEELS[grade]
    T = Kind.THICKNESS
    pitch = layout not in (EndPlateLayout.FLUSH_2, EndPlateLayout.EXTENDED_4,
                           EndPlateLayout.EXTENDED_4_STIFFENED)
    extended = layout in EXTENDED
    pretension = _text(e.get("pretension"))
    return EndPlate(
        layout=layout,
        bolt=BoltSpec(diameter=r.need(e, "bolt_diameter", "el diámetro de los pernos"),
                      grade=bolt_grade, threads=Threads(e.get("bolt_threads") or "N")),
        width=r.need(e, "width", "el ancho de la placa"),
        thickness=r.need(e, "thickness", "el espesor de la placa", T),
        gage=r.need(e, "gage", "el gramil"),
        pf=r.need(e, "pf", "la distancia p_f del ala a la fila interior"),
        Fy=steel.Fy, Fu=steel.Fu,
        pb=r.need(e, "pb", "el paso p_b entre filas") if pitch else 0.0,
        pf_o=r.need(e, "pf_o", "la distancia p_f,o del ala a la fila exterior")
        if extended else 0.0,
        pext=r.need(e, "pext", "la extensión de la placa") if extended else 0.0,
        ps_o=r.need(e, "ps_o", "la distancia p_s,o al rigidizador")
        if layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN else 0.0,
        stiffener_thickness=r.need(e, "stiffener_thickness", "el espesor del rigidizador", T)
        if layout is EndPlateLayout.FLUSH_4_STIFFENED_BETWEEN else 0.0,
        ps=r.need(e, "ps", "la distancia p_s al rigidizador")
        if layout is EndPlateLayout.FLUSH_4_STIFFENED_INSIDE else 0.0,
        snug_tight=bool(e.get("snug_tight")),
        pretension=r.q(pretension, Kind.FORCE) if pretension else None,
        web_weld=r.q(e.get("web_weld"), T, 0.0),
        flange_weld=r.q(e.get("flange_weld"), T, 0.0),
        weld_reinforcement=r.q(e.get("weld_reinforcement"), T, 0.0),
        symmetric=bool(e.get("symmetric", True)))


def _expected(grade: str, value: Any, plate: bool = False, tensile: bool = False) -> float:
    text = _text(value)
    if text:
        return float(text)
    ratios = expected_ratios(grade, plate)
    if ratios is None:
        raise ValueError(f"AISC 341 no da R_y/R_t para {grade}: escríbalos en los datos "
                         "sísmicos")
    return ratios[1] if tensile else ratios[0]


def _seismic(data: dict[str, Any], s: dict[str, Any], r: _Reader, layout: EndPlateLayout,
             beam_row, column_row, plate_grade: str, continuity: float) -> Seismic:
    connection = prequalified(layout)
    if connection is None:
        raise ValueError(f"la placa {LAYOUTS[layout]} no está precalificada en AISC 358: "
                         "use 4E, 4ES u 8ES para el diseño sísmico")
    if connection is Prequalified.BSEEP and not _text(s.get("stiffener_thickness")):
        raise ValueError("falta el espesor del rigidizador de la extensión (sísmico)")
    weight = to_internal(beam_row["W"] * 9.80665, "N/m", Kind.FORCE_PER_LENGTH)
    beam_grade = data.get("beam_grade") or "ASTM A992"
    column_grade = data.get("column_grade") or "ASTM A992"
    F = Kind.FORCE
    return Seismic(
        connection=connection, system=SeismicSystem(s.get("system") or "smf"),
        span=r.need(data, "span", "la luz libre de la viga entre caras de columna"),
        beam_Zx=beam_row["Zx"], beam_A=beam_row["A"], beam_weight=weight,
        column_Zx=column_row["Zx"], column_A=column_row["A"],
        Ry_beam=_expected(beam_grade, s.get("Ry_beam")),
        Rt_beam=_expected(beam_grade, s.get("Rt_beam"), tensile=True),
        Ry_column=_expected(column_grade, s.get("Ry_column")),
        Ry_plate=_expected(plate_grade, s.get("Ry_plate"), plate=True) if continuity else 1.0,
        gravity_load=r.q(s.get("gravity_load"), Kind.FORCE_PER_LENGTH, 0.0),
        gravity_shear=r.q(s.get("gravity_shear"), F, 0.0),
        column_axial=r.q(s.get("column_axial"), F, 0.0),
        column_above=bool(s.get("column_above", True)),
        beam_depth_label=nominal_depth(beam_row.label),
        column_depth_label=nominal_depth(column_row.label),
        stiffener_thickness=r.q(s.get("stiffener_thickness"), Kind.THICKNESS, 0.0),
        stiffener_Fy=STEELS[plate_grade].Fy,
        column_shear=r.q(s.get("column_shear"), F, 0.0),
        column_height_above=r.q(s.get("column_height_above"), Kind.LENGTH, 0.0),
        column_height_below=r.q(s.get("column_height_below"), Kind.LENGTH, 0.0))


def build(data: dict[str, Any], units: UnitSystem) -> MomentConnection:
    """OpenConex model of one ``moment_end_plate`` entry; ``units`` gives the unit of
    bare numbers."""
    r = _Reader(units)
    beam_row, beam = _shape(data.get("beam", ""), data.get("beam_grade") or "ASTM A992",
                            "viga")
    column_row, column = _shape(data.get("column", ""),
                                data.get("column_grade") or "ASTM A992", "columna")
    e = data.get("end_plate") or {}
    ep = _end_plate(e, r)
    plate_grade = e.get("grade") or "ASTM A572 Gr. 50"
    electrode = data.get("electrode") or "E70XX"
    if electrode not in ELECTRODES:
        raise ValueError(f"electrodo desconocido: {electrode}")
    c = data.get("column_side") or {}
    T = Kind.THICKNESS
    continuity = r.q(c.get("continuity_plate"), T, 0.0)
    seismic = None
    if data.get("seismic"):
        seismic = _seismic(data, data["seismic"], r, ep.layout, beam_row, column_row,
                           plate_grade, continuity)
    return MomentConnection(
        detail=FlangeDetail.END_PLATE, beam=beam, beam_Sx=beam_row["Sx"], column=column,
        end_plate=ep, plate_Fy=ep.Fy, plate_Fu=ep.Fu, FEXX=ELECTRODES[electrode].FEXX,
        continuity_plate=continuity,
        continuity_plate_width=r.q(c.get("continuity_plate_width"), Kind.LENGTH, 0.0),
        continuity_plate_weld=r.q(c.get("continuity_plate_weld"), T, 0.0),
        doubler_plate=r.q(c.get("doubler_plate"), T, 0.0),
        doubler_weld=r.q(c.get("doubler_weld"), T, 0.0),
        two_sided=bool(c.get("two_sided")), column_near_end=bool(c.get("column_near_end")),
        panel_zone=bool(c.get("panel_zone")),
        panel_zone_inelastic=bool(c.get("panel_zone_inelastic")), seismic=seismic)


def _kind(key: str) -> Kind:
    return Kind.MOMENT if key.startswith("M") else Kind.FORCE


@dataclass
class Combination:
    name: str
    method: Method = Method.LRFD
    V: float = 0.0
    M: float = 0.0
    P: float = 0.0
    Vc: float = 0.0
    Pc: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    source: str = ""


@dataclass
class ComboResult:
    combo: Combination
    checks: list[CheckResult] = field(default_factory=list)
    fem: list = field(default_factory=list)
    """CalculiX results, when solved (later phases)."""

    @property
    def all_checks(self) -> list[CheckResult]:
        return self.checks + [c for side in self.fem for c in side.checks]

    @property
    def ok(self) -> bool:
        return all(r.status.value != "ng" for r in self.all_checks)

    @property
    def worst(self) -> CheckResult | None:
        return max((r for r in self.all_checks if r.applicable), key=lambda r: r.ratio,
                   default=None)


@dataclass
class EndPlateResults:
    """Checks of every combination plus, for a seismic connection, the AISC 358 block."""

    combos: list[ComboResult]
    seismic: list[CheckResult] = field(default_factory=list)
    curve: Any = None
    """The moment-rotation curve (``end_plate_fem.MomentRotation``), once solved."""

    @property
    def ok(self) -> bool:
        return (all(r.ok for r in self.combos)
                and all(c.status.value != "ng" for c in self.seismic))

    def all_checks(self) -> list[CheckResult]:
        return [c for r in self.combos for c in r.all_checks] + self.seismic


def case_values(data: dict[str, Any], units: UnitSystem) -> dict[str, dict[str, float]]:
    """Forces of each load case, in N and N·mm."""
    r = _Reader(units)
    return {_text(c.get("name")): {k: r.q(c.get(k), _kind(k), 0.0) for k in CASE_KEYS}
            for c in data.get("cases") or []}


def combinations(data: dict[str, Any], units: UnitSystem) -> list[Combination]:
    """Factored forces of every combination of the load cases."""
    from openfemconex.load_cases import factored, load_combinations

    values = case_values(data, units)
    out = []
    for combo in load_combinations(data.get("cases") or [], data.get("combinations"),
                                   METHODS):
        f = factored(combo, values)
        out.append(Combination(combo.name, combo.method,
                               **{k: f.get(k, 0.0) for k in CASE_KEYS},
                               factors=dict(combo.factors), source=combo.source))
    return out


def run(data: dict[str, Any], units: UnitSystem) -> EndPlateResults:
    """Analytic checks of every combination and, if seismic, the AISC 358 checks."""
    mc = build(data, units)
    out = []
    for combo in combinations(data, units):
        column_shear = combo.Vc if mc.panel_zone else None
        checks = check_moment_connection(mc, combo.V, combo.M, combo.method, combo.name,
                                         column_shear=column_shear,
                                         column_axial=abs(combo.Pc), P=combo.P)
        out.append(ComboResult(combo, checks))
    seismic = seismic_checks(mc) if mc.seismic is not None else []
    return EndPlateResults(out, seismic)


def summary(data: dict[str, Any]) -> str:
    """One line for the project tree."""
    e = data.get("end_plate") or {}
    try:
        layout = LAYOUTS[EndPlateLayout(e.get("layout"))]
    except ValueError:
        layout = str(e.get("layout", "?"))
    seismic = ", sísmica" if data.get("seismic") else ""
    return f"{data.get('beam', '?')} a {data.get('column', '?')}, {layout}{seismic}"


# -- report ----------------------------------------------------------------------------
def _data_rows(data: dict[str, Any], mc: MomentConnection) -> list[list[str]]:
    e, c = data.get("end_plate") or {}, data.get("column_side") or {}
    ep = mc.end_plate
    assert ep is not None
    layout = LAYOUTS[ep.layout]
    welds = []
    welds.append(f"alas con filete de {e.get('flange_weld')}" if _text(e.get("flange_weld"))
                 else "alas con penetración completa"
                 + (f" y refuerzo de {e.get('weld_reinforcement')}"
                    if _text(e.get("weld_reinforcement")) else ""))
    welds.append(f"alma con filete de {e.get('web_weld')} a cada lado"
                 if _text(e.get("web_weld")) else "alma con penetración completa")
    dims = [f"gramil {e.get('gage')}", f"p_f,i {e.get('pf')}"]
    for key, label in (("pb", "p_b"), ("pf_o", "p_f,o"), ("pext", "extensión"),
                       ("ps_o", "p_s,o"), ("ps", "p_s"),
                       ("stiffener_thickness", "rigidizador")):
        if _text(e.get(key)):
            dims.append(f"{label} {e.get(key)}")
    rows = [
        ["Viga", f"{data.get('beam')}, {data.get('beam_grade')}"],
        ["Columna", f"{data.get('column')}, {data.get('column_grade')}; unión al ala"
                    + ("; vigas a ambos lados" if c.get("two_sided") else "")],
        ["Placa de extremo", f"{layout}, {e.get('width')} × {e.get('thickness')}, "
                             f"{e.get('grade')}; " + ", ".join(dims)],
        ["Pernos", f"{e.get('bolt_grade')} de {e.get('bolt_diameter')}, "
                   f"{ep.tension_bolts} en el ala traccionada"
                   + (", ajustados sin pretensión" if ep.snug_tight else ", pretensados")
                   + ("" if ep.symmetric else "; solo 2 pernos en el ala comprimida")],
        ["Soldaduras", f"{data.get('electrode') or 'E70XX'}: " + "; ".join(welds)],
    ]
    stiff = []
    if _text(c.get("continuity_plate")):
        stiff.append(f"placas de continuidad de {c.get('continuity_plate')}")
    if _text(c.get("doubler_plate")):
        stiff.append(f"placa doble de {c.get('doubler_plate')}")
    rows.append(["Columna rigidizada", ", ".join(stiff) if stiff else "No"])
    if data.get("seismic"):
        s = data["seismic"]
        system = "Pórtico especial (SMF)" if (s.get("system") or "smf") == "smf" else \
            "Pórtico intermedio (IMF)"
        conn = prequalified(ep.layout)
        rows.append(["Diseño sísmico", f"{system}, conexión precalificada "
                                       f"{conn.value.upper() if conn else '—'} "
                                       f"(AISC 358-22 cap. 6), luz libre {data.get('span')}"])
    return rows


def _loads_blocks(data: dict[str, Any], results: EndPlateResults, units: UnitSystem,
                  panel: bool) -> list:
    from openconex.report.builder import fmt

    from openfemconex.load_cases import combination_text

    keys = [k for k in CASE_KEYS if panel or k not in ("Vc", "Pc")]
    values = case_values(data, units)
    rows = [[name, str(c.get("type", "")), *[fmt(values[name][k], _kind(k), units)
                                              for k in keys]]
            for c in data.get("cases") or [] for name in [_text(c.get("name"))]]
    combos = [[r.combo.name, r.combo.method.value,
               combination_text(r.combo.factors) if r.combo.factors else "—",
               *[fmt(getattr(r.combo, k), _kind(k), units) for k in keys]]
              for r in results.combos]
    return [
        ("h2", "Cargas"),
        ("p", "Fuerzas de la viga en la cara de la columna: V cortante, M momento, P axial "
              "positiva en compresión"
              + ("; Vc y Pc cortante de piso y axial de la columna para la zona de panel"
                 if panel else "") + ".", ""),
        ("table", ["Caso", "Tipo", *keys], rows, set()),
        ("table", ["Combinación", "Método", "Factores", *keys], combos, set()),
    ]


def _fem_blocks(side, units: UnitSystem, figures: dict | None = None,
                figure_base: str = "") -> list:
    """Results, bolt forces, figures and checks of the CalculiX model of one combination
    (``end_plate_fem.FemSide``)."""
    from openconex.report.builder import fmt

    from openfemconex.report import _checks_block

    res = side.results
    F, S = Kind.FORCE, Kind.STRESS
    blocks: list = [("h3", "Modelo CalculiX")]
    if not res.converged:
        blocks.append(("p", f"El análisis no convergió: llegó al {100 * res.load_fraction:.0f} "
                            "% de la carga. Los resultados son los del último incremento "
                            "resuelto.", "ng"))
    T_max = max((a.tension for a in res.anchors), default=0.0)
    rows = [
        ["Tracción total en los pernos", fmt(res.anchor_tension_total, F, units)],
        ["Tracción del perno más cargado (con acción de palanca)", fmt(T_max, F, units)],
        ["Compresión de la placa sobre el ala de la columna", fmt(res.bearing_force, F, units)],
        ["Presión de contacto máxima", fmt(res.bearing_pressure_max, S, units)],
        ["von Mises máximo en la placa", fmt(res.plate_von_mises_max, S, units)],
        ["Deformación plástica de la placa (media por elemento)",
         f"{100 * res.plate_peeq_element:.2f} %"],
        ["von Mises máximo en el ala de la columna", fmt(res.flange_von_mises_max, S, units)],
        ["Deformación plástica del ala de la columna (media por elemento)",
         f"{100 * res.flange_peeq_element:.2f} %"],
    ]
    if side.model.stiffeners:
        rows.append(["Deformación plástica de los rigidizadores (media por elemento)",
                     f"{100 * res.stiffener_peeq_element:.2f} %"])
    blocks.append(("table", ["Resultado", "FEM"], rows, {1}))
    bolts = [[f"{a.x:.0f}", f"{a.y:.0f}", fmt(a.tension, F, units),
              fmt(math.hypot(a.Vx, a.Vy), F, units)] for a in res.anchors]
    blocks.append(("table", ["x [mm]", "y [mm]", "Tracción", "Cortante"], bolts, {2, 3}))
    vtu = side.vtu
    figs = [(c, f"{figure_base}{f}") for c, f in (figures or {}).get(
        vtu.name if vtu is not None else "", []) if f]
    if figs:
        blocks.append(("figs", "Resultados del modelo", figs, False))
    blocks += [("h3", "Verificaciones con demandas del FEM"), _checks_block(side.checks, units)]
    return blocks


def _curve_blocks(curve, units: UnitSystem, figure: str = "", figure_base: str = "") -> list:
    """The moment-rotation curve, its stiffness and the FR/PR classification."""
    from openconex.report.builder import fmt

    blocks: list = [("h2", "Curva momento-rotación")]
    if curve is None:
        return blocks + [("p", "La curva se calcula con CalculiX: use Análisis › Resolver "
                               "(se resuelve siempre, aunque no haya combinaciones marcadas).",
                          "note")]
    from openfemconex.end_plate_fem import FR_LIMIT, ROTATION_REF, SIMPLE_LIMIT

    M = Kind.MOMENT
    name = {"FR": "totalmente restringida (FR)", "PR": "parcialmente restringida (PR)",
            "simple": "simple"}[curve.classification]
    blocks.append(("p", "Momento solo, creciente hasta 1.5 veces el mayor de las "
                        "combinaciones, con los pernos pretensados "
                        f"(T_b = {curve.pretension / 1e3:.0f} kN). La rotación es la del "
                        "extremo de la viga respecto de la cara de la columna (sin la "
                        "deformación elástica de la viga); el alma y la zona de panel de "
                        "la columna no se incluyen. Clasificación según el comentario de "
                        f"AISC 360-22 §B3.4: FR si K_s·L/EI ≥ {FR_LIMIT:g}, simple si "
                        f"≤ {SIMPLE_LIMIT:g}, PR entre ambos.", ""))
    if figure:
        blocks.append(("figs", "", [("Curva momento-rotación", f"{figure_base}{figure}")],
                       False))
    theta_s = curve.rotation_at(curve.Ms) if curve.Ms > 0 else None
    M_ref = curve.M_ref
    rows = [
        ["Momento de servicio M_s", fmt(curve.Ms, M, units)],
        ["Rotación en servicio θ_s",
         f"{1000 * theta_s:.2f} mrad" if theta_s is not None else "—"],
        ["Rigidez secante K_s = M_s/θ_s", f"{fmt(curve.Ks, M, units)}/rad"],
        ["Rigidez inicial", f"{fmt(curve.initial_stiffness, M, units)}/rad"],
        ["Luz de la viga L", fmt(curve.span, Kind.LENGTH, units)],
        ["K_s·L/EI", f"{curve.stiffness_ratio:.1f}"],
        ["Clasificación", name],
        ["Momento máximo alcanzado", f"{fmt(curve.M_max, M, units)} a "
                                     f"{1000 * curve.theta_max:.1f} mrad"
                                     + ("" if curve.converged else " (el modelo no resiste "
                                                                    "más)")],
        [f"Momento a {1000 * ROTATION_REF:.0f} mrad",
         fmt(M_ref, M, units) if M_ref is not None else "no se alcanza"],
    ]
    blocks.append(("table", ["Resultado", "Valor"], rows, {1}))
    return blocks


def report_blocks(data: dict[str, Any], results: EndPlateResults, units: UnitSystem,
                  info: dict[str, Any], figures: str = "", figure_base: str = "",
                  picture: bool = False, fem_figures: dict | None = None) -> list:
    """Calculation report of one connection, as the blocks of ``openfemconex.report``:
    data, loads, then for each combination the CalculiX model (when solved), the
    analytic checks and their traces, the AISC 358 block, and the common closing
    (summary, recommendations, installation, scope). ``fem_figures`` are those of
    ``scenes.render_through_bolt_figures``."""
    from openfemconex.end_plate_advice import installation_notes, limitations, recommendations
    from openfemconex.report import (
        _checks_block,
        _traces_block,
        check_title,
        closing_blocks,
        governing,
    )

    mc = build(data, units)
    name = data.get("name") or "Placa de extremo"
    seismic = bool(results.seismic)
    norms = "AISC 360-22, AISC Design Guide 16 y Design Guide 4"
    if seismic:
        norms += ", AISC 358-22 y AISC 341-22"
    fem_figures = fem_figures or {}
    solved = any(r.fem for r in results.combos)
    method = ("Modelo de elementos finitos con CalculiX (viga elástica, placa y ala de la "
              "columna elastoplásticas, contacto placa-ala, pernos solo a tracción) y "
              "verificaciones analíticas." if solved else
              "Cálculo analítico (sin modelo de elementos finitos: resuelva con CalculiX "
              "para agregarlo).")
    live = [x for x in results.all_checks() if x.applicable]
    worst = max(live, key=lambda x: x.ratio, default=None)
    blocks: list = [
        ("h1", f"Reporte de verificación · {name}"),
        ("ficha", [("Proyecto", str(info.get("name", ""))),
                   ("Número", str(info.get("number", ""))),
                   ("Cliente", str(info.get("client", ""))),
                   ("Conexión", f"{name}: viga-columna a momento con placa de extremo"),
                   ("Ingeniero", str(info.get("engineer", ""))),
                   ("Revisión", str(info.get("revision", ""))),
                   ("Normas", norms),
                   ("Fecha", str(info.get("date") or dt.date.today().isoformat()))]),
        ("p", method, "note"),
        ("verdict", results.ok, f". Rige: {check_title(worst)} ({worst.combo}), ratio "
                                f"{worst.ratio:.2f}." if worst else "."),
        ("h2", "Datos"),
        ("table", ["Elemento", "Datos"], _data_rows(data, mc), set()),
    ]
    if picture:
        blocks.append(("figs", "Conexión", [("Vista 3D", f"{figure_base}conexion.png")],
                       False))
    if figures:
        blocks.append(("figs", "Esquemas", [
            ("Cómo viaja la fuerza", f"{figures}/placa_extremo_fuerzas.png"),
            ("Estados límite de la columna", f"{figures}/placa_extremo_columna.png")], False))
    if fem_figures.get(""):
        blocks.append(("figs", "Modelo de elementos finitos",
                       [(c, f"{figure_base}{f}") for c, f in fem_figures[""] if f], False))
    blocks += _curve_blocks(results.curve, units, fem_figures.get("curva", ""), figure_base)
    blocks += _loads_blocks(data, results, units, mc.panel_zone)
    for r in results.combos:
        c = r.combo
        blocks += [("h2", f"Combinación {c.name} ({c.method.value})"),
                   ("p", f"V = {c.V / 1e3:.0f} kN, M = {c.M / 1e6:.0f} kN·m, "
                         f"P = {c.P / 1e3:.0f} kN.", "")]
        if r.worst:
            blocks.append(("verdict", r.ok, f" · rige: {check_title(r.worst)} "
                                            f"(ratio {r.worst.ratio:.2f})"))
        for side in r.fem:
            blocks += _fem_blocks(side, units, fem_figures, figure_base)
        if not r.fem:
            blocks.append(("p", "Esta combinación no se resolvió con CalculiX: solo tiene "
                                "las verificaciones analíticas.", "note"))
        blocks += [("h3", "Verificaciones analíticas"),
                   _checks_block(r.checks, units),
                   ("h3", "Traza de cálculo"),
                   _traces_block(r.all_checks, units)]
    if seismic:
        blocks += [
            ("h2", "Diseño sísmico (AISC 358-22 y AISC 341-22)"),
            ("p", "Diseño por capacidad para el momento probable en la rótula plástica de la "
                  "viga; no depende de las combinaciones de carga (LRFD).", ""),
            _checks_block(results.seismic, units),
            _traces_block(results.seismic, units),
        ]
    rows = [[r.combo.name, "Sí" if r.fem else "No",
             governing([x for side in r.fem for x in side.checks]), governing(r.checks),
             "Cumple" if r.ok else "No cumple"] for r in results.combos]
    if seismic:
        ok = all(c.status.value != "ng" for c in results.seismic)
        rows.append([SEISMIC_COMBO, "No", "—", governing(results.seismic),
                     "Cumple" if ok else "No cumple"])
    blocks += closing_blocks(results.ok, rows, recommendations(results.all_checks()),
                             installation_notes(data, mc),
                             "Requisitos de instalación", limitations(data, mc))
    return blocks


def report_html(data: dict[str, Any], results: EndPlateResults, units: UnitSystem,
                info: dict[str, Any], figures: str = "", figure_base: str = "",
                picture: bool = False, fem_figures: dict | None = None) -> str:
    """Calculation report as HTML (see ``report_blocks``)."""
    from openfemconex.report import blocks_to_html

    return blocks_to_html(report_blocks(data, results, units, info, figures, figure_base,
                                        picture, fem_figures))


def report_docx(path, figure_dir, data: dict[str, Any], results: EndPlateResults,
                units: UnitSystem, info: dict[str, Any], figures: str = "",
                picture: bool = False, fem_figures: dict | None = None):
    """Editable Word report with the same content."""
    from openfemconex.report_docx import write_docx

    blocks = report_blocks(data, results, units, info, figures, "", picture, fem_figures)
    return write_docx(blocks, path, figure_dir)


# layouts by family, for the type picker and the help
FLUSH_LAYOUTS = tuple(sorted(FLUSH, key=list(EndPlateLayout).index))
EXTENDED_LAYOUTS = tuple(sorted(EXTENDED, key=list(EndPlateLayout).index))
STIFFENED_LAYOUTS = tuple(sorted(STIFFENED_EXTENSION, key=list(EndPlateLayout).index))
