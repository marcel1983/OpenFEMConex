# Inicio rápido

OpenFEMConex diseña y verifica placas base de columna con un modelo de
elementos finitos resuelto en CalculiX y las verificaciones de AISC 360 y
ACI 318 con las fuerzas que salen de ese modelo.

## Primer cálculo

1. **Proyecto › Abrir** y elija un ejemplo de la carpeta `examples`, por
   ejemplo `dg1_2ed_ej_4_7.ocnx` (ejemplo 4.7 de la Guía de Diseño 1).
2. En **Geometría** revise la columna, la placa, los anclajes, el concreto y la
   soldadura. El modelo 3D se actualiza al confirmar cada dato y muestra las
   cotas de la placa, del arreglo de anclajes, de la distancia f y de hef (y el número de cada anclaje
   cuando están por coordenadas). Sobre la vista: **＋** y **－** para acercar y
   alejar, **Centrar** para volver a ver todo el modelo, y las vistas isométrica,
   planta, frente y lateral; las casillas **Cotas** y **Números de anclaje** las
   muestran u ocultan. El reporte incluye una vista en planta con las cotas.
3. En **Cargas** revise los casos y marque las combinaciones que quiere resolver.
   **Editar combinaciones** permite definir combinaciones propias con sus factores
   (uno por caso; negativo invierte el caso) o copiar las de ASCE 7 para
   cambiarlas y desmarcar las generadas.
4. En **Análisis** pulse **Resolver**. CalculiX corre en segundo plano y una
   ventana flotante muestra la combinación, la etapa, cada incremento de carga
   (con sus iteraciones y el residuo), el tiempo y la barra de avance; **Cancelar**
   detiene CalculiX. **Ocultar** la cierra sin detener el análisis (el avance
   sigue en la barra de estado y **Avance** la vuelve a abrir).
5. En **Verificación** vea la tabla de resultados. Al seleccionar una fila se
   muestra su traza de cálculo con la fórmula y la cláusula.
6. En **Reporte** genere la memoria en HTML (con gráficos) o expórtela a PDF o a
   Word (.docx editable). **Reporte › Ficha** guarda el proyecto, número, cliente,
   nombre de la conexión, ingeniero, revisión y fecha, que encabezan el reporte.
   Después de los isométricos van la planta y la elevación acotadas, con llamadas
   que indican cada elemento y su material, y flechas a las soldaduras (filete o
   CJP).

## Varias conexiones

Un proyecto puede tener varias conexiones: **Proyecto › Agregar conexión** abre
un selector con la vista isométrica de cada tipo (placa base o pernos pasantes
en concreto; los demás vendrán). Cada conexión aparece en el árbol con su icono;
al seleccionarla, el ribbon y los paneles cambian a ese tipo. **Proyecto ›
Nuevo** pregunta el tipo de la primera conexión.

## Unidades

Las unidades se eligen en **Proyecto › Unidades de presentación** y rigen en todo
el programa: formularios, tablas, cotas, reportes y Word. Todas las longitudes
van en mm (sistemas SI y MKS) o en pulgadas (US), incluso las dimensiones de la
placa y del pedestal. Al cambiar de sistema, los valores del proyecto se
reescriben en las nuevas unidades. Un número escrito sin unidad se toma en las
unidades del proyecto; también puede escribirse con su unidad (`22 in`, `560 mm`,
`3/4 in`).

## La ventana

- **Ribbon** arriba: una pestaña por etapa, en el orden de trabajo.
- **Proyecto** a la izquierda: árbol que también sirve para navegar.
- **Visor 3D** al centro: modelo, malla o resultados.
- **Propiedades** a la derecha: los datos de lo seleccionado.
- **Resultados** abajo: registro del solver y tabla de verificaciones.

La barra de estado dice si los datos son válidos, si los resultados quedaron
desactualizados por un cambio y qué verificación gobierna.

## Datos y unidades

Escriba cada valor con su unidad: `22 in`, `560 mm`, `376 kip`, `4 ksi`. Un
número solo se interpreta en las unidades del proyecto. Las unidades con que se
muestran los resultados se eligen en **Proyecto › Unidades de presentación**.

Los resultados se guardan junto al proyecto, en la carpeta `<nombre>_fem`. Si
una combinación no cambió, no se vuelve a correr CalculiX.

## Idioma y tema

En **Proyecto › Apariencia** se elige el idioma (español o inglés) y el tema
claro u oscuro. El idioma se aplica al reiniciar la ventana.
