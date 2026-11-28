# Tipos de conexión: lo que todos comparten

Todas las conexiones del programa siguen las mismas reglas de interfaz y de
reporte, para que el usuario trabaje igual con cualquiera.

## Estado de los tipos

| Tipo | Clave | Cálculo analítico | Modelo CalculiX | Estado |
|---|---|---|---|---|
| Placa base | `base_plate` | DG1 (camino de la guía) | Sí | Completo |
| Pernos pasantes en concreto | `through_bolt` | AISC 360, ACI 318 | Sí (placa de extremo, placa posterior o viga opuesta) | Completo |
| Corte simple (placa simple a columna) | `shear_tab` | No | No | Deshabilitado en el selector |
| Momento con placa de extremo | `moment_end_plate` | AISC 360-22, DG16/DG4 y AISC 358-22 (motor de OpenConex) | Sí (`end_plate_fem`: placa, ala de la columna, pernos, rigidizadores) | Interfaz, analítico, CalculiX, reporte y ayuda; falta la curva momento-rotación |
| Empalme de viga con cubreplacas | `splice` | No | No | Deshabilitado en el selector |

Corte simple y empalme solo tienen el icono en el selector. La placa de extremo (`end_plate_project.py`, `gui/end_plate_panel.py`, `gui/end_plate_window.py`, `ep_scene.py`) reutiliza los formularios, el editor de cargas y la tabla de verificaciones de los pernos pasantes (`ThroughBoltEditor` con sus propias `PAGES`, `FORM` y `LOADS`). Antes de su modelo
CalculiX hace falta definir su alcance (qué estados límite, qué se modela con
elementos sólidos y qué como resortes, cómo se apoya y se carga) igual que se
hizo con los pernos pasantes.

## Pestañas compartidas (`gui/stages.py`)

Un tipo nuevo llena un `StageActions` con lo que hace cada comando y llama a
`add_loads_tab`, `add_analysis_tab` y `add_report_tab`. Así queda:

- **Cargas**: casos de carga y combinaciones editables generadas a partir de
  ellos. El tipo implementa un `gui.loads.LoadsSource` (dónde guarda sus casos y
  combinaciones) y usa el `LoadsEditor` y el `CombinationsDialog` comunes.
- **Análisis**: el `AnalysisPanel` común (tamaño de malla, malla rápida, capas,
  hilos de CalculiX, límite de deformación plástica) con el botón verde
  **Resolver**, **Detener** y **Ver avance de CalculiX**; en el ribbon, el mismo
  botón verde. Resolver corre las verificaciones analíticas y el modelo FEM. El
  avance de CalculiX se muestra en `gui.progress.SolveProgress` (incrementos,
  iteraciones, residuo y tiempo) y en el registro.
- **Reporte**: Generar, Abrir, Exportar PDF, Exportar Word y la Ficha.

## Orden del reporte

1. Ficha, veredicto global, datos, isométricos del modelo y de la malla.
2. Por combinación: resultados FEM con gráficos (von Mises, deformación
   plástica, desplazamiento, presión de contacto en cada placa apoyada), las
   verificaciones con demandas del FEM, luego las verificaciones analíticas y su
   traza.
3. Cierre común, `report.closing_blocks`: resumen por combinación (qué rige en
   el FEM y en el analítico), recomendaciones para lo que no cumple, requisitos
   de instalación que hacen válidas las hipótesis del análisis, y alcance y
   limitaciones.

El reporte se arma como bloques (`report.Block`) y de ahí sale el HTML
(`blocks_to_html`), el PDF (desde el HTML) y el Word (`report_docx.write_docx`),
así que los tres tienen el mismo contenido.

Los requisitos de instalación se escriben con palabras propias, ligadas a cada
hipótesis del modelo (por ejemplo, "el modelo supone contacto continuo bajo la
placa": mortero sin vacíos). No se copia texto de AISC ni de ACI.
