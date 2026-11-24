# Modelo de elementos finitos

El modelo sigue el enfoque por componentes: el acero con sólidos y material
elástico-plástico, y los anclajes y el apoyo en concreto como componentes.

| Parte | Modelo |
|---|---|
| Columna, placa y rigidizadores | Hexaedros C3D8I, acero bilineal |
| Soldaduras | Nodos compartidos (unión continua) |
| Concreto con mortero | Bloque elástico, Ec = 4700 √f'c, base empotrada |
| Apoyo | Contacto superficie a superficie, sin tracción, con fricción μ |
| Anclajes | Resorte axial solo a tracción (EA/L) repartido en el área de la arandela |
| Cortante en anclajes | Solo con arandelas soldadas; si no, va por fricción |
| Llave de cortante | Resorte de aplastamiento contra el concreto |
| Cargas | Cuerpo rígido en la cabeza de la columna; P, V y M se dan en la base |

La carga axial se aplica primero y los momentos y cortantes después.

## Datos que agrega OpenFEMConex

Además de los datos de OpenConex, el archivo `.ocnx` puede llevar:

- **Anclajes por coordenadas** (Geometría › Anclajes): tabla x, y desde el
  centro de la placa. x va a lo largo del peralte de la columna.
- **Refuerzo del pedestal** (Geometría › Concreto): barras, estribos y altura.
  Necesita las dimensiones del pedestal.
- **Rigidizadores** (Geometría › Rigidizadores): en línea con el alma o tres
  por patín para perfiles W, y radiales para tubos circulares.

Un archivo con estos datos solo se abre en OpenFEMConex.

## Malla

El tamaño fino automático es el menor espesor entre la pared de la columna y
la placa. Se cambia en **Análisis › Ajustes**, junto con las capas en el
espesor de la placa y los hilos de CalculiX.

## Resultados

- **von Mises** y **deformación plástica** en el acero, con la deformada.
- **Presión de contacto** bajo la placa.
- **Desplazamiento**.
- La tracción de cada anclaje aparece rotulada en la vista.
