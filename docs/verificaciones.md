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
| Anclaje con arandela soldada | Tracción y cortante de cada anclaje, flexión con brazo (tp + tw/2)/2 | F'nt reducido, AISC J3.7 (360-05) o J3.8 (360-22) |
| Refuerzo de anclaje (pedestal) | Tracción del grupo y cortante de los anclajes | φ·As·fy con φ = 0.75; reemplaza al arrancamiento si cumple |
| Pedestal | P y M de la combinación, más V·h | Flexocompresión biaxial por compatibilidad de deformaciones y cuantía mínima de 1 % |
| Llave de cortante | Todo el cortante en su dirección | Verificaciones de OpenConex (ACI 318-19 §17.11, AISC J4 y J2.4) |
| Rigidizadores | Deformación plástica media por elemento y fuerzas en sus soldaduras | Límite de PEEQ, filete con aumento direccional y b/t ≤ 0.56√(E/Fy) |
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

Otros ejemplos de la guía resueltos por FEM: 4.5 (levantamiento neto: 17.5 kips
por anclaje y ratios 0.89, 0.90 y 0.69, iguales a la guía, también en ASD) y
4.11 (tracción, cortante y flexión del anclaje; en el FEM aparece efecto
palanca que la guía no considera). La llave de cortante tiene su propio ejemplo
en `examples/llave_de_cortante.ocnx`.

## Guía de Diseño 1, 3.ª edición: ejemplo 4.7-11

`examples/dg1_3ed_ej_4_7_11.ocnx` (W12×96, Pu = 376 kips, Mu = 3600 kip·in,
placa de 24 × 22 × 2 in, anclajes de 1 in a f = 9.25 in), con las normas
vigentes:

| Resultado | Guía (bloque rectangular) | FEM |
|---|---|---|
| Tracción total en anclajes | 42.0 kips | 65.3 kips |
| Longitud de apoyo | 8.60 in | 9.8 in |
| Resultante de compresión, desde el eje | 7.70 in | 6.82 in |

Aquí el FEM da 55 % más tracción que la guía. La guía supone la placa rígida,
con el bloque de presión pegado al borde; en el modelo la placa de 2 in con
5.65 in de voladizo se flexiona y la compresión se concentra bajo el patín, a
6.82 in del eje en vez de 7.70 in, con lo que baja el brazo de palanca. Con
esa demanda el anclaje de 1 in no cumple a tracción (ratio 1.24), mientras
que con el método de la guía sí. El concreto del modelo es elástico, lo que
limita cuánto puede extenderse el apoyo; aun así es una diferencia que el
ingeniero debe conocer al usar placas flexibles.

## Pernos pasantes en concreto

Módulo `openfemconex.through_bolt` (analítico, sin FEM todavía): viga con placa
frontal unida a un muro o columna nuevo con pernos pasantes sin adherencia y una
placa posterior corrida, o una segunda viga del otro lado con los mismos pernos.
Cada cara tiene una zona de apoyo arriba y otra abajo; los pernos de cada grupo
llevan la mayor tracción de los dos lados y la fuerza no equilibrada ΔF cruza el
espesor por un puntal diagonal. La ayuda integrada (tema *Pernos pasantes en concreto*)
explica el camino de las fuerzas con esquemas.

| Componente | Verificación |
|---|---|
| Placa frontal, pernos, soldaduras | Las de placa de extremo de las Guías de Diseño 16 y 4 (OpenConex) para cada viga; la placa de la otra cara hace de ala de la columna |
| Concreto | Aplastamiento bajo cada placa (§22.8) con el área limitada por la flexión de la placa; punzonamiento de la fuerza no equilibrada de cada grupo (§22.6), con b0 recortado por los bordes de una columna; hendimiento detrás de cada placa (§25.9 por analogía) |
| Muro o columna | Puntal y tensor del par T·z (Cap. 23): ángulo, puntal, nodos C-C-T, refuerzo vertical como tensor y su desarrollo; flexocompresión de la franja de muro o de la columna con ΔM = (M1 − M2) + (V1 − V2) h/2 (§22.4) |
| Cortante | Fricción bajo la compresión de cada cara (DG1) o, con grout, perno más cargado a tracción, cortante y flexión sobre la holgura (AISC J3.7) y apoyo del perno en el grout (§22.8) |

Las pruebas (`tests/test_through_bolt.py`) comparan cada verificación con un
cálculo a mano independiente, incluidos los casos de la conexión opuesta
(balanceada, desbalanceada, un solo lado y sismo). Pendiente: interfaz, proyecto
`.ocnx` y modelo CalculiX.

## Momento con placa de extremo

Módulo `openfemconex.end_plate_project`: viga unida al ala de una columna con
placa de extremo al ras o extendida. Las verificaciones son las del motor de
OpenConex (`openconex.connections.moment`), validado allí contra las Guías de
Diseño 16, 4 y 39 y AISC 358-22; este módulo lleva los datos del proyecto a ese
motor, corre todas las combinaciones (LRFD o ASD) y arma el reporte común. La
ayuda integrada (tema *Momento con placa de extremo*) explica las configuraciones
y el camino de las fuerzas con esquemas.

| Componente | Verificación |
|---|---|
| Placa de extremo | Fluencia por líneas de fluencia (DG16 tablas 3-2 a 4-6, DG4 tabla 3.3 para 8ES); cortante de la extensión (§J4.2) |
| Pernos | Ruptura con o sin acción de palanca (DG16); cortante, aplastamiento y desgarre de los pernos del lado comprimido (§J3.7, §J3.11) |
| Soldaduras | Alma a cortante y a tracción cerca de los pernos, alas con filete (§J2.4) |
| Columna | Flexión del ala (DG4), fluencia y aplastamiento del alma (§J10.2, §J10.3), pandeo con vigas a ambos lados (§J10.5), zona de panel (§J10.6), placas de continuidad (§J10.8, DG13) y placa doble |
| Sísmico | BUEEP (4E) y BSEEP (4ES, 8ES) de AISC 358-22 cap. 6 con AISC 341-22: límites de precalificación, esbeltez, cortante de la viga, relación columna-viga, zona de panel y placas de continuidad |

Las pruebas (`tests/test_end_plate.py`) comprueban que los datos del proyecto
llegan al motor sin cambios con el Ejemplo A de la Guía de Diseño 4 (4E) y el
Ejemplo 6.3-2 de la Guía de Diseño 39 (4ES sísmica).

El modelo CalculiX (`openfemconex.end_plate_fem`) lleva la placa sobre el modelo
de placa base: la viga es la "columna" (tramo elástico de dos peraltes), la placa
de extremo la "placa base" y el ala cercana de la columna el "bloque"; con
`model.ColumnFlange` la malla agrega el resto de la columna (alma, ala lejana,
placas de continuidad y placa doble), todo de acero elastoplástico con nodos
compartidos, empotrada en los extremos del tramo (altura de la placa más un
peralte de columna a cada lado); los pernos son resortes solo a tracción entre la
arandela y la tuerca en la cara interior del ala, ajustados sin pretensión para las verificaciones (la
pretensión de la Tabla J3.1 queda como opción del modelo, para la rigidez en
servicio). Con sus resultados:

| Verificación FEM | Criterio |
|---|---|
| Perno más cargado | Tracción con acción de palanca y cortante, F'nt de §J3.7 |
| Placa, alas y alma de la columna, rigidizadores, placas de continuidad, placa doble | Deformación plástica equivalente media por elemento ≤ 5 % |
| Soldaduras de filete | §J2.4; alas con la fuerza repartida en su ancho, alma en su punto más cargado |

`tests/test_end_plate_fem.py` comprueba el modelo, la malla y el archivo de
CalculiX y resuelve la 4E de la Guía de Diseño 4 con un momento de servicio.

La curva momento-rotación (`end_plate_fem.moment_rotation`) es un modelo más con
los pernos pretensados (par de fuerzas T_b en un primer paso, Tabla J3.1) y un
momento solo hasta 1.5 veces el mayor de las combinaciones, en pasos de 5 %; la
rotación es la del extremo de la viga menos su giro elástico M·L_c/EI, medida
respecto de la sección de la columna en el eje de la viga (con la zona de panel)
o, con la opción `curve_connection_only`, respecto del ala sobre el alma entre
las alas de la viga (solo la conexión); se calculan las dos y la otra queda como
comparación. La
conexión se clasifica con K_s·L/EI (comentario de AISC 360-22 §B3.4: FR ≥ 20,
simple ≤ 2), con K_s secante en el momento de servicio (mayor ASD, o mayor LRFD
/ 1.5). En la 4E del ejemplo (`examples/placa_extremo.ocnx`, malla rápida) la
curva con la zona de panel tiene 15 puntos hasta 1012 kN·m a 18 mrad, con
K_s·L/EI = 23 (FR); solo la conexión da K_s·L/EI = 72. La meseta viene de la
fluencia del alma en la zona de panel, por debajo de los 1326 kN·m de la placa
por líneas de fluencia.

## Pendiente

- Rotura del metal base en la soldadura (J4) y soldadura de penetración.
- Diseño sísmico y verificación ASD del concreto.
- Rigidizadores en HSS rectangular.
