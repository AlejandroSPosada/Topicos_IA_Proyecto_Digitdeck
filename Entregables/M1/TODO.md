# TODO · M1

Paso a paso para cumplir los cuatro criterios de aceptación de M1 (ver [`README.md`](README.md)).
Cada sección apunta a Nivel 4; los pasos están ordenados para que el trabajo de uno alimente al
siguiente.

**Punto de partida:** los notebooks de clase en `Clases/M1/` son la referencia base para cada
sección. Ejecutarlos antes de arrancar el trabajo propio.

---

## 0. Entorno y punto de partida

- [ ] Abrir [S04_Lab_Fine_tuning_SOLUCION.ipynb](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb)
      en Colab y verificar que corre de punta a punta con GPU T4.
- [x] Instalar las librerías del ecosistema HF que se usarán:
      `transformers`, `datasets`, `accelerate`, `evaluate`, `sentence-transformers`.
- [x] Registrar las versiones exactas del entorno con el que se entrenará (Python, torch,
      transformers) — esto es requisito de reproducibilidad del criterio 3.
      _(Python 3.12.13 · torch 2.11.0+cu128 · transformers 5.13.1)_
- [ ] Crear cuenta en [Hugging Face](https://huggingface.co) si no existe; generar un token de
      acceso para poder cargar y subir modelos.

---

## 1. Selección y justificación del modelo base

**Referencia de clase:** Lab A de [S02](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) y sección
"La decisión para M1" de [S03](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb).

El equipo evalúa **encoders multilingües** bajo el mismo split ESCI y presupuesto T4.
El candidato eficiente es `intfloat/multilingual-e5-small`; se compara contra BM25 y su propia
variante congelada antes de adoptar el fine-tuning como decisión.

- [ ] Definir la lista de variantes a evaluar:

  | Variante | Entrenamiento | Métrica primaria | Guardrails |
  |---|---|---|---|
  | BM25 | Ninguno | nDCG@10 | latencia, tamaño de índice |
  | E5-small congelado | Ninguno | nDCG@10 | memoria, p95 |
  | **E5-small ajustado** ← candidato | Pares/grados ESCI es | nDCG@10 | MRR, Recall@10, memoria, p95 |
  | E5-base ajustado *(opcional)* | Mismo split; mayor presupuesto | nDCG@10 | mejora por costo |

  > **Por qué esta lista:**
  > - BM25 es el techo léxico; sin él la tabla no tiene referencia.
  > - E5-small congelado separa el efecto del encoder pre-entrenado del efecto del fine-tuning.
  >   Si ya supera BM25 sin entrenamiento, el argumento de fine-tuning se fortalece.
  > - E5-small ajustado es el candidato real: multilingüe, visto en clase (S01), ~117 M params.
  > - E5-base ajustado es ablación de tamaño (~278 M params); incluir si el tiempo lo permite.
  > - BGE-M3 + reranker descartado de M1: arquitectura de dos etapas, p95 prohibitiva en T4.

- [ ] Para cada variante encoder, registrar: número de parámetros, tamaño en disco, licencia
      y fuente oficial (model card en Hugging Face).

- [ ] Reunir una muestra de 15–20 consultas reales o representativas del dominio (ecommerce en
      español: nombres de producto, marcas, tildes, abreviaturas, spanglish, errores comunes).
- [ ] **Ejecutar el análisis de tokenizador** sobre esa muestra: cargar los tokenizadores de
      E5-small y E5-base y anotar casos donde fragmentan mal palabras del dominio. Esta tabla
      es la evidencia del criterio 1.
- [ ] Redactar la justificación citando esa evidencia (no una afirmación general de "es bueno
      para español").
- [ ] Formular explícitamente la pregunta que el argumento debe resistir (ej. "¿por qué no usar
      E5-base directamente?") y responderla con los datos del análisis y el presupuesto T4.

---

## 2. Dataset: construcción y documentación

**Dataset:** [Amazon Shopping Queries Dataset (ESCI)](https://github.com/amazon-science/esci-data)

| Atributo | Detalle |
|---|---|
| **Fuente** | Amazon Science (público en GitHub) |
| **Licencia** | Apache 2.0 |
| **Idiomas** | Inglés, Español, Japonés |
| **Subconjunto ES** | ~8 049 queries únicas · ~218 774 pares query-producto |
| **Etiquetas** | `E` (Exact) · `S` (Substitute) · `C` (Complement) · `I` (Irrelevant) |
| **Campos clave** | `query`, `product_title`, `product_locale`, `esci_label`, `split` |
| **Splits** | Train y Test ya definidos en el dataset |

Mapeo de etiquetas ESCI → clasificación binaria para el encoder:

| ESCI | Significado | Etiqueta |
|---|---|---|
| `E` (Exact) | Producto que responde directamente la consulta | `relevante` (1) |
| `S` (Substitute) | Producto alternativo | `no relevante` (0) |
| `C` (Complement) | Producto complementario | `no relevante` (0) |
| `I` (Irrelevant) | Sin relación con la consulta | `no relevante` (0) |

> Mapeo binario: `E → 1`, `S+C+I → 0`. La pérdida de información en `S` y `C` queda como
> limitación documentada en la sección 2.8 del notebook.

- [x] Descargar el dataset ESCI desde el repositorio oficial:
      `shopping_queries_dataset_examples.parquet` +
      `shopping_queries_dataset_products.parquet`.
      _(Celda 2.1 — detecta y corrige punteros Git LFS automáticamente)_
- [x] Filtrar solo los ejemplos con `product_locale == 'es'` (subconjunto español).
      _(Celda 2.2)_
- [x] Documentar la licencia Apache 2.0 en el README del dataset dentro de `Datos/`.
      _(Celda 2.7 — genera `Datos/README.md` automáticamente)_
- [x] Aplicar los criterios de inclusión/exclusión:
      - Conservar solo `split == 'train'` para training y `split == 'test'` para evaluación.
      - Descartar filas con `product_title` nulo o con menos de 3 palabras.
      - Deduplicar por `(query_id, product_id)`.
      _(Celda 2.3)_
- [x] Aplicar limpieza reproducible: normalizar mayúsculas/minúsculas del query,
      eliminar whitespace extra.
      _(Función `limpiar_texto()` en celda 2.3)_
- [ ] Formatear cada ejemplo para el encoder (par de texto + etiqueta numérica):
      ```python
      {"text_a": query, "text_b": product_title, "label": 1 | 0}
      ```
      _(Actualizar celda 2.4 del notebook — reemplaza el formato causal LM anterior)_
- [x] Generar el subconjunto de entrenamiento con semilla fija (`SEMILLA = 42`).
      _(Celda 2.5)_
- [x] Verificar reproducibilidad: hash MD5 del DataFrame confirma que el pipeline es
      determinista.
      _(Celda 2.6)_
- [x] Documentar limitaciones conocidas: origen Amazon US/ES, mapeo binario pierde info de
      `S` y `C`, desbalance de clases, solo `product_title` (sin descripción).
      _(Celda 2.8 — 4 limitaciones explícitas)_
- [x] Guardar el script de construcción del dataset en `Datos/` junto a una muestra.
      _(Celda 2.7 — `esci_es_muestra_train.csv` + `esci_es_muestra_test.csv`)_

> **Pendiente:** actualizar celda 2.4 del ENTREGABLE.ipynb al formato de clasificación encoder.

---

## 3. Implementación del fine-tuning del encoder

**Referencia de clase:** [S04](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb).

- [ ] Cargar `intfloat/multilingual-e5-small` con `AutoModel` / `AutoTokenizer` y verificar
      que produce embeddings coherentes sobre texto de dominio.
- [ ] **Medir E5-small congelado** (sin ningún fine-tuning) sobre el split de test:
      score de similitud coseno entre query y product_title → nDCG@10. Este es el baseline
      semántico y el punto de comparación directo con el modelo ajustado.
- [ ] Configurar la cabeza de clasificación y los hiperparámetros de entrenamiento:
      - Cabeza lineal sobre pooling de tokens (o `[CLS]`)
      - `learning_rate` (justificar elección frente a alternativas)
      - `num_train_epochs`
      - `per_device_train_batch_size`
      - `fp16=True` (con GPU T4)
      - Semilla fija (`seed = 42`)
- [ ] Implementar el script de entrenamiento con `Trainer` o `SentenceTransformer` y correrlo
      de punta a punta sin errores.
- [ ] Registrar todos los hiperparámetros usados en un archivo de config junto al modelo
      entrenado — no solo mencionarlos en el reporte.
- [ ] Cargar el modelo resultante y verificar que produce scores coherentes:
      par relevante → score alto; par irrelevante → score bajo.
- [ ] Confirmar reproducibilidad: volver a correr con la misma configuración y verificar
      métricas consistentes.
- [ ] *(Opcional)* Repetir el fine-tuning con `intfloat/multilingual-e5-base` como ablación
      de tamaño; documentar la mejora de nDCG@10 por costo adicional de cómputo.
- [ ] *(Opcional recomendado)* Guardar el encoder fine-tuned en Hugging Face Hub.

---

## 4. Baselines y reporte de métricas

**Métrica primaria:** nDCG@10 (normalised Discounted Cumulative Gain, top-10 resultados).
**Guardrails:** MRR · Recall@10 · memoria en VRAM · p95 de latencia de inferencia.
**Métricas de diagnóstico** (secundarias): accuracy y F1 sobre la clasificación binaria.

> Las métricas se definen aquí, antes de ver los resultados. No se cambian ni ajustan
> a posteriori en función de qué sistema queda mejor.

- [ ] Implementar el **baseline BM25** sobre el mismo corpus: dado un par
      `(consulta, product_title)`, el score BM25 determina el ranking.
- [ ] Evaluar **E5-small congelado** sobre el split de test → nDCG@10, MRR, Recall@10.
- [ ] Evaluar **E5-small ajustado** (fine-tuned en sección 3) sobre el mismo split.
- [ ] *(Opcional)* Evaluar **E5-base ajustado** bajo las mismas condiciones.
- [ ] Construir la tabla comparativa de resultados:

  | Variante | nDCG@10 | MRR | Recall@10 | Memoria | Notas |
  |---|---|---|---|---|---|
  | BM25 | — | — | — | — | |
  | E5-small congelado | — | — | — | — | |
  | E5-small ajustado (M1) | — | — | — | — | |
  | E5-base ajustado *(opcional)* | — | — | — | — | |

- [ ] Identificar explícitamente los casos donde el modelo fine-tuned **no** mejora sobre los
      baselines y escribir una hipótesis de por qué (no ocultarlos ni minimizarlos).
- [ ] Redactar la lectura honesta del delta: qué mejoró en nDCG@10, qué no, y qué implica
      para la decisión de adoptar este encoder como base del sistema.

---

## Antes de entregar

- [ ] Releer el `README.md` de M1 y confirmar que cada criterio de la tabla tiene evidencia
      verificable en el repo (no solo texto afirmando que se cumplió).
- [ ] Confirmar que el notebook está ejecutado con outputs visibles (celdas con resultado).
- [ ] Confirmar que el análisis de tokenizador sobre texto de dominio está incluido como
      evidencia del criterio 1.
- [ ] Revisar que los splits del dataset son reproducibles y el script está versionado.
- [ ] Confirmar que la tabla de métricas incluye nDCG@10 para todas las variantes bajo las
      mismas condiciones de evaluación.
- [ ] Revisar que no se atribuyeron a la docente criterios, formatos o fechas que no han
      sido publicados oficialmente.