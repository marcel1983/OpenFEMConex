# Validación y limitaciones

## Ejemplos de la Guía de Diseño 1 (2.ª ed.)

| Ejemplo | Guía | OpenFEMConex |
|---|---|---|
| 4.7 momento grande: tracción en anclajes | 76.0 kips | 76.7 kips (FEM) |
| 4.5 levantamiento: fuerza por anclaje | 17.5 kips | 17.5 kips (FEM) |
| 4.5: ratios de anclaje, arrancamiento y placa | 0.89, 0.90, 0.69 | 0.89, 0.90, 0.69 |
| 4.11: tracción, cortante y flexión del anclaje de 1⅛ in | 46.7 > 25.1 ksi | 46.7 > 25.1 ksi |

Las capacidades de los ejemplos 4.3, 4.5, 4.7 y 4.10 y la Tabla 3.2 se
reproducen en las pruebas automáticas.

## Limitaciones

- El concreto es elástico: no se aplasta ni se fisura. El pico de presión del
  modelo es un indicador, no la demanda de diseño.
- Los anclajes son resortes: sin cono de concreto ni flexión local del perno
  en el modelo (la flexión se verifica con la fórmula de la guía).
- Sin radios de acuerdo en perfiles W ni esquinas redondeadas en HSS.
- Rigidizadores solo para perfiles W y tubos circulares.
- No incluye diseño sísmico ni la verificación ASD del concreto.

**Aviso:** herramienta de apoyo. La responsabilidad del diseño corresponde al
profesional que lo firma.
