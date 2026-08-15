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

- [x] Definir la lista de variantes a evaluar:

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

- [x] Para cada variante encoder, registrar: número de parámetros, tamaño en disco, licencia
      y fuente oficial (model card en Hugging Face).
      _(Celda 1.1 — tabla de variantes con params, familia y licencia)_

- [x] Reunir una muestra de 15–20 consultas reales o representativas del dominio (ecommerce en
      español: nombres de producto, marcas, tildes, abreviaturas, spanglish, errores comunes).
      _(Celda 1.3 — `MUESTRA_DOMINIO`)_
- [x] **Ejecutar el análisis de tokenizador** sobre esa muestra: cargar los tokenizadores de
      E5-small y E5-base y anotar casos donde fragmentan mal palabras del dominio.
      _(Celdas 1.3 — `comparar()` + tablas de costo total y términos críticos)_
- [x] Redactar la justificación citando esa evidencia.
      _(Celda 1.4 — justificación del modelo elegido con números reales)_
- [x] Formular explícitamente la pregunta que el argumento debe resistir y responderla con
      los datos del análisis.
      _(Celda 1.4 — sección "Preguntas que el argumento debe resistir")_

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

- [x] Descargar el dataset ESCI desde el repositorio oficial.
      _(Celda 2.1 — detecta y corrige punteros Git LFS automáticamente)_
- [x] Filtrar solo los ejemplos con `product_locale == 'es'`.
      _(Celda 2.2)_
- [x] Documentar la licencia Apache 2.0 en `Datos/README.md`.
      _(Celda 2.7 — genera el README automáticamente)_
- [x] Aplicar criterios de inclusión/exclusión: nulos, titles < 3 palabras, deduplicar.
      _(Celda 2.3)_
- [x] Limpieza reproducible: minúsculas + colapso de espacios (`limpiar_texto()`).
      _(Celda 2.3)_
- [x] Formatear para el encoder: `{"text_a": "query: ...", "text_b": "passage: ...", "label": 0|1}`.
      _(Celda 2.4–2.5 — con prefijos `query:` / `passage:` que requiere E5)_
- [x] Semilla fija documentada (`SEMILLA = 42`); splits predefinidos del dataset usados directamente.
      _(Celda 2.5–2.6)_
- [x] Verificación de reproducibilidad: hash MD5 de df_train y df_test.
      _(Celda 2.6)_
- [x] Limitaciones conocidas documentadas: origen Amazon US/ES, mapeo binario, desbalance, solo title.
      _(Celda 2.8 — 4 limitaciones explícitas)_
- [x] Muestra versionable guardada en `Datos/`.
      _(Celda 2.7 — `esci_es_muestra_train.csv` + `esci_es_muestra_test.csv`)_

---

## 3. Implementación del fine-tuning del encoder

**Referencia de clase:** [S04](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb).

- [x] Cargar `intfloat/multilingual-e5-small` y verificar embeddings con mean pooling.
      _(Celda 3.1)_
- [x] Medir **E5-small congelado** sobre el split de test → nDCG@10 como baseline semántico.
      _(Celda 3.3)_
- [x] Configurar cabeza de clasificación e hiperparámetros registrados en `hparams.json`.
      _(Celda 3.4 — `HIPERPARAMETROS` exportado a archivo)_
- [x] Tokenizar dataset y entrenar con `Trainer` de punta a punta.
      _(Celdas 3.5–3.6)_
- [x] Guardar modelo y tokenizador entrenados en `modelo_e5_small_finetuned/`.
      _(Celda 3.7)_
- [x] Verificar coherencia: par relevante → score alto; par irrelevante → score bajo.
      _(Celda 3.8)_
- [x] Verificación de reproducibilidad: subset rápido corrido dos veces, hashes comparados.
      _(Celda 3.9)_
- [x] Ablación E5-base implementada (opcional; activar `ENTRENAR_E5_BASE = True`).
      _(Celda 3.10)_
- [x] Subida a Hugging Face Hub implementada (opcional; activar `SUBIR_A_HUB = True`).
      _(Celda 3.11)_

---

## 4. Baselines y reporte de métricas

**Métrica primaria:** nDCG@10.
**Guardrails:** MRR · Recall@10 · memoria en VRAM · p95 de latencia.
**Métricas de diagnóstico** (secundarias): accuracy y F1 sobre la clasificación binaria.

> Métricas definidas en §3.2, antes de ver ningún resultado. No se ajustan a posteriori.

- [x] Implementar baseline BM25 sobre el mismo corpus.
      _(Celda 4.1 — `BM25Okapi` + `score_bm25_por_query()`)_
- [x] Recuperar métricas de E5-small congelado (ya calculadas en §3.3).
      _(Celda 4.2 — reutiliza `scores_congelado`)_
- [x] Evaluar E5-small ajustado sobre el split de test.
      _(Celda 4.3 — `scorear_lote_finetuned()`)_
- [x] Medir guardrails: VRAM pico y p95 de latencia de inferencia.
      _(Celda 4.4 — `medir_guardrails_encoder()`)_
- [x] Evaluación de E5-base ajustado implementada (opcional).
      _(Celda 4.5)_
- [x] Tabla comparativa de resultados con nDCG@10 / MRR / Recall@10 / Memoria.
      _(Celda 4.6)_
- [x] Identificación de queries donde el fine-tuning no mejora sobre los baselines.
      _(Celda 4.7 — `comparacion_q` con delta por query)_
- [x] Distribución del delta (histograma fine-tuned vs. mejor baseline).
      _(Celda 4.8 — gráfico matplotlib)_
- [ ] **Hipótesis y lectura honesta del delta** — completar con los resultados reales tras ejecutar.
      _(Celda 4.9 — placeholder pendiente de completar por el equipo)_

---

## Antes de entregar

- [ ] Releer el `README.md` de M1 y confirmar que cada criterio tiene evidencia verificable.
- [ ] Confirmar que el notebook está ejecutado con outputs visibles (celdas con resultado).
- [ ] Confirmar que el análisis de tokenizador sobre texto de dominio está en la sección 1.
- [ ] Revisar que los splits son reproducibles y el script está versionado.
- [ ] Confirmar que la tabla de métricas incluye nDCG@10 para todas las variantes.
- [ ] Completar celda 4.9 con la hipótesis y lectura honesta tras ver los resultados reales.
- [ ] Revisar que no se atribuyeron a la docente criterios, formatos o fechas no publicados.