# Modelo de elementos finitos

El modelo sigue el enfoque por componentes: el acero con sólidos y material
elástico-plástico, y los anclajes y el apoyo en concreto como componentes.

| Parte | Modelo |
|---|---|
| Columna, placa y rigidizadores | Hexaedros C3D8I, acero bilineal o la ley elegida en Materiales |
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
- **Refuerzo del pedestal** (Geometría › Refuerzo del pedestal): barras, estribos y altura.
  Necesita las dimensiones del pedestal.
- **Rigidizadores** (Geometría › Rigidizadores): en línea con el alma o tres
  por patín para perfiles W, y radiales para tubos circulares.

**Horquillas en U** (en la misma página): U invertidas sobre cada anclaje, con una
pata a cada lado. Cuentan como refuerzo de anclaje a tracción si las patas quedan
a menos de 0.5·hef; se verifica su desarrollo sobre el cono (el doblez hace de
gancho) y bajo el cono (largo de las patas). No requieren pedestal. Se dibujan en
verde.

Las barras del pedestal terminan arriba en gancho de 90°, de 180° o rectas
(Terminación arriba). Los ganchos de 90° y 180° tienen el mismo largo de
desarrollo l_dh (ACI 318-19 §25.4.3); una barra recta necesita l_d, más largo.

El refuerzo del pedestal se dibuja dentro del concreto (estribos que toman
cortante en naranja), pero no forma parte del modelo FEM: solo entra en las
verificaciones.

Un archivo con estos datos solo se abre en OpenFEMConex.

## Columnas, perfiles armados y materiales

**Columna cruciforme** (Geometría › Columna, Tipo: Cruciforme): un perfil W
principal y un segundo perfil I cortado por el alma en dos T, soldadas a las dos
caras del alma del principal. Los patines del perfil cruzado quedan a lo largo
del eje y y deben caber entre los patines del principal (bf2 < d − 2 tf). Ambos
perfiles usan el acero de la columna. En las cruciformes la flexión de la placa
por los anclajes en tracción se toma respecto de la pared más cercana, los
rigidizadores van en línea con las dos almas, y no se calcula el camino analítico
de DG1 (que supone un perfil simple).

**Perfiles armados** (Geometría › Biblioteca › Perfiles): perfiles I formados por
tres placas soldadas (d, bf, tf, tw), con vista de la sección y sus propiedades
(A, I, S, Z, r, J). Se guardan con el proyecto y aparecen en la lista de perfiles
de la columna y del perfil cruzado. "Copiar del catálogo" parte de un perfil AISC.

**Materiales** (Geometría › Biblioteca › Materiales): aceros de la biblioteca AISC
y del proyecto (Fy, Fu, E y ν) y grados de anclaje (Fu, Fy, Fnt, Fnv). Para cada
acero se elige la ley constitutiva del modelo de elementos finitos, con vista previa
de la curva esfuerzo-deformación:

| Ley | Curva |
|---|---|
| Bilineal | Fluencia en Fy y pendiente H (E/1000 si se deja vacío) hasta εp última |
| Elastoplástica | Plástica perfecta en Fy |
| Trilineal | Escalón en Fy hasta εp de endurecimiento, luego recta hasta Fu en εp última |
| Tabla | Puntos (esfuerzo, deformación plástica) que empiezan en (Fy, 0) |

Las resistencias de los materiales AISC son fijas; su ley FEM sí se puede cambiar.

## Malla

El tamaño fino automático es el menor espesor entre la pared de la columna y
la placa. Se cambia en **Análisis › Ajustes**, junto con las capas en el
espesor de la placa y los hilos de CalculiX.

## Avisos antes de resolver

- Junto a las paredes de la columna y a los rigidizadores el tamaño de elemento se
  limita a 1.5 veces su espesor, para que un tubo delgado no deje elementos
  deformados. Si aun así hay alguno, el programa lo avisa antes de llamar a
  CalculiX.
- Si el tramo de columna no resiste las cargas (cortante, o axial más flexión con
  el momento V·Lc en su extremo), se avisa. Con un uso mayor que 2 la combinación
  no se resuelve: el análisis no podría converger.
- Con levantamiento y cortante, sin llave ni arandelas soldadas, no hay fricción:
  el cortante lo toman los anclajes tras deslizar la placa en los agujeros.

## Resultados

- **von Mises** y **deformación plástica** en el acero, con la deformada.
- **Presión de contacto** bajo la placa.
- **Desplazamiento**.
- La tracción de cada anclaje aparece rotulada en la vista.
