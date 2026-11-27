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
    "<p>Sin verificaciones todavía: use Análisis › Calcular.</p>":
        "<p>No checks yet: use Analysis › Calculate.</p>",
    "Los resultados están desactualizados: vuelva a calcular.":
        "The results are out of date: calculate again.",
    "Listo. Sin resultados: use Análisis › Calcular.":
        "Ready. No results: use Analysis › Calculate.",
    "Al ras, 2 pernos (2F)": "Flush, 2 bolts (2F)", "Al ras, 4 pernos (4F)": "Flush, 4 bolts (4F)",
    "Extendida, 4 pernos (4E)": "Extended, 4 bolts (4E)",
    "Extendida rigidizada (4ES)": "Extended stiffened (4ES)",
    "Extendida rigidizada, 8 pernos (8ES)": "Extended stiffened, 8 bolts (8ES)",
    "FEM: tracción del perno más cargado (con efecto palanca)":
        "FEM: tension of the most loaded bolt (with prying)",
    "FEM: deformación plástica de la placa de extremo": "FEM: plastic strain of the end plate",
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
}
EN.update({k: v for k, v in _CONNECTIONS.items() if k not in EN})
