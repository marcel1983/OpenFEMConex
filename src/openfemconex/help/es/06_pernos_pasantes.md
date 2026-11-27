# Pernos pasantes en concreto

Viga con placa frontal unida a un muro o columna **nuevo** de concreto con pernos
que lo atraviesan dentro de una camisa (sin adherencia) y se anclan en una
**placa posterior corrida** en la cara opuesta. Puede haber otra viga del otro
lado, con los mismos pernos.

Las verificaciones de este tema están en el módulo `openfemconex.through_bolt`.
Esta primera versión cubre una sola viga con el cortante por fricción; el
esquema con grout y la conexión opuesta se describen aquí y se completan en las
versiones siguientes.

## Camino de las fuerzas

Con el momento M de la viga y el brazo z = d − tf entre los centros de los patines:

- los pernos del patín traccionado llevan **T = |M|/z − P/2** hasta la placa
  posterior, que la apoya en la cara opuesta del concreto (sin adherencia, toda
  la tracción llega a la placa posterior);
- la placa frontal se apoya en la cara cercana, en el patín comprimido, con
  **C = T + P** (P positiva en compresión).

## 1. Cortante: por fricción o con grout

![Cortante por fricción](img/es/corte_friccion.png)

**Fricción.** El cortante pasa de la placa frontal al concreto por fricción
bajo la compresión C: φ μ C ≥ Vu, con los límites de la Guía de Diseño 1 y μ
definido por el usuario (0.55 por defecto). Los pernos no trabajan a cortante.

- A favor: obra simple (camisa vacía) y coherente con el perno sin adherencia.
- En contra: necesita compresión en todas las combinaciones; la pretensión se
  pierde por fluencia y retracción del concreto, por lo que no se cuenta; en
  diseño sísmico normalmente no se acepta confiar en la fricción. ACI 318 §22.9
  solo permite sumar la compresión **permanente** a la fricción: el ingeniero
  debe juzgar si la compresión de cada combinación es aceptable.

![Cortante con grout](img/es/corte_grout.png)

**Grout.** La camisa se rellena con grout en un tramo ℓg junto a la cara
frontal; el perno se apoya lateralmente en el grout. Para conservar la
condición sin adherencia, el perno lleva desadherente (cinta o vaina) dentro
del grout. Revisiones: perno a cortante y tracción combinados (AISC J3.7),
aplastamiento en los agujeros de la placa (J3.10), apoyo del perno en el grout
(ACI §22.8) y flexión del perno si hay holgura.

- A favor: no depende de la compresión; sirve con un solo lado cargado, con
  tracción axial y en sismo.
- En contra: obra más delicada; si falta el desadherente, el perno queda
  adherido y cambia el reparto de la tracción.

## 2. Sección de concreto

![Fuerzas sobre el concreto](img/es/concreto_fuerzas.png)

| Revisión | Referencia | Cómo se hace |
|---|---|---|
| Aplastamiento bajo cada placa | ACI 318 §22.8 | A1 = núcleo (patín o arandelas) más un voladizo l de la placa con φ Fy tp²/4 = fp l²/2; A2 por el tronco de pirámide 1:2 dentro del elemento |
| Punzonamiento por la placa posterior | ACI 318 §22.6 | Fuerza T; b0 a d/2 del área que apoya, recortado por los bordes en una columna (αs = 40 o 20) |
| Hendimiento detrás de cada placa | §25.9 (analogía), Cap. 23 | T_burst = 0.25 F (1 − a/H), H = a + h, contra las barras de las dos caras dentro de H |

![Cara posterior](img/es/concreto_cara.png)

Una placa posterior corrida y flexible solo apoya cerca de los pernos
traccionados: por eso A1 se limita con la flexión de la placa, no con toda su área.

## 3. Flexión del muro o columna

![Puntal y tensor](img/es/flexion_muro.png)

Las dos zonas de presión están desfasadas: forman un par que flexiona el muro o
la columna.

- **Junto a la conexión** (puntal y tensor, ACI 318 Cap. 23): puntal diagonal
  de la placa posterior a la zona comprimida de la placa frontal, con θ =
  arctan(jz/jx); el refuerzo vertical de cada cara es el tensor, F_t = T tan θ,
  dentro de b_eff = b_bp + 2h. Se revisan el puntal (βs = 0.4, o 0.75 con
  estribos que lo crucen), los nodos C-C-T (βn = 0.8, βc = √(A2/A1)), el tensor,
  su desarrollo ℓd más allá de cada nodo y el ángulo mínimo de 25°.
- **Fuera de la conexión** (§22.2 a §22.4): el momento M + V h/2 se reparte
  arriba y abajo (mitad y mitad por defecto); se revisa la franja de muro de
  ancho b_eff, o la sección completa de la columna con su carga axial.

El diseño global del muro o columna y el nudo de una columna con vigas a los
dos lados (ACI 318 Cap. 15) quedan para el análisis global.

## 4. Conexión opuesta

![Conexión opuesta](img/es/conexion_opuesta.png)

Con viga del otro lado, la placa posterior es la placa frontal de la otra viga
y los pernos son compartidos. Cada placa se revisa en sus dos papeles. El
concreto recibe el momento desbalanceado ΔM; en sismo los momentos van en el
mismo sentido y trabajan a tracción las filas de arriba y de abajo.

## Datos

| Dato | Descripción |
|---|---|
| Viga y placa frontal | Perfil, disposición de pernos (Guías de Diseño 16 y 4), espesor, soldaduras |
| Placa posterior | Ancho, alto, espesor, acero, diámetro de arandela |
| Muro o columna | Tipo, espesor (en la dirección de los pernos), ancho de columna, f'c, recubrimiento, barras verticales y horizontales de cada cara, distancia a los extremos, carga axial |
| Cortante | Fricción (μ) o grout |
