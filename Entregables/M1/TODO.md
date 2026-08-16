# TODO · M1

Paso a paso del trabajo de M1, organizado según los cuatro frentes de la **autoevaluación del
equipo** (ver [`README.md`](README.md)). Esos frentes y sus niveles los definió el equipo como
control de calidad interno; no son una rúbrica publicada por el curso. Los pasos están ordenados
para que el trabajo de uno alimente al siguiente.

**Punto de partida:** los notebooks de clase en `Clases/M1/` son la referencia base para cada
sección. Ejecutarlos antes de arrancar el trabajo propio.

**Estado global:** el notebook está ejecutado de punta a punta y las secciones de lectura de
resultados (§4.9 y §4.10) están escritas con los números reales de esa corrida.

---

## 0. Entorno y punto de partida

- [ ] Abrir [S04_Lab_Fine_tuning_SOLUCION.ipynb](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb)
      en Colab y verificar que corre de punta a punta con GPU T4.
- [x] Instalar las librerías del ecosistema HF que se usarán:
      `transformers`, `datasets`, `accelerate`, `evaluate`, `sentence-transformers`.
- [x] Registrar las versiones exactas del entorno con el que se entrenó — requisito de
      reproducibilidad del criterio 3.
      _(Corrida local: Python 3.11.9 · torch 2.11.0+cu128 · transformers 4.57.1 · datasets 5.0.1 ·
      GPU NVIDIA RTX 5060 Ti. El canal `cu128` o superior es obligatorio en GPU serie RTX 50.)_
- [x] Crear cuenta en [Weights & Biases](https://wandb.ai) y guardar la API key
      (https://wandb.ai/authorize). En local queda en `_netrc` tras `wandb login`; en Colab, como
      secreto con el nombre `WANDB_API_KEY`.
      _(Celda 0.1 — corrida registrada en https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg)_
- [ ] Crear cuenta en [Hugging Face](https://huggingface.co) y generar un token de acceso.
      _(Solo necesario si se decide publicar el modelo: hoy `SUBIR_A_HUB = False`.)_

---

## 1. Selección y justificación del modelo base

**Referencia de clase:** Lab A de [S02](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) y sección
"La decisión para M1" de [S03](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb).

El equipo evalúa **encoders multilingües** bajo el mismo split ESCI y el mismo presupuesto de GPU.
El candidato eficiente es `intfloat/multilingual-e5-small`; se compara contra BM25 y su propia
variante congelada antes de adoptar el fine-tuning como decisión.

- [x] Definir la lista de variantes a evaluar:

  | Variante | Entrenamiento | Métrica primaria | Guardrails |
  |---|---|---|---|
  | BM25 | Ninguno | nDCG@10 | latencia, tamaño de índice |
  | E5-small congelado | Ninguno | nDCG@10 | memoria, p95 |
  | **E5-small ajustado** ← candidato | Pares ESCI es | nDCG@10 | MRR, Recall@10, memoria, p95 |
  | E5-base ajustado *(opcional)* | Mismo split; mayor presupuesto | nDCG@10 | mejora por costo |

  > **Por qué esta lista:**
  > - BM25 es el techo léxico; sin él la tabla no tiene referencia.
  > - E5-small congelado separa el efecto del encoder pre-entrenado del efecto del fine-tuning.
  > - E5-small ajustado es el candidato real: multilingüe, visto en clase (S01), 118 M params.
  > - E5-base ajustado es ablación de tamaño (278 M params); incluir si el tiempo lo permite.
  > - BGE-M3 + reranker descartado de M1: arquitectura de dos etapas.

- [x] Para cada variante encoder, registrar: número de parámetros, tamaño en disco, licencia
      y fuente oficial (model card en Hugging Face).
      _(Celda 1.1)_
- [x] Reunir una muestra de 15–20 consultas representativas del dominio (ecommerce en español:
      nombres de producto, marcas, tildes, abreviaturas, spanglish, errores comunes).
      _(Celda 1.3 — `MUESTRA_DOMINIO`, 18 consultas)_
- [x] **Ejecutar el análisis de tokenizador** sobre esa muestra, contrastando contra **otras
      familias** (BETO monolingüe español y DistilBERT multilingüe), no solo entre E5-small y
      E5-base, que comparten tokenizador y por tanto no aportan contraste.
      _(Celda 1.4 — E5 gasta 147 tokens en la muestra frente a 164 de BETO y 171 de DistilBERT)_
- [x] Redactar la justificación citando esa evidencia.
      _(Celda 1.5)_
- [x] Formular explícitamente la pregunta que el argumento debe resistir y responderla con
      los datos del análisis.
      _(Celda 1.5 — "¿por qué no usar E5-base directamente?")_

---

## 2. Dataset: construcción y documentación

**Dataset:** [Amazon Shopping Queries Dataset (ESCI)](https://github.com/amazon-science/esci-data)

| Atributo | Detalle |
|---|---|
| **Fuente** | Amazon Science (público en GitHub) |
| **Licencia** | Apache 2.0 |
| **Idiomas** | Inglés, Español, Japonés |
| **Subconjunto ES** | 15.180 consultas únicas · 356.410 pares; **354.288 pares tras la limpieza** |
| **Splits** | train 235.354 · validación 26.195 · test 92.739 |
| **Etiquetas** | `E` (Exact) · `S` (Substitute) · `C` (Complement) · `I` (Irrelevant) |
| **Campos clave** | `query`, `product_title`, `product_locale`, `esci_label`, `split` |

Mapeo de etiquetas ESCI a clasificación binaria para el encoder:

| ESCI | Significado | Etiqueta |
|---|---|---|
| `E` (Exact) | Producto que responde directamente la consulta | `relevante` (1) |
| `S` (Substitute) | Producto alternativo | `no relevante` (0) |
| `C` (Complement) | Producto complementario | `no relevante` (0) |
| `I` (Irrelevant) | Sin relación con la consulta | `no relevante` (0) |

- [x] Descargar el dataset ESCI desde el repositorio oficial.
      _(Celda 2.1 — detecta y corrige punteros Git LFS automáticamente)_
- [x] Filtrar solo los ejemplos con `product_locale == 'es'`.
      _(Celda 2.2 — 356.410 pares de 2.621.288 totales)_
- [x] Documentar la licencia Apache 2.0 en `Datos/README.md`.
      _(Celda 2.7 — generado automáticamente)_
- [x] Aplicar criterios de inclusión/exclusión: nulos, títulos de menos de 3 palabras, deduplicar.
      _(Celda 2.3 — se descartan 2.122 pares)_
- [x] Limpieza reproducible: minúsculas y colapso de espacios (`limpiar_texto()`).
      _(Celda 2.3)_
- [x] Formatear para el encoder: `{"text_a": "query: ...", "text_b": "passage: ...", "label": 0|1}`.
      _(Celda 2.4)_
- [x] Semilla fija documentada (`SEMILLA = 42`); splits train/test predefinidos del dataset.
      _(Celda 2.5)_
- [x] Split de **validación separado del train por `query_id`** (10% de las consultas), no por
      par, verificado con `assert`. El test no participa en ninguna decisión de entrenamiento.
      _(Celda 2.5 — 0 consultas compartidas entre splits)_
- [x] Verificación de reproducibilidad: hash MD5 de train, validación y test.
      _(Celda 2.6 — hashes en el `README.md`)_
- [x] Limitaciones conocidas documentadas: origen Amazon US/ES, mapeo binario, desbalance hacia
      la clase "relevante", solo se usa el título.
      _(Celda 2.8 — 4 limitaciones explícitas)_
- [x] Muestra versionable guardada en `Datos/` para los tres splits.
      _(Celda 2.7 — `esci_es_muestra_{train,val,test}.csv`)_

---

## 3. Implementación del fine-tuning del encoder

**Referencia de clase:** [S04](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb).

- [x] Cargar `intfloat/multilingual-e5-small` y verificar embeddings con mean pooling.
      _(Celda 3.1)_
- [x] Verificar el encoder base sobre 200 consultas antes de entrenar, no sobre un par suelto.
      _(Celda 3.1 — los relevantes puntúan más alto en 135 de 163 consultas, 82,8%)_
- [x] Medir **E5-small congelado** sobre el split de test y obtener su nDCG@10 como baseline
      semántico.
      _(Celda 3.3 — nDCG@10 = 0,7885)_
- [x] Configurar cabeza de clasificación e hiperparámetros registrados en archivo.
      _(Celda 3.4)_
- [x] Pesos de clase por frecuencia inversa en la pérdida, para compensar el desbalance.
      _(Celda 3.5 — no relevante 1,186 · relevante 0,864)_
- [x] Tokenizar dataset y entrenar con `Trainer`, con `report_to="wandb"`, selección de
      checkpoint por `eval_loss` en validación y parada temprana.
      _(Celdas 3.5–3.6 — 7.356 pasos, 6 min en RTX 5060 Ti)_
- [x] Graficar la curva de pérdida de entrenamiento y validación, y capturar la URL de W&B.
      _(Celda 3.6b — la parada temprana cortó en la época 2 y se cargó el checkpoint de la 1)_
- [x] Guardar modelo y tokenizador entrenados en `modelo_e5_small_finetuned/`.
      _(Celda 3.7)_
- [x] Verificar coherencia: un par relevante da score alto y uno irrelevante da score bajo.
      _(Celda 3.8 — 0,7636 contra 0,6680)_
- [x] Verificación de determinismo: subset pequeño corrido dos veces, pérdidas comparadas.
      _(Celda 3.9 — diferencia de 4,17e-07)_
- [x] Ablación E5-base implementada.
      _(Celda 3.10 — **no ejecutada**: requiere `ENTRENAR_E5_BASE = True`)_
- [x] Subida a Hugging Face Hub implementada.
      _(Celda 3.11 — **no ejecutada**: requiere `SUBIR_A_HUB = True` y token de HF)_

---

## 4. Baselines y reporte de métricas

**Métrica primaria:** nDCG@10, con el IDCG calculado sobre el ranking ideal completo (no sobre
la lista truncada a k, que infla la métrica).
**Guardrails:** MRR · Recall@10 · memoria · p95 de latencia.
**Métricas de diagnóstico** (secundarias): accuracy y F1 sobre la clasificación binaria.

> Métricas definidas en §3.2, antes de ver ningún resultado. No se ajustan a posteriori.

- [x] Implementar baseline BM25 sobre el mismo conjunto de candidatos.
      _(Celda 4.1 — nDCG@10 = 0,7508 · p95 real de 0,47 ms por consulta)_
- [x] Recuperar métricas de E5-small congelado.
      _(Celda 4.2)_
- [x] Evaluar E5-small ajustado sobre el split de test, usando los mismos prefijos
      `query: ` / `passage: ` con los que se entrenó.
      _(Celda 4.3 — nDCG@10 = 0,8369, con `assert` de control de formato)_
- [x] Medir guardrails por variante: tamaño del modelo, memoria incremental de inferencia y
      p95 de latencia.
      _(Celda 4.4 — 448,8 MB de modelo · 67,1 MB de inferencia · p95 33,43 ms por lote de 64)_
- [x] Accuracy y F1 sobre test como métricas de diagnóstico secundarias.
      _(Celda 4.5b — accuracy 0,7579 · F1 0,7782)_
- [x] Tabla comparativa de resultados.
      _(Celda 4.6 — `Resultados/tabla_metricas_m1.csv`)_
- [x] Identificación de consultas donde el fine-tuning no mejora sobre los baselines.
      _(Celda 4.7 — 1.119 de 3.844, 29,1%)_
- [x] Señales objetivas de esas consultas y ejemplos concretos citables.
      _(Celda 4.7b — `Resultados/senales_por_query.csv`)_
- [x] Distribución del delta.
      _(Celda 4.8 — `Resultados/distribucion_delta_ndcg.png`)_
- [x] Resumen numérico que sustenta la lectura del delta: se calcula, no se escribe a mano.
      _(Celda 4.8b — `Resultados/metricas_m1.json`)_
- [x] **Hipótesis sobre las consultas sin mejora.**
      _(Celda 4.9 — las señales no separan mejora de empeora; lo que explican es la varianza)_
- [x] **Lectura honesta del delta.**
      _(Celda 4.10 — efecto neto del fine-tuning: +0,0485 de nDCG@10 sobre el congelado)_
- [ ] Ejecutar la ablación E5-base para completar la comparación de cuatro sistemas.
      _(Opcional; queda para M2 si no alcanza el tiempo.)_

---

## 5. Artefactos versionados

- [x] Celda que empaqueta `Datos/` y `Resultados/` en `entregable_m1_artefactos.zip`.
      _(Celda 5)_
- [x] Descargar el zip.
- [ ] Descomprimirlo dentro de `Entregables/M1/` del repositorio.
- [ ] Hacer commit de `Datos/` y `Resultados/` junto al notebook ejecutado.

---

## Plantilla de definición del proyecto

- [x] Diligenciar los campos 1 a 4 (dominio, usuario + decisión, tarea del modelo, dataset +
      licencia).
      _([`PLANTILLA_DEFINICION.md`](PLANTILLA_DEFINICION.md))_
- [ ] Campos 5 a 8 (métrica de éxito, componente visual de M4, riesgos éticos, compromisos del
      equipo): quedan con su encabezado para completarse en los módulos siguientes.

---

## Antes de entregar

- [x] Correr el notebook de punta a punta en una sola sesión, con los `execution_count` en orden
      y todas las salidas de la misma corrida.
- [x] Confirmar que el notebook está ejecutado con outputs visibles.
- [x] Confirmar que el análisis de tokenizador sobre texto de dominio está en la sección 1.
- [x] Revisar que los splits son reproducibles y sus hashes están documentados.
- [x] Confirmar que la tabla de métricas incluye nDCG@10 para todas las variantes evaluadas.
- [x] Completar §4.9 y §4.10 con la lectura real de los resultados.
- [x] Pegar el enlace de la corrida de W&B en el `README.md` (sección Observabilidad).
- [x] Actualizar las cifras del dataset en `README.md` y en este archivo.
- [ ] Registrar en el encabezado del notebook y del `README.md` la fecha y el canal de la
      autorización de la docente para el cambio de alcance (encoder con dataset público en vez
      de 20 ejemplos con LoRA). Hoy están como `[COMPLETAR]`.
- [ ] Corregir la celda de instalación: el output guardado muestra
      `ERROR: Could not find a version that satisfies the requirement cuda`, porque quedó el
      paquete inexistente `cuda` en la lista de `pip install`. Es cosmético y no afectó la
      corrida, pero conviene quitarlo.
- [ ] Poner `SUBIR_A_HUB = True` (§3.11) si el equipo quiere que el modelo quede verificable
      por la docente. Hoy el modelo solo existe en la máquina local.
- [x] Revisar que no se atribuyeron a la docente criterios, formatos o fechas no publicados.
