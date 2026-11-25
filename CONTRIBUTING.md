# Contribuir a OpenFEMConex / Contributing to OpenFEMConex

*English below.*

## Español

¡Gracias por tu interés! OpenFEMConex es software libre bajo
**AGPL-3.0-or-later**; al enviar una contribución aceptas que se publique bajo
esa licencia.

### Sin programar

La mayor parte de lo que este proyecto necesita no es código. Todo se hace desde
la pestaña [Issues](https://github.com/marcel1983/openfemconex/issues/new/choose),
eligiendo una plantilla:

| Quiero… | Plantilla |
|---|---|
| Aportar un ejemplo con resultado conocido (guía de diseño, libro, cálculo a mano, otro programa) | **Caso de validación** |
| Avisar de que un número o una verificación está mal | **Error de cálculo** |
| Avisar de que el programa se cierra o no hace lo que debería | **Reportar un fallo** |
| Pedir una función nueva o un tipo de conexión | **Solicitar una característica** |

Las dudas de uso van a
[Discussions](https://github.com/marcel1983/openfemconex/discussions). También
ayudan las traducciones, las correcciones a la ayuda integrada y a `docs/`, y
probar las versiones nuevas en tu sistema.

Para abrir un issue necesitas una cuenta gratuita de GitHub.

### Con código

#### Entorno

Requiere Python 3.12 y CalculiX (`ccx`); ver el [README](README.md#instalación-desde-el-código).

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[gui,dev]"
```

#### Antes de abrir un pull request

```bash
.venv/bin/ruff check src tests
```
```bash
.venv/bin/python -m pytest
```

Las pruebas marcadas `ccx` corren CalculiX y tardan unos minutos; durante el
desarrollo se omiten con `-m "not ccx"`, pero deben pasar antes de pedir revisión.

#### Reglas

- **Un cambio por pull request**, en una rama nueva desde `main`, con una
  descripción del problema y de la solución.
- **DCO, sin CLA.** Firma cada commit (`git commit -s`): la línea
  `Signed-off-by` certifica el
  [Developer Certificate of Origin 1.1](https://developercertificate.org/).
- **Encabezado SPDX** en cada archivo Python:
  ```python
  # SPDX-License-Identifier: AGPL-3.0-or-later
  # Copyright (C) 2026 The OpenFEMConex contributors
  ```
- **Código de terceros** solo con licencia compatible con AGPL-3.0.
- **Material protegido:** no copies texto, tablas ni figuras de normas o
  manuales (AISC, ACI, ASCE). En las pruebas usa solo datos numéricos de
  ejemplos resueltos y cita la fuente.
- **Toda verificación nueva** muestra su fórmula, valores y cláusula, y se
  valida contra un ejemplo publicado o un cálculo independiente en `tests/`.
- **Documentación en el mismo PR:** la ayuda integrada, `docs/` y los README
  (español e inglés) cuando el cambio altera lo que describen.
- Lo que sea común con [OpenConex](https://github.com/marcel1983/openconex)
  (catálogo de perfiles AISC, materiales, formato `.ocnx`) se cambia allí.

## English

Thanks for your interest! OpenFEMConex is free software under
**AGPL-3.0-or-later**.

- **No programming needed** for most of what helps: open an issue from the
  [templates](https://github.com/marcel1983/openfemconex/issues/new/choose):
  *Validation case* (an example with a known answer), *Calculation error*,
  *Bug report* or *Feature request*. Questions go to
  [Discussions](https://github.com/marcel1983/openfemconex/discussions).
- **Setup:** Python 3.12 and CalculiX; `pip install -e ".[gui,dev]"`.
- Run `ruff check src tests` and `python -m pytest` (including the `ccx` tests)
  before asking for review.
- One change per pull request, from a new branch off `main`.
- **DCO, no CLA:** sign off every commit (`git commit -s`).
- **SPDX header** in every Python file; third-party code only under
  AGPL-3.0-compatible licenses.
- **Do not copy** text, tables or figures from AISC/ACI/ASCE publications;
  tests may use numeric data from worked examples, with a citation.
- Every new check shows its formula, values and clause and is validated
  against a published example or an independent calculation.
- Update the in-app help, `docs/` and both READMEs in the same pull request.
- What is shared with [OpenConex](https://github.com/marcel1983/openconex)
  (AISC shape catalog, materials, the `.ocnx` format) is changed there.
