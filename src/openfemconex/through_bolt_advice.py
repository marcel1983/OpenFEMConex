# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Recommendations and installation requirements of the through-bolt connection.

The recommendations say what to change for every check that does not pass; they are
qualitative (one parameter changes the whole load path), so solve again after the
change. The installation requirements are what the construction must ensure for the
assumptions of the analysis to hold: bolts free in their sleeves, snug nuts, plates
seated on the concrete, grout only where the design counts on it.
"""

from __future__ import annotations

from openconex.core.checks import CheckResult

__all__ = ["installation_notes", "recommendations"]

# check id prefix -> what to change (first match wins)
ADVICE: list[tuple[str, str]] = [
    ("through_bolt.fem_bolt_tension",
     "Aumente el diámetro o el grado de los pernos, o agregue filas de pernos. Una placa de "
     "extremo más gruesa reduce la acción de palanca que suma tracción a los pernos."),
    ("through_bolt.bolt_combined",
     "Aumente el diámetro o el grado de los pernos, o agregue pernos: la tracción y el "
     "cortante combinados superan la resistencia del perno."),
    ("through_bolt.fem_plate_strain",
     "Aumente el espesor de la placa de extremo, o acerque los pernos a las alas de la viga "
     "(menor gramil y distancia al ala) para reducir la flexión de la placa."),
    ("through_bolt.fem_back_plate_strain",
     "Aumente el espesor de la placa posterior o su ancho; la placa trabaja en flexión entre "
     "los pernos y la zona apoyada en el concreto."),
    ("through_bolt.fem_weld",
     "Aumente la soldadura de la viga a la placa de extremo (filete mayor o penetración "
     "completa en las alas)."),
    ("through_bolt.fem_back_bearing",
     "Aumente el área de la placa posterior o la resistencia f'c del concreto: el "
     "aplastamiento bajo la placa posterior supera la capacidad."),
    ("through_bolt.fem_bearing",
     "Aumente el ancho o el alto de la placa de extremo, o la resistencia f'c: la presión "
     "de contacto sobre el concreto supera la capacidad de aplastamiento."),
    ("through_bolt.bearing_",
     "Aumente el área de apoyo (placa de extremo o placa posterior más grandes) o f'c."),
    ("through_bolt.bursting_",
     "Coloque refuerzo de hendimiento detrás de la zona cargada (zona de anclaje, ACI 318 "
     "§25.9 por analogía) o amplíe la placa para bajar la fuerza por unidad de área."),
    ("through_bolt.punching",
     "Aumente el espesor del muro o columna, o f'c, o amplíe la placa posterior para "
     "aumentar el perímetro crítico de punzonamiento."),
    ("through_bolt.fem_friction",
     "La fricción no alcanza para el cortante: use grout en las camisas (cortante por "
     "aplastamiento del perno) o cuente solo con la compresión permanente que exista."),
    ("through_bolt.friction_",
     "La fricción no alcanza para el cortante: use grout en las camisas (cortante por "
     "aplastamiento del perno) o cuente solo con la compresión permanente que exista."),
    ("through_bolt.grout_bearing",
     "Aumente la longitud con grout en las camisas o el diámetro de los pernos."),
    ("through_bolt.stm_tie",
     "Aumente el refuerzo vertical del muro o columna junto a la conexión (tensor del "
     "modelo de puntal y tensor) y verifique su anclaje más allá de la zona comprimida."),
    ("through_bolt.stm_",
     "Aumente el espesor del muro o columna o f'c: el puntal diagonal entre las zonas "
     "comprimidas de las dos caras no tiene capacidad suficiente."),
    ("through_bolt.member_flexure",
     "Aumente el refuerzo de flexión del muro o columna en la zona de la conexión, o su "
     "espesor."),
    ("end_plate.",
     "Revise la placa de extremo y los pernos (espesor, diámetro, grado o disposición) "
     "según la verificación que no cumple."),
]


def recommendations(checks: list[CheckResult], title) -> list[tuple[str, list[str]]]:
    """(failing check, [what to change]) for every applicable check that does not pass,
    the worst first; ``title`` names a check."""
    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    failing = [r for r in checks if r.applicable and r.status.value == "ng"]
    for r in sorted(failing, key=lambda r: r.ratio / (r.ratio_limit or 1.0), reverse=True):
        text = next((a for prefix, a in ADVICE if r.id.startswith(prefix)),
                    "Revise los datos que intervienen en esta verificación.")
        label = f"{title(r)} ({r.combo}, ratio {r.ratio:.2f})"
        key = r.id
        if key in seen:
            continue
        seen.add(key)
        out.append((label, [text]))
    return out


def installation_notes(*, grout: bool, back_plate: bool, opposite: bool) -> list[str]:
    """What the construction must ensure for the analysis to be valid."""
    notes = [
        "Camisas sin adherencia: cada perno pasa por una camisa (tubo de PVC o acero) que "
        "atraviesa todo el espesor del muro o columna. Selle los extremos de las camisas "
        "antes de colar para que no entre lechada: el perno debe quedar libre para alargarse "
        "en toda su longitud, como en el modelo (resorte de tracción EA/L entre las dos "
        "caras).",
        "Coloque las camisas con plantilla, coaxiales y perpendiculares a las caras, en la "
        "posición de los agujeros de las placas. Fíjelas al refuerzo sin cortar ni desplazar "
        "barras; el refuerzo de hendimiento y los tensores verticales van alrededor de ellas.",
        "Cara de apoyo: la placa debe apoyarse en toda su superficie. Si la cara del concreto "
        "no es plana, asiente la placa sobre mortero de nivelación sin retracción de "
        "resistencia no menor que f'c, de poco espesor; el modelo supone contacto directo "
        "placa-concreto.",
        "No cargue la conexión ni apriete los pernos hasta que el concreto alcance la "
        "resistencia f'c de diseño.",
        "Apriete las tuercas al contacto firme (snug-tight) en ambas caras, con arandelas "
        "endurecidas. El análisis no cuenta con pretensión de los pernos: no la use para "
        "resistir el cortante por fricción.",
        "Longitud del perno: tuerca completa en cada extremo y al menos dos hilos fuera de "
        "ella; use la tuerca y el grado de perno indicados en los datos.",
    ]
    if grout:
        notes.append(
            "Cortante con grout: inyecte grout sin retracción en la longitud indicada de cada "
            "camisa desde la cara cargada, sin aire atrapado, y deje el resto de la camisa sin "
            "adherencia. Coloque el grout con las tuercas al contacto, antes de cargar.")
    else:
        notes.append(
            "Cortante por fricción: las camisas quedan vacías (sin grout). La fricción solo "
            "cuenta con la compresión permanente sobre el concreto (ACI 318 §22.9): no use "
            "este esquema si la compresión puede desaparecer (sismo, inversión de momento).")
    if back_plate:
        notes.append(
            "Placa posterior corrida: debe quedar asentada en la cara opuesta en toda su "
            "superficie (mortero de nivelación si hace falta) y con los agujeros alineados con "
            "las camisas; es continua en todo su alto, como en el modelo.")
    if opposite:
        notes.append(
            "Viga opuesta: los mismos pernos sujetan las dos placas de extremo. Monte y "
            "asiente las dos placas antes de apretar las tuercas, y apriete en ambas caras "
            "de forma alternada para no desplazar las placas.")
    return notes
