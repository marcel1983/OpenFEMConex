# Momento con placa de extremo

Viga de acero soldada a una **placa de extremo** que se atornilla al **ala de
una columna de acero** (eje fuerte). La conexión transmite momento, cortante y
carga axial de la viga. Las verificaciones analíticas son las del motor de
OpenConex (módulo `openconex.connections.moment`), que OpenFEMConex llama con
los datos del proyecto (módulo `openfemconex.end_plate_project`). El modelo
CalculiX y la curva momento-rotación se agregan sobre estos resultados.

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

## Cargas y reporte

Los casos de carga dan, en la cara de la columna: V, M y P de la viga (P
positiva en compresión) y, si se revisa la zona de panel, Vc y Pc de la columna.
Las combinaciones se generan con ASCE 7 en LRFD o ASD, o se escriben a mano.

El reporte sigue el orden común: datos y cargas, verificaciones de cada
combinación con su traza, el bloque sísmico, y al final el resumen, las
recomendaciones, los requisitos de instalación y el alcance.
