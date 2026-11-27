# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Through-bolt connections saved in a project file.

A project holds a list of connections in the OpenFEMConex block of the ``.ocnx``
file (``openfemconex.connections``). Each one is a dictionary with its ``type``,
its ``name`` and its data as texts with units, like the rest of the file. This
module turns a ``through_bolt`` entry into the model of :mod:`through_bolt`,
runs its checks and writes its report.
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Any

from openconex.connections.moment.end_plate import EXTENDED, EndPlate, EndPlateLayout
from openconex.core.checks import CheckResult
from openconex.core.materials import BOLTS, STEELS
from openconex.core.model import BoltSpec
from openconex.core.shapes import aisc_shapes
from openconex.units import Kind, UnitSystem, parse

from openfemconex.checks import EDITIONS
from openfemconex.through_bolt import (
    BackPlate,
    ConcreteMember,
    OppositeBeam,
    Rebar,
    ShearTransfer,
    Support,
    ThroughBoltConnection,
    check_through_bolt,
    forces,
)

TYPE = "through_bolt"

LAYOUTS = {
    EndPlateLayout.FLUSH_2: "Al ras, 2 pernos (2F)",
    EndPlateLayout.FLUSH_4: "Al ras, 4 pernos (4F)",
    EndPlateLayout.EXTENDED_4: "Extendida, 4 pernos (4E)",
    EndPlateLayout.EXTENDED_4_STIFFENED: "Extendida rigidizada (4ES)",
    EndPlateLayout.EXTENDED_8_STIFFENED: "Extendida rigidizada, 8 pernos (8ES)",
}
"""End-plate layouts offered for this connection."""

TEMPLATE: dict[str, Any] = {
    "type": TYPE,
    "name": "Pernos pasantes",
    "beam": "W18X50",
    "beam_grade": "ASTM A992",
    "end_plate": {
        "layout": "extended_4", "bolt_diameter": "1 in", "bolt_grade": "ASTM F3125 Gr. A325",
        "width": "8 in", "thickness": "1 in", "gage": "5.5 in", "pf": "1.75 in",
        "pb": "3.5 in", "pf_o": "1.75 in", "pext": "3.5 in", "grade": "ASTM A36",
        "web_weld": "5/16 in",
    },
    "back_plate": {"width": "10 in", "height": "", "thickness": "1 in", "grade": "ASTM A36",
                   "washer": ""},
    "member": {
        "kind": "wall", "thickness": "500 mm", "fc": "28 MPa", "cover": "40 mm",
        "vertical_diameter": "19 mm", "vertical_spacing": "150 mm",
        "horizontal_diameter": "12 mm", "horizontal_spacing": "200 mm", "fy": "420 MPa",
        "width": "", "top": "", "bottom": "", "axial": "", "cross_ties": True,
    },
    "shear": {"type": "friction", "mu": 0.55, "grout_length": "150 mm", "grout_fc": "",
              "gap": "6 mm"},
    "opposite": None,
    "cases": [
        {"name": "D", "type": "D", "V": "40 kN", "M": "70 kN*m"},
        {"name": "L", "type": "L", "V": "32.5 kN", "M": "60 kN*m"},
    ],
    "combinations": {"methods": ["LRFD"]},
}
"""A new through-bolt connection: the first example of the help topic."""

CASE_KEYS = ("V", "M", "P", "V2", "M2", "P2")
"""Forces of a load case: near beam, then the opposite one."""

METHODS = ("LRFD",)
"""The checks of this connection are LRFD."""

OPPOSITE: dict[str, Any] = {"beam": "W18X50", "beam_grade": "ASTM A992"}
"""Opposite beam when it is switched on: same end plate and bolts as the near beam."""


def new_connection(name: str = "") -> dict[str, Any]:
    data = copy.deepcopy(TEMPLATE)
    if name:
        data["name"] = name
    return data


@dataclass
class Combination:
    name: str
    V: float = 0.0
    M: float = 0.0
    P: float = 0.0
    V2: float = 0.0
    M2: float = 0.0
    P2: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    """Factor of each load case (empty for a combination typed already factored)."""
    source: str = ""

    def loads(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in ("V", "M", "P", "V2", "M2", "P2")}


@dataclass
class ComboResult:
    combo: Combination
    checks: list[CheckResult] = field(default_factory=list)
    T: float = 0.0
    C: float = 0.0
    fem: list = field(default_factory=list)
    """CalculiX results of each beam (``through_bolt_fem.FemSide``), when solved."""

    @property
    def all_checks(self) -> list[CheckResult]:
        """Analytic checks followed by those with the forces of the FEM."""
        return self.checks + [c for side in self.fem for c in side.checks]

    @property
    def ok(self) -> bool:
        return all(r.status.value != "ng" for r in self.all_checks)

    @property
    def worst(self) -> CheckResult | None:
        return max((r for r in self.all_checks if r.applicable), key=lambda r: r.ratio,
                   default=None)


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


def _beam(name: str, grade: str):
    if grade not in STEELS:
        raise ValueError(f"acero desconocido: {grade}")
    try:
        return aisc_shapes().get(name).to_ishape(grade)
    except Exception as exc:
        raise ValueError(f"perfil no válido para la viga: {name}") from exc


def _end_plate(e: dict[str, Any], r: _Reader) -> EndPlate:
    layout = EndPlateLayout(e.get("layout", "extended_4"))
    grade = e.get("grade", "ASTM A36")
    bolt_grade = e.get("bolt_grade", "ASTM F3125 Gr. A325")
    if grade not in STEELS:
        raise ValueError(f"acero desconocido: {grade}")
    if bolt_grade not in BOLTS:
        raise ValueError(f"grado de perno desconocido: {bolt_grade}")
    steel = STEELS[grade]
    T = Kind.THICKNESS
    extended = layout in EXTENDED
    two_rows = layout not in (EndPlateLayout.FLUSH_2, EndPlateLayout.EXTENDED_4,
                              EndPlateLayout.EXTENDED_4_STIFFENED)
    return EndPlate(
        layout=layout, bolt=BoltSpec(diameter=r.q(e.get("bolt_diameter")), grade=bolt_grade),
        width=r.q(e.get("width")), thickness=r.q(e.get("thickness"), T),
        gage=r.q(e.get("gage")), pf=r.q(e.get("pf")), Fy=steel.Fy, Fu=steel.Fu,
        pb=r.q(e.get("pb"), default=0.0) if two_rows else 0.0,
        pf_o=r.q(e.get("pf_o")) if extended else 0.0,
        pext=r.q(e.get("pext")) if extended else 0.0,
        web_weld=r.q(e.get("web_weld"), T, default=0.0),
        flange_weld=r.q(e.get("flange_weld"), T, default=0.0))


def build(data: dict[str, Any], units: UnitSystem) -> ThroughBoltConnection:
    """Model of one ``through_bolt`` entry; ``units`` gives the unit of bare numbers."""
    r = _Reader(units)
    beam = _beam(data.get("beam", ""), data.get("beam_grade", "ASTM A992"))
    ep = _end_plate(data.get("end_plate") or {}, r)
    m = data.get("member") or {}
    inf = math.inf
    member = ConcreteMember(
        kind=Support(m.get("kind", "wall")), thickness=r.q(m.get("thickness")),
        fc=r.q(m.get("fc"), Kind.STRESS), cover=r.q(m.get("cover")),
        vertical=Rebar(r.q(m.get("vertical_diameter")), r.q(m.get("vertical_spacing")),
                       r.q(m.get("fy"), Kind.STRESS, 420.0)),
        horizontal=Rebar(r.q(m.get("horizontal_diameter")), r.q(m.get("horizontal_spacing")),
                         r.q(m.get("fy"), Kind.STRESS, 420.0)),
        width=r.q(m.get("width"), default=inf), top=r.q(m.get("top"), default=inf),
        bottom=r.q(m.get("bottom"), default=inf),
        axial=r.q(m.get("axial"), Kind.FORCE, 0.0), cross_ties=bool(m.get("cross_ties")))
    if member.kind is Support.COLUMN and not math.isfinite(member.width):
        raise ValueError("falta el ancho de la columna")
    opposite = None
    o = data.get("opposite")
    if o:
        opposite = OppositeBeam(_beam(o.get("beam", ""), o.get("beam_grade", "ASTM A992")), ep)
    back = None
    if opposite is None:
        b = data.get("back_plate") or {}
        ext = ep.pext if ep.layout in EXTENDED else 0.0
        back = BackPlate(width=r.q(b.get("width")),
                         height=r.q(b.get("height"), default=beam.d + 2 * ext + 50.0),
                         thickness=r.q(b.get("thickness"), Kind.THICKNESS),
                         grade=b.get("grade", "ASTM A36"),
                         washer=r.q(b.get("washer"), default=0.0))
    s = data.get("shear") or {}
    scheme = ShearTransfer(s.get("type", "friction"))
    grout = scheme is ShearTransfer.GROUT
    return ThroughBoltConnection(
        beam, ep, back, member, shear=scheme, mu=float(s.get("mu", 0.55) or 0.55),
        opposite=opposite,
        grout_length=r.q(s.get("grout_length")) if grout else 0.0,
        grout_fc=r.q(s.get("grout_fc"), Kind.STRESS, 0.0) if grout else 0.0,
        gap=r.q(s.get("gap"), default=0.0) if grout else 0.0)


def _kind(key: str) -> Kind:
    return Kind.MOMENT if key.startswith("M") else Kind.FORCE


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """A connection of the first format, with its combinations typed already factored,
    in load cases: one case per combination, and a combination of that case alone."""
    old = data.get("combinations")
    if not isinstance(old, list):
        return data
    cases, custom = [], []
    for i, c in enumerate(old, start=1):
        name = _text(c.get("name")) or f"C{i}"
        cases.append({"name": name, "type": "D",
                      **{k: c[k] for k in CASE_KEYS if _text(c.get(k))}})
        custom.append({"name": name, "method": "LRFD", "factors": {name: 1.0}})
    data["cases"] = cases
    data["combinations"] = {"methods": ["LRFD"], "include_code": False, "custom": custom}
    return data


def case_values(data: dict[str, Any], units: UnitSystem) -> dict[str, dict[str, float]]:
    """Forces of each load case, in N and N·mm."""
    r = _Reader(units)
    return {_text(c.get("name")): {k: r.q(c.get(k), _kind(k), 0.0) for k in CASE_KEYS}
            for c in data.get("cases") or []}


def combinations(data: dict[str, Any], units: UnitSystem) -> list[Combination]:
    """Factored forces of every combination of the load cases (LRFD)."""
    from openfemconex.load_cases import factored, load_combinations

    data = migrate(copy.deepcopy(data))
    values = case_values(data, units)
    out = []
    for combo in load_combinations(data.get("cases") or [], data.get("combinations"),
                                   METHODS):
        f = factored(combo, values)
        out.append(Combination(combo.name, **{k: f.get(k, 0.0) for k in CASE_KEYS},
                               factors=dict(combo.factors), source=combo.source))
    return out


def run(data: dict[str, Any], units: UnitSystem, edition: str = "current"
        ) -> list[ComboResult]:
    """Checks of every combination of the connection (LRFD)."""
    conn = build(data, units)
    ed = EDITIONS.get(edition, EDITIONS["current"])
    out = []
    for combo in combinations(data, units):
        loads = combo.loads()
        if conn.opposite is None:
            loads = {k: v for k, v in loads.items() if not k.endswith("2")}
        res = check_through_bolt(conn, ed=ed, combo=combo.name, **loads)
        f = forces(conn, combo.V, combo.M, combo.P)
        out.append(ComboResult(combo, res, f.T, f.C))
    return out


def _fem_blocks(side, units: UnitSystem) -> list:
    """Bolt forces and checks of the CalculiX model of one beam."""
    from openconex.report.builder import fmt

    from openfemconex.report import _checks_block

    res = side.results
    model = getattr(side, "model", None)
    F = Kind.FORCE
    rows = [[str(i), fmt(a.x, Kind.LENGTH, units), fmt(a.y, Kind.LENGTH, units),
             fmt(a.tension, F, units)] for i, a in enumerate(res.anchors, start=1)]
    state = ("" if res.converged else
             f" El análisis no convergió: llegó al {100 * res.load_fraction:.0f} % de la "
             "carga.")
    both = model is not None and model.opposite is not None
    if both and side.side == "viga 2":
        # the same solution as beam 1: its far face results
        return [
            ("h3", f"Modelo CalculiX, {side.side}"),
            ("p", f"Mismo modelo que la viga 1 (las dos vigas cargadas a la vez). Compresión "
                  f"de su placa sobre el concreto {fmt(res.far_bearing_force, F, units)}, "
                  f"deformación plástica de la placa {100 * res.far_peeq_element:.2f} %."
                  f"{state}", ""),
            _checks_block(side.checks, units),
        ]
    far = ""
    if model is not None and model.far is not None:
        far = (f" La placa posterior es flexible y se apoya en la cara opuesta: compresión "
               f"{fmt(res.far_bearing_force, F, units)}, presión máxima "
               f"{fmt(res.far_pressure_max, Kind.STRESS, units)}, deformación plástica "
               f"{100 * res.far_peeq_element:.2f} %. El muro se apoya arriba y abajo.")
    elif both:
        far = (" La viga opuesta está en el mismo modelo, con su placa de extremo en la cara "
               "opuesta y sus cargas aplicadas a la vez; el muro se apoya arriba y abajo.")
    return [
        ("h3", f"Modelo CalculiX, {side.side}"),
        ("p", f"Placa de extremo sobre la cara del concreto con contacto y pernos sin "
              f"adherencia como resortes de tracción. Compresión sobre el concreto "
              f"{fmt(res.bearing_force, F, units)}, presión máxima "
              f"{fmt(res.bearing_pressure_max, Kind.STRESS, units)}, deformación plástica "
              f"de la placa {100 * res.plate_peeq_element:.2f} %.{far}{state}", ""),
        ("table", ["Perno", "Altura x", "y", "Tracción"], rows, set()),
        _checks_block(side.checks, units),
    ]


def _loads_blocks(data: dict[str, Any], results: list[ComboResult], conn, units: UnitSystem
                  ) -> list:
    """Load cases (service) and the factored combinations."""
    from openconex.report.builder import fmt

    from openfemconex.load_cases import combination_text

    data = migrate(copy.deepcopy(data))
    keys = [k for k in CASE_KEYS if conn.opposite is not None or not k.endswith("2")]
    heads = {"V": "V", "M": "M", "P": "P", "V2": "V2", "M2": "M2", "P2": "P2"}
    values = case_values(data, units)
    rows = [[name, str(c.get("type", "")), *[fmt(values[name][k], _kind(k), units)
                                              for k in keys]]
            for c in data.get("cases") or [] for name in [_text(c.get("name"))]]
    combos = [[r.combo.name, combination_text(r.combo.factors) if r.combo.factors else "—",
               *[fmt(getattr(r.combo, k), _kind(k), units) for k in keys]] for r in results]
    return [
        ("h2", "Cargas"),
        ("p", "Casos de carga de servicio en la cara del muro o columna: V positivo hacia "
              "abajo, M positivo con tracción arriba, P positiva en compresión; V2, M2 y P2 "
              "son de la viga opuesta.", ""),
        ("table", ["Caso", "Tipo", *[heads[k] for k in keys]], rows, set()),
        ("table", ["Combinación", "Factores", *[heads[k] for k in keys]], combos, set()),
    ]


def summary(data: dict[str, Any]) -> str:
    """One line for the project tree."""
    m = data.get("member") or {}
    kind = "columna" if m.get("kind") == "column" else "muro"
    opp = " + viga opuesta" if data.get("opposite") else ""
    return f"{data.get('beam', '?')}{opp}, {kind} {m.get('thickness', '?')}"


def report_html(data: dict[str, Any], results: list[ComboResult], units: UnitSystem,
                info: dict[str, Any], edition: str = "current", figures: str = "",
                figure_base: str = "") -> str:
    """Calculation report of one connection.

    ``figures`` is the folder (or URL) of the help figures; ``figure_base`` is put
    in front of the 3D picture ``conexion.png`` when it is given.
    """
    from openfemconex.report import _checks_block, _traces_block, blocks_to_html, check_title

    ed = EDITIONS.get(edition, EDITIONS["current"])
    conn = build(data, units)
    e, m, s = data.get("end_plate") or {}, data.get("member") or {}, data.get("shear") or {}
    kind = "Columna" if m.get("kind") == "column" else "Muro"
    rows = [
        ["Viga", f"{data.get('beam')}, {data.get('beam_grade')}"],
        ["Placa de extremo", f"{LAYOUTS.get(EndPlateLayout(e.get('layout')), e.get('layout'))}"
                             f", {e.get('width')} × {e.get('thickness')}, {e.get('grade')}; "
                             f"pernos {e.get('bolt_grade')} de {e.get('bolt_diameter')} "
                             f"({conn.bolts} en total), gramil {e.get('gage')}"],
    ]
    if conn.opposite is None:
        b = data.get("back_plate") or {}
        rows.append(["Placa posterior", f"Corrida, {b.get('width')} × {b.get('thickness')}, "
                                        f"alto {conn.back_plate.height:.0f} mm, "
                                        f"{b.get('grade')}"])
    else:
        o = data["opposite"]
        rows.append(["Viga opuesta", f"{o.get('beam')}, {o.get('beam_grade')}, con la misma "
                                     "placa de extremo y los mismos pernos"])
    rows.append([kind, f"Nuevo, espesor {m.get('thickness')}, f'c = {m.get('fc')}, "
                       f"recubrimiento {m.get('cover')}; vertical Ø{m.get('vertical_diameter')}"
                       f" @ {m.get('vertical_spacing')} y horizontal "
                       f"Ø{m.get('horizontal_diameter')} @ {m.get('horizontal_spacing')} en "
                       "cada cara" + ("; con estribos que cruzan el espesor"
                                      if m.get("cross_ties") else "")])
    if conn.shear is ShearTransfer.GROUT:
        rows.append(["Cortante", f"Grout en {s.get('grout_length')} de cada camisa, holgura "
                                 f"{s.get('gap')}"])
    else:
        rows.append(["Cortante", f"Fricción, μ = {conn.mu}"])
    name = data.get("name", "Pernos pasantes")
    blocks: list = [
        ("h1", f"Reporte de verificación · {name}"),
        ("ficha", [("Proyecto", str(info.get("name", ""))),
                   ("Número", str(info.get("number", ""))),
                   ("Cliente", str(info.get("client", ""))),
                   ("Conexión", f"{name}: viga con placa de extremo y pernos pasantes"),
                   ("Ingeniero", str(info.get("engineer", ""))),
                   ("Revisión", str(info.get("revision", ""))),
                   ("Normas", f"{ed.aisc}, {ed.aci}, AISC DG16/DG4, {ed.guide}"),
                   ("Fecha", str(info.get("date") or dt.date.today().isoformat()))]),
        ("p", "Cálculo analítico (sin modelo de elementos finitos). Las verificaciones del "
              "concreto son de resistencia (LRFD).", "note"),
        ("h2", "Datos"),
        ("table", ["Elemento", "Datos"], rows, set()),
    ]
    if figure_base:
        blocks.append(("figs", "Conexión", [("Vista 3D", f"{figure_base}conexion.png")], False))
    if figures:
        figs = [("Fuerzas sobre el concreto", f"{figures}/concreto_fuerzas.png"),
                ("Puntal y tensor del par de compresiones", f"{figures}/flexion_muro.png")]
        figs.insert(0, ("Camino de cargas: cortante con grout", f"{figures}/corte_grout.png")
                    if conn.shear is ShearTransfer.GROUT else
                    ("Camino de cargas: cortante por fricción", f"{figures}/corte_friccion.png"))
        if conn.opposite is not None:
            figs.append(("Casos de la conexión opuesta", f"{figures}/conexion_opuesta.png"))
        blocks.append(("figs", "Esquemas", figs, True))
    blocks += _loads_blocks(data, results, conn, units)
    ok_all = all(r.ok for r in results)
    blocks.append(("h2", "Resumen"))
    blocks.append(("verdict", ok_all, ""))
    blocks.append(("table", ["Combinación", "Rige", "Ratio", "Estado"], [
        [r.combo.name, check_title(r.worst) if r.worst else "—",
         f"{r.worst.ratio:.2f}" if r.worst else "—", "Cumple" if r.ok else "No cumple"]
        for r in results], set()))
    for r in results:
        c = r.combo
        blocks.append(("h2", f"Combinación {c.name}"))
        extra = (f"; viga 2: V2 = {c.V2 / 1e3:.0f} kN, M2 = {c.M2 / 1e6:.0f} kN·m"
                 if conn.opposite is not None else "")
        blocks.append(("p", f"Viga 1: V = {c.V / 1e3:.0f} kN, M = {c.M / 1e6:.0f} kN·m, "
                            f"P = {c.P / 1e3:.0f} kN{extra}. Pernos: T = {r.T / 1e3:.0f} kN, "
                            f"C = {r.C / 1e3:.0f} kN.", ""))
        if r.worst:
            blocks.append(("verdict", r.ok, f" · rige: {check_title(r.worst)} "
                                            f"(ratio {r.worst.ratio:.2f})"))
        blocks.append(_checks_block(r.checks, units))
        for side in r.fem:
            blocks += _fem_blocks(side, units)
        blocks.append(("h3", "Traza de cálculo"))
        blocks.append(_traces_block(r.all_checks, units))
    blocks.append(("notes", "Notas", [
        "La fricción solo puede contar con compresión permanente (ACI 318 §22.9): el "
        "ingeniero juzga cada combinación. En sismo se recomienda grout.",
        "Hendimiento con la zona de anclaje de §25.9 por analogía; apoyo del perno en el grout "
        "con ℓ = mín(ℓg, 4d), supuesto del programa.",
        "El diseño global del muro y el nudo de una columna con vigas a los dos lados quedan "
        "para el análisis global.",
    ]))
    return blocks_to_html(blocks)
