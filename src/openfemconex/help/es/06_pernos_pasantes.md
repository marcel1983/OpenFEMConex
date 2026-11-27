# Pernos pasantes en concreto

Viga con placa frontal unida a un muro o columna **nuevo** de concreto con pernos
que lo atraviesan dentro de una camisa (sin adherencia) y se anclan en una
**placa posterior corrida** en la cara opuesta. Puede haber otra viga del otro
lado, con los mismos pernos.

Las verificaciones de este tema están en el módulo `openfemconex.through_bolt`
(cálculo analítico y modelo CalculiX). Cubre una
viga o dos vigas opuestas, con el cortante por fricción o con grout.

## Camino de las fuerzas

Para cada viga, con su momento M (positivo con tracción arriba), su cortante V
y el brazo z = d − tf entre los centros de los patines:

- su patín traccionado tira de los pernos de ese grupo (arriba o abajo) con
  **T = |M|/z − P/2**, y su patín comprimido apoya la placa en su cara con
  **C = T + P** (P positiva en compresión);
- los pernos de un grupo llevan la mayor tracción de los dos lados,
  **Tb = máx(T1, T2)**; la placa del lado que tira menos se apoya en su cara con
  Tb − Ti (con una sola viga, la placa posterior recibe toda la T);
- así cada cara tiene una zona de apoyo arriba y otra abajo. Lo que no se
  equilibra a través del espesor, ΔF, lo lleva un puntal diagonal y el refuerzo
  vertical, y flexiona el elemento con **ΔM = (M1 − M2) + (V1 − V2) h/2**.

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
del grout. Revisiones:

- perno más cargado con la tracción de su grupo, el cortante V/n del lado más
  cargado y la flexión sobre la holgura g entre placa y grout (brazo g/2),
  con la tracción reducida de AISC J3.7 (como la varilla con arandela soldada de
  la Guía de Diseño 1);
- apoyo del perno en el grout: V/n ≤ φ 0.85 f'cg d ℓ, con ℓ = mín(ℓg, 4d)
  porque la presión se concentra junto a la cara;
- cortante, aplastamiento y desgarramiento en los agujeros de la placa con los
  pernos de la zona comprimida (Guías de Diseño 16 y 4).

- A favor: no depende de la compresión; sirve con un solo lado cargado, con
  tracción axial y en sismo.
- En contra: obra más delicada; si falta el desadherente, el perno queda
  adherido y cambia el reparto de la tracción.

## 2. Sección de concreto

![Fuerzas sobre el concreto](img/es/concreto_fuerzas.png)

| Revisión | Referencia | Cómo se hace |
|---|---|---|
| Aplastamiento bajo cada placa | ACI 318 §22.8 | A1 = núcleo (patín o arandelas) más un voladizo l de la placa con φ Fy tp²/4 = fp l²/2; A2 por el tronco de pirámide 1:2 dentro del elemento |
| Punzonamiento de cada grupo | ACI 318 §22.6 | Fuerza no equilibrada por la otra cara; b0 a d/2 del área que apoya, recortado por los bordes en una columna (αs = 40 o 20) |
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
y los pernos son compartidos. Las dos placas deben tener las mismas filas,
gramil y diámetro de pernos; los ejes de las vigas, a la misma altura.

| Caso | Pernos | Concreto |
|---|---|---|
| A. Balanceada (M1 = M2) | Tb = T, no 2T | Solo compresión abajo en las dos caras: sin puntal ni punzonamiento, ΔM ≈ 0 |
| B. Desbalanceada | Tb = máx(T1, T2) | La placa 2 se apoya arriba con T1 − T2; ΔM = M1 − M2 |
| C. Un solo lado | Tb = T1 | La placa 2 trabaja como placa posterior; ΔM = M1 |
| D. Sismo (mismo sentido) | Filas de arriba y de abajo a tracción | ΔF = T + C; ΔM = M1 + M2 |

Cada viga tiene sus revisiones de placa de extremo (las de la viga 2 llevan
«viga 2» en la combinación) y, con fricción, su propio cortante por fricción con
la compresión de su cara. En sismo no conviene confiar en la fricción: use grout.

## En la interfaz

**Proyecto › Agregar conexión › Pernos pasantes en concreto** agrega una
conexión con los datos del primer ejemplo. Al seleccionarla en el árbol:

- **Geometría**: viga, placa de extremo, placa posterior, muro o columna, viga
  opuesta y cortante; la vista 3D muestra el muro, las placas, los pernos y el
  grout de las camisas.
- **Cargas**: combinaciones mayoradas (LRFD) en la cara del muro: V, M y P de la
  viga 1 y, con viga opuesta, V2, M2 y P2.
- **Análisis › Calcular**: corre las verificaciones analíticas; **Análisis ›
  Resolver** agrega las del modelo CalculiX. **Verificación** muestra la tabla
  y la traza de la fila elegida.
- **Reporte**: HTML (con la vista 3D y los esquemas de esta ayuda) o PDF.

## Modelo CalculiX

**Análisis › Resolver** resuelve cada combinación con CalculiX. La placa de
extremo apoyada en la cara del muro o columna es el mismo problema que una
placa base sobre su bloque de concreto, así que se usa ese modelo:

- la viga y su placa de extremo son sólidos de acero elastoplástico; la placa
  apoya en el concreto con contacto (sin tracción) y, con cortante por
  fricción, con fricción μ;
- el concreto es un bloque elástico del espesor h del muro, con la cara opuesta
  fija: la placa posterior (o la otra viga) se toma como rígida;
- cada perno es un resorte solo a tracción de rigidez E·A/L, con L = h más los
  espesores de las dos placas, porque va sin adherencia en la camisa; con grout,
  los pernos también toman el cortante;
- con viga opuesta se resuelve cada lado con sus cargas, como en el modelo de
  zonas.

Con sus fuerzas se revisan el perno más cargado (con efecto palanca, J3.6), la
deformación plástica de la placa (5 %), el aplastamiento con la resultante del
contacto, la fricción y las soldaduras de patines y alma. Las verificaciones
del concreto (punzonamiento, hendimiento, puntal y tensor, flexión del muro)
siguen siendo las analíticas. La vista 3D muestra el modelo con la viga
vertical (ejes de la placa base). **Malla rápida** viene marcada: cada
combinación toma unos minutos.

## Datos

| Dato | Descripción |
|---|---|
| Viga y placa frontal | Perfil, disposición de pernos (Guías de Diseño 16 y 4), espesor, soldaduras |
| Placa posterior | Ancho, alto, espesor, acero, diámetro de arandela |
| Muro o columna | Tipo, espesor (en la dirección de los pernos), ancho de columna, f'c, recubrimiento, barras verticales y horizontales de cada cara, distancia a los extremos, carga axial |
| Viga opuesta | Perfil y placa de extremo con los mismos pernos; cargas V2, M2, P2 |
| Cortante | Fricción (μ) o grout (largo ℓg, f'c del grout, holgura g) |
