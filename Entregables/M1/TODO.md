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
      `transformers`, `peft`, `datasets`, `accelerate`, `evaluate`, `bitsandbytes`.
- [x] Registrar las versiones exactas del entorno con el que se entrenará (Python, torch,
      transformers, peft) — esto es requisito de reproducibilidad del criterio 3.
      _(Python 3.12.13 · torch 2.11.0+cu128 · transformers 5.13.1 · peft 0.19.1)_
- [ ] Crear cuenta en [Hugging Face](https://huggingface.co) si no existe; generar un token de
      acceso para poder cargar y subir modelos.

---

## 1. Selección y justificación del modelo base

**Referencia de clase:** Lab A de [S02](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) y sección
"La decisión para M1" de [S03](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb).

- [x] Definir la lista de candidatos a evaluar. Se proponen cinco opciones que cubren distintas
      familias, tamaños y estrategias de cobertura del español, todas dentro del presupuesto de
      la GPU T4 de Colab gratuito:

  | Modelo | Params | Familia | Español | Licencia |
  |---|---|---|---|---|
  | `Qwen/Qwen2.5-0.5B` | 0.5 B | Qwen2.5 (decoder) | Multilingüe | Apache 2.0 |
  | `meta-llama/Llama-3.2-1B` | 1 B | LLaMA 3.2 (decoder) | Multilingüe | Llama 3.2 Community |
  | `HuggingFaceTB/SmolLM2-1.7B` | 1.7 B | SmolLM2 (decoder) | Multilingüe | Apache 2.0 |
  | `BSC-LT/salamandra-2b` | 2 B | Decoder especializado en español | **Solo español/catalán** | Apache 2.0 |
  | `microsoft/Phi-3.5-mini-instruct` | 3.8 B | Phi-3.5 (decoder) | Multilingüe | MIT |

  > **Por qué estos cinco:** van de 0.5 B a 3.8 B (presupuesto de cómputo real), cubren tres
  > familias distintas (Qwen, LLaMA, Phi), e incluyen `Salamandra`, el único entrenado
  > *exclusivamente* en español — un punto de comparación directo para el dominio del proyecto.
  > La decisión final se toma *después* del análisis de tokenizador, no antes.

- [x] Para cada candidato, registrar: número de parámetros, tamaño en disco, licencia y
      fuente oficial (model card en Hugging Face).

- [x] Reunir una muestra de 15–20 consultas reales o representativas del dominio (ecommerce en
      español: nombres de producto, marcas, tildes, abreviaturas, spanglish, errores comunes).
- [x] **Ejecutar el análisis de tokenizador del Lab A de S02** sobre esa muestra:
      cargar los tokenizadores de los candidatos y anotar casos donde fragmentan mal palabras
      del dominio (nombres de marca, SKUs, spanglish). Esta tabla es la evidencia del criterio 1.
      _(4/5 cargados — Llama requiere token HF; resultados: Salamandra 126 tok · Qwen 149 tok · Phi 161 tok · SmolLM2 170 tok)_
- [x] Redactar la justificación citando esa evidencia (no una afirmación general de "es bueno
      para español").
- [x] Formular explícitamente la pregunta que el argumento debe resistir (ej. "¿qué pasa si la
      consulta tiene errores ortográficos?") y responderla con los datos del análisis.

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
| **Campos clave** | `query`, `product_title`, `product_description`, `product_brand`, `esci_label`, `split` |
| **Splits** | Train y Test ya definidos en el dataset |

Mapeo de etiquetas ESCI → formato para fine-tuning causal:

| ESCI | Significado | Etiqueta en el modelo |
|---|---|---|
| `E` (Exact) | Producto que responde directamente la consulta | `relevante` |
| `S` (Substitute) | Producto alternativo, posiblemente útil | `no relevante` |
| `C` (Complement) | Producto complementario | `no relevante` |
| `I` (Irrelevant) | Sin relación con la consulta | `no relevante` |

> Para un primer modelo, se usa mapeo binario: `E` → `relevante`, `S+C+I` → `no relevante`.
> La versión de 4 clases queda documentada como limitación conocida del dataset simplificado.

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
- [x] Aplicar limpieza reproducible: normalizar mayusculas/minusculas del query,
      eliminar whitespace extra. Dejarla en un script versionado (no manual).
      _(Función `limpiar_texto()` en celda 2.3)_
- [x] Formatear cada ejemplo como texto plano para fine-tuning causal:
      ```
      Consulta: {query}
      Producto: {product_title}
      Relevancia: {relevante | no relevante}
      ```
      _(Celda 2.4 — `PLANTILLA` con `df.apply(formatear)`)_
- [x] Generar el subconjunto de entrenamiento con semilla fija (el split ya viene definido
      en el dataset; documentar la semilla usada para cualquier submuestreo adicional).
      _(Celda 2.5 — `SEMILLA = 42`; submuestreo opcional comentado)_
- [x] Verificar reproducibilidad: correr el script de preprocesamiento dos veces y confirmar
      que el output es idéntico.
      _(Celda 2.6 — hash MD5 de df_train y df_test)_
- [x] Documentar limitaciones conocidas: el dataset es de Amazon US/ES (puede no cubrir
      catálogo Digitdeck exacto), el mapeo ESCI binario pierde información de `S` y `C`,
      posible sesgo hacia categorías con mayor número de anotaciones.
      _(Celda 2.8 — 4 limitaciones explícitas)_
- [x] Guardar el script de construcción del dataset en `Datos/` junto a una muestra
      (los archivos `.parquet` completos no se versionan por tamaño).
      _(Celda 2.7 — `esci_es_muestra_train.csv` + `esci_es_muestra_test.csv` + `Datos/README.md`)_

---

## 3. Implementación del fine-tuning con LoRA

**Referencia de clase:** Lab B de [S04](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb).

- [ ] Cargar el modelo base elegido (`Qwen/Qwen2.5-0.5B` u otro) con `AutoModelForCausalLM`.
- [ ] **Medir el baseline ANTES del fine-tuning** (Lab A de S04): hacerle preguntas de dominio
      al modelo y anotar sus respuestas — este es el punto de comparación del criterio 4.
- [ ] Configurar LoRA con `peft.LoraConfig` usando como punto de partida los hiperparámetros
      de clase y justificando cualquier cambio:
      - `r=8` (rank)
      - `lora_alpha=16`
      - `target_modules=["q_proj", "v_proj"]`
      - `lora_dropout=0.05`
      - `task_type="CAUSAL_LM"`
- [ ] Definir los hiperparámetros de entrenamiento con `TrainingArguments`:
      - `learning_rate=2e-4`
      - `num_train_epochs` (ajustar según tamaño del dataset)
      - `per_device_train_batch_size=2`
      - `fp16=True` (con GPU T4)
      - Semilla fija (`seed`)
- [ ] Implementar el script de entrenamiento y correrlo de punta a punta sin errores.
- [ ] Registrar todos los hiperparámetros usados en un archivo de config junto al modelo
      entrenado — no solo mencionarlos en el reporte.
- [ ] Cargar el modelo resultante en un script independiente y verificar que produce salidas
      coherentes (ej. dado un par relevante → clasifica como `relevante`; dado un par
      irrelevante → clasifica como `no relevante`).
- [ ] Confirmar reproducibilidad: volver a correr con la misma configuración y verificar
      comportamiento consistente.
- [ ] (Opcional recomendado) Guardar el adaptador LoRA en Hugging Face Hub:
      `model.push_to_hub("su-usuario/digitdeck-lora-m1")`.

---

## 4. Baseline y reporte de métricas

- [ ] Definir la(s) métrica(s) de evaluación **antes** de ver los resultados (no después):
      ej. accuracy sobre el split de test, o F1 para la etiqueta `relevante`.
- [ ] Implementar el baseline BM25 léxico sobre el mismo corpus: dado un par
      `(consulta, producto)`, el score BM25 determina si lo clasifica como relevante.
- [ ] Evaluar el modelo **antes** del fine-tuning (baseline B) sobre el split de test.
- [ ] Evaluar el modelo **después** del fine-tuning sobre el mismo split.
- [ ] Evaluar BM25 sobre el mismo split.
- [ ] Construir la tabla comparativa de resultados:

  | Sistema | Accuracy | F1 (relevante) | Notas |
  |---|---|---|---|
  | BM25 (baseline léxico) | — | — | |
  | `Qwen2.5-0.5B` sin fine-tuning | — | — | |
  | `Qwen2.5-0.5B` con LoRA (M1) | — | — | |

- [ ] Identificar explícitamente los casos donde el modelo fine-tuned **no** mejora sobre el
      baseline y escribir una hipótesis de por qué (no ocultarlos ni minimizarlos).
- [ ] Redactar la lectura honesta del delta: qué mejoró, qué no, y qué implica para la decisión
      de adoptar este modelo como base del sistema.

---

## Antes de entregar

- [ ] Releer el `README.md` de M1 y confirmar que cada criterio de la tabla tiene evidencia
      verificable en el repo (no solo texto afirmando que se cumplió).
- [ ] Confirmar que el notebook de entrenamiento está ejecutado con outputs visibles
      (celdas con resultado, no vacías).
- [ ] Confirmar que el análisis de tokenizador del Lab A de S02 sobre texto de dominio
      está incluido como evidencia del criterio 1.
- [ ] Revisar que los splits del dataset son reproducibles y el script está versionado.
- [ ] Confirmar que la tabla de métricas incluye los tres sistemas (BM25, modelo pre y
      post fine-tuning) bajo las mismas condiciones.
- [ ] Revisar que no se atribuyeron a la docente criterios, formatos o fechas que no han
      sido publicados oficialmente.