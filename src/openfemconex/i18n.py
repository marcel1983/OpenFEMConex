# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Interface and report language: Spanish (source texts) or English.

Texts are written in Spanish in the code and wrapped in :func:`tr`, which returns
the English text when English is active. Texts with values use named fields:
``tr("Malla: {n} nodos", n=12)``.
"""

from __future__ import annotations

__all__ = ["LANGUAGES", "language", "set_language", "tr"]

LANGUAGES = {"es": "Español", "en": "English"}
_current = "es"


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGUAGES else "es"


def language() -> str:
    return _current


ES: dict[str, str] = {"strong": "eje fuerte", "weak": "eje débil", "both": "ambas (en cruz)",
                      "90": "gancho de 90°", "180": "gancho de 180°", "recta": "recta"}
"""Spanish texts of the few codes that are stored in English in the project file."""


def tr(text: str, context: str = "", **values: object) -> str:
    """Text in the active language; ``context`` tells apart equal Spanish texts."""
    if _current == "en":
        out = EN_CONTEXT.get((context, text)) or EN.get(text, text)
    else:
        out = ES.get(text, text)
    return out.format(**values) if values else out


EN_CONTEXT: dict[tuple[str, str], str] = {
    ("column", "Verificación"): "Check",
}

EN: dict[str, str] = {
    # ribbon: tabs, groups and buttons
    "Proyecto": "Project", "Geometría": "Geometry", "Cargas": "Loads", "Análisis": "Analysis",
    "Verificación": "Checks", "Reporte": "Report", "Ayuda": "Help",
    "Archivo": "File", "Nuevo": "New", "Abrir": "Open", "Guardar": "Save",
    "Guardar como": "Save as", "Unidades y normas": "Units and codes",
    "Unidades de presentación": "Display units", "Normas": "Codes",
    "Componentes": "Components", "Columna": "Column", "Placa": "Plate", "Anclajes": "Anchors",
    "Concreto": "Concrete", "Soldadura": "Weld", "Rigidizadores": "Stiffeners",
    "Vista": "View", "Modelo": "Model", "Malla": "Mesh", "Casos": "Cases",
    "Combinaciones": "Combinations", "Ajustes": "Settings", "Generar malla": "Generate mesh",
    "Resolver": "Solve", "Detener": "Stop", "Resultados": "Results",
    "Combinación": "Combination", "Resultado": "Result", "Deformada": "Deformed shape",
    "Verificaciones": "Checks", "Resumen": "Summary", "Ver en 3D": "Show in 3D",
    "Memoria de cálculo": "Calculation report", "Generar": "Generate",
    "Exportar PDF": "Export PDF", "Apariencia": "Appearance", "Idioma": "Language",
    "Tema": "Theme", "Claro": "Light", "Oscuro": "Dark", "Manual": "Manual",
    "Acerca de": "About",
    "Resuelve las combinaciones marcadas en Cargas": "Solves the combinations ticked in Loads",
    "Abre el reporte completo en el navegador": "Opens the full report in the browser",
    "Manual de uso, verificaciones y validación": "User manual, checks and validation",
    # docks and tables
    "Propiedades": "Properties", "Registro del solver": "Solver log",
    "Demanda": "Demand", "Capacidad": "Capacity", "Ratio": "Ratio", "Estado": "Status",
    "Referencia": "Reference", "Cumple": "OK", "No cumple": "Not OK", "No rige": "Not governing",
    "Símbolo": "Symbol", "Expresión": "Expression", "Valor": "Value", "Dato": "Item",
    # status bar and log
    "Datos no válidos: {error}": "Invalid data: {error}",
    "Los resultados están desactualizados: cambió la geometría, las cargas o los ajustes. "
    "Vuelva a resolver.": "The results are out of date: the geometry, loads or settings "
                          "changed. Solve again.",
    "Gobierna: {check}, ratio {ratio} ({combo})": "Governs: {check}, ratio {ratio} ({combo})",
    "Listo. Sin resultados: use Análisis › Resolver.": "Ready. No results: use Analysis › Solve.",
    "No se pudo mallar: {error}": "Meshing failed: {error}",
    "Malla actual: {nodes} nodos y {elements} hexaedros (tamaño fino {size} mm).":
        "Current mesh: {nodes} nodes and {elements} hexahedra (fine size {size} mm).",
    "Malla: {nodes} nodos, {elements} hexaedros. Salida: {out}":
        "Mesh: {nodes} nodes, {elements} hexahedra. Output: {out}",
    "{name}: falló. {msg}": "{name}: failed. {msg}", "Análisis detenido.": "Analysis stopped.",
    "{name}: resolviendo con CalculiX…": "{name}: solving with CalculiX…",
    "convergió": "converged", "NO convergió ({pct} % de la carga)":
        "did NOT converge ({pct} % of the load)",
    " en {s} s. Tracción total en anclajes {t}, compresión {c}, equilibrio {e} %.":
        " in {s} s. Total anchor tension {t}, compression {c}, equilibrium {e} %.",
    " Gobierna {check}: {ratio}.": " Governs {check}: {ratio}.",
    "Marque al menos una combinación en la pestaña Cargas.":
        "Tick at least one combination in the Loads tab.",
    "Primero resuelva el modelo.": "Solve the model first.",
    "Generando los gráficos del reporte…": "Rendering the report figures…",
    "Reporte escrito en {path}": "Report written to {path}", "PDF escrito en {path}":
        "PDF written to {path}",
    "Cambios sin guardar": "Unsaved changes",
    "El proyecto tiene cambios sin guardar. ¿Descartarlos?":
        "The project has unsaved changes. Discard them?",
    "Abrir proyecto": "Open project", "Guardar proyecto": "Save project",
    "Proyecto OpenConex (*.ocnx *.json)": "OpenConex project (*.ocnx *.json)",
    "Proyecto OpenConex (*.ocnx)": "OpenConex project (*.ocnx)",
    "No se pudo abrir {path}:\n{error}": "Could not open {path}:\n{error}",
    "El idioma se aplica a toda la ventana.": "The language applies to the whole window.",
    # project tree
    "por coordenadas": "by coordinates", "{n} de {d}": "{n} of {d}",
    "filete mínimo": "minimum fillet", "ninguno": "none", "sin resolver": "not solved",
    "no convergió": "did not converge", "ratio máx. {ratio}": "max. ratio {ratio}",
    " (desactualizado)": " (out of date)", "sin título": "untitled",
    "proyecto no válido": "invalid project",
    # check detail
    "Combinación {name}. Referencia: {clause}.": "Combination {name}. Reference: {clause}.",
    "Demanda {d}, capacidad {c}, ratio <b>{r}</b>:": "Demand {d}, capacity {c}, ratio <b>{r}</b>:",
    "cumple": "OK", "no cumple": "not OK",
    "El reporte completo muestra las fórmulas con notación matemática.":
        "The full report shows the formulas in mathematical notation.",
    "<p>No hay verificaciones todavía. Resuelva el modelo en la pestaña Análisis.</p>":
        "<p>No checks yet. Solve the model in the Analysis tab.</p>",
    # forms
    "Perfil AISC": "AISC shape", "Acero": "Steel", "Largo N (dirección del peralte)":
        "Length N (along the depth)", "Ancho B": "Width B", "Espesor tp": "Thickness tp",
    "Diámetro": "Diameter", "Grado": "Grade", "Anclajes por lado": "Anchors per side",
    "Distancia f del eje a cada fila": "Distance f from the axis to each row",
    "Separación entre los extremos de la fila": "Spacing between the outer rods of a row",
    "Empotramiento hef": "Embedment hef", "Arandelas soldadas, espesor":
        "Welded plate washers, thickness",
    "Resistencia f'c": "Strength f'c", "Relación A2/A1": "Ratio A2/A1",
    "Pedestal, largo": "Pedestal, length", "Pedestal, ancho": "Pedestal, width",
    "Espesor de mortero": "Grout thickness", "Concreto fisurado": "Cracked concrete",
    "Fricción μ (verificación)": "Friction μ", "Tamaño del filete": "Fillet size",
    "Electrodo": "Electrode",
    "W, M, S, HP, HSS y Pipe del catálogo AISC": "W, M, S, HP, HSS and Pipe of the AISC catalog",
    "Vacío: sin arandelas soldadas y el cortante va por fricción":
        "Empty: no welded washers, the shear goes by friction",
    "Vacío: concreto sin bordes cercanos": "Empty: concrete without near edges",
    "Vacío: filete mínimo de la Tabla J2.4": "Empty: minimum fillet of Table J2.4",
    "Vacío: mínimo de la Tabla J2.4": "Empty: minimum of Table J2.4",
    "valor con unidad, p. ej. 22 in o 560 mm": "value with unit, e.g. 22 in or 560 mm",
    "Refuerzo del pedestal": "Pedestal reinforcement",
    "Barras longitudinales": "Longitudinal bars", "Diámetro de barra": "Bar diameter",
    "fy del refuerzo": "Reinforcement fy",
    "Recubrimiento libre a estribos": "Clear cover to the ties",
    "Barras con gancho arriba": "Bars hooked at the top", "Terminación arriba": "Top end",
    "90": "90° hook", "180": "180° hook", "recta": "straight",
    "Gancho estándar de 90° o de 180°, o barra recta":
        "Standard 90° or 180° hook, or straight bar", "Diámetro de estribo": "Tie diameter",
    "Separación de estribos": "Tie spacing", "Ramas por estribo": "Legs per tie",
    "Estribos superiores que toman cortante": "Top ties taking shear",
    "Altura del pedestal": "Pedestal height",
    "Se reparten por igual en el perímetro": "Spread evenly along the perimeter",
    "Estribos cerca del tope que encierran los anclajes":
        "Ties near the top enclosing the anchors",
    "El cortante suma V·h al momento en la base del pedestal":
        "The shear adds V·h to the moment at the base of the pedestal",
    "Disposición": "Layout", "Cantidad (radial)": "Count (radial)",
    "Largo desde la cara de la columna": "Length from the column face",
    "Alto junto a la columna": "Height at the column", "Alto en el extremo libre":
        "Height at the free end", "Espesor": "Thickness",
    "Perfiles W: en línea con el alma o tres por patín. Tubos: radial":
        "W shapes: in line with the web or three per flange. Tubes: radial",
    "alma": "web", "alma y bordes": "web and edges", "radial": "radial",
    "Posiciones por coordenadas": "Positions by coordinates",
    "x a lo largo del peralte de la columna, y a lo largo del patín, desde el centro de la "
    "placa": "x along the column depth, y along the flange, from the plate centre",
    "Agregar": "Add", "Quitar": "Remove", "Agregar caso": "Add case", "Quitar caso": "Remove case",
    "<b>Casos de carga</b> (valores con unidad, p. ej. 100 kip)":
        "<b>Load cases</b> (values with unit, e.g. 100 kip)",
    "<b>Combinaciones</b> (marque las que se resuelven)":
        "<b>Combinations</b> (tick the ones to solve)",
    "Combinaciones ASCE 7:": "ASCE 7 combinations:", "Caso": "Case", "Tipo": "Type",
    "P (compresión +)": "P (compression +)", "M (eje fuerte)": "M (strong axis)",
    "V eje débil": "V weak axis", "M eje débil": "M weak axis", "Método": "Method",
    "<b>Ajustes de malla y análisis</b>": "<b>Mesh and analysis settings</b>",
    "automático": "automatic", "Tamaño fino de malla": "Fine mesh size",
    "Tamaño de elemento junto a la columna y los agujeros. Automático: el menor espesor entre "
    "la pared de la columna y la placa.": "Element size next to the column and the holes. "
                                         "Automatic: the thinner of column wall and plate.",
    "Capas en el espesor de la placa": "Layers through the plate", "Hilos de CalculiX":
        "CalculiX threads", "Tuercas de nivelación": "Leveling nuts",
    "Los anclajes también toman compresión": "The anchors also take compression",
    "Límite de deformación plástica": "Plastic strain limit",
    "Visor 3D desactivado": "3D view disabled",
    "Modelo: {nodes} nodos, {elements} hexaedros": "Model: {nodes} nodes, {elements} hexahedra",
    "Resultados {combo}: {field}": "Results {combo}: {field}",
    "Llave de cortante": "Shear lug", "Dirección del cortante que resiste":
        "Direction of the shear it resists", "strong": "strong axis", "weak": "weak axis",
    "both": "both (cruciform)", "Ancho de la llave": "Lug width",
    "Empotramiento bajo el mortero": "Embedment below the grout",
    "Filete a la placa (ambas caras)": "Fillet to the plate (both faces)",
    "Eje fuerte: cortante a lo largo de N (la llave va a lo largo de B). Ambas: llave en cruz":
        "Strong axis: shear along N (the lug runs along B). Both: cruciform lug",
    "Fuerzas en anclajes": "Anchor forces", "Anclaje": "Anchor", "Axial": "Axial",
    "Cortante Vx": "Shear Vx", "Cortante Vy": "Shear Vy", "Cortante total": "Total shear",
    "N = {n} {u}": "N = {n} {u}", "sí": "yes",
    "La columna {col} no resiste las cargas de {combo}: uso plástico {u} (cortante {v}, "
    "axial y flexión {m}). El tramo de columna del modelo fluye por completo y CalculiX no "
    "puede converger. Revise el perfil o las cargas.":
        "Column {col} cannot carry the loads of {combo}: plastic usage {u} (shear {v}, axial "
        "and bending {m}). The modelled column stub yields completely and CalculiX cannot "
        "converge. Check the section or the loads.",
    "En {combo} hay cortante sin compresión: no hay fricción. Sin llave de cortante ni "
    "arandelas soldadas, el modelo supone que los anclajes toman el cortante después de "
    "deslizar la placa en los agujeros (DG1).":
        "In {combo} there is shear without compression: no friction. Without a shear lug or "
        "welded washers, the model assumes the anchors take the shear after the plate slides "
        "in the holes (DG1).",
    "Aviso: {msg}": "Warning: {msg}",
    "barra más cercana a un anclaje en tracción": "bar closest to an anchor in tension",
    "distancia máxima para contar una barra": "largest distance for a bar to count",
    "barras con": "bars with", "distancia anclaje-barra contada": "anchor to counted bar distance",
    "No rige: ninguna barra del pedestal está a menos de 0.5·hef de un anclaje en tracción; "
    "rige el arrancamiento del concreto.": "Not governing: no pedestal bar is within 0.5·hef "
        "of an anchor in tension; concrete breakout governs.",
    "no rige": "not governing",
    "{n} barras de {d}": "{n} bars of {d}",
    "Las barras longitudinales a menos de 0.5·hef de los anclajes en tracción y desarrolladas "
    "sobre el cono trabajan como refuerzo de anclaje a tracción; los estribos superiores, como "
    "refuerzo de anclaje a cortante (ACI 318-19 §17.5.2.1). Si cumplen, reemplazan al "
    "arrancamiento del concreto. Requiere las dimensiones del pedestal (Geometría › Concreto).":
        "Longitudinal bars within 0.5·hef of the anchors in tension and developed above the "
        "cone work as anchor reinforcement in tension; the top ties, as anchor reinforcement "
        "in shear (ACI 318-19 §17.5.2.1). When they work they replace concrete breakout. It "
        "needs the pedestal dimensions (Geometry › Concrete).",
    "{name}: no se resolvió porque la columna no resiste las cargas.":
        "{name}: not solved because the column cannot carry the loads.",
    "no se resolvió porque la columna no resiste las cargas.":
        "not solved because the column cannot carry the loads.",
    # 3D fields and figures
    "von Mises": "von Mises", "Deformación plástica": "Plastic strain",
    "Presión de contacto": "Contact pressure", "Desplazamiento": "Displacement",
    "Contacto [MPa]": "Contact [MPa]", "Desplazamiento [mm]": "Displacement [mm]",
    "Geometría del modelo": "Model geometry", "Malla de elementos finitos": "Finite element mesh",
    "Esfuerzo de von Mises (deformada × {s})": "von Mises stress (deformation × {s})",
    "Deformación plástica equivalente": "Equivalent plastic strain",
    "Desplazamiento total (deformada × {s})": "Total displacement (deformation × {s})",
    "Presión de contacto bajo la placa": "Contact pressure under the plate",
    "máx. placa {p}, columna {c}": "max. plate {p}, column {c}",
    "cabeza de la columna {d} mm": "column top {d} mm", "máx. {m}, media {a}": "max. {m}, mean {a}",
    # check titles
    "Aplastamiento del concreto (bloque centrado en la resultante FEM)":
        "Concrete bearing (block centred on the FEM resultant)",
    "Deformación plástica equivalente de la placa": "Equivalent plastic strain of the plate",
    "Flexión de la placa por tracción de anclajes": "Plate bending from anchor tension",
    "Soldadura columna-placa (punto más solicitado)": "Column-to-plate weld (most loaded point)",
    "Anclaje: resistencia del acero a tracción": "Anchor: steel strength in tension",
    "Anclaje: resistencia del acero a cortante": "Anchor: steel strength in shear",
    "Concreto: arrancamiento del grupo en tracción": "Concrete: group breakout in tension",
    "Anclaje: extracción (pullout)": "Anchor: pullout",
    "Concreto: desprendimiento lateral": "Concrete: side-face blowout",
    "Concreto: arrancamiento en cortante": "Concrete: breakout in shear",
    "Concreto: desprendimiento por palanca (pryout)": "Concrete: pryout",
    "Anclaje: interacción tracción y cortante": "Anchor: tension and shear interaction",
    "Cortante por fricción": "Shear by friction",
    "Refuerzo de anclaje a tracción (barras y horquillas)":
        "Anchor reinforcement in tension (bars and hairpins)",
    "Horquillas: desarrollo sobre el cono (doblez)":
        "Hairpins: development above the cone (bend)",
    "Horquillas: desarrollo bajo el cono (patas)": "Hairpins: development below the cone (legs)",
    "patas de horquilla con": "hairpin legs with",
    "distancia anclaje-pata": "anchor to leg distance",
    "Horquillas en U": "U hairpins", "horquillas en U": "U hairpins",
    "{n} por anclaje de {d} mm, patas a {o} mm del anclaje, largo {L} mm, fy = {fy}":
        "{n} per anchor of {d} mm, legs {o} mm from the anchor, length {L} mm, fy = {fy}",
    "Horquillas por anclaje": "Hairpins per anchor",
    "Distancia del anclaje a cada pata": "Distance from the anchor to each leg",
    "Largo de cada pata": "Length of each leg", "Recubrimiento sobre el doblez":
        "Cover above the bend",
    "Debe ser menor que 0.5·hef para que cuente": "Must be less than 0.5·hef to count",
    "Horquillas en U invertida sobre cada anclaje, con sus dos patas a cada lado del anclaje. "
    "Cuentan como refuerzo de anclaje a tracción si las patas quedan a menos de 0.5·hef y se "
    "desarrollan sobre y bajo el cono (ACI 318-19 §17.5.2.1). No requieren pedestal.":
        "Inverted U hairpins over each anchor, with one leg on each side of it. They count as "
        "anchor reinforcement in tension when the legs are within 0.5·hef and developed above "
        "and below the cone (ACI 318-19 §17.5.2.1). No pedestal is needed.",
    "Refuerzo de anclaje: desarrollo sobre el cono":
        "Anchor reinforcement: development above the cone",
    "Refuerzo de anclaje a cortante (estribos superiores)":
        "Anchor reinforcement in shear (top ties)",
    "Pedestal: flexocompresión de la sección": "Pedestal: axial force and bending",
    "Pedestal: cuantía mínima longitudinal": "Pedestal: minimum longitudinal reinforcement",
    "Anclaje: tracción, cortante y flexión (arandela soldada)":
        "Anchor: tension, shear and bending (welded washer)",
    "Llave de cortante: aplastamiento del concreto": "Shear lug: concrete bearing",
    "Rigidizadores: deformación plástica equivalente": "Stiffeners: equivalent plastic strain",
    "Rigidizadores: soldadura (punto más solicitado)": "Stiffeners: weld (most loaded point)",
    "Rigidizadores: esbeltez del borde libre": "Stiffeners: slenderness of the free edge",
    # report
    "Verificación de placa base por elementos finitos (CalculiX). Normas: {codes}. Fecha: "
    "{date}.": "Base plate check by finite elements (CalculiX). Codes: {codes}. Date: {date}.",
    "Resultado global:": "Overall result:", "Gobierna: {check} ({combo}), ratio {ratio}.":
        "Governs: {check} ({combo}), ratio {ratio}.",
    "Datos": "Input", "Geometría y malla": "Geometry and mesh",
    "Gráficos de resultados": "Result figures",
    "Combinación {name} ({method})": "Combination {name} ({method})",
    "El análisis no convergió: llegó al {pct} % de momentos y cortantes.":
        "The analysis did not converge: it reached {pct} % of the moments and shears.",
    "Resultados del modelo FEM": "Results of the FEM model",
    "Verificaciones con demandas del FEM": "Checks with FEM demands",
    "Camino analítico (OpenConex: DG1 3.ª ed., AISC 360-22, ACI 318-19)":
        "Analytical path (OpenConex: DG1 3rd ed., AISC 360-22, ACI 318-19)",
    "Mismas cargas con el método de la guía (placa rígida y bloque de esfuerzos). Sirve para ver "
    "dónde coincide con el FEM y dónde no.": "Same loads with the method of the guide (rigid "
                                             "plate and stress block), to see where it agrees "
                                             "with the FEM and where it does not.",
    "Alcance y limitaciones": "Scope and limitations",
    "Las demandas de anclajes, apoyo, placa y soldadura salen del modelo FEM; las capacidades, "
    "de las fórmulas de la norma indicada en cada fila.": "The demands on anchors, bearing, "
        "plate and weld come from the FEM model; the capacities from the code formulas named "
        "in each row.",
    "El aplastamiento reparte la compresión del FEM en el mayor bloque rectangular centrado en "
    "su resultante, como el bloque de esfuerzos de la guía. La presión media y el pico del "
    "modelo se informan aparte: el concreto del modelo es elástico y no redistribuye.":
        "Bearing spreads the FEM compression over the largest rectangular block centred on its "
        "resultant, like the stress block of the guide. The mean and peak pressures of the "
        "model are reported apart: the concrete of the model is elastic and does not "
        "redistribute.",
    "La deformación plástica de la placa usa la media por elemento y un límite de referencia "
    "configurable (5 %); AISC no fija ese límite.": "The plastic strain of the plate uses the "
        "element mean and a configurable reference limit (5 %); AISC sets no such limit.",
    "La soldadura se revisa a tracción y cortante en el punto más solicitado; la compresión se "
    "supone transmitida por contacto. Si el proyecto no da el tamaño del filete se usa el "
    "mínimo de la Tabla J2.4.": "The weld is checked for tension and shear at its most loaded "
        "point; compression is assumed to go through contact. Without a fillet size in the "
        "project the minimum of Table J2.4 is used.",
    "Las verificaciones del concreto (ACI) son de resistencia última y solo se evalúan en "
    "combinaciones LRFD.": "The concrete (ACI) checks are strength-level and are evaluated only "
                           "for LRFD combinations.",
    "Herramienta de apoyo: la responsabilidad del diseño es del profesional que lo firma.":
        "Support tool: the design is the responsibility of the engineer who signs it.",
    "FEM": "FEM", "DG1 (bloque rectangular)": "DG1 (rectangular block)",
    "Fuerzas en anclajes (FEM)": "Anchor forces (FEM)", "N.º": "No.", "Tracción": "Tension",
    "Cortante": "Shear", "Levantamiento": "Uplift",
    "Tracción total en anclajes": "Total anchor tension",
    "Compresión sobre el concreto": "Compression on the concrete",
    "Longitud de apoyo": "Bearing length", "Presión de contacto media": "Mean contact pressure",
    "Presión de contacto máxima (concreto elástico)": "Peak contact pressure (elastic concrete)",
    "von Mises máximo en la placa": "Maximum von Mises in the plate",
    "Deformación plástica en la placa (media por elemento / pico nodal)":
        "Plastic strain in the plate (element mean / nodal peak)",
    "Cortante transferido por fricción": "Shear transferred by friction",
    "Error de equilibrio vertical / de momento": "Vertical / moment equilibrium error",
    " (límite {limit})": " (limit {limit})", "Resultado FEM": "FEM result",
    "Columna_": "Column", "Fricción": "Friction", "Pedestal": "Pedestal",
    "{n} de {d} ({grade}), hef = {hef}": "{n} of {d} ({grade}), hef = {hef}",
    "{n} de {d} ({grade}) en posiciones libres, hef = {hef}":
        "{n} of {d} ({grade}) at free positions, hef = {hef}",
    "fisurado": "cracked", "no fisurado": "uncracked",
    "{nodes} nodos, {elements} hexaedros C3D8I": "{nodes} nodes, {elements} C3D8I hexahedra",
    "{n} barras de {d} mm, estribos de {t} mm cada {s} mm, fy = {fy}":
        "{n} bars of {d} mm, ties of {t} mm every {s} mm, fy = {fy}",
}
