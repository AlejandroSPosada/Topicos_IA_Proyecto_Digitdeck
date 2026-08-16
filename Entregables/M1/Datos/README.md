# Datos · ESCI español (M1)

**Fuente:** https://github.com/amazon-science/esci-data (Amazon Science)
**Licencia:** Apache 2.0
**Subconjunto:** product_locale == "es"

Este directorio contiene una muestra balanceada de 200 pares por split (train, val,
test) como smoke-test y ejemplo de formato. Los archivos `.parquet` completos (~1,2 GB) no se
versionan; se descargan con la celda de la sección 2.1 del notebook `ENTREGABLE.ipynb`.

## Splits

| Split | Pares | Consultas | Origen |
|---|---|---|---|
| train | 235,354 | 10,203 | split `train` de ESCI menos el 10% de consultas apartadas |
| val | 26,195 | 1,133 | 10% de las consultas del split `train`, semilla 42 |
| test | 92,739 | 3,844 | split `test` de ESCI, sin tocar |

La partición de validación se hace **por `query_id`**, no por fila: ninguna consulta aparece en
train y validación a la vez.

## Formato de cada fila

| Campo | Descripción |
|---|---|
| `query_id`, `product_id` | Identificadores originales del dataset ESCI |
| `query` | Consulta, texto limpio (minúsculas, espacios colapsados) |
| `product_title` | Título del producto, texto limpio |
| `text_a` | `"query: ..."` — formato de entrada para el encoder E5 |
| `text_b` | `"passage: ..."` — formato de entrada para el encoder E5 |
| `label` | `1` = relevante (ESCI `E`) · `0` = no relevante (ESCI `S`, `C`, `I`) |

## Reproducibilidad

- Semilla fija: `SEMILLA = 42`
- Splits `train` / `test`: los predefinidos por ESCI, sin remezclar
- Split de validación: 10% de las consultas de train, muestreadas con la semilla
- Hashes MD5 de verificación: ver sección 2.6 del notebook
