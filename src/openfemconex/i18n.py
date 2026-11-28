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
    "alma": "web", "alma y bordes": "web and edges", "bordes": "edges only",
    "radial": "radial",
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
    "Reporte sin gráficos: el visor 3D (OpenGL) no está disponible.":
        "Report without figures: the 3D viewer (OpenGL) is not available.",
    "No se pudieron generar los gráficos del reporte: {error}":
        "The report figures could not be generated: {error}",
    "Filas frente al eje débil": "Rows facing the weak axis",
    "Sin marcar: las dos filas en x = ±f, frente a los patines (eje fuerte). Marcada: las filas en y = ±f, frente al eje débil, con los anclajes por lado repartidos a lo largo de N":  # noqa: E501
        "Unticked: the two rows at x = ±f, facing the flanges (strong axis). Ticked: the rows at y = ±f, facing the weak axis, with the anchors per side spread along N",  # noqa: E501
    "Malla actual: {nodes} nodos y {elements} hexaedros (tamaño fino {size}).":
        "Current mesh: {nodes} nodes and {elements} hexahedra (fine size {size}).",
    "{n} barras de {d}, estribos de {t} cada {s}, fy = {fy}":
        "{n} bars of {d}, ties of {t} every {s}, fy = {fy}",
    "{n} por anclaje de {d}, patas a {o} del anclaje, largo {L}, fy = {fy}":
        "{n} per anchor of {d}, legs at {o} from the anchor, length {L}, fy = {fy}",
    "cabeza de la columna {d}": "column top {d}",
    "Cortante de anclajes a través del mortero": "Anchor shear through the grout pad",
    "ACI 17.7.1.2.1: con mortero bajo la placa la resistencia del acero a cortante se multiplica por 0.80":  # noqa: E501
        "ACI 17.7.1.2.1: with grout under the plate the steel shear strength is multiplied by 0.80",
    'Exportar Word':
        'Export Word',
    'Word escrito en {path}':
        'Word file written to {path}',
    'Desarrollo de las verificaciones':
        'Check calculations',
    'Elevación acotada':
        'Dimensioned elevation',
    'Planta acotada':
        'Dimensioned plan',
    'Planta y elevación acotadas':
        'Dimensioned plan and elevation',
    'Cliente':
        'Client',
    'Conexión':
        'Connection',
    'Fecha':
        'Date',
    'Ingeniero':
        'Engineer',
    'Número de proyecto':
        'Project number',
    'Revisión':
        'Revision',
    'Columna {name} — {grade}':
        'Column {name} — {grade}',
    "Concreto f'c = {fc}":
        "Concrete f'c = {fc}",
    'Filete {w} a ambos lados del rigidizador':
        '{w} fillet on both sides of the stiffener',
    'Llave de cortante PL {w} × {t}, empotrada {e} — {grade}':
        'Shear lug PL {w} × {t}, embedded {e} — {grade}',
    'Memoria de cálculo: {name}':
        'Calculation report: {name}',
    'Mortero de nivelación {t}':
        'Grout {t}',
    "Pedestal {n} × {b}, f'c = {fc}":
        "Pedestal {n} × {b}, f'c = {fc}",
    'Placa base {n} × {b} × {t} — {grade}':
        'Base plate {n} × {b} × {t} — {grade}',
    'Soldadura de filete {w} ({e}) todo alrededor':
        '{w} fillet weld ({e}) all around',
    'Soldadura de penetración completa (CJP) columna-placa':
        'Complete-joint-penetration (CJP) column-to-plate weld',
    '{n} anclajes Ø {d} — {grade}, hef = {hef}':
        '{n} anchors Ø {d} — {grade}, hef = {hef}',
    '{n} rigidizadores PL {t} — {grade}':
        '{n} stiffeners PL {t} — {grade}',
    'Ficha':
        'Title block',
    'Identificación':
        'Identification',
    'Memoria editable en Word (.docx)':
        'Editable report in Word (.docx)',
    'Proyecto, conexión, ingeniero y revisión que encabezan el reporte':
        'Project, connection, engineer and revision at the head of the report',
    'Nombre de la conexión':
        'Connection name',
    'Por ejemplo: Placa base PB-1, eje A-3':
        'For example: Base plate BP-1, grid A-3',
    'Vacío: la fecha del día del reporte':
        'Empty: the date the report is generated',
    'Soldadura CJP columna-placa: metal base de la pared (punto más solicitado)':
        'CJP column-to-plate weld: base metal of the wall (most stressed point)',
    'Con penetración completa resiste la pared de la columna: aumentar su espesor o su grado de acero, o agregar rigidizadores que repartan la carga.':  # noqa: E501
        'With complete joint penetration the column wall governs: increase its thickness or steel grade, or add stiffeners that spread the load.',  # noqa: E501
    'Penetración completa (CJP)':
        'Complete joint penetration (CJP)',
    'Soldadura columna-placa de penetración completa: la resistencia es la del metal base de la pared de la columna (AISC Tabla J2.5) y no se usa el tamaño del filete':  # noqa: E501
        'Complete-joint-penetration column-to-plate weld: the strength is that of the base metal of the column wall (AISC Table J2.5) and the fillet size is not used',  # noqa: E501
    'Perfiles W: en línea con el alma, solo en los bordes de los patines o ambos. Cruciformes: en línea con las dos almas. Tubos rectangulares: al centro de cada cara, junto a las esquinas (bordes), ambos, o en diagonal en las esquinas (radial). Tubos circulares: radial':  # noqa: E501
        'W-shapes: in line with the web, only at the flange edges, or both. Cruciform: in line with both webs. Rectangular tubes: at the middle of each face, next to the corners (edges), both, or diagonal at the corners (radial). Round tubes: radial',  # noqa: E501
    'Cada combinación necesita al menos un factor distinto de cero.':
        'Every combination needs at least one non-zero factor.',
    'Cada combinación necesita un nombre.':
        'Every combination needs a name.',
    'Comb':
        'Comb',
    'Combinaciones de carga':
        'Load combinations',
    'Hay combinaciones con el mismo nombre.':
        'Several combinations have the same name.',
    'Incluir las combinaciones generadas de ASCE 7':
        'Include the generated ASCE 7 combinations',
    'Las combinaciones ASCE 7 se generan solas a partir de los tipos de caso. Para cambiar sus factores, cópielas como combinaciones propias y desmarque las generadas. Un factor negativo invierte el caso; una celda vacía o 0 lo omite.':  # noqa: E501
        'The ASCE 7 combinations are generated from the case types. To change their factors, copy them as your own combinations and untick the generated ones. A negative factor reverses the case; an empty cell or 0 leaves it out.',  # noqa: E501
    'Sin combinaciones: incluya las de ASCE 7 o defina alguna propia.':
        'No combinations: include the ASCE 7 ones or define your own.',
    'factor no válido en {name}, caso {case}: {text}':
        'invalid factor in {name}, case {case}: {text}',
    'Combinaciones propias con sus factores, o copia editable de las de ASCE 7':
        'Your own combinations with their factors, or an editable copy of the ASCE 7 ones',
    'Editar combinaciones…':
        'Edit combinations…',
    'Editar combinaciones':
        'Edit combinations',
    'Factores':
        'Factors',
    'Subir':
        'Move up',
    'Bajar':
        'Move down',
    'Copiar las de ASCE 7':
        'Copy the ASCE 7 ones',
    'Agrega las combinaciones generadas como combinaciones propias editables':
        'Adds the generated combinations as your own editable combinations',
    'Tubos circulares: rigidizadores alrededor. Tubos rectangulares: 4 en las esquinas, o 8 con uno más al centro de cada cara':  # noqa: E501
        'Round tubes: stiffeners all around. Rectangular tubes: 4 at the corners, or 8 with one more at the middle of each face',  # noqa: E501
    'Planta: dimensiones de la placa y del arreglo de anclajes':
        'Plan: dimensions of the plate and of the anchor layout',
    'Centrar':
        'Fit',
    'Cotas':
        'Dimensions',
    'Dimensiones de la placa y del arreglo de anclajes':
        'Dimensions of the plate and of the anchor layout',
    'Frente':
        'Front',
    'Isométrica':
        'Isometric',
    'Lateral':
        'Side',
    'Planta':
        'Plan',
    'Número de cada anclaje en posiciones libres (por coordenadas), como en la tabla de anclajes y en la de fuerzas':  # noqa: E501
        'Number of every anchor at free positions (by coordinates), as in the anchor table and the anchor forces table',  # noqa: E501
    'Números de anclaje':
        'Anchor numbers',
    'Acercar':
        'Zoom in',
    'Alejar':
        'Zoom out',
    'Centrar el modelo y ajustarlo a la vista':
        'Center the model and fit it to the view',
    'Vista isométrica':
        'Isometric view',
    'Vista en planta (desde arriba)':
        'Plan view (from above)',
    'Vista de frente (plano x-z)':
        'Front view (x-z plane)',
    'Vista lateral (plano y-z)':
        'Side view (y-z plane)',
    'Perfiles W: en línea con el alma o tres por patín. Cruciformes: en línea con las dos almas. Tubos rectangulares: al centro de cada cara, tres por cara o en diagonal en las esquinas (radial). Tubos circulares: radial':  # noqa: E501
        'W-shapes: in line with the web or three per flange. Cruciform: in line with both webs. Rectangular tubes: at the middle of each face, three per face or diagonal at the corners (radial). Round tubes: radial',  # noqa: E501
    "Resuelto con la malla rápida: las fuerzas en anclajes y el aplastamiento difieren menos de 3 % de la malla normal, pero la soldadura columna-placa puede quedar hasta 10 % por debajo y la deformación plástica bastante por debajo. Confirme con la malla normal antes de la memoria final.":  # noqa: E501
        "Solved with the fast mesh: anchor forces and bearing differ by less than 3 % from the normal mesh, but the column-to-plate weld may come out up to 10 % low and the plastic strain well below. Confirm with the normal mesh before the final report.",  # noqa: E501
    'Deteniendo CalculiX…':
        'Stopping CalculiX…',
    'Malla rápida.':
        'Fast mesh.',
    'Malla rápida (prioriza el tiempo de solución)':
        'Fast mesh (favours solution time)',
    'Sigue siendo automática, con elementos de unas dos veces el tamaño normal en la placa y tres capas en su espesor. En los ejemplos tardó entre un quinto y la mitad del tiempo (más ahorro cuanto más grande el modelo); anclajes y aplastamiento cambian menos de 3 %, la soldadura hasta 10 % por debajo. Útil para tantear; para la memoria final use la malla normal.':  # noqa: E501
        'Still automatic, with elements about twice the normal size in the plate and three layers through it. In the examples it took between a fifth and half of the time (more savings on larger models); anchors and bearing change by less than 3 %, the weld comes out up to 10 % low. Useful for trial designs; use the normal mesh for the final report.',  # noqa: E501
    'Análisis terminado.':
        'Analysis finished.',
    'CalculiX no convergió: se reintenta con la ley de anclaje suavizada':
        'CalculiX did not converge: retrying with the softened anchor law',
    'Cancelando…':
        'Cancelling…',
    'Cancelar':
        'Cancel',
    'Cerrar':
        'Close',
    'Combinación {i} de {n}: {name}':
        'Combination {i} of {n}: {name}',
    'El análisis sigue; el avance queda en la barra de estado':
        'The analysis goes on; the progress stays in the status bar',
    'Iteración {i} del incremento siguiente; residuo de fuerza máximo {r} N':
        'Iteration {i} of the next increment; largest residual force {r} N',
    'Malla de {elements} hexaedros y {nodes} nodos; {n} combinaciones; CalculiX con {t} hilos.':
        'Mesh of {elements} hexahedra and {nodes} nodes; {n} combinations; CalculiX with {t} threads.',  # noqa: E501
    'Ocultar':
        'Hide',
    'Paso {step} ({load}), incremento {n}: no convergió en {it} iteraciones; se reintenta con un incremento menor':  # noqa: E501
        'Step {step} ({load}), increment {n}: did not converge in {it} iterations; retrying with a smaller increment',  # noqa: E501
    'Paso {step} ({load}), incremento {n}: {pct} % aplicado, {it} iteraciones':
        'Step {step} ({load}), increment {n}: {pct} % applied, {it} iterations',
    'Resolviendo con CalculiX':
        'Solving with CalculiX',
    'Tiempo total {t}.':
        'Total time {t}.',
    'Tiempo: {t} en esta combinación, {all} en total':
        'Time: {t} in this combination, {all} in total',
    'Total':
        'Total',
    'carga axial':
        'axial load',
    'momentos y cortantes':
        'moments and shears',
    '— {name} —':
        '— {name} —',
    'CalculiX resolviendo':
        'CalculiX solving',
    'Escribiendo el archivo de CalculiX (.inp)':
        'Writing the CalculiX input file (.inp)',
    'Generando la malla':
        'Generating the mesh',
    'Leyendo los resultados':
        'Reading the results',
    'Los datos no cambiaron: se reutiliza la solución anterior':
        'The data did not change: the previous solution is reused',
    '(malla rápida)':
        '(fast mesh)',
    'Verificaciones de AISC y ACI':
        'AISC and ACI checks',
    'Avance':
        'Progress',
    'Muestra el avance detallado de CalculiX':
        'Shows the detailed progress of CalculiX',
    'A = {a}; Mp eje fuerte = {mpy}; Mp eje débil = {mpx}':
        'A = {a}; strong-axis Mp = {mpy}; weak-axis Mp = {mpx}',
    'Acero nuevo':
        'New steel',
    'Aceros':
        'Steels',
    'Copiar del catálogo':
        'Copy from catalog',
    'Corrija el grado {name}: falta o no es válido {error}':
        'Fix the grade {name}: {error} is missing or not valid',
    'Corrija el material {name}: {error}':
        'Fix the material {name}: {error}',
    'Corrija el perfil {name}: {error}':
        'Fix the section {name}: {error}',
    'Crea un perfil armado con las dimensiones de un perfil AISC':
        'Creates a built-up section with the dimensions of an AISC shape',
    'Cruciforme (perfil W + perfil cruzado en dos T)':
        'Cruciform (W-shape + cross shape split in two tees)',
    'Cruciforme: un segundo perfil I cortado por el alma y soldado a las dos caras del alma del principal; sus patines quedan a lo largo del eje y':  # noqa: E501
        'Cruciform: a second I-shape split along its web and welded to both faces of the main web; its flanges lie along the y axis',  # noqa: E501
    'El acero {name} está en uso en el proyecto.':
        'The steel {name} is used in the project.',
    'El grado {name} está en uso en el proyecto.':
        'The grade {name} is used in the project.',
    'El perfil es la columna del proyecto: elija otra columna antes de eliminarlo.':
        'This section is the column of the project: choose another column before deleting it.',
    'En el modelo de elementos finitos los anclajes son resortes elásticos que solo trabajan a tracción (y a compresión con tuercas de nivelación); sus resistencias se usan en las verificaciones de AISC y ACI.':  # noqa: E501
        'In the finite element model the anchors are elastic springs that only work in tension (and in compression with leveling nuts); their strengths are used in the AISC and ACI checks.',  # noqa: E501
    'Esfuerzo':
        'Stress',
    'Fu debe ser al menos Fy':
        'Fu must be at least Fy',
    'Fy, Fu y E deben ser positivos':
        'Fy, Fu and E must be positive',
    'Grado de la biblioteca AISC (Tabla J3.2), solo lectura.':
        'Grade of the AISC library (Table J3.2), read only.',
    'Grado del proyecto.':
        'Grade of the project.',
    'Grado nuevo':
        'New grade',
    'Hay perfiles con el mismo nombre.':
        'Several sections have the same name.',
    'Ley constitutiva (FEM)':
        'Constitutive law (FEM)',
    'Material de la biblioteca AISC: sus resistencias son fijas; la ley del modelo de elementos finitos sí se puede cambiar.':  # noqa: E501
        'Material of the AISC library: its strengths are fixed, but its law in the finite element model can be changed.',  # noqa: E501
    'Material del proyecto: todas sus propiedades se pueden editar.':
        'Material of the project: all its properties can be edited.',
    'Materiales':
        'Materials',
    'Materiales…':
        'Materials…',
    'Módulo de endurecimiento H':
        'Hardening modulus H',
    'Perfil':
        'Section',
    'Perfil I del catálogo o armado; sus patines deben caber entre los patines del perfil principal':  # noqa: E501
        'I-shape from the catalog or built-up; its flanges must fit between the flanges of the main shape',  # noqa: E501
    'Perfil armado':
        'Built-up section',
    'Perfil cruzado':
        'Cross shape',
    'Perfil simple':
        'Single shape',
    'Perfiles I doblemente simétricos formados por tres placas soldadas, sin radios de acuerdo. Se guardan con el proyecto y aparecen en la lista de perfiles de la columna y del perfil cruzado de una cruciforme.':  # noqa: E501
        'Doubly symmetric I-shapes made of three welded plates, without fillets. They are saved with the project and appear in the section lists of the column and of the cross shape of a cruciform.',  # noqa: E501
    'Perfiles armados':
        'Built-up sections',
    'Perfiles armados…':
        'Built-up sections…',
    'Perfiles del proyecto':
        'Sections of the project',
    'Puntos (esfuerzo verdadero, deformación plástica); el primero es la fluencia con deformación plástica 0':  # noqa: E501
        'Points (true stress, plastic strain); the first one is the yield point with plastic strain 0',  # noqa: E501
    'Usar como columna':
        'Use as column',
    'W, M, S, HP, HSS y Pipe del catálogo AISC, o un perfil armado del proyecto':
        'W, M, S, HP, HSS and Pipe of the AISC catalog, or a built-up section of the project',
    'armado':
        'built-up',
    'biblioteca':
        'library',
    'copia':
        'copy',
    'deformación unitaria total':
        'total strain',
    'eje x: fuerte (a lo largo de d)':
        'x axis: strong (along d)',
    'el alma es más gruesa que el ancho del patín':
        'the web is thicker than the flange width',
    'esfuerzo':
        'stress',
    'las dimensiones deben ser positivas':
        'the dimensions must be positive',
    'los patines son más gruesos que el peralte':
        'the flanges are thicker than the depth',
    'sin curva':
        'no curve',
    'sin sección':
        'no section',
    'εp al final del escalón de fluencia':
        'εp at the end of the yield plateau',
    'εp última (en Fu para la trilineal)':
        'ultimate εp (at Fu for the trilinear law)',
    'ν, coeficiente de Poisson':
        "ν, Poisson's ratio",
    'cruciforme {main} + {cross}':
        'cruciform {main} + {cross}',
    'cruciforme {main} + {cross} ({grade})':
        'cruciform {main} + {cross} ({grade})',
    'Nombre':
        'Name',
    'Peralte d':
        'Depth d',
    'Ancho de patín bf':
        'Flange width bf',
    'Espesor de patín tf':
        'Flange thickness tf',
    'Espesor de alma tw':
        'Web thickness tw',
    'Distancia k de diseño (opcional)':
        'Design distance k (optional)',
    'Fy, fluencia mínima':
        'Fy, minimum yield stress',
    'Fu, resistencia a tracción':
        'Fu, tensile strength',
    'E, módulo de elasticidad':
        'E, modulus of elasticity',
    'Fy, fluencia (opcional)':
        'Fy, yield stress (optional)',
    'Fnt, tracción nominal':
        'Fnt, nominal tensile stress',
    'Fnv, cortante con rosca en el plano':
        'Fnv, shear stress, threads included',
    'Fnv, cortante sin rosca en el plano':
        'Fnv, shear stress, threads excluded',
    'Bilineal (endurecimiento lineal)':
        'Bilinear (linear hardening)',
    'Elastoplástica perfecta':
        'Elastic-perfectly plastic',
    'Trilineal (escalón de fluencia y endurecimiento hasta Fu)':
        'Trilinear (yield plateau and hardening up to Fu)',
    'Tabla de puntos':
        'Table of points',
    'Biblioteca':
        'Library',
    'Perfiles':
        'Sections',
    'Perfiles W armados de placas, guardados con el proyecto':
        'W-shapes built up from plates, saved with the project',
    'Aceros y grados de anclaje, con la ley constitutiva del modelo FEM':
        'Steels and anchor rod grades, with the constitutive law of the FEM model',
    'Duplicar':
        'Duplicate',
    'Eliminar':
        'Delete',
    'Agregar punto':
        'Add point',
    'Quitar punto':
        'Remove point',
    'Perfiles W: en línea con el alma o tres por patín. Cruciformes: en línea con las dos almas. Tubos: radial':  # noqa: E501
        'W-shapes: in line with the web or three per flange. Cruciform: in line with both webs. Tubes: radial',  # noqa: E501
    'Aumentar el diámetro del anclaje a {d} ({grade}).':
        'Increase the anchor diameter to {d} ({grade}).',
    'O usar un grado más resistente con el mismo diámetro: {grade}.':
        'Or use a stronger grade with the same diameter: {grade}.',
    'Aumentar el empotramiento hef a {h} como mínimo.':
        'Increase the embedment hef to at least {h}.',
    'Aumentar hef no basta con los bordes actuales (hasta 25 in.): use refuerzo de anclaje o un pedestal mayor.':  # noqa: E501
        'Increasing hef is not enough with the current edges (up to 25 in.): use anchor reinforcement or a larger pedestal.',  # noqa: E501
    'O agregar refuerzo de anclaje (barras del pedestal a menos de 0.5·hef u horquillas en U) con As ≥ {a}, desarrollado a ambos lados del cono; así el arrancamiento deja de regir.':  # noqa: E501
        'Or add anchor reinforcement (pedestal bars within 0.5·hef or U hairpins) with As ≥ {a}, developed on both sides of the cone; breakout then no longer governs.',  # noqa: E501
    'O agregar anclajes para repartir la tracción.':
        'Or add anchors to share the tension.',
    'O tomar el cortante con una llave de cortante o por fricción (sin arandelas soldadas).':
        'Or carry the shear with a shear lug or by friction (without welded washers).',
    'O separar más los anclajes o alejarlos de los bordes del pedestal.':
        'Or space the anchors further apart or away from the pedestal edges.',
    'Aumentar el área de apoyo de la cabeza embebida a {a} (por ejemplo, una placa de {s} × {s} bajo la tuerca).':  # noqa: E501
        'Increase the bearing area of the embedded head to {a} (for instance a {s} × {s} plate under the nut).',  # noqa: E501
    'O usar un diámetro de anclaje mayor (tuerca más grande).':
        'Or use a larger anchor diameter (larger nut).',
    'Alejar los anclajes del borde lateral o agrandar el pedestal; también puede reducirse hef para que no supere 2.5 veces la distancia al borde.':  # noqa: E501
        'Move the anchors away from the side edge or enlarge the pedestal; hef may also be reduced so that it does not exceed 2.5 times the edge distance.',  # noqa: E501
    'Aumentar la distancia al borde en la dirección del cortante (pedestal más grande) o el espesor del pedestal.':  # noqa: E501
        'Increase the edge distance in the direction of the shear (larger pedestal) or the pedestal depth.',  # noqa: E501
    'O agregar estribos superiores como refuerzo de anclaje a cortante con Av ≥ {a}.':
        'Or add top ties as anchor reinforcement in shear with Av ≥ {a}.',
    'O tomar el cortante con una llave de cortante.':
        'Or carry the shear with a shear lug.',
    'Aumentar el empotramiento hef a {h} aproximadamente, o separar más los anclajes.':
        'Increase the embedment hef to about {h}, or space the anchors further apart.',
    'Bajar la mayor de las dos relaciones (tracción o cortante) con las recomendaciones de su verificación; la suma debe quedar en 1.2 o menos.':  # noqa: E501
        'Lower the larger of the two ratios (tension or shear) following the advice for its check; the sum must be 1.2 or less.',  # noqa: E501
    'Aumentar el diámetro del anclaje a {d} aproximadamente.':
        'Increase the anchor diameter to about {d}.',
    'O reducir el brazo de flexión: placa más delgada o arandela soldada más delgada, o tomar el cortante con una llave.':  # noqa: E501
        'Or reduce the bending lever: thinner plate or thinner welded washer, or carry the shear with a lug.',  # noqa: E501
    'Agrandar la placa: con el mismo largo N, el ancho B debería ser de {b} aproximadamente.':
        'Enlarge the plate: with the same length N, the width B should be about {b}.',
    'O un pedestal mayor que la placa (A2/A1 = {r}, máximo 4).':
        'Or a pedestal larger than the plate (A2/A1 = {r}, at most 4).',
    "O un concreto de f'c = {fc}.":
        "Or concrete with f'c = {fc}.",
    'Aumentar el espesor de la placa a {t}.':
        'Increase the plate thickness to {t}.',
    'O acercar los anclajes a la columna, o agregar rigidizadores.':
        'Or move the anchors closer to the column, or add stiffeners.',
    'Aumentar el espesor de la placa (la deformación plástica baja rápido con el espesor) o agregar rigidizadores; vuelva a resolver.':  # noqa: E501
        'Increase the plate thickness (plastic strain drops quickly with thickness) or add stiffeners; solve again.',  # noqa: E501
    'Aumentar el tamaño del filete a {w}.':
        'Increase the fillet size to {w}.',
    'Aumentar el tamaño del filete en proporción {r} (o usar soldadura de penetración completa).':
        'Increase the fillet size by a factor of {r} (or use a complete-joint-penetration weld).',
    'O un electrodo más resistente (E80XX).':
        'Or a stronger electrode (E80XX).',
    'Aumentar el espesor del rigidizador a {t} o acortar su largo.':
        'Increase the stiffener thickness to {t} or shorten it.',
    'Rigidizadores más gruesos o más altos; vuelva a resolver.':
        'Thicker or taller stiffeners; solve again.',
    'Agregar una llave de cortante, o arandelas soldadas para que los anclajes tomen el cortante.':
        'Add a shear lug, or welded washers so that the anchors take the shear.',
    'Aumentar el refuerzo de anclaje a As ≥ {a} (más barras a menos de 0.5·hef, más horquillas o de mayor diámetro).':  # noqa: E501
        'Increase the anchor reinforcement to As ≥ {a} (more bars within 0.5·hef, more or larger hairpins).',  # noqa: E501
    'Falta largo de desarrollo sobre el cono: aumentar hef en {d} como mínimo, usar barras más delgadas o con gancho.':  # noqa: E501
        'Development length above the cone is short: increase hef by at least {d}, or use thinner or hooked bars.',  # noqa: E501
    'Alargar las patas de las horquillas en {d} como mínimo.':
        'Lengthen the hairpin legs by at least {d}.',
    'Más estribos superiores, más ramas o de mayor diámetro: Av ≥ {a}.':
        'More top ties, more legs or larger ties: Av ≥ {a}.',
    'Más barras longitudinales o de mayor diámetro, o un pedestal mayor.':
        'More or larger longitudinal bars, or a larger pedestal.',
    'Usar al menos {n} barras del diámetro actual (1 % del área).':
        'Use at least {n} bars of the current diameter (1 % of the area).',
    'Aumentar el espesor, el ancho o el empotramiento de la llave de cortante, según el estado límite.':  # noqa: E501
        'Increase the thickness, width or embedment of the shear lug, depending on the limit state.',  # noqa: E501
    'Revise los datos de este componente; la relación es {r}.':
        'Review the data of this component; the ratio is {r}.',
    'Recomendaciones':
        'Recommendations',
    'Cambios posibles para que cumpla, uno a la vez; los valores son estimaciones: vuelva a resolver después de cambiar los datos.':  # noqa: E501
        'Possible changes to make it pass, one at a time; the values are estimates: solve again after changing the data.',  # noqa: E501
    'filete':
        'fillet',
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
    "Presión de contacto en la cara opuesta": "Contact pressure on the far face",
    "Reporte editable en Word (.docx), con los mismos gráficos":
        "Editable Word report (.docx) with the same figures",
    "Modelo de elementos finitos (vista isométrica)": "Finite element model (isometric view)",
    "Malla de elementos finitos (vista isométrica)": "Finite element mesh (isometric view)",
    "Esfuerzo de von Mises (deformada × {s}): máx. {v} MPa":
        "von Mises stress (deformation × {s}): max. {v} MPa",
    "Deformación plástica equivalente: máx. {p} %": "Equivalent plastic strain: max. {p} %",
    "Presión de contacto de la {plate} sobre el concreto: máx. {p} MPa":
        "Contact pressure of the {plate} on the concrete: max. {p} MPa",
    "placa de extremo": "end plate", " de la viga 1": " of beam 1",
    "placa de extremo de la viga 2": "end plate of beam 2", "placa posterior": "back plate",
    "placa opuesta": "far plate",
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
    "Concreto: desprendimiento lateral del anclaje más cargado":
        "Concrete: side-face blowout of the most loaded anchor",
    "Concreto: desprendimiento lateral del grupo junto al borde":
        "Concrete: side-face blowout of the group along the edge",
    "Concreto: arrancamiento del grupo en cortante": "Concrete: group breakout in shear",
    "Concreto: desprendimiento por palanca del grupo (pryout)": "Concrete: group pryout",
    "Anclaje: interacción tracción y cortante": "Anchor: tension and shear interaction",
    "Cortante por fricción": "Shear by friction",
    "Pernos pasantes: aplastamiento bajo la placa frontal, arriba":
        "Through-bolts: bearing under the end plate, top",
    "Pernos pasantes: hendimiento detrás de la placa frontal, arriba":
        "Through-bolts: bursting behind the end plate, top",
    "Pernos pasantes: aplastamiento bajo la placa frontal, abajo":
        "Through-bolts: bearing under the end plate, bottom",
    "Pernos pasantes: hendimiento detrás de la placa frontal, abajo":
        "Through-bolts: bursting behind the end plate, bottom",
    "Pernos pasantes: cortante por fricción en la placa frontal":
        "Through-bolts: shear by friction at the end plate",
    "Pernos pasantes: apoyo del perno en el grout, placa frontal":
        "Through-bolts: bolt bearing on the grout, end plate",
    "Pernos pasantes: aplastamiento bajo la placa del otro lado, arriba":
        "Through-bolts: bearing under the far plate, top",
    "Pernos pasantes: hendimiento detrás de la placa del otro lado, arriba":
        "Through-bolts: bursting behind the far plate, top",
    "Pernos pasantes: aplastamiento bajo la placa del otro lado, abajo":
        "Through-bolts: bearing under the far plate, bottom",
    "Pernos pasantes: hendimiento detrás de la placa del otro lado, abajo":
        "Through-bolts: bursting behind the far plate, bottom",
    "Pernos pasantes: cortante por fricción en la placa del otro lado":
        "Through-bolts: shear by friction at the far plate",
    "Pernos pasantes: apoyo del perno en el grout, placa del otro lado":
        "Through-bolts: bolt bearing on the grout, far plate",
    "Pernos pasantes: punzonamiento de la zona de arriba":
        "Through-bolts: punching shear of the top zone",
    "Puntal y tensor: nodo de arriba": "Strut-and-tie: top node",
    "Pernos pasantes: punzonamiento de la zona de abajo":
        "Through-bolts: punching shear of the bottom zone",
    "Puntal y tensor: nodo de abajo": "Strut-and-tie: bottom node",
    "Pernos pasantes: tracción, cortante y flexión del perno con grout":
        "Through-bolts: bolt tension, shear and bending with grout",
    "Puntal y tensor: ángulo entre puntal y tensor": "Strut-and-tie: angle between strut and tie",
    "Puntal y tensor: puntal diagonal del concreto": "Strut-and-tie: diagonal concrete strut",
    "Puntal y tensor: refuerzo vertical como tensor": "Strut-and-tie: vertical bars as tie",
    "Puntal y tensor: desarrollo del tensor más allá del nodo":
        "Strut-and-tie: development of the tie past the node",
    "Muro o columna: flexocompresión junto a la conexión":
        "Wall or column: flexure and axial force next to the connection",
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

# several connections per project and the through-bolt connection in the interface
_CONNECTIONS: dict[str, str] = {
    "Conexiones": "Connections", "Agregar conexión": "Add connection",
    "Quitar conexión": "Remove connection", "Nuevo proyecto": "New project",
    "Agrega al proyecto una conexión de otro tipo, elegido con su imagen":
        "Adds a connection of another type to the project, picked from its picture",
    "Quita del proyecto la conexión seleccionada":
        "Removes the selected connection from the project",
    "¿Quitar la conexión {name} del proyecto?": "Remove connection {name} from the project?",
    "Elija el tipo de conexión. Un proyecto puede tener varias conexiones; cada una tiene "
    "sus datos, cargas y reporte.":
        "Pick the connection type. A project can hold several connections; each one has "
        "its own data, loads and report.",
    "(próximamente)": "(coming soon)",
    "Placa base": "Base plate", "Pernos pasantes en concreto": "Through-bolts in concrete",
    "Corte simple": "Shear tab", "Momento con placa de extremo": "Moment end plate",
    "Empalme de viga": "Beam splice",
    "Columna sobre placa base con anclajes en pedestal o fundación. Modelo de elementos "
    "finitos con CalculiX y verificaciones AISC 360, DG1 y ACI 318.":
        "Column on a base plate with anchors in a pedestal or footing. Finite element "
        "model with CalculiX and AISC 360, DG1 and ACI 318 checks.",
    "Viga con placa de extremo y pernos pasantes en un muro o columna nuevo de concreto, "
    "con placa posterior corrida o viga opuesta. Cálculo analítico y modelo CalculiX de la "
    "placa de extremo.":
        "Beam end plate with through-bolts across a new concrete wall or column, with a "
        "continuous back plate or an opposite beam. Analytic checks and a CalculiX model "
        "of the end plate.",
    "Placa simple a la columna. Próximamente.": "Single plate to the column. Coming soon.",
    "Viga a columna de acero. Próximamente.": "Beam to steel column. Coming soon.",
    "Empalme con cubreplacas. Próximamente.": "Splice with cover plates. Coming soon.",
    "El proyecto ya tiene una placa base (una por proyecto en esta versión)":
        "The project already has a base plate (one per project in this version)",
    "el proyecto ya tiene una placa base": "the project already has a base plate",
    "el proyecto necesita al menos una conexión": "the project needs at least one connection",
    "el proyecto no tiene placa base": "the project has no base plate",
    "Identificación": "Identification", "Nombre de la conexión": "Connection name",
    "Por ejemplo: PP-1, muro eje 3": "For example: PP-1, wall on grid 3",
    "Viga": "Beam", "Perfil": "Shape", "Acero": "Steel",
    "Perfiles W, M, S y HP del catálogo AISC": "W, M, S and HP shapes of the AISC catalog",
    "Placa de extremo": "End plate", "Disposición": "Layout", "Ancho bp": "Width bp",
    "Espesor tp": "Thickness tp", "Diámetro de los pernos": "Bolt diameter",
    "Grado de los pernos": "Bolt grade", "Gramil g": "Gage g",
    "pf (fila interior a la cara del patín)": "pf (inner row to the flange face)",
    "pb (entre filas interiores)": "pb (between inner rows)",
    "Solo para las disposiciones con dos filas entre los patines":
        "Only for the layouts with two rows between the flanges",
    "pf,o (fila exterior al patín)": "pf,o (outer row to the flange)",
    "Placas extendidas": "Extended plates", "Extensión pext": "Extension pext",
    "Filete del alma": "Web fillet weld", "Filete de los patines": "Flange fillet weld",
    "Vacío: soldadura de penetración completa": "Empty: complete joint penetration weld",
    "Placa posterior": "Back plate", "Ancho": "Width", "Alto": "Height",
    "Espesor": "Thickness",
    "Vacío: el alto de la placa de extremo + 50 mm": "Empty: the end plate height + 50 mm",
    "Diámetro de arandela": "Washer diameter",
    "Vacío: el núcleo de apoyo es la placa misma": "Empty: the bearing core is the plate",
    "Muro o columna": "Wall or column", "Tipo": "Type", "Muro": "Wall",
    "Espesor h (dirección de los pernos)": "Thickness h (along the bolts)",
    "Ancho de la columna": "Column width",
    "Solo columnas; un muro es continuo a los lados":
        "Columns only; a wall is continuous at the sides",
    "f'c": "f'c", "Recubrimiento libre": "Clear cover",
    "Barras verticales, diámetro": "Vertical bars, diameter",
    "Barras verticales, separación": "Vertical bars, spacing",
    "Barras horizontales, diámetro": "Horizontal bars, diameter",
    "Barras horizontales, separación": "Horizontal bars, spacing",
    "fy del refuerzo": "Reinforcement fy",
    "Estribos que cruzan el espesor": "Ties across the thickness",
    "El puntal se revisa con βs = 0.75 en vez de 0.4":
        "The strut is checked with βs = 0.75 instead of 0.4",
    "Distancia al extremo superior": "Distance to the top end",
    "Distancia al extremo inferior": "Distance to the bottom end",
    "Vacío: el elemento continúa": "Empty: the member continues",
    "Carga axial (compresión +)": "Axial force (compression +)",
    "Viga opuesta": "Opposite beam",
    "Hay una viga del otro lado (conexión opuesta)":
        "There is a beam on the far side (opposite connection)",
    "Cortante": "Shear", "Transferencia": "Transfer", "Grout en las camisas": "Grout in sleeves",
    "Coeficiente de fricción μ": "Friction coefficient μ", "Largo con grout ℓg":
        "Grouted length ℓg", "f'c del grout": "Grout f'c",
    "Vacío: el f'c del concreto": "Empty: the concrete f'c",
    "Holgura g entre placa y grout": "Gap g between plate and grout",
    "Con viga del otro lado, su placa de extremo es la placa posterior: usa la misma placa y "
    "los mismos pernos que la viga 1 (filas, gramil y diámetro).":
        "With a beam on the far side, its end plate is the back plate: it uses the same plate "
        "and bolts as beam 1 (rows, gage and diameter).",
    "Fricción: el cortante pasa por la compresión de cada cara (solo la compresión permanente "
    "según ACI 318 §22.9). Grout: los pernos se apoyan en el grout de la camisa; vea la ayuda.":
        "Friction: the shear goes through the compression on each face (only the permanent "
        "compression per ACI 318 §22.9). Grout: the bolts bear on the grout in the sleeve; "
        "see the help.",
    "Placa corrida en la cara opuesta; no se usa cuando hay viga opuesta.":
        "Continuous plate on the far face; not used with an opposite beam.",
    "valor con unidad, p. ej. 1 in o 25 mm": "value with unit, e.g. 1 in or 25 mm",
    "M (+ tracción arriba)": "M (+ tension at top)", "P (compresión +)": "P (compression +)",
    "Combinaciones mayoradas (LRFD) en la cara del muro o columna. V positivo hacia abajo, M "
    "positivo con tracción arriba, P positiva en compresión. V2, M2 y P2 son de la viga "
    "opuesta. Un número sin unidad se toma en las unidades del proyecto.":
        "Factored (LRFD) combinations at the face of the wall or column. V positive "
        "downwards, M positive with tension at the top, P positive in compression. V2, M2 and "
        "P2 belong to the opposite beam. A number without unit is taken in the project units.",
    "Agregar combinación": "Add combination", "Quitar": "Remove",
    "Cálculo analítico": "Analytic checks", "Calcular": "Calculate",
    "Verifica todas las combinaciones (AISC 360, DG16/DG4 y ACI 318)":
        "Checks every combination (AISC 360, DG16/DG4 and ACI 318)",
    "Modelo FEM": "FEM model",
    "El modelo de elementos finitos de esta conexión vendrá en una fase siguiente":
        "The finite element model of this connection will come in a later phase",
    "Nombre de la conexión; el proyecto, cliente e ingeniero son los del proyecto":
        "Connection name; the project, client and engineer are those of the project",
    "Pernos pasantes": "Through-bolts",
    "Camino de cargas, esquemas de cortante y verificaciones de esta conexión":
        "Load path, shear diagrams and checks of this connection",
    "No se pudo calcular: {error}": "Could not calculate: {error}",
    "<p>Sin verificaciones todavía: use Análisis › Resolver.</p>":
        "<p>No checks yet: use Analysis › Solve.</p>",
    "Los resultados están desactualizados: vuelva a calcular.":
        "The results are out of date: calculate again.",
    "Listo. Sin resultados: use Análisis › Resolver.":
        "Ready. No results: use Analysis › Solve.",
    "Al ras, 2 pernos (2F)": "Flush, 2 bolts (2F)", "Al ras, 4 pernos (4F)": "Flush, 4 bolts (4F)",
    "Extendida, 4 pernos (4E)": "Extended, 4 bolts (4E)",
    "Extendida rigidizada (4ES)": "Extended stiffened (4ES)",
    "Extendida rigidizada, 8 pernos (8ES)": "Extended stiffened, 8 bolts (8ES)",
    "FEM: tracción del perno más cargado (con efecto palanca)":
        "FEM: tension of the most loaded bolt (with prying)",
    "FEM: deformación plástica de la placa de extremo": "FEM: plastic strain of the end plate",
    "FEM: deformación plástica de la placa posterior": "FEM: plastic strain of the back plate",
    "FEM: aplastamiento del concreto bajo la placa posterior":
        "FEM: concrete bearing under the back plate",
    "FEM: aplastamiento del concreto bajo la placa de extremo":
        "FEM: concrete bearing under the end plate",
    "FEM: cortante por fricción con la compresión del modelo":
        "FEM: shear by friction with the compression of the model",
    "FEM: soldadura de los patines a la placa de extremo": "FEM: flange-to-end-plate weld",
    "FEM: soldadura del alma a la placa de extremo": "FEM: web-to-end-plate weld",
    "Malla rápida": "Fast mesh",
    "Elementos del doble de tamaño: resultados en segundos, para tantear":
        "Elements twice as large: results in seconds, for trial runs",
    "Resuelve cada combinación con CalculiX: placa de extremo sobre la cara del concreto, "
    "pernos sin adherencia y soldaduras":
        "Solves each combination with CalculiX: end plate on the concrete face, unbonded "
        "bolts and welds",
    "{name}: no se pudo resolver: {error}": "{name}: could not be solved: {error}",
    "sin calcular": "not calculated", "Pernos pasantes: {n} pernos": "Through-bolts: {n} bolts",
    # shared Loads and Analysis tabs
    "Casos de carga de servicio en la cara del muro o columna, como en la placa base: las "
    "combinaciones ASCE 7 (LRFD) se generan de sus tipos y se pueden editar o agregar "
    "propias. V positivo hacia abajo, M positivo con tracción arriba, P positiva en "
    "compresión; V2, M2 y P2 son de la viga opuesta. Un número sin unidad se toma en las "
    "unidades del proyecto.":
        "Service load cases at the face of the wall or column, as for the base plate: the "
        "ASCE 7 (LRFD) combinations come from their types and can be edited, or your own "
        "added. V positive downwards, M positive with tension at the top, P positive in "
        "compression; V2, M2 and P2 belong to the opposite beam. A number without a unit "
        "takes the project units.",
    "V (+ hacia abajo)": "V (+ downwards)",
    "Aceleración espectral de diseño de periodo corto: con casos E genera las combinaciones "
    "sísmicas de ASCE 7 (vacío: sin ellas)":
        "Short-period design spectral acceleration: with E cases it generates the ASCE 7 "
        "seismic combinations (empty: none)",
    "Factor de redundancia (1.0 por omisión)": "Redundancy factor (1.0 by default)",
    "Sobrerresistencia: agrega las combinaciones con Ω0 (vacío: sin ellas)":
        "Overstrength: adds the combinations with Ω0 (empty: none)",
    "valor no válido: {text}": "invalid value: {text}",
    "Verificaciones analíticas listas; el modelo CalculiX no se resolvió: {error}":
        "Analytic checks done; the CalculiX model was not solved: {error}",
    "Verificaciones analíticas listas. Marque en Cargas las combinaciones que se resuelven "
    "con CalculiX.":
        "Analytic checks done. Check in Loads the combinations to solve with CalculiX.",
    "{n} combinaciones con CalculiX ({mesh}, {t} hilos). Salida: {out}":
        "{n} combinations with CalculiX ({mesh}, {t} threads). Output: {out}",
    "malla rápida": "fast mesh", "malla normal": "normal mesh",
    "{n} combinaciones; CalculiX con {t} hilos.": "{n} combinations; CalculiX with {t} threads.",
    " en {s} s. Tracción total en pernos {t}, compresión {c}.":
        " in {s} s. Total bolt tension {t}, compression {c}.",
    "sin carga": "no load",
    "Calcula las verificaciones analíticas y resuelve con CalculiX las combinaciones marcadas "
    "en Cargas: placas sobre el concreto, pernos sin adherencia y soldaduras":
        "Runs the analytic checks and solves with CalculiX the combinations checked in "
        "Loads: plates on the concrete, unbonded bolts and welds",
    "Tamaño de malla, malla rápida, capas, hilos de CalculiX y límite de deformación "
    "plástica (los mismos de la placa base)":
        "Mesh size, fast mesh, layers, CalculiX threads and plastic strain limit (the same "
        "as the base plate)",
    "Casos": "Cases", "todas las cargas": "all loads",
    'Requisitos de instalación de la placa base':
        'Base plate installation requirements',  # noqa: E501
    'Resumen de resultados':
        'Summary of results',  # noqa: E501
    'Todas las verificaciones cumplen: no hay recomendaciones de cambio.':
        'All checks pass: no changes are recommended.',  # noqa: E501
    'Sí':
        'Yes',  # noqa: E501
    'Incompleto':
        'Incomplete',  # noqa: E501
    'Rige (FEM)':
        'Governs (FEM)',  # noqa: E501
    'Rige (analítico)':
        'Governs (analytic)',  # noqa: E501
    'Cambios sugeridos para las verificaciones que no cumplen (un cambio a la vez; los valores son estimaciones: vuelva a resolver después):':  # noqa: E501
        'Suggested changes for the checks that fail (one change at a time; the values are estimates: solve again afterwards):',  # noqa: E501
    'Calcula las verificaciones analíticas y resuelve con CalculiX las combinaciones marcadas en Cargas':  # noqa: E501
        'Runs the analytic checks and solves with CalculiX the combinations checked in Loads',  # noqa: E501
    'Ver avance de CalculiX':
        'Show CalculiX progress',  # noqa: E501
    'Tamaño de malla, malla rápida, capas, hilos de CalculiX y límite de deformación plástica':
        'Mesh size, fast mesh, layers, CalculiX threads and plastic strain limit',  # noqa: E501
    'Resuelve con CalculiX las combinaciones marcadas en Cargas y calcula las verificaciones con sus demandas y el camino analítico de la guía':  # noqa: E501
        'Solves with CalculiX the combinations checked in Loads and runs the checks with their demands and the analytic path of the guide',  # noqa: E501
    'Anclajes colocados con plantilla rígida antes de colar, en la posición, la verticalidad y la longitud embebida hef = {hef} de los datos; el modelo y las verificaciones de ACI 318 Cap. 17 suponen esas posiciones y esa profundidad.':  # noqa: E501
        'Anchor rods set with a rigid template before casting, at the position, plumbness and embedment hef = {hef} of the data; the model and the ACI 318 Ch. 17 checks assume those positions and that depth.',  # noqa: E501
    'Agujeros de la placa de {hole} para anclajes de {d}: si en obra se agrandan o se cortan con soplete, el cortante ya no se reparte como en el modelo; consulte al ingeniero.':  # noqa: E501
        'Plate holes of {hole} for {d} anchor rods: if they are enlarged or torch-cut on site, the shear no longer spreads as in the model; consult the engineer.',  # noqa: E501
    "Concreto con la resistencia f'c de diseño antes de montar la columna y de apretar las tuercas; no cargue la conexión antes.":  # noqa: E501
        "Concrete at its design strength f'c before erecting the column and tightening the nuts; do not load the connection earlier.",  # noqa: E501
    'Tuercas apretadas al contacto firme (snug-tight) con la arandela de placa indicada; el análisis no cuenta con pretensión de los anclajes.':  # noqa: E501
        'Nuts snug-tight with the specified plate washer; the analysis does not count on anchor pretension.',  # noqa: E501
    "Mortero de nivelación sin retracción de {t}, de resistencia no menor que f'c, que llene todo el espacio bajo la placa sin vacíos (con agujeros de respiro si la placa es grande): el modelo apoya la placa en contacto continuo y la fricción usa μ = {mu} sobre ese mortero.":  # noqa: E501
        "Non-shrink grout of {t}, with strength not less than f'c, filling the whole space under the plate without voids (with vent holes if the plate is large): the model bears the plate in continuous contact and friction uses μ = {mu} on that grout.",  # noqa: E501
    'Placa apoyada directamente sobre el concreto, con la superficie plana y nivelada en toda el área de la placa: el modelo supone contacto continuo (μ = {mu}).':  # noqa: E501
        'Plate bearing directly on the concrete, with the surface flat and level over the whole plate area: the model assumes continuous contact (μ = {mu}).',  # noqa: E501
    'Tuercas de nivelación bajo la placa: el modelo cuenta con que los anclajes toman compresión. Verifique que las tuercas queden en contacto con la placa antes de colocar el mortero.':  # noqa: E501
        'Leveling nuts under the plate: the model counts on the rods taking compression. Check that the nuts bear on the plate before placing the grout.',  # noqa: E501
    'Sin tuercas de nivelación que tomen carga: nivele con calzas o lainas de acero que no impidan llenar el mortero, o retire las tuercas de nivelación después de que el mortero endurezca. El modelo supone que toda la compresión pasa por el contacto bajo la placa.':  # noqa: E501
        'No load-carrying leveling nuts: level with steel shims that do not prevent filling the grout, or back off the leveling nuts once the grout has hardened. The model assumes all compression goes through the contact under the plate.',  # noqa: E501
    'Arandelas de placa soldadas a la placa base después de nivelar, con la soldadura indicada: así todos los anclajes toman cortante, como en las verificaciones.':  # noqa: E501
        'Plate washers welded to the base plate after leveling, with the specified weld: so all rods take shear, as in the checks.',  # noqa: E501
    'Llave de cortante en una cajuela dejada en el concreto, con holgura para nivelar; llene la cajuela con el mismo mortero sin retracción, sin vacíos frente a la cara cargada de la llave (empotramiento {e}).':  # noqa: E501
        'Shear lug in a pocket left in the concrete, with clearance for leveling; fill the pocket with the same non-shrink grout, without voids in front of the loaded face of the lug (embedment {e}).',  # noqa: E501
    'Rigidizadores con las soldaduras indicadas en los dos lados; recorte las esquinas para no cruzar la soldadura columna-placa.':  # noqa: E501
        'Stiffeners with the specified welds on both sides; clip the corners so as not to cross the column-to-plate weld.',  # noqa: E501
    'Soldadura de penetración completa columna-placa con procedimiento calificado e inspección por ultrasonido, como supone la verificación CJP.':  # noqa: E501
        'Complete joint penetration column-to-plate weld with a qualified procedure and ultrasonic inspection, as the CJP check assumes.',  # noqa: E501
    'Soldadura de filete columna-placa de {w} todo alrededor del perfil, como en el modelo.':
        'Column-to-plate fillet weld of {w} all around the shape, as in the model.',  # noqa: E501
    'Refuerzo de anclaje (horquillas, estribos superiores del pedestal) colocado antes de colar, en contacto con los anclajes o a la distancia indicada, con su longitud de desarrollo completa a cada lado del cono de arrancamiento: las verificaciones solo cuentan con él en esas condiciones.':  # noqa: E501
        'Anchor reinforcement (hairpins, top ties of the pedestal) placed before casting, against the rods or at the specified distance, with its full development length on each side of the breakout cone: the checks only count on it under those conditions.',  # noqa: E501
}
EN.update({k: v for k, v in _CONNECTIONS.items() if k not in EN})

EN.update({
    # moment end-plate connection: pages, fields and tips
    "Diseño sísmico": "Seismic design", "Pernos": "Bolts", "Soldaduras": "Welds",
    "Rigidización de la columna": "Column stiffening", "Rosca": "Threads", "Sistema": "System",
    "Por ejemplo: PE-1, eje B-3": "For example: PE-1, grid B-3",
    "Luz libre entre caras de columna": "Clear span between column faces",
    "Diseño sísmico (rótula plástica) y clasificación por rigidez":
        "Seismic design (plastic hinge) and stiffness classification",
    "La viga se une al ala (eje fuerte)": "The beam frames to the flange (strong axis)",
    "Al ras, 1 fila por ala": "Flush, 1 row per flange",
    "Al ras, 2 filas por ala": "Flush, 2 rows per flange",
    "Al ras, 2 filas, rigidizador entre filas": "Flush, 2 rows, stiffener between the rows",
    "Al ras, 2 filas, rigidizador interior": "Flush, 2 rows, inside stiffener",
    "Extendida rigidizada, 4 pernos (4ES)": "Extended stiffened, 4 bolts (4ES)",
    "Extendida multifila 1/2": "Extended multiple row 1/2",
    "Extendida multifila 1/3": "Extended multiple row 1/3",
    "Extendida multifila 1/3 rigidizada": "Extended multiple row 1/3 stiffened",
    "pf,i (cara interior del ala a la primera fila)":
        "pf,i (inner face of the flange to the first row)",
    "pb (paso entre filas)": "pb (pitch between rows)",
    "Disposiciones con dos o más filas dentro del ala, y entre las dos filas exteriores de "
    "la 8ES": "Layouts with two or more rows inside the flange, and between the two outer "
              "rows of the 8ES",
    "pf,o (cara exterior del ala a la fila exterior)":
        "pf,o (outer face of the flange to the outer row)",
    "Extensión más allá del ala": "Extension past the flange",
    "ps,o (fila exterior al rigidizador)": "ps,o (outer row to the stiffener)",
    "Espesor del rigidizador entre filas": "Thickness of the stiffener between the rows",
    "Al ras con rigidizador entre las filas": "Flush with a stiffener between the rows",
    "ps (fila al rigidizador)": "ps (row to the stiffener)",
    "Al ras con rigidizador interior": "Flush with an inside stiffener",
    "Mismo patrón en las dos alas (momento reversible)":
        "Same pattern at both flanges (moment reversal)",
    "Sin marcar: solo dos pernos en el ala comprimida":
        "Unchecked: only two bolts at the compression flange",
    "Incluida en el plano de corte (N)": "Included in the shear plane (N)",
    "Excluida (X)": "Excluded (X)",
    "Ajustados sin pretensión (snug-tight)": "Snug-tightened (no pretension)",
    "La fuerza de pretensión de la acción de palanca es una fracción de la de la tabla J3.1":
        "The pretension used for prying is a fraction of that of Table J3.1",
    "Pretensión Tb": "Pretension Tb",
    "Vacío: la de la tabla J3.1 de AISC 360-22": "Empty: that of AISC 360-22 Table J3.1",
    "E70XX": "E70XX", "E80XX": "E80XX",
    "Filete de las alas": "Flange fillet weld",
    "Filete de refuerzo de la CJP": "Reinforcing fillet of the CJP weld",
    "Alas con penetración completa: N = tf + 2w en el alma de la columna":
        "CJP flange welds: N = tf + 2w on the column web",
    "Filete del alma (cada lado)": "Web fillet weld (each side)",
    "Espesor de las placas de continuidad": "Thickness of the continuity plates",
    "Un par a la altura de cada ala de la viga; vacío: sin placas":
        "A pair at each beam flange; empty: no plates",
    "Ancho de cada placa": "Width of each plate",
    "Vacío: (bf − tw)/2 de la columna": "Empty: (bf − tw)/2 of the column",
    "Filete de las placas a las alas": "Fillet weld of the plates to the flanges",
    "Vacío: penetración completa": "Empty: complete joint penetration",
    "Espesor de la placa doble": "Doubler plate thickness",
    "Vacío: sin placa doble": "Empty: no doubler plate",
    "Filete de la placa doble a las alas": "Fillet weld of the doubler to the flanges",
    "Vigas a ambos lados de la columna": "Beams on both sides of the column",
    "Revisa el pandeo del alma por compresión (§J10.5)":
        "Checks web compression buckling (§J10.5)",
    "Cerca del extremo de la columna": "Near the column end",
    "Fuerza del ala a menos de d de la columna de su extremo (§J10)":
        "Flange force within the column depth d of its end (§J10)",
    "Revisar la zona de panel": "Check the panel zone",
    "Con el cortante de piso Vc y la carga axial Pc de cada caso de carga":
        "With the story shear Vc and axial force Pc of each load case",
    "Deformación de la zona de panel considerada": "Panel-zone deformation considered",
    "En el análisis de estabilidad (§J10.6, Ec. J10-11 y J10-12)":
        "In the stability analysis (§J10.6, Eq. J10-11 and J10-12)",
    "Pórtico especial (SMF)": "Special moment frame (SMF)",
    "Pórtico intermedio (IMF)": "Intermediate moment frame (IMF)",
    "Carga de gravedad factorada en la viga": "Factored gravity load on the beam",
    "1.2D + f1 L + 0.15S, fuerza por longitud": "1.2D + f1 L + 0.15S, force per length",
    "Cortante de gravedad adicional en la rótula": "Additional gravity shear at the hinge",
    "Carga axial de la columna (compresión)": "Column axial force (compression)",
    "Para la relación columna-viga": "For the column-beam ratio",
    "La columna sigue arriba del nudo": "The column continues above the joint",
    "Espesor del rigidizador de la extensión": "Thickness of the extension stiffener",
    "BSEEP (4ES y 8ES)": "BSEEP (4ES and 8ES)",
    "Cortante de piso de la columna Vc": "Story shear of the column Vc",
    "Se resta del cortante de la zona de panel (SMF)":
        "Subtracted from the panel-zone shear (SMF)",
    "Altura al punto de inflexión arriba": "Height to the inflection point above",
    "Proyecta los momentos de columna al eje de la viga (SMF)":
        "Projects the column moments to the beam centreline (SMF)",
    "Altura al punto de inflexión abajo": "Height to the inflection point below",
    "pf,i, pf,o y pb se miden desde las caras del ala de la viga, como en las Guías de "
    "Diseño 4 y 16; vea los esquemas en la ayuda.":
        "pf,i, pf,o and pb are measured from the faces of the beam flange, as in Design "
        "Guides 4 and 16; see the sketches in the help.",
    "Con placas de continuidad, las revisiones del alma de la columna no aplican y la "
    "flexión del ala usa el mecanismo rigidizado.":
        "With continuity plates, the column web checks do not apply and the flange bending "
        "uses the stiffened mechanism.",
    "Conexión precalificada AISC 358-22 capítulo 6: 4E (BUEEP), 4ES y 8ES (BSEEP). Usa la "
    "luz libre de la viga (página Viga). Es diseño por capacidad: no depende de las "
    "combinaciones.":
        "AISC 358-22 Chapter 6 prequalified connection: 4E (BUEEP), 4ES and 8ES (BSEEP). "
        "It uses the clear span of the beam (Beam page). It is capacity design: it does "
        "not depend on the combinations.",
    "Conexión sísmica precalificada (AISC 358)": "Prequalified seismic connection (AISC 358)",
    "Configuraciones, camino de las fuerzas y estados límite de esta conexión":
        "Layouts, load path and limit states of this connection",
    "Calcula las verificaciones de AISC 360-22, las Guías de Diseño 16 y 4 y, si es "
    "sísmica, AISC 358-22 para todas las combinaciones, y resuelve con CalculiX las "
    "combinaciones marcadas en Cargas: placa, pernos pretensados, ala de la columna y "
    "soldaduras":
        "Runs the checks of AISC 360-22, Design Guides 16 and 4 and, when seismic, AISC "
        "358-22 for every combination, and solves with CalculiX the combinations ticked in "
        "Loads: plate, pretensioned bolts, column flange and welds",
    "Placa de extremo: {n} combinaciones calculadas.": "End plate: {n} combinations checked.",
    "Después, la curva momento-rotación (un modelo más).":
        "Then the moment-rotation curve (one more model).",
    "Curva momento-rotación: {n} puntos hasta {m}; K_s·L/EI = {r}: {name}.":
        "Moment-rotation curve: {n} points up to {m}; K_s·L/EI = {r}: {name}.",
    "Curva momento-rotación: no se pudo resolver: {error}":
        "Moment-rotation curve: could not be solved: {error}",
    "Curva momento-rotación": "Moment-rotation curve",
    "La curva se calcula con CalculiX: use Análisis › Resolver.":
        "The curve is computed with CalculiX: use Analysis › Solve.",
    "Curva M-θ": "M-θ curve",
    "Curva momento-rotación de la conexión y su clasificación (FR, PR o simple)":
        "Moment-rotation curve of the connection and its classification (FR, PR or simple)",
    "totalmente restringida (FR)": "fully restrained (FR)",
    "parcialmente restringida (PR)": "partially restrained (PR)",
    "simple": "simple",
    "FEM: perno más cargado, tracción con palanca y cortante (J3.7)":
        "FEM: most loaded bolt, tension with prying, and shear (J3.7)",
    "Presión de contacto de la placa de extremo sobre el ala de la columna: máx. {p} MPa":
        "Contact pressure of the end plate on the column flange: max. {p} MPa",
    "FEM: deformación plástica del ala de la columna":
        "FEM: plastic strain of the column flange",
    "FEM: deformación plástica de los rigidizadores": "FEM: plastic strain of the stiffeners",
    "FEM: deformación plástica del alma de la columna":
        "FEM: plastic strain of the column web",
    "FEM: deformación plástica de las placas de continuidad":
        "FEM: plastic strain of the continuity plates",
    "FEM: deformación plástica de la placa doble": "FEM: plastic strain of the doubler plate",
    "Agregue una placa doble en la zona de panel o placas de continuidad, o use una "
    "columna con alma más gruesa: el alma se plastifica en el nudo.":
        "Add a doubler plate in the panel zone or continuity plates, or use a column with "
        "a thicker web: the web yields in the joint.",
    "Aumente el espesor o el ancho de las placas de continuidad.":
        "Increase the thickness or the width of the continuity plates.",
    "Aumente el espesor de la placa doble o agregue placas de continuidad.":
        "Increase the thickness of the doubler plate or add continuity plates.",
    "FEM: soldadura de las alas de la viga a la placa":
        "FEM: weld of the beam flanges to the plate",
    "FEM: soldadura del alma de la viga a la placa": "FEM: weld of the beam web to the plate",
    "Aumente el diámetro o el grado de los pernos, o el espesor de la placa y del ala de la "
    "columna: el modelo muestra la fuerza de palanca que reciben.":
        "Increase the bolt diameter or grade, or the thickness of the plate and of the "
        "column flange: the model shows the prying force they get.",
    "Aumente el espesor de la placa de extremo o acerque los pernos a las alas de la viga.":
        "Increase the end-plate thickness or bring the bolts closer to the beam flanges.",
    "Agregue placas de continuidad, o use una columna de ala más gruesa: el ala se "
    "plastifica bajo los pernos.":
        "Add continuity plates, or use a column with a thicker flange: the flange yields "
        "under the bolts.",
    "Aumente el espesor o la longitud de los rigidizadores.":
        "Increase the thickness or the length of the stiffeners.",
    "Aumente el filete de la soldadura de la viga a la placa, o use penetración completa.":
        "Increase the fillet of the beam-to-plate weld, or use complete joint penetration.",
    "Placa de extremo: {n} pernos": "End plate: {n} bolts",
    "Viga de acero al ala de una columna con placa de extremo al ras o extendida (4E, 4ES, "
    "8ES, multifila), con diseño sísmico AISC 358. Cálculo analítico AISC 360-22 y Guías de "
    "Diseño 16 y 4.":
        "Steel beam to a column flange with a flush or extended end plate (4E, 4ES, 8ES, "
        "multiple row), with AISC 358 seismic design. Analytic checks to AISC 360-22 and "
        "Design Guides 16 and 4.",
    "Casos de carga de servicio de la viga en la cara de la columna: las combinaciones ASCE "
    "7 (LRFD o ASD) se generan de sus tipos y se pueden editar o agregar propias. M positivo "
    "con tracción arriba, P positiva en compresión; Vc y Pc son el cortante de piso y la "
    "carga axial de la columna, solo para la zona de panel. Un número sin unidad se toma en "
    "las unidades del proyecto.":
        "Service load cases of the beam at the column face: the ASCE 7 combinations (LRFD "
        "or ASD) are generated from their types and can be edited, or your own added. M "
        "positive with tension at the top, P positive in compression; Vc and Pc are the "
        "story shear and axial force of the column, for the panel zone only. A number "
        "without a unit is taken in the project units.",
})
