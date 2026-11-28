# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Recommendations, installation requirements and scope of the moment end-plate
connection.

The recommendations say what to change for every check that does not pass. They are
qualitative: one change can move several limit states (a thicker plate reduces the
prying force on the bolts, continuity plates switch off the column web checks), so
solve again after each change. The installation requirements are what the
construction must ensure for the assumptions of the analysis to hold. All texts are
the program's own words, not text of AISC.
"""

from __future__ import annotations

from typing import Any

from openconex.connections.moment.fr_moment import MomentConnection
from openconex.core.checks import CheckResult

__all__ = ["ADVICE", "installation_notes", "limitations", "recommendations"]

# check id prefix -> what to change (first match wins)
ADVICE: list[tuple[str, str]] = [
    ("end_plate.fem_bolt_tension",
     "Aumente el diámetro o el grado de los pernos, o el espesor de la placa y del ala de "
     "la columna: el modelo muestra la fuerza de palanca que reciben."),
    ("end_plate.fem_plate_strain",
     "Aumente el espesor de la placa de extremo o acerque los pernos a las alas de la viga."),
    ("end_plate.fem_flange_strain",
     "Agregue placas de continuidad, o use una columna de ala más gruesa: el ala se "
     "plastifica bajo los pernos."),
    ("end_plate.fem_stiffener_strain",
     "Aumente el espesor o la longitud de los rigidizadores."),
    ("end_plate.fem_weld",
     "Aumente el filete de la soldadura de la viga a la placa, o use penetración completa."),
    ("moment.end_plate_yielding",
     "Aumente el espesor de la placa de extremo, acerque las filas de pernos a las alas de "
     "la viga (menor p_f) o cambie a una placa extendida rigidizada (4ES u 8ES)."),
    ("moment.end_plate_bolt_rupture",
     "Aumente el diámetro o el grado de los pernos, o use una placa con más filas (8ES o "
     "multifila). Una placa más gruesa elimina la acción de palanca."),
    ("moment.end_plate_shear",
     "Aumente el espesor o el ancho de la placa de extremo: la extensión no resiste el "
     "cortante de la mitad de la fuerza del ala."),
    ("moment.end_plate_bolt_shear",
     "Aumente el diámetro o el grado de los pernos del lado comprimido, o el espesor de la "
     "placa y del ala de la columna (aplastamiento y desgarre)."),
    ("moment.end_plate_web_weld",
     "Aumente el filete de la soldadura del alma a la placa, o use penetración completa."),
    ("moment.end_plate_flange_weld",
     "Aumente el filete de las alas a la placa o use soldadura de penetración completa."),
    ("moment.column_flange",
     "Agregue placas de continuidad a la altura de las alas de la viga o placas de respaldo "
     "del ala, o use una columna con ala más gruesa."),
    ("moment.column_web",
     "Agregue placas de continuidad a la altura de las alas de la viga, o use una columna "
     "con alma más gruesa."),
    ("moment.continuity_plate",
     "Aumente el espesor o el ancho de las placas de continuidad, o sus soldaduras a la "
     "columna."),
    ("moment.column_panel_zone",
     "Agregue una placa doble en el alma de la columna en la zona de panel, o use una "
     "columna con alma más gruesa."),
    ("moment.doubler",
     "Aumente el espesor de la placa doble o su soldadura a las alas de la columna."),
    ("seismic.beam_flange_slenderness",
     "La viga no es de alta ductilidad: elija un perfil con alas más compactas (b_f/2t_f "
     "menor)."),
    ("seismic.beam_web_slenderness",
     "La viga no es de alta ductilidad: elija un perfil con alma más compacta."),
    ("seismic.column_",
     "Elija una columna que cumpla los límites de la conexión precalificada y de ductilidad "
     "(alas y alma más compactas, peralte dentro del límite)."),
    ("seismic.column_beam_ratio",
     "Aumente la columna (mayor Z_x) o reduzca la viga: la columna debe ser más fuerte que "
     "la viga en el nudo."),
    ("seismic.panel_zone",
     "Agregue una placa doble en la zona de panel o use una columna con alma más gruesa."),
    ("seismic.end_plate_stiffener",
     "Aumente el espesor del rigidizador de la extensión o reduzca su esbeltez."),
    ("seismic.end_plate_",
     "Ajuste la placa o los pernos a los límites de la conexión precalificada (espesor, "
     "ancho, gramil, distancias y diámetro de pernos) y vuelva a resolver."),
    ("seismic.",
     "Revise los datos de la conexión precalificada que intervienen en esta verificación."),
]


def recommendations(checks: list[CheckResult]) -> list[tuple[str, list[str]]]:
    """(failing check, [what to change]) for every applicable check that does not pass,
    the worst first, once per check."""
    from openfemconex.report import check_title

    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    failing = [r for r in checks if r.applicable and r.status.value == "ng"]
    for r in sorted(failing, key=lambda r: r.ratio / (r.ratio_limit or 1.0), reverse=True):
        if r.id in seen:
            continue
        seen.add(r.id)
        text = next((a for prefix, a in ADVICE if r.id.startswith(prefix)),
                    "Revise los datos que intervienen en esta verificación.")
        out.append((f"{check_title(r)} ({r.combo}, ratio {r.ratio:.2f})", [text]))
    return out


def installation_notes(data: dict[str, Any], mc: MomentConnection) -> list[str]:
    """What the construction must ensure for the analysis to be valid."""
    ep = mc.end_plate
    assert ep is not None
    notes = [
        "Planitud: la placa de extremo debe quedar plana después de soldar la viga, para que "
        "apoye en el ala de la columna en toda la zona comprimida como supone el análisis. "
        "Si la soldadura la deforma, enderécela antes del montaje.",
        "Acerque la placa al ala de la columna hasta el contacto firme antes de apretar los "
        "pernos; no use los pernos para cerrar una holgura entre placa y columna.",
    ]
    if ep.snug_tight:
        notes.append(
            "Pernos ajustados sin pretensión (snug-tight), como en el cálculo. Si la conexión "
            "lleva cargas cíclicas, de fatiga o sísmicas, deben ir pretensados.")
    else:
        notes.append(
            "Pernos pretensados según AISC 360-22 tabla J3.1 con un método aprobado (giro de "
            "tuerca, indicador directo de tensión o llave calibrada), apretando del centro "
            "hacia los bordes. El cálculo de la acción de palanca supone esa pretensión.")
    if not ep.flange_weld:
        notes.append(
            "Soldadura de las alas de la viga a la placa de penetración completa, con "
            "inspección por ultrasonido; quite el respaldo y repase la raíz si el "
            "procedimiento lo pide.")
    if mc.continuity_plate:
        notes.append(
            "Placas de continuidad a la altura de las alas de la viga, ajustadas contra el "
            "alma y con los recortes de esquina indicados, soldadas a las alas de la columna "
            "como en los datos.")
    if mc.doubler_plate:
        notes.append(
            "Placa doble del alma ajustada contra el alma de la columna y soldada a las alas "
            "en toda la altura de la zona de panel.")
    if data.get("seismic"):
        notes.append(
            "Conexión sísmica precalificada (AISC 358-22): respete los límites de "
            "precalificación de perfiles, placa y pernos, use pernos pretensados y las "
            "soldaduras de demanda crítica con su inspección y ensayos. La zona protegida "
            "de la viga no admite perforaciones, conectores ni soldaduras de otros "
            "elementos.")
    return notes


def limitations(data: dict[str, Any], mc: MomentConnection) -> list[str]:
    """Scope and limitations of the report."""
    out = [
        "Viga unida al ala de la columna (eje fuerte), con dos pernos por fila.",
        "Resistencia de la placa por líneas de fluencia y fuerzas en los pernos con acción "
        "de palanca según AISC Design Guide 16 (y Design Guide 4 para 8ES); demás estados "
        "límite según AISC 360-22.",
        "La carga axial de la viga se convierte en un momento equivalente sumado al momento "
        "de la combinación.",
        "El cortante lo toman los pernos del lado comprimido.",
        "Modelo CalculiX: viga elástica, placa y ala de la columna elastoplásticas, ala "
        "apoyada rígidamente en el alma y en las placas de continuidad, pernos ajustados "
        "sin pretensión que toman el cortante. El alma de la columna, la zona de panel y "
        "las soldaduras de penetración completa se verifican de forma analítica.",
        "Curva momento-rotación con pernos pretensados y momento solo; no incluye la "
        "deformación del alma ni de la zona de panel de la columna.",
    ]
    if data.get("seismic"):
        out.append("El diseño sísmico revisa la conexión precalificada para el momento "
                   "probable de la viga; no reemplaza la revisión del pórtico.")
    return out
