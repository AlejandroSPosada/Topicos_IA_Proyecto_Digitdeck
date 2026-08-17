# M1 · Fine-tuning de encoder para ranking de relevancia (S02–S04)

## Sobre el proyecto

**Digitdeck** es un copiloto de calidad de búsqueda para ecommerce en español. Su objetivo es
detectar consultas con resultados deficientes, **ordenar productos por relevancia** y preparar
recomendaciones trazables para la persona responsable de ecommerce. El proyecto se desarrolla
como entregable de **Tópicos Especiales y Aplicaciones en IA** (Universidad EAFIT, SI4006), y
cada módulo del curso (`M1` a `M5`) corresponde a una capa del sistema.

El motor del sistema es la capacidad del modelo de **asignar un score de relevancia a un par
(consulta, producto)**. M1 es donde ese motor se construye y valida por primera vez.

## Decisión técnica de M1

El equipo fine-tunea `intfloat/multilingual-e5-small` sobre pares ESCI en español y lo compara
contra otras variantes bajo el mismo split y el mismo presupuesto de GPU:

| Variante | Entrenamiento | Métrica primaria | Guardrails | Estado |
|---|---|---|---|---|
| BM25 | Ninguno | nDCG@10 | latencia, tamaño de índice | Evaluado |
| E5-small congelado | Ninguno | nDCG@10 | memoria, p95 | Evaluado |
| **E5-small ajustado** ← candidato | Pares ESCI es | nDCG@10 | MRR, Recall@10, memoria, p95 | Evaluado |
| E5-base ajustado *(opcional)* | Mismo split; mayor presupuesto | nDCG@10 | mejora por costo | Implementado, no ejecutado |

> **BGE-M3 + reranker** queda descartado de M1: su arquitectura de dos etapas no permite
> comparación bajo las mismas condiciones. Candidato natural para M2/M3.

| Componente | Elección |
|---|---|
| **Modelo base** | `intfloat/multilingual-e5-small` (118 M params, encoder, multilingüe, MIT) |
| **Técnica** | Fine-tuning con cabeza de clasificación binaria sobre el encoder |
| **Tarea** | Dado un par `(consulta, product_title)`, predecir `relevante` / `no relevante` |
| **Dataset** | [Amazon ESCI](https://github.com/amazon-science/esci-data) · Apache 2.0 · subconjunto en español |
| **Métrica primaria** | nDCG@10 (IDCG sobre el ranking ideal completo, no sobre la lista truncada) |
| **Guardrails** | MRR · Recall@10 · memoria · p95 latencia |

> **E5-small congelado** actúa como baseline semántico sin entrenamiento — separa el efecto del
> encoder pre-entrenado del efecto del fine-tuning.

## Resultados

Split de test completo: **92.739 pares · 3.844 consultas**. Ninguna consulta de test participó
en el entrenamiento ni en la selección del checkpoint.

| Sistema | nDCG@10 | MRR | Recall@10 | Modelo (MB) | Memoria inferencia (MB) | p95 latencia |
|---|---|---|---|---|---|---|
| BM25 | 0,7508 | 0,8258 | 0,5877 | índice 10,5 | — | 0,47 ms por consulta |
| E5-small congelado | 0,7885 | 0,8685 | 0,6121 | 448,8 | 67,1 | 42,68 ms por lote de 64 pares |
| **E5-small ajustado (M1)** | **0,8369** | **0,9091** | **0,6445** | 448,8 | 67,1 | 33,43 ms por lote de 64 pares |

**Lectura corta** (la extensa está en §4.9 y §4.10 del notebook):

- El encoder **congelado ya supera a BM25** (`+0,0376`, 5,0% relativo) sin haber visto un solo
  ejemplo de ESCI. El pre-entrenamiento multilingüe aporta señal semántica por sí solo.
- El **efecto neto del fine-tuning** es `+0,0485` sobre el congelado (6,1% relativo). Contra
  BM25 la diferencia es `+0,0861`, pero esa cifra mezcla pre-entrenamiento y fine-tuning.
- Consulta por consulta, el ajustado le gana a BM25 en 50,9% de los casos y pierde en 18,9%;
  contra el congelado, gana en 44,7% y pierde en 21,8%.
- La **parada temprana cortó el entrenamiento en la época 2** y se conservó el checkpoint de la
  época 1: la pérdida de validación subió de `0,5075` a `0,5127` mientras la de entrenamiento
  seguía bajando. Sobreajuste incipiente, detectado y contenido.
- Métricas de diagnóstico sobre test (secundarias): accuracy `0,7579`, F1 `0,7782`.

## Qué se espera en M1

M1 cubre la primera capa del sistema: elegir un encoder base, construir el dataset de
entrenamiento y evaluación del dominio, hacer fine-tuning eficiente, y demostrar con métricas
de ranking que el modelo resultante mejora (o no) sobre los baselines.

Concretamente, el equipo debe producir cuatro cosas verificables:

1. **Un modelo base elegido y justificado con evidencia** — argumentar la decisión con datos
   sobre tamaño, licencia, cobertura de idioma y comportamiento del tokenizador sobre texto
   de ecommerce en español, contrastado contra otras familias de tokenizador.
2. **Un dataset documentado y reproducible** — origen, licencia, tamaño, criterios de inclusión,
   limpieza aplicada, limitaciones conocidas, y splits que cualquiera pueda regenerar.
3. **Un fine-tuning de encoder que efectivamente corre** — entrenamiento reproducible, con
   hiperparámetros registrados, cuyo modelo resultante carga y produce scores coherentes.
4. **Baselines y métricas comparables** — comparar el encoder fine-tuned contra BM25 y E5-small
   congelado sobre el mismo split de test con nDCG@10 como métrica primaria, con una lectura
   honesta de dónde sí y dónde no hay mejora.

> **Estado actual:** los cuatro frentes están ejecutados y documentados en `ENTREGABLE.ipynb`,
> con la lectura de resultados escrita en §4.9 y §4.10. La única pieza planeada que **no** se
> ejecutó es la ablación con `E5-base`: está implementada en §3.10 y §4.5 y solo requiere poner
> `ENTRENAR_E5_BASE = True`, pero se dejó fuera de esta corrida. Por eso la comparación es
> entre tres sistemas y no cuatro, y así se reporta.

## Dataset

| Atributo | Valor |
|---|---|
| Fuente | [amazon-science/esci-data](https://github.com/amazon-science/esci-data) |
| Licencia | Apache 2.0 |
| Subconjunto | `product_locale == "es"` |
| Antes de limpieza | 356.410 pares · 15.180 consultas únicas |
| Después de limpieza | **354.288 pares** (se descartan 2.122 títulos de menos de 3 palabras) |
| Balance | 56,7% relevante / 43,3% no relevante |

| Split | Pares | Consultas | Origen |
|---|---|---|---|
| train | 235.354 | 10.203 | split `train` de ESCI menos el 10% de consultas de validación |
| validación | 26.195 | 1.133 | 10% de las **consultas** de train, semilla 42 |
| test | 92.739 | 3.844 | split `test` de ESCI, sin tocar |

La validación se separa **por `query_id`**, no por fila: cero consultas compartidas entre train
y validación, verificado con `assert` en §2.5. El test no participa en ninguna decisión de
entrenamiento.

Hashes MD5 de verificación (§2.6):

| Split | Hash |
|---|---|
| train | `e5f8baa5f301d5c5cbc2bdb79c7dfff5` |
| validación | `ee5ffaeedf8796119758c32670304dc1` |
| test | `4d31950e81340999c4cbda611b4256c9` |

## Observabilidad

El entrenamiento se registra en **Weights & Biases** (sección 0.1 del notebook, con
`report_to="wandb"` en la configuración del `Trainer`).

| Artefacto | Dónde |
|---|---|
| **Corrida de W&B** | https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg |
| Curva de pérdida | §3.6b del notebook · `Resultados/curva_perdida.png` |
| Hiperparámetros | `modelo_e5_small_finetuned/hiperparametros.json` · `Resultados/resumen_entrega.json` |
| Hashes de los splits | `Resultados/resumen_entrega.json` |
| Métricas completas | `Resultados/metricas_m1.json` · `Resultados/tabla_metricas_m1.csv` |
| Delta por consulta | `Resultados/comparacion_por_query.csv` · `Resultados/senales_por_query.csv` |
| Muestras del dataset | `Datos/esci_es_muestra_{train,val,test}.csv` |

## Entorno de la corrida

La corrida que produjo estos resultados se ejecutó **en máquina local**, no en Colab:

| Componente | Valor |
|---|---|
| GPU | NVIDIA GeForce RTX 5060 Ti (16 GB, arquitectura Blackwell) |
| Python | 3.11.9 |
| torch | 2.11.0+cu128 (el canal `cu128` o superior es obligatorio para GPU serie RTX 50) |
| transformers | 4.57.1 |
| datasets · accelerate · evaluate | 5.0.1 · 1.14.0 · 0.4.6 |
| sentence-transformers · rank_bm25 · wandb | 5.1.2 · 0.2.2 · 0.28.2 |
| Tiempo de entrenamiento | 6 min 5 s (7.356 pasos, 2 épocas de 3 posibles) |

El notebook también corre en **Google Colab con GPU T4** sin cambios, salvo la celda de
instalación y la de descarga del dataset, que en Windows usan `urllib` en lugar de `wget`.

## Material de referencia (Clases/M1)

| Sesión | Notebook | Qué cubre |
|---|---|---|
| S01 | [S01_Demo_Capacidades.ipynb](../../Clases/M1/S01_Demo_Capacidades.ipynb) | Demo LLM + RAG + multimodal; introducción a `multilingual-e5-small` |
| S02 | [S02_Lab_Abrir_la_caja.ipynb](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) | Tokenizadores (BPE, WordPiece, SentencePiece), self-attention, positional encoding |
| S03 | [S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb) | Bloque transformer, conexión residual, tres familias (encoder/decoder/enc-dec) |
| S04 | [S04_Lab_Fine_tuning_SOLUCION.ipynb](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb) | Fine-tuning de encoders; baseline antes/después |

## Rubrica


| Criterios | Nivel 4 <br> 5 puntos | Nivel 3 <br> 3.5 puntos | Nivel 2 <br> 2 puntos | Nivel 1 <br> 0 puntos | Puntuación del criterio |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Selección y justificación del modelo base** | Escoge un modelo base y argumenta la decisión con evidencia: tamaño, licencia, idioma y comportamiento del tokenizador sobre el dominio | Escoge con criterio pero la justificación es parcial o no está respaldada con datos | Escoge sin argumentar, o el argumento no resiste una pregunta | No hay modelo base identificable | /5 |
| **Dataset: construcción y documentación** | Dataset documentado: origen, licencia, tamaño, criterios de inclusión, limpieza y limitaciones conocidas. Splits reproducibles | Documentado en lo esencial; faltan licencia, limitaciones o criterios de split | Dataset sin documentar, o splits no reproducibles | No hay dataset o no es del dominio declarado | /5 |
| **Implementación del fine-tuning con LoRA** | Entrenamiento correcto y reproducible; hiperparámetros registrados; el modelo resultante carga y produce salidas coherentes | Entrena y funciona, pero con configuración no registrada o parcialmente reproducible | Corre con errores, o no se puede reproducir | No entrenó | /5 |
| **Baseline y reporte de métricas** | Hay baseline explícito, métricas comparables y una lectura honesta del delta, incluidos los casos donde no mejoró | Hay baseline y métricas, pero la comparación es superficial o solo reporta lo favorable | Reporta métricas sin baseline, o el baseline no es comparable | Sin métricas | /5 |
| **Total** | | | | | **/20** |


---

Ver [`TODO.md`](TODO.md) para el paso a paso, y [`PLANTILLA_DEFINICION.md`](PLANTILLA_DEFINICION.md)
para la definición del proyecto integrador.
