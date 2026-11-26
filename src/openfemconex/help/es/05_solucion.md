# Solución con CalculiX

Esta sección describe qué hace el programa entre **Resolver** y los resultados,
y qué parámetros toma solo.

## Flujo de solución

Para cada combinación marcada:

1. **Revisión previa.** Se estima el uso plástico de la columna modelada (axial,
   flexión y cortante con sus capacidades plásticas). Con uso mayor que 1.5 se
   avisa que puede no converger; con uso mayor que 2.0 la combinación no se
   resuelve. También se avisa si hay cortante sin compresión (no hay fricción).
2. **Malla.** Se genera una sola vez para todas las combinaciones (ver *Malla
   automática*).
3. **Archivo de entrada.** Se escribe `NOMBRE.inp` en la carpeta `*_fem` junto al
   proyecto.
4. **Reutilización.** Si ya hay una solución y el `.inp` no cambió (mismos datos,
   malla y cargas), se leen los resultados guardados sin volver a resolver.
5. **CalculiX.** Se ejecuta `ccx` con la mitad de los núcleos del equipo (se
   cambia en Análisis › Ajustes). La ventana de avance lee el archivo `.sta`
   (incrementos) y el `.cvg` (iteraciones y residuo). Si CalculiX encuentra
   elementos distorsionados (*nonpositive jacobian*) se detiene de inmediato.
6. **Reintento.** Si no convergió, se vuelve a resolver con la ley de anclaje
   suavizada (ver abajo) y se conserva el intento que llegó más lejos.
7. **Lectura.** Del `.dat` se leen reacciones de anclajes y del concreto; del
   `.frd`, desplazamientos, esfuerzos, PEEQ y presión de contacto. Se calculan
   las fuerzas por anclaje, las fuerzas por unidad de largo en las soldaduras, la
   resultante de compresión y el error de equilibrio. Se escriben el `.json` y el
   `.vtu` para el visor.
8. **Verificaciones** de AISC y ACI con esas demandas, y recomendaciones para
   las que no cumplen.

## Análisis no lineal

| Parámetro | Valor |
|---|---|
| Tipo | Estático (`*STATIC`), no lineal por material y contacto; pequeños desplazamientos (sin NLGEOM) |
| Método | Newton-Raphson completo de CalculiX con incrementación automática |
| Pasos | 1: carga axial de compresión sola; 2: momentos y cortantes. Si no hay compresión, un solo paso con todo |
| Paso 1 | Incremento único (1.0) |
| Paso 2 (o único) | Incremento inicial 0.05, máximo 0.2, mínimo 1·10⁻⁶ (0.02 si la columna está al límite), hasta 200 incrementos |
| Criterios de convergencia | Los de CalculiX por defecto (`*CONTROLS` sin cambios) |
| Resultado parcial | Si un paso no termina, se informa el último incremento convergido y el porcentaje de carga alcanzado |

Aplicar primero la compresión hace que toda la placa apoye y que la zona de
contacto se reduzca poco a poco con el momento, en vez de tener que encontrarla
en el primer incremento.

## Materiales

| Parte | Ley |
|---|---|
| Columna, placa, rigidizadores | Elastoplástica con endurecimiento isótropo (`*PLASTIC`). Por defecto bilineal: fluencia en Fy y pendiente E/1000 hasta εp = 0.15. Se cambia por acero en Materiales |
| Concreto con mortero | Elástico lineal, Ec = 4700 √f'c, ν = 0.2 |
| Elementos | Hexaedros C3D8I (modos incompatibles, buenos a flexión con pocas capas) |

## Contacto placa-concreto

- Superficie a superficie (`*CONTACT PAIR`), placa sobre concreto.
- Presión-penetración lineal: rigidez K = 10·Ec / 25 mm y tracción residual
  σ∞ = 0.05 MPa (la placa puede separarse).
- Fricción μ (la del proyecto) solo si hay cortante y no hay arandelas soldadas;
  rigidez de adherencia K/10. Sin cortante el contacto es sin fricción (sistema
  simétrico, converge más rápido).

## Anclajes

- Cada anclaje es un nodo de referencia que sigue el promedio, ponderado por
  área, de los nodos de la placa bajo la arandela (`*EQUATION`), unido a tierra
  por resortes (`SPRING2`).
- **Axial:** ley tabulada solo a tracción, rigidez E·A/L con L = hef + mortero +
  tp. A compresión 1/1000 de esa rigidez (con tuercas de nivelación, la misma).
- **Ley suavizada (reintento):** la rigidez cambia en escalones de 10 en ±0.005 mm
  alrededor de cero, para que Newton no oscile cuando un anclaje empieza a
  trabajar.
- **Lateral:** solo con arandelas soldadas (si no, el cortante va por fricción):
  flexión de la barra empotrada en ambos extremos sobre mortero + tp/2,
  12·E·I/L³, entre la cara inferior de la placa y el concreto junto a la barra.

## Llave de cortante y cargas

- La llave es un resorte de aplastamiento entre la placa y el concreto, de
  rigidez Ec × ancho, en la dirección del cortante que resiste.
- Las cargas se aplican en un nodo de referencia unido a la cabeza de la columna
  como cuerpo rígido (`*RIGID BODY`). Los momentos se corrigen por el brazo del
  cortante: M arriba = M base ∓ V·Lc, para que en la base actúen los valores
  dados.

## Configuraciones automáticas

| Dato | Valor automático |
|---|---|
| Largo de columna modelado Lc | 2.5 × la mayor dimensión de la sección |
| Bloque de concreto | El pedestal si se dio; si no, la placa escalada para que A2/A1 sea la del proyecto (máximo 4). Profundidad = su mayor dimensión. Base empotrada |
| Tamaño fino de malla | El menor entre la pared de la columna y tp, al menos 8 mm |
| Junto a paredes y rigidizadores | Como máximo 1.5 × su espesor (evita elementos distorsionados) |
| Tamaño grueso | 3 × el fino; a lo largo de la columna, 2 × el fino creciendo hacia arriba |
| Capas | 4 en el espesor de la placa; 10 en el concreto |
| Malla rápida | Fino ×2 (al menos 15 mm), 3 capas en la placa, 8 en el concreto; la primera altura de la columna se mantiene. Si salen elementos distorsionados se refina sola |
| Hilos de CalculiX | La mitad de los núcleos |
| Ejecutable ccx | El indicado, `$OPENFEMCONEX_CCX`, `ccx` del sistema o la copia incluida en el instalador |
| Soldadura | Filete del proyecto o el mínimo de la Tabla J2.4; CJP si se marca |
| Fricción | μ del proyecto (0.55 sobre mortero, 0.7 sobre concreto según DG1) |

## Archivos que quedan

En la carpeta `*_fem`, por combinación: `.inp` (entrada), `.sta` y `.cvg`
(avance), `.dat` (reacciones), `.frd` (resultados completos, se abre con
CalculiX GraphiX), `.json` (resumen) y `.vtu` (para ParaView), además del
reporte y sus figuras.
