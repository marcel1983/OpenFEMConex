# Momento con placa de extremo

Viga de acero soldada a una **placa de extremo** que se atornilla al **ala de
una columna de acero** (eje fuerte). La conexión transmite momento, cortante y
carga axial de la viga. Las verificaciones analíticas son las del motor de
OpenConex (módulo `openconex.connections.moment`), que OpenFEMConex llama con
los datos del proyecto (módulo `openfemconex.end_plate_project`). Encima de
estos resultados, un modelo CalculiX de la placa, los pernos y el ala de la
columna da las fuerzas reales en los pernos, las deformaciones plásticas y la
curva momento-rotación con la clasificación FR, PR o simple.

Normas: AISC 360-22; resistencia de la placa y fuerzas en los pernos según AISC
Design Guide 16 y Design Guide 4 (8ES); diseño sísmico según AISC 358-22
capítulo 6 con AISC 341-22. Los esquemas de este tema son dibujos propios.

## Configuraciones

![Configuraciones de placa de extremo](img/es/placa_extremo_configuraciones.png)

| Configuración | Filas de pernos por ala | Rigidizador | Sísmica (AISC 358) |
|---|---|---|---|
| Al ras, 1 fila | 1 dentro | No | No |
| Al ras, 2 filas | 2 dentro | Opcional, entre filas o interior | No |
| Extendida 4E | 1 fuera y 1 dentro | No | Sí (BUEEP) |
| Extendida 4ES | 1 fuera y 1 dentro | En la extensión | Sí (BSEEP) |
| Extendida multifila 1/2 y 1/3 | 1 fuera y 2 o 3 dentro | 1/3 opcional | No |
| Extendida 8ES | 2 fuera y 2 dentro | En la extensión | Sí (BSEEP) |

Todas llevan dos pernos por fila, separados por el gramil g. Las distancias que
pide el programa son p<sub>f,i</sub> (cara interior del ala a la primera fila
interior), p<sub>f,o</sub> (cara exterior del ala a la fila exterior), p<sub>b</sub>
(paso entre filas) y la extensión de la placa más allá del ala. Con la placa
**simétrica** el patrón se repite en las dos alas (momento reversible).

## Cómo viaja la fuerza

![Camino de las fuerzas](img/es/placa_extremo_fuerzas.png)

- El momento se reduce a un par de fuerzas en las alas, separadas por
  d − t<sub>f</sub>: **F<sub>fu</sub> = M / (d − t<sub>f</sub>)**. La carga axial
  de la viga se convierte en un momento equivalente que se suma.
- En el ala traccionada la placa se dobla entre las filas de pernos y tira de
  ellos. El ala comprimida apoya la placa contra el ala de la columna.
- El cortante lo toman los pernos del lado comprimido, que no trabajan a
  tracción.
- Las dos fuerzas de ala llegan al alma de la columna y la zona de panel entre
  ellas trabaja a cortante.

## Placa gruesa o delgada

![Acción de palanca](img/es/placa_extremo_palanca.png)

Si la placa es **gruesa**, no fluye antes que los pernos y cada perno lleva su
parte de la fuerza del ala. Si es **delgada**, su borde se apoya contra la
columna y aparece la fuerza de palanca Q, que aumenta la tracción de los pernos.
El programa clasifica la placa como la Guía de Diseño 16 y revisa:

- la fluencia de la placa por líneas de fluencia, φM<sub>pl</sub>;
- la ruptura de los pernos sin palanca (placa gruesa) o con palanca (placa
  delgada);
- el cortante de la extensión (fluencia y ruptura, §J4.2);
- el cortante, el aplastamiento y el desgarre de los pernos del lado
  comprimido (§J3.7, §J3.11);
- las soldaduras del alma (a cortante y a tracción cerca de los pernos) y de
  las alas (§J2.4).

## Lado de la columna

![Estados límite de la columna](img/es/placa_extremo_columna.png)

1. **Flexión del ala** de la columna alrededor de los pernos traccionados, con
   su propio mecanismo de líneas de fluencia (Guía de Diseño 4).
2. **Fluencia local del alma** frente al ala traccionada (§J10.2).
3. **Aplastamiento** y **pandeo** del alma frente al ala comprimida (§J10.3;
   §J10.5 cuando hay vigas a ambos lados).
4. **Zona de panel** a cortante (§J10.6), con la placa doble si la hay. Pide el
   cortante de piso y la carga axial de la columna en cada caso de carga.
5. **Placas de continuidad**: si la columna no alcanza, sus placas toman la
   diferencia y se revisa su tamaño y sus soldaduras (§J10.8 y Guía de Diseño 13).

Con placas de continuidad, las revisiones del alma no aplican y la flexión del
ala usa el mecanismo rigidizado.

## Diseño sísmico

Las placas 4E (BUEEP), 4ES y 8ES (BSEEP) están precalificadas para pórticos
especiales (SMF) e intermedios (IMF). Al activar el diseño sísmico, el programa
hace el diseño por capacidad: momento probable de la viga en la rótula, su
cortante con la carga de gravedad, momento en la cara de la columna, límites de
precalificación de perfiles, placa y pernos, esbeltez de alta o moderada
ductilidad, relación columna-viga, zona de panel y placas de continuidad. Este
bloque no depende de las combinaciones (es LRFD) y aparece en el reporte como
«AISC 358». Pide la luz libre de la viga entre caras de columna y, para la
relación columna-viga, la carga axial de la columna.

## Modelo CalculiX

Resolver también arma un modelo de elementos finitos de cada combinación marcada
en Cargas (módulo `openfemconex.end_plate_fem`):

- **Viga**: un tramo de dos peraltes, elástico, que lleva las fuerzas a la
  placa. La resistencia de la viga es del diseño del marco (y de AISC 358 si es
  sísmica): una placa de extremo suele diseñarse para más que el momento
  plástico de la viga.
- **Placa de extremo y rigidizadores**: sólidos de acero elastoplástico,
  soldados a la viga (nodos compartidos).
- **Columna**: el perfil completo, de acero elastoplástico, sobre la altura de
  la placa más un peralte de la columna arriba y abajo: ala cercana, alma y ala
  lejana, con las **placas de continuidad** (a la altura de las alas de la viga,
  a ambos lados del alma, del ancho indicado o hasta el borde del ala, en todo el
  peralte) y la **placa doble** del alma si la hay (entre las placas de
  continuidad, o 6 in más allá de las alas de la viga sin ellas). Todas las
  piezas comparten nodos, como soldadas. La columna se empotra en sus dos
  extremos. La placa apoya en el ala por contacto sin fricción y sin tracción.
- **Pernos**: resortes axiales solo a tracción E·A/L sobre el agarre (placa más
  ala), entre la arandela y la tuerca en la cara interior del ala; toman el
  cortante por aplastamiento. Para las verificaciones van ajustados sin
  pretensión, como en los modelos de resistencia de las Guías de Diseño: la
  fuerza que dan ya incluye la acción de palanca.

Con el modelo se verifica el perno más cargado a tracción y cortante (§J3.6 y
§J3.7), la deformación plástica de la placa, de las alas y del alma de la
columna, de los rigidizadores, de las placas de continuidad y de la placa doble
(límite 5 %) y las soldaduras de filete (las de las alas con la fuerza repartida
en el ancho del ala). Una soldadura de penetración completa es tan resistente
como la viga y no se verifica con el modelo. El alma de la columna, la zona de
panel y las placas de continuidad se verifican además de forma analítica: el
tramo de columna del modelo es corto y empotrado, así que el cortante de la zona
de panel del modelo no es exactamente el del pórtico.

## Curva momento-rotación

Resolver calcula siempre, además, la curva momento-rotación de la conexión: un
modelo más, con un momento solo que crece en pasos de 5 % hasta 1.5 veces el
mayor de las combinaciones, y los pernos **pretensados** (la pretensión de la
Tabla J3.1 de AISC 360, o la fracción de pernos ajustados, como un par de
fuerzas en un primer paso). La rotación es la del extremo de la viga, sin su
deformación elástica, respecto de la columna. Hay dos maneras de medirla, y la
opción **Viga › Curva M-θ solo de la conexión** elige cuál clasifica:

- **Con la zona de panel** (por omisión): respecto de la sección de la columna en
  el eje de la viga. Incluye la placa, los pernos, la flexión local del ala y la
  distorsión por cortante de la zona de panel.
- **Solo la conexión**: respecto del ala de la columna sobre el alma, entre las
  alas de la viga. Deja fuera la zona de panel, para cuando el análisis del
  pórtico ya la modela.

En las dos se deja fuera la flexión del tramo corto de columna del modelo. El
reporte dibuja las dos curvas y da K_s·L/EI de la otra como comparación.

Con la curva se clasifica la conexión según el comentario de AISC 360-22 §B3.4:
la rigidez secante K_s = M_s/θ_s en el momento de servicio M_s (el mayor de las
combinaciones ASD o, solo con LRFD, el mayor dividido entre 1.5) se compara con
la rigidez de la viga, EI/L:

| K_s·L/EI | Conexión |
|---|---|
| ≥ 20 | Totalmente restringida (FR) |
| entre 2 y 20 | Parcialmente restringida (PR) |
| ≤ 2 | Simple |

El reporte incluye la curva, la rigidez inicial y la secante, la clasificación,
el momento máximo alcanzado y el momento a 0.02 rad. En la interfaz, Análisis ›
Curva M-θ la muestra.

## Cargas y reporte

Los casos de carga dan, en la cara de la columna: V, M y P de la viga (P
positiva en compresión) y, si se revisa la zona de panel, Vc y Pc de la columna.
Las combinaciones se generan con ASCE 7 en LRFD o ASD, o se escriben a mano.

El reporte sigue el orden común: datos y cargas y, para cada combinación,
primero el modelo CalculiX (tablas de resultados, fuerzas en cada perno y
gráficos) y después las verificaciones analíticas con su traza (antes de las
combinaciones va la curva momento-rotación); el bloque sísmico, y al final el resumen, las
recomendaciones, los requisitos de instalación y el alcance.
