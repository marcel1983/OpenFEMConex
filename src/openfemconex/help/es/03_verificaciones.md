# Verificaciones

Cada verificación toma la demanda del FEM y la capacidad de la fórmula de la
norma. Las ediciones se eligen en **Proyecto › Normas**:

- **AISC 360-22 / ACI 318-19** (vigentes).
- **DG1 2.ª ed.**: AISC 360-05 y ACI 318-08 como los aplica la Guía de Diseño 1,
  para reproducir sus ejemplos.

| Componente | Verificación |
|---|---|
| Concreto | Aplastamiento con el bloque centrado en la resultante FEM (J8) |
| Placa | Deformación plástica (límite configurable, 5 %) y flexión por tracción de anclajes |
| Anclajes | Acero a tracción y cortante, extracción, desprendimiento lateral |
| Anclajes | Tracción, cortante y flexión con arandela soldada (AISC J3.7/J3.8) |
| Concreto | Arrancamiento en tracción y en cortante, palanca (pryout), interacción |
| Pedestal | Refuerzo de anclaje a tracción (barras y horquillas en U) y cortante, flexocompresión, cuantía mínima |
| Cortante | Fricción, o llave de cortante (aplastamiento, acero y soldadura) |
| Soldadura | Columna-placa y rigidizadores, con aumento direccional (J2.4) |
| Rigidizadores | Deformación plástica y esbeltez del borde libre |

Una fila *No rige* es una alternativa que no gobierna: por ejemplo, el
arrancamiento del concreto cuando el refuerzo de anclaje del pedestal cumple.

Las verificaciones del concreto (ACI) son de resistencia última y solo se
evalúan en combinaciones LRFD.

Con la edición vigente, el reporte añade el camino analítico de OpenConex
(placa rígida y bloque de esfuerzos) con las mismas cargas, para comparar.

## Recomendaciones

Cuando una verificación no cumple, al seleccionarla en la pestaña Verificación
aparece una lista de cambios posibles en los datos que se pueden ajustar: diámetro
o grado de los anclajes, empotramiento hef, espesor y tamaño de la placa, tamaño
del filete, refuerzo de anclaje, pedestal, llave de cortante. Donde hay una fórmula
directa se da el valor mínimo (por ejemplo, el espesor de placa a partir de
tp·√relación, redondeado a 1/16 in o 1 mm). El reporte incluye la misma lista
después de la tabla de verificaciones.

Son estimaciones para un cambio a la vez: el modelo de elementos finitos
redistribuye las fuerzas, así que vuelva a resolver después de cambiar los datos.
