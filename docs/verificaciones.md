# Verificaciones normativas con demandas del FEM

`openfemconex run` resuelve cada combinación y, con los resultados, evalúa las
verificaciones de [`checks.py`](../src/openfemconex/checks.py). Cada una es una
función pura que devuelve demanda, capacidad, ratio, la traza del cálculo y la
cláusula, con el mismo `CheckResult` de OpenConex. El resultado se imprime y se
escribe en `reporte.html` (ejemplo: [ejemplo_reporte_dg1_4_7.html](ejemplo_reporte_dg1_4_7.html)).

```bash
.venv/bin/openfemconex run examples/dg1_2ed_ej_4_7.ocnx --combo LRFD-2 --edition dg1-2ed
```

Con `--reuse` no se vuelve a correr ccx si el `.inp` no cambió, por ejemplo para
comparar ediciones.

## Ediciones

| `--edition` | Acero | Concreto | Diferencias que aplican aquí |
|---|---|---|---|
| `current` (por defecto) | AISC 360-22 | ACI 318-19 Cap. 17 | Acero del anclaje con Ase·futa; φ = 0.65 a cortante; tope 9√f'c·ca1^1.5 en Vb; fricción según DG1 3.ª ed. |
| `dg1-2ed` | AISC 360-05 | ACI 318-08 Ap. D | Como los aplica la DG1 2.ª ed.: acero del anclaje 0.75·Fu·Ab y 0.4·Fu·Ab con φ = 0.75 (J3.6); sin tope en Vb; cláusulas D.x |

En las dos, el aplastamiento usa φ = 0.65, que es el que usa la guía (AISC 360-05
J8 dice 0.60). Las fórmulas de arrancamiento, extracción y palanca son iguales
en ambas ediciones del ACI para anclajes preinstalados; cambian la numeración y
los puntos de la tabla.

## Qué se verifica y de dónde sale la demanda

| Verificación | Demanda (FEM) | Capacidad |
|---|---|---|
| Aplastamiento del concreto | Compresión resultante repartida en el mayor bloque rectangular centrado en ella, (N − 2\|x\|)(B − 2\|y\|) | φ·0.85·f'c·√(A2/A1) ≤ φ·1.7·f'c (J8) |
| Deformación plástica de la placa | PEEQ medio por elemento | Límite de referencia, 5 % por defecto (`--strain-limit`) |
| Flexión de la placa por tracción | Tracción de la fila × brazo al centro del patín | φ·Fy·B·tp²/4 (DG1) |
| Anclaje, acero a tracción | Tracción máxima de un anclaje | según edición |
| Arrancamiento del concreto en tracción | Suma de tracciones del grupo traccionado, con su excentricidad y los bordes del pedestal | Ncbg (método CCD) |
| Extracción (pullout) | Tracción máxima | 8·Abrg·f'c |
| Desprendimiento lateral | Tracción máxima, si hef > 2.5·ca1 | Nsb |
| Cortante por fricción | Cortante que pasa por el contacto | φ·μ·C con sus topes; C es la compresión FEM |
| Anclaje a cortante, arrancamiento y palanca | Cortante de los anclajes, solo con arandelas soldadas | Vsa, Vcbg, Vcpg |
| Interacción tracción-cortante | Ratios anteriores | suma ≤ 1.2 |
| Soldadura columna-placa | Fuerza por unidad de longitud en la pared de la columna justo sobre la placa, en el punto más solicitado | Filete con aumento direccional (J2.4) |

Las verificaciones del concreto son de resistencia última y solo se evalúan en
combinaciones LRFD. Con la edición vigente el reporte añade el camino analítico
de OpenConex (DG1 3.ª ed.) con las mismas cargas, para comparar.

## Validación contra la Guía de Diseño 1, 2.ª edición

`tests/test_checks_dg1.py` reproduce las capacidades de los ejemplos:

| Ejemplo | Valor de la guía | Calculado |
|---|---|---|
| 4.3, 4.5, 4.7: tracción de anclajes de ¾, ⅞ y 1½ in | 14.4, 19.6 y 57.7 kips | igual (0.5 %) |
| 4.10: cortante de un anclaje de ¾ in | 7.69 kips | igual |
| 4.5: arrancamiento, hef = 13 in | 77.5 kips | 77.5 kips |
| 4.5b: pedestal de 20 in, hef' = 5.33 in | 25.6 kips | 25.6 kips |
| 4.7: arrancamiento, hef = 18 in | 134 kips | 133.8 kips |
| Tabla 3.2: extracción con tuerca pesada, ⅞ y 1½ in | 27.3 y 70.1 kips | 26.6 y 69.8 kips |
| 4.10: arrancamiento en cortante, c1 = 14 in | 32.7 kips | 32.7 kips |
| 4.5: filete de 3/16 in transversal | 6.26 kips/in | 6.26 kips/in |
| 4.7: aplastamiento con A2/A1 = 1 | 2.21 ksi | 2.21 ksi |
| 4.7: espesor por tracción | 1.24 in | 1.24 in |

Y con el modelo FEM del ejemplo 4.7 (`tests/test_dg1_4_7.py`):

| Verificación | Guía | FEM + `dg1-2ed` |
|---|---|---|
| Anclaje a tracción | 38.0 / 57.7 = 0.66 | 0.67 |
| Arrancamiento del concreto | 76.0 / 134 = 0.57 | 0.57 |
| Extracción | 38.0 / 70.1 = 0.54 (tabla, fisurado) | 0.39 (no fisurado, ψ = 1.4) |
| Aplastamiento | 1.00 por construcción | 1.03 |
| Soldadura | no se calcula | 0.78 con el filete mínimo de 5/16 in |
| Deformación plástica de la placa | no aplica | 0.01 |

El aplastamiento da 1.03 y no 1.00 porque en el FEM los anclajes toman 7 % menos
tracción que en la fórmula de la guía con los anclajes en la misma posición,
así que la resultante de compresión queda 0.1 in más cerca del borde. El
concreto del modelo es elástico y no redistribuye; un concreto con plastificación
local llevaría ese 3 % a los anclajes. Se intentó con una ley de contacto con
meseta en ccx y no convergió; queda pendiente.

## Pendiente

- Rotura del metal base en la soldadura (J4) y soldadura de penetración.
- Refuerzo de anclaje y refuerzo suplementario (hoy solo cambia φ).
- Diseño sísmico, llave de cortante y verificación ASD del concreto.
- Reporte en PDF.
