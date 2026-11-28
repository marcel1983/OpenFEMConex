# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Verification report in HTML: FEM results, FEM-based checks and the DG1 analytical path."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from openconex.core.checks import CheckResult
from openconex.i18n import tr
from openconex.report.builder import fmt
from openconex.report.html import latex_to_mathml
from openconex.units import Kind, UnitSystem

from openfemconex.checks import Edition
from openfemconex.i18n import language
from openfemconex.i18n import tr as _
from openfemconex.results import Results

__all__ = ["ComboReport", "TITLES", "blocks_to_html", "check_title", "closing_blocks",
           "render_report", "report_blocks", "write_report"]

TITLES = {
    "fem.concrete_bearing": "Aplastamiento del concreto (bloque centrado en la resultante FEM)",
    "fem.plate_plastic_strain": "Deformación plástica equivalente de la placa",
    "fem.plate_bending_tension": "Flexión de la placa por tracción de anclajes",
    "fem.weld": "Soldadura columna-placa (punto más solicitado)",
    "fem.weld_cjp": "Soldadura CJP columna-placa: metal base de la pared (punto más solicitado)",
    "anchor.steel_tension": "Anclaje: resistencia del acero a tracción",
    "anchor.steel_shear": "Anclaje: resistencia del acero a cortante",
    "anchor.concrete_breakout_tension": "Concreto: arrancamiento del grupo en tracción",
    "anchor.pullout": "Anclaje: extracción (pullout)",
    "anchor.side_face_blowout": "Concreto: desprendimiento lateral del anclaje más cargado",
    "anchor.side_face_blowout_group": "Concreto: desprendimiento lateral del grupo junto al borde",
    "anchor.concrete_breakout_shear": "Concreto: arrancamiento del grupo en cortante",
    "anchor.pryout": "Concreto: desprendimiento por palanca del grupo (pryout)",
    "anchor.interaction": "Anclaje: interacción tracción y cortante",
    "base_plate.friction": "Cortante por fricción",
    "anchor.reinforcement": "Refuerzo de anclaje a tracción (barras y horquillas)",
    "anchor.reinforcement_development": "Refuerzo de anclaje: desarrollo sobre el cono",
    "anchor.hairpin_development_top": "Horquillas: desarrollo sobre el cono (doblez)",
    "anchor.hairpin_development_bottom": "Horquillas: desarrollo bajo el cono (patas)",
    "anchor.reinforcement_shear": "Refuerzo de anclaje a cortante (estribos superiores)",
    "pedestal.flexure_axial": "Pedestal: flexocompresión de la sección",
    "pedestal.min_reinforcement": "Pedestal: cuantía mínima longitudinal",
    "anchor.combined_bending": "Anclaje: tracción, cortante y flexión (arandela soldada)",
    "base_plate.lug_bearing": "Llave de cortante: aplastamiento del concreto",
    "fem.stiffener_plastic_strain": "Rigidizadores: deformación plástica equivalente",
    "fem.stiffener_weld": "Rigidizadores: soldadura (punto más solicitado)",
    "fem.stiffener_slenderness": "Rigidizadores: esbeltez del borde libre",
    "through_bolt.bearing_front_top":
        "Pernos pasantes: aplastamiento bajo la placa frontal, arriba",
    "through_bolt.bursting_front_top":
        "Pernos pasantes: hendimiento detrás de la placa frontal, arriba",
    "through_bolt.bearing_front_bottom":
        "Pernos pasantes: aplastamiento bajo la placa frontal, abajo",
    "through_bolt.bursting_front_bottom":
        "Pernos pasantes: hendimiento detrás de la placa frontal, abajo",
    "through_bolt.friction_front": "Pernos pasantes: cortante por fricción en la placa frontal",
    "through_bolt.grout_bearing_front":
        "Pernos pasantes: apoyo del perno en el grout, placa frontal",
    "through_bolt.bearing_back_top":
        "Pernos pasantes: aplastamiento bajo la placa del otro lado, arriba",
    "through_bolt.bursting_back_top":
        "Pernos pasantes: hendimiento detrás de la placa del otro lado, arriba",
    "through_bolt.bearing_back_bottom":
        "Pernos pasantes: aplastamiento bajo la placa del otro lado, abajo",
    "through_bolt.bursting_back_bottom":
        "Pernos pasantes: hendimiento detrás de la placa del otro lado, abajo",
    "through_bolt.friction_back":
        "Pernos pasantes: cortante por fricción en la placa del otro lado",
    "through_bolt.grout_bearing_back":
        "Pernos pasantes: apoyo del perno en el grout, placa del otro lado",
    "through_bolt.punching_top": "Pernos pasantes: punzonamiento de la zona de arriba",
    "through_bolt.stm_node_top": "Puntal y tensor: nodo de arriba",
    "through_bolt.punching_bottom": "Pernos pasantes: punzonamiento de la zona de abajo",
    "through_bolt.stm_node_bottom": "Puntal y tensor: nodo de abajo",
    "through_bolt.bolt_combined":
        "Pernos pasantes: tracción, cortante y flexión del perno con grout",
    "through_bolt.stm_angle": "Puntal y tensor: ángulo entre puntal y tensor",
    "through_bolt.stm_strut": "Puntal y tensor: puntal diagonal del concreto",
    "through_bolt.stm_tie": "Puntal y tensor: refuerzo vertical como tensor",
    "through_bolt.stm_tie_anchorage": "Puntal y tensor: desarrollo del tensor más allá del nodo",
    "through_bolt.member_flexure": "Muro o columna: flexocompresión junto a la conexión",
    "through_bolt.fem_bolt_tension": "FEM: tracción del perno más cargado (con efecto palanca)",
    "through_bolt.fem_plate_strain": "FEM: deformación plástica de la placa de extremo",
    "through_bolt.fem_bearing": "FEM: aplastamiento del concreto bajo la placa de extremo",
    "through_bolt.fem_friction": "FEM: cortante por fricción con la compresión del modelo",
    "through_bolt.fem_weld_flange": "FEM: soldadura de los patines a la placa de extremo",
    "through_bolt.fem_weld_web": "FEM: soldadura del alma a la placa de extremo",
    "through_bolt.fem_back_plate_strain": "FEM: deformación plástica de la placa posterior",
    "through_bolt.fem_back_bearing": "FEM: aplastamiento del concreto bajo la placa posterior",
    "end_plate.fem_bolt_tension":
        "FEM: perno más cargado, tracción con palanca y cortante (J3.7)",
    "end_plate.fem_plate_strain": "FEM: deformación plástica de la placa de extremo",
    "end_plate.fem_flange_strain": "FEM: deformación plástica del ala de la columna",
    "end_plate.fem_stiffener_strain": "FEM: deformación plástica de los rigidizadores",
    "end_plate.fem_column_web_strain": "FEM: deformación plástica del alma de la columna",
    "end_plate.fem_continuity_strain": "FEM: deformación plástica de las placas de continuidad",
    "end_plate.fem_doubler_strain": "FEM: deformación plástica de la placa doble",
    "end_plate.fem_weld_flange": "FEM: soldadura de las alas de la viga a la placa",
    "end_plate.fem_weld_web": "FEM: soldadura del alma de la viga a la placa",
}


def check_title(result: CheckResult) -> str:
    if result.id in TITLES:
        return _(TITLES[result.id])
    title = tr(result.text_id, language())
    if title == result.text_id:
        title = tr(result.text_id, "es")
    return result.id if title == result.text_id else title


@dataclass
class ComboReport:
    results: Results
    method: str
    fem_checks: list[CheckResult]
    analytical: list[CheckResult] = field(default_factory=list)
    reference: dict[str, float] = field(default_factory=dict)
    """DG1 stress-block reference: T, Y, fp (internal units)."""
    advice: dict[str, list[str]] = field(default_factory=dict)
    """Recommendations for the checks that do not pass, by check id."""


_CSS = """
body{font-family:system-ui,sans-serif;max-width:1000px;margin:2em auto;padding:0 1em;color:#222}
h1{font-size:1.5em}h2{font-size:1.2em;margin-top:2em;border-bottom:2px solid #ccc}
h3{font-size:1.05em;margin-top:1.5em}
table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:.92em}
th,td{border:1px solid #ccc;padding:.3em .5em;text-align:left;vertical-align:top}
th{background:#f0f0f0}td.n{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#17692b;font-weight:600}.ng{color:#b00020;font-weight:600}.na{color:#777}
table.figs td{border:none;text-align:center;padding:.4em}
table.ficha{width:auto;min-width:60%}table.ficha th{width:12em}
table.figs img{max-width:100%;height:auto;border:1px solid #ddd}
details{margin:.3em 0 .8em}summary{cursor:pointer}small,.note{color:#555;font-size:.88em}
"""


# ---------------------------------------------------------------------------- blocks
# The report is built once as a list of format-neutral blocks, then written as HTML
# (browser, PDF) or as an editable Word document.
#   ("h1" | "h2" | "h3", text)
#   ("p", text, style)                  style: "", "note", "ok", "ng"
#   ("verdict", ok, text)
#   ("ficha", [(label, value)])         identification card at the top
#   ("table", headers, rows, numeric)   a cell is a text or (status, text)
#   ("figs", heading, [(caption, file)], wide)   wide: one figure per row
#   ("advice", intro, [(title, [items])])
#   ("traces", [(title, ratio, [(symbol, expression, value, clause)])])
#   ("notes", heading, [items])
#   ("image", path)
Block = tuple


def _status_cell(result: CheckResult) -> tuple[str, str]:
    kind = {"ok": "ok", "ng": "ng"}.get(result.status.value, "na")
    text = {"ok": _("Cumple"), "ng": _("No cumple")}.get(result.status.value, _("No rige"))
    return kind, text


def _checks_block(checks: list[CheckResult], units: UnitSystem) -> Block:
    rows = [[check_title(r), fmt(r.demand, r.kind, units), fmt(r.capacity, r.kind, units),
             "—" if not r.applicable else
             f"{r.ratio:.2f}" + (_(" (límite {limit})", limit=f"{r.ratio_limit:g}")
                                 if r.ratio_limit != 1 else ""),
             _status_cell(r), r.clause] for r in checks]
    return ("table", [_(h, "column") for h in ("Verificación", "Demanda", "Capacidad", "Ratio",
                                                "Estado", "Referencia")], rows, {1, 2, 3})


def closing_blocks(ok: bool, rows: list[list], advice: list[tuple[str, list[str]]],
                   installation: list[str], installation_title: str, limits: list[str],
                   advice_intro: str = "") -> list[Block]:
    """The end of every connection report, in the same order for all types: summary of
    results by combination, recommendations, installation requirements that make the
    assumptions of the analysis valid, and scope and limitations.

    ``rows`` are [combination, FEM solved (Sí/No), governing FEM check, governing
    analytical check, status]; ``advice`` is (failing check, [changes]).
    """
    out: list[Block] = [
        ("h2", _("Resumen de resultados")),
        ("verdict", ok, ""),
        ("table", [_(h, "column") for h in ("Combinación", "FEM", "Rige (FEM)",
                                             "Rige (analítico)", "Estado")], rows, set()),
    ]
    if advice:
        out += [("h3", _("Recomendaciones")),
                ("advice", advice_intro or _("Cambios sugeridos para las verificaciones que "
                                             "no cumplen (un cambio a la vez; los valores son "
                                             "estimaciones: vuelva a resolver después):"),
                 advice)]
    else:
        out.append(("p", _("Todas las verificaciones cumplen: no hay recomendaciones de "
                           "cambio."), ""))
    if installation:
        out.append(("notes", installation_title, installation))
    out.append(("notes", _("Alcance y limitaciones"), limits))
    return out


def governing(checks: list[CheckResult]) -> str:
    """'title (ratio)' of the governing applicable check, or a dash."""
    live = [r for r in checks if r.applicable]
    worst = max(live, key=lambda r: r.ratio / (r.ratio_limit or 1.0), default=None)
    return f"{check_title(worst)} ({worst.ratio:.2f})" if worst else "—"


def _status_word(checks: list[CheckResult]) -> tuple[str, str]:
    ok = all(r.status.value != "ng" for r in checks)
    return ("ok", _("Cumple")) if ok else ("ng", _("No cumple"))


def _base_plate_advice(combos: list[ComboReport]) -> list[tuple[str, list[str]]]:
    """Recommendations of every combination, the worst first, one entry per check."""
    items = []
    for c in combos:
        for r in c.fem_checks:
            if r.id in c.advice:
                items.append((r.ratio / (r.ratio_limit or 1.0), r, c.advice[r.id]))
    out, seen = [], set()
    for _ratio, r, adv in sorted(items, key=lambda t: t[0], reverse=True):
        if r.id in seen:
            continue
        seen.add(r.id)
        out.append((f"{check_title(r)} ({r.combo}, ratio {r.ratio:.2f})", adv))
    return out


def _traces_block(checks: list[CheckResult], units: UnitSystem) -> Block:
    return ("traces", [(check_title(r), r.ratio,
                        [(s.symbol, s.expression, fmt(s.value, s.kind, units), s.clause)
                         for s in r.steps]) for r in checks])


def _fem_summary_blocks(c: ComboReport, units: UnitSystem) -> list[Block]:
    r = c.results
    F, S, L = Kind.FORCE, Kind.STRESS, Kind.LENGTH
    rows = [
        [_("Tracción total en anclajes"), fmt(r.anchor_tension_total, F, units),
         fmt(c.reference["T"], F, units) if "T" in c.reference else "—"],
        [_("Compresión sobre el concreto"), fmt(r.bearing_force, F, units),
         fmt(c.reference["T"] + r.applied["P"], F, units) if "T" in c.reference else "—"],
        [_("Longitud de apoyo"), fmt(r.bearing_length_x, L, units),
         fmt(c.reference["Y"], L, units) if "Y" in c.reference else "—"],
        [_("Presión de contacto media"), fmt(r.bearing_pressure_mean, S, units),
         fmt(c.reference["fp"], S, units) if "fp" in c.reference else "—"],
        [_("Presión de contacto máxima (concreto elástico)"),
         fmt(r.bearing_pressure_max, S, units), "—"],
        [_("von Mises máximo en la placa"), fmt(r.plate_von_mises_max, S, units), "—"],
        [_("Deformación plástica en la placa (media por elemento / pico nodal)"),
         f"{100 * r.plate_peeq_element:.2f} % / {100 * r.plate_peeq_max:.2f} %", "—"],
        [_("Cortante transferido por fricción"),
         fmt((r.friction[0] ** 2 + r.friction[1] ** 2) ** 0.5, F, units), "—"],
        [_("Error de equilibrio vertical / de momento"),
         f"{100 * r.equilibrium_error:.2f} % / {100 * r.moment_error:.2f} %", "—"],
    ]
    anchors = [[str(i), fmt(a.x, L, units), fmt(a.y, L, units), fmt(a.tension, F, units),
                fmt(a.Vx, F, units), fmt(a.Vy, F, units),
                fmt((a.Vx**2 + a.Vy**2) ** 0.5, F, units), fmt(a.uplift, Kind.THICKNESS, units, 3)]
               for i, a in enumerate(r.anchors, start=1)]
    return [("table", [_("Resultado"), "FEM", _("DG1 (bloque rectangular)")], rows, {1, 2}),
            ("h3", _("Fuerzas en anclajes (FEM)")),
            ("table", [_("N.º"), "x", "y", _("Axial"), _("Cortante Vx"), _("Cortante Vy"),
                       _("Cortante total"), _("Levantamiento")], anchors, set(range(1, 8)))]


NOTES = [
    "Las demandas de anclajes, apoyo, placa y soldadura salen del modelo FEM; las "
    "capacidades, de las fórmulas de la norma indicada en cada fila.",
    "El aplastamiento reparte la compresión del FEM en el mayor bloque rectangular centrado en "
    "su resultante, como el bloque de esfuerzos de la guía. La presión media y el pico del "
    "modelo se informan aparte: el concreto del modelo es elástico y no redistribuye.",
    "La deformación plástica de la placa usa la media por elemento y un límite de referencia "
    "configurable (5 %); AISC no fija ese límite.",
    "La soldadura se revisa a tracción y cortante en el punto más solicitado; la compresión se "
    "supone transmitida por contacto. Si el proyecto no da el tamaño del filete se usa el "
    "mínimo de la Tabla J2.4.",
    "Las verificaciones del concreto (ACI) son de resistencia última y solo se evalúan en "
    "combinaciones LRFD.",
    "Herramienta de apoyo: la responsabilidad del diseño es del profesional que lo firma.",
]


def report_blocks(title: str, edition: Edition, units: UnitSystem, combos: list[ComboReport],
                  inputs: list[tuple[str, str]], today: dt.date | None = None,
                  image: str | None = None, traces: bool = True,
                  figures: dict[str, list[tuple[str, str]]] | None = None,
                  ficha: list[tuple[str, str]] | None = None,
                  installation: list[str] | None = None) -> list[Block]:
    """The whole report as blocks: data, FEM results and checks of each combination,
    the analytical path, then :func:`closing_blocks` (summary, recommendations,
    installation requirements, limitations)."""
    today = today or dt.date.today()
    every = [r for c in combos for r in c.fem_checks]
    ok = all(r.status.value != "ng" for r in every)
    worst = max(every, key=lambda r: r.ratio / r.ratio_limit, default=None)
    codes = f"{edition.aisc}, {edition.aci}, {edition.guide}"
    figures = figures or {}
    out: list[Block] = [("h1", title)]
    if ficha:
        out.append(("ficha", ficha))
    out += [
        ("p", _("Verificación de placa base por elementos finitos (CalculiX). Normas: "
                "{codes}. Fecha: {date}.", codes=codes, date=today.isoformat()), ""),
        ("verdict", ok, (". " + _("Gobierna: {check} ({combo}), ratio {ratio}.",
                                 check=check_title(worst), combo=worst.combo,
                                 ratio=f"{worst.ratio:.2f}")) if worst else "."),
        ("h2", _("Datos")),
        ("table", [_("Dato"), _("Valor")], [[k, v] for k, v in inputs], set()),
        ("figs", _("Geometría y malla"), [(c, f) for c, f in figures.get("", []) if f]),
    ]
    drawings = [(c, f) for c, f in figures.get("planos", []) if f]
    if drawings:
        out.append(("figs", _("Planta y elevación acotadas"), drawings, True))
    if image:
        out.append(("image", image))
    for c in combos:
        r = c.results
        a = r.applied
        loads = (f"P = {fmt(a['P'], Kind.FORCE, units)}, My = {fmt(a['My'], Kind.MOMENT, units)}, "
                 f"Mx = {fmt(a['Mx'], Kind.MOMENT, units)}, "
                 f"Vx = {fmt(a['Vx'], Kind.FORCE, units)}, "
                 f"Vy = {fmt(a['Vy'], Kind.FORCE, units)}.")
        out += [("h2", _("Combinación {name} ({method})", name=r.load, method=c.method)),
                ("p", loads, "")]
        if not r.converged:
            out.append(("p", _("El análisis no convergió: llegó al {pct} % de momentos y "
                               "cortantes.", pct=f"{100 * r.load_fraction:.0f}"), "ng"))
        out += [("p", _("Aviso: {msg}", msg=w), "ng") for w in r.warnings]
        out += [("h3", _("Resultados del modelo FEM")), *_fem_summary_blocks(c, units),
                ("figs", _("Gráficos de resultados"),
                 [(cap, f) for cap, f in figures.get(r.load, []) if f]),
                ("h3", _("Verificaciones con demandas del FEM")),
                _checks_block(c.fem_checks, units)]
        if traces:
            out.append(_traces_block(c.fem_checks, units))
        if c.analytical:
            out += [("h3", _("Camino analítico (OpenConex: DG1 3.ª ed., AISC 360-22, "
                             "ACI 318-19)")),
                    ("p", _("Mismas cargas con el método de la guía (placa rígida y bloque de "
                            "esfuerzos). Sirve para ver dónde coincide con el FEM y dónde no."),
                     "note"),
                    _checks_block(c.analytical, units)]
    rows = [[c.results.load, _("Sí") if c.results.converged else _("Incompleto"),
             governing(c.fem_checks), governing(c.analytical) if c.analytical else "—",
             _status_word(c.fem_checks)] for c in combos]
    out += closing_blocks(ok, rows, _base_plate_advice(combos), installation or [],
                          _("Requisitos de instalación de la placa base"),
                          [_(n) for n in NOTES],
                          _("Cambios posibles para que cumpla, uno a la vez; los valores son "
                            "estimaciones: vuelva a resolver después de cambiar los datos."))
    return out


# ---------------------------------------------------------------------------- HTML
def _cell(value) -> str:
    if isinstance(value, tuple):
        return f'<span class="{value[0]}">{escape(value[1])}</span>'
    return escape(str(value))


def blocks_to_html(blocks: list[Block], figure_base: str = "") -> str:
    title = next((b[1] for b in blocks if b[0] == "h1"), "")
    parts = [f"<!doctype html><html lang='{language()}'><head><meta charset='utf-8'>"
             f"<title>{escape(title)}</title><style>{_CSS}</style></head><body>"]
    for b in blocks:
        kind = b[0]
        if kind in ("h1", "h2", "h3"):
            parts.append(f"<{kind}>{escape(b[1])}</{kind}>")
        elif kind == "p":
            cls = f' class="{b[2]}"' if b[2] else ""
            parts.append(f"<p{cls}>{escape(b[1])}</p>")
        elif kind == "verdict":
            word = (f'<span class="ok">{_("Cumple")}</span>' if b[1]
                    else f'<span class="ng">{_("No cumple")}</span>')
            parts.append(f"<p>{_('Resultado global:')} {word}{escape(b[2])}</p>")
        elif kind == "ficha":
            cells = "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>"
                            for k, v in b[1])
            parts.append(f'<table class="ficha">{cells}</table>')
        elif kind == "table":
            _k, headers, rows, numeric = b
            head = "".join(f"<th>{escape(h)}</th>" for h in headers)
            body = "".join(
                "<tr>" + "".join(f'<td class="n">{_cell(c)}</td>' if i in numeric
                                 else f"<td>{_cell(c)}</td>" for i, c in enumerate(row))
                + "</tr>" for row in rows)
            parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
        elif kind == "figs":
            items = b[2]
            if not items:
                continue
            per_row, width = (1, 940) if len(b) > 3 and b[3] else (2, 470)
            rows = ""
            for i in range(0, len(items), per_row):
                rows += "<tr>" + "".join(
                    f'<td class="fig"><img src="{escape(figure_base + name)}" width="{width}" '
                    f'alt="{escape(caption)}"><br><small>{escape(caption)}</small></td>'
                    for caption, name in items[i:i + per_row]) + "</tr>"
            parts.append(f"<h3>{escape(b[1])}</h3><table class='figs'>{rows}</table>")
        elif kind == "advice":
            items = "".join(
                f"<li><b>{escape(t)}</b><ul>" + "".join(f"<li>{escape(a)}</li>" for a in adv)
                + "</ul></li>" for t, adv in b[2])
            parts.append(f"<p class='note'>{escape(b[1])}</p><ul>{items}</ul>")
        elif kind == "traces":
            heads = "".join(f"<th>{_(h)}</th>" for h in ("Símbolo", "Expresión", "Valor",
                                                         "Referencia"))
            for t, ratio, steps in b[1]:
                lines = "".join(
                    f"<tr><td>{latex_to_mathml(sym)}</td><td>{latex_to_mathml(expr)}</td>"
                    f'<td class="n">{value}</td><td>{escape(clause)}</td></tr>'
                    for sym, expr, value, clause in steps)
                parts.append(f"<details><summary>{escape(t)}: ratio {ratio:.2f}</summary>"
                             f"<table><thead><tr>{heads}</tr></thead><tbody>{lines}</tbody>"
                             "</table></details>")
        elif kind == "notes":
            parts.append(f"<h2>{escape(b[1])}</h2><ul class=\"note\">"
                         + "".join(f"<li>{escape(n)}</li>" for n in b[2]) + "</ul>")
        elif kind == "image":
            parts.append(f'<p><img src="{escape(b[1])}" alt="FEM" style="max-width:100%"></p>')
    parts.append("</body></html>")
    return "".join(parts)


def render_report(title: str, edition: Edition, units: UnitSystem, combos: list[ComboReport],
                  inputs: list[tuple[str, str]], today: dt.date | None = None,
                  image: str | None = None, traces: bool = True,
                  figures: dict[str, list[tuple[str, str]]] | None = None,
                  figure_base: str = "", ficha: list[tuple[str, str]] | None = None,
                  installation: list[str] | None = None) -> str:
    return blocks_to_html(report_blocks(title, edition, units, combos, inputs, today, image,
                                        traces, figures, ficha, installation), figure_base)


def write_report(path: str | Path, *args, **kwargs) -> Path:
    path = Path(path)
    path.write_text(render_report(*args, **kwargs), encoding="utf-8")
    return path
