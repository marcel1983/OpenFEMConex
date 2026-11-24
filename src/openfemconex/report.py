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

__all__ = ["ComboReport", "TITLES", "check_title", "render_report", "write_report"]

TITLES = {
    "fem.concrete_bearing": "Aplastamiento del concreto (bloque centrado en la resultante FEM)",
    "fem.plate_plastic_strain": "Deformación plástica equivalente de la placa",
    "fem.plate_bending_tension": "Flexión de la placa por tracción de anclajes",
    "fem.weld": "Soldadura columna-placa (punto más solicitado)",
    "anchor.steel_tension": "Anclaje: resistencia del acero a tracción",
    "anchor.steel_shear": "Anclaje: resistencia del acero a cortante",
    "anchor.concrete_breakout_tension": "Concreto: arrancamiento del grupo en tracción",
    "anchor.pullout": "Anclaje: extracción (pullout)",
    "anchor.side_face_blowout": "Concreto: desprendimiento lateral",
    "anchor.concrete_breakout_shear": "Concreto: arrancamiento en cortante",
    "anchor.pryout": "Concreto: desprendimiento por palanca (pryout)",
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


_CSS = """
body{font-family:system-ui,sans-serif;max-width:1000px;margin:2em auto;padding:0 1em;color:#222}
h1{font-size:1.5em}h2{font-size:1.2em;margin-top:2em;border-bottom:2px solid #ccc}
h3{font-size:1.05em;margin-top:1.5em}
table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:.92em}
th,td{border:1px solid #ccc;padding:.3em .5em;text-align:left;vertical-align:top}
th{background:#f0f0f0}td.n{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#17692b;font-weight:600}.ng{color:#b00020;font-weight:600}.na{color:#777}
table.figs td{border:none;text-align:center;padding:.4em}
table.figs img{max-width:100%;height:auto;border:1px solid #ddd}
details{margin:.3em 0 .8em}summary{cursor:pointer}small,.note{color:#555;font-size:.88em}
"""


def _status(result: CheckResult) -> str:
    cls = {"ok": "ok", "ng": "ng"}.get(result.status.value, "na")
    text = {"ok": _("Cumple"), "ng": _("No cumple")}.get(result.status.value, _("No rige"))
    return f'<span class="{cls}">{text}</span>'


def _table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td class="n">{c}</td>' if i in numeric else f"<td>{c}</td>"
                         for i, c in enumerate(row)) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _checks_table(checks: list[CheckResult], units: UnitSystem) -> str:
    rows = [[escape(check_title(r)), fmt(r.demand, r.kind, units), fmt(r.capacity, r.kind, units),
             "—" if not r.applicable else
             f"{r.ratio:.2f}" + (_(" (límite {limit})", limit=f"{r.ratio_limit:g}")
                                 if r.ratio_limit != 1 else ""),
             _status(r), escape(r.clause)] for r in checks]
    return _table([_(h, "column") for h in ("Verificación", "Demanda", "Capacidad", "Ratio",
                                            "Estado", "Referencia")], rows, {1, 2, 3})


def _trace(checks: list[CheckResult], units: UnitSystem) -> str:
    out = []
    for r in checks:
        lines = "".join(
            f"<tr><td>{latex_to_mathml(s.symbol)}</td><td>{latex_to_mathml(s.expression)}</td>"
            f'<td class="n">{fmt(s.value, s.kind, units)}</td><td>{escape(s.clause)}</td></tr>'
            for s in r.steps)
        heads = "".join(f"<th>{_(h)}</th>" for h in ("Símbolo", "Expresión", "Valor",
                                                     "Referencia"))
        out.append(f"<details><summary>{escape(check_title(r))}: ratio {r.ratio:.2f}</summary>"
                   f"<table><thead><tr>{heads}</tr></thead><tbody>{lines}</tbody></table>"
                   "</details>")
    return "".join(out)


def _fem_summary(c: ComboReport, units: UnitSystem) -> str:
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
                fmt((a.Vx**2 + a.Vy**2) ** 0.5, F, units), f"{a.uplift:.3f} mm"]
               for i, a in enumerate(r.anchors, start=1)]
    return (_table([_("Resultado"), "FEM", _("DG1 (bloque rectangular)")], rows, {1, 2})
            + f"<h3>{_('Fuerzas en anclajes (FEM)')}</h3>"
            + _table([_("N.º"), "x", "y", _("Axial"), _("Cortante Vx"), _("Cortante Vy"),
                      _("Cortante total"), _("Levantamiento")], anchors, set(range(1, 8))))


def render_report(title: str, edition: Edition, units: UnitSystem, combos: list[ComboReport],
                  inputs: list[tuple[str, str]], today: dt.date | None = None,
                  image: str | None = None, traces: bool = True,
                  figures: dict[str, list[tuple[str, str]]] | None = None,
                  figure_base: str = "") -> str:
    today = today or dt.date.today()
    every = [r for c in combos for r in c.fem_checks]
    ok = all(r.status.value != "ng" for r in every)
    worst = max(every, key=lambda r: r.ratio / r.ratio_limit, default=None)
    codes = f"{edition.aisc}, {edition.aci}, {edition.guide}"
    parts = [
        f"<!doctype html><html lang='{language()}'><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{_CSS}</style></head><body>",
        f"<h1>{escape(title)}</h1>",
        "<p>" + escape(_("Verificación de placa base por elementos finitos (CalculiX). Normas: "
                         "{codes}. Fecha: {date}.", codes=codes, date=today.isoformat()))
        + "</p>",
        f"<p>{_('Resultado global:')} "
        + (f'<span class="ok">{_("Cumple")}</span>' if ok
           else f'<span class="ng">{_("No cumple")}</span>')
        + (". " + escape(_("Gobierna: {check} ({combo}), ratio {ratio}.",
                           check=check_title(worst), combo=worst.combo,
                           ratio=f"{worst.ratio:.2f}")) if worst else ".") + "</p>",
        f"<h2>{_('Datos')}</h2>",
        _table([_("Dato"), _("Valor")], [[escape(k), escape(v)] for k, v in inputs]),
    ]
    figures = figures or {}

    def gallery(key: str, heading: str) -> str:
        items = [(c, f) for c, f in figures.get(key, []) if f]
        if not items:
            return ""
        rows = ""
        for i in range(0, len(items), 2):
            cells = "".join(
                f'<td class="fig"><img src="{escape(figure_base + name)}" width="470" '
                f'alt="{escape(caption)}"><br><small>{escape(caption)}</small></td>'
                for caption, name in items[i:i + 2])
            rows += f"<tr>{cells}</tr>"
        return f"<h3>{_(heading)}</h3><table class='figs'>{rows}</table>"

    parts.append(gallery("", "Geometría y malla"))
    if image:
        parts.append(f'<p><img src="{escape(image)}" alt="FEM" style="max-width:100%"></p>')
    for c in combos:
        r = c.results
        a = r.applied
        state = "" if r.converged else (
            ' <span class="ng">' + escape(_(
                "El análisis no convergió: llegó al {pct} % de momentos y cortantes.",
                pct=f"{100 * r.load_fraction:.0f}")) + "</span>")
        parts += [
            "<h2>" + escape(_("Combinación {name} ({method})", name=r.load, method=c.method))
            + "</h2>",
            f"<p>P = {fmt(a['P'], Kind.FORCE, units)}, My = {fmt(a['My'], Kind.MOMENT, units)}, "
            f"Mx = {fmt(a['Mx'], Kind.MOMENT, units)}, Vx = {fmt(a['Vx'], Kind.FORCE, units)}, "
            f"Vy = {fmt(a['Vy'], Kind.FORCE, units)}.{state}</p>",
            "".join(f'<p class="ng">{escape(_("Aviso: {msg}", msg=w))}</p>'
                    for w in r.warnings),
            f"<h3>{_('Resultados del modelo FEM')}</h3>", _fem_summary(c, units),
            gallery(r.load, "Gráficos de resultados"),
            f"<h3>{_('Verificaciones con demandas del FEM')}</h3>",
            _checks_table(c.fem_checks, units),
            _trace(c.fem_checks, units) if traces else "",
        ]
        if c.analytical:
            parts += [
                f"<h3>{_('Camino analítico (OpenConex: DG1 3.ª ed., AISC 360-22, ACI 318-19)')}"
                "</h3>",
                '<p class="note">' + _("Mismas cargas con el método de la guía (placa rígida y "
                                       "bloque de esfuerzos). Sirve para ver dónde coincide con "
                                       "el FEM y dónde no.") + "</p>",
                _checks_table(c.analytical, units)]
    notes = [
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
    parts.append(f"<h2>{_('Alcance y limitaciones')}</h2><ul class=\"note\">"
                 + "".join(f"<li>{escape(_(n))}</li>" for n in notes) + "</ul></body></html>")
    return "".join(parts)


def write_report(path: str | Path, *args, **kwargs) -> Path:
    path = Path(path)
    path.write_text(render_report(*args, **kwargs), encoding="utf-8")
    return path
