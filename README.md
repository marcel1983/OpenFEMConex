# OpenFEMConex

Conexiones metálicas por elementos finitos con CalculiX, según AISC y ACI.
Software libre bajo [GPL-3.0-or-later](LICENSE).

> **Estado: paso 2 del plan.** Genera el modelo FEM de una placa base de columna,
> lo resuelve con CalculiX y lee los resultados. Las verificaciones normativas
> (paso 3) y la interfaz gráfica (paso 4) todavía no están.

## Qué hace

A partir de un proyecto de [OpenConex](https://github.com/marcel1983/openconex)
(`.ocnx`: perfil AISC, placa, anclajes, concreto, casos y combinaciones):

1. malla la planta de la placa con Gmsh en cuadriláteros (agujeros, arandelas de
   placa y huella de la columna) y la extruye a hexaedros `C3D8I`;
2. escribe un `.inp` por combinación de carga;
3. corre `ccx` y lee los archivos `.dat` y `.frd`;
4. resume tracción en cada anclaje, presión de contacto, esfuerzos, deformación
   plástica y equilibrio, y guarda un `.json` por combinación.

| Parte | Modelo |
|---|---|
| Columna y placa | sólidos `C3D8I`, acero bilineal (`*PLASTIC`) |
| Soldadura columna–placa | nodos compartidos en la huella de la columna |
| Concreto | bloque elástico (Ec = 4700√f'c), base empotrada |
| Apoyo | `*CONTACT PAIR` superficie a superficie, sin tracción, con fricción |
| Anclajes | resorte axial solo a tracción (EA/L) unido al área de la arandela; toman cortante solo con arandelas soldadas |
| Cargas | `*RIGID BODY` en la cabeza de la columna; P, V y M se dan en la base. Primero se aplica P y luego M y V |

Perfiles admitidos: W, M, S, HP, HSS rectangular y cuadrado, HSS circular y Pipe.

## Instalación

Requiere Python 3.12, CalculiX y una copia local de OpenConex.

```bash
sudo apt install calculix-ccx
```
```bash
python3 -m venv .venv && .venv/bin/pip install -e ../openconex -e ".[dev]"
```

Gmsh se instala solo desde pip. Para usar otro ejecutable de CalculiX defina
`OPENFEMCONEX_CCX` o pase `--ccx`.

## Uso

```bash
.venv/bin/openfemconex run examples/dg1_2ed_ej_4_7.ocnx --combo LRFD-2
```

Opciones útiles: `--list` (combinaciones), `--only-inp` (no corre ccx), `--size`
(tamaño fino de malla en mm), `--layers`, `--threads`, `--leveling-nuts`, `--mu`,
`--out`. Cada combinación deja en la carpeta de salida el `.inp`, los archivos de
ccx, un `.json` con el resumen y un `.vtu` para ver en ParaView o PyVista.

## Convenciones

- Unidades internas N, mm y MPa.
- Ejes: x a lo largo del peralte de la columna, y a lo largo del patín, z hacia
  arriba; la cara inferior de la placa está en z = 0.
- `P` positiva en compresión; `My` (eje fuerte) positivo comprime el lado +x.

## Pruebas

```bash
.venv/bin/python -m pytest
```

Las pruebas marcadas `ccx` corren CalculiX y tardan varios minutos; se omiten
con `-m "not ccx"`.

## Validación

Ver [docs/validacion.md](docs/validacion.md): ejemplo 4.7 de la Guía de Diseño 1
del AISC, 2.ª edición.

**Aviso:** herramienta de apoyo. La responsabilidad del diseño corresponde al
profesional que lo firma.
