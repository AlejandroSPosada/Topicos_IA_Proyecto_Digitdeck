# M3 - RAG con herramientas, evaluado con el harness de M2 y con RAGAS (S07, S08, S10)

## Sobre el proyecto

**Digitdeck** es un copiloto de calidad de búsqueda para ecommerce en español. En **M1** el equipo construyó el motor: un encoder `intfloat/multilingual-e5-small` ajustado que puntúa pares (consulta, título de producto), con `nDCG@10 = 0,8369` contra `0,7508` de BM25. En **M2** construyó la vara: un harness de tres dimensiones sobre un eval set propio de 13 casos.

**M3 le da al sistema conocimiento consultable.** Un asistente que responde preguntas de un **comprador** sobre el catálogo: busca primero en las fichas de producto y responde después, citando la ficha de donde sacó cada producto.

## En una frase, qué hace el sistema

> Le preguntas al asistente si la tienda tiene un producto, o qué hay parecido a uno; el asistente decide cuál de las dos preguntas es, busca en el catálogo con la herramienta que corresponde y responde con los productos que encontró, o te dice que no lo tiene.

## Quién lo usa y qué decide

La plantilla de definición del proyecto **no se modifica**: en M1 el usuario definido es el líder de ecommerce, y ese sigue siendo el usuario del motor de ranking. El asistente de M3 es la cara del sistema hacia **quien compra**.

| Intención | Ejemplo | Herramienta | Etiqueta ESCI |
|---|---|---|---|
| Existencia | "¿tienen el Xiaomi Redmi Note 7 negro?" | `verificar_existencia` | `E` (Exact) |
| Similar | "¿qué hay parecido al Xiaomi Redmi Note 7 negro?" | `buscar_similares` | `S` (Substitute) |
| Ninguna | "¿cuál es el horario de atención?" | ninguna: el sistema se abstiene | no aplica |

## Qué pide la entrega M3

1. El sistema RAG completo, con **al menos dos técnicas avanzadas** y **al menos una herramienta** (tool).
2. El reporte de evaluación: **scorecard propio** más las **métricas de RAGAS**.
3. Una **lectura honesta**: qué técnica movió qué, qué costó en latencia y qué falla queda pendiente.

### Rúbrica de evaluación

| Criterios | Nivel 4 (5 puntos) | Nivel 3 (3.5 puntos) | Nivel 2 (2 puntos) | Nivel 1 (0 puntos) | Puntuación |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Corpus: procedencia y responsabilidad** | Documenta de dónde salió el corpus, su licencia, su vigencia y quién responde por él. Identifica qué pasa si el corpus está mal | Documenta el origen pero no las implicaciones de que esté desactualizado o sesgado | Corpus sin procedencia clara | Sin corpus del dominio | /5 |
| **Técnicas avanzadas de retrieval** | Al menos dos técnicas implementadas (hybrid search, reranking, query transformation) con el delta medido contra el RAG ingenuo | Dos técnicas implementadas, pero sin medir si mejoraron | Una sola técnica, o técnicas sin integrar | RAG ingenuo sin avanzar | /5 |
| **Integración de tool use** | Al menos una herramienta externa integrada, con criterio explícito de cuándo el sistema la invoca y qué hace si falla | Herramienta integrada y funcional, sin manejo de fallas | Herramienta que no aporta a la decisión del usuario | Sin tool | /5 |
| **Evaluación con RAGAS + harness propio** | Reporta faithfulness, context precision/recall y answer relevancy, los cruza con el harness de M2, y analiza dónde el sistema falla | Reporta métricas RAGAS sin cruzarlas con el harness propio, o sin análisis de errores | Corre RAGAS y pega los números sin leerlos | Sin evaluación | /5 |

### Dónde está cada requisito

| Requisito | Dónde |
|---|---|
| Técnicas avanzadas (2): búsqueda híbrida BM25 + densa con RRF y reranking con cross-encoder | `ENTREGABLE.ipynb` §4 y §6 |
| Herramientas (2): `verificar_existencia` y `buscar_similares`, elegidas por el modelo con function calling | `ENTREGABLE.ipynb` §7 |
| Scorecard propio (harness de M2) con IC 95% | `ENTREGABLE.ipynb` §11, `Resultados/scorecard_m3.csv`, `Resultados/scorecard_m3.png` |
| RAGAS: las cuatro métricas con el cálculo del Lab C y juez propio (Phi-3.5) | `ENTREGABLE.ipynb` §10, `Resultados/ragas_manual.csv` |
| Tabla de deltas con latencia | `ENTREGABLE.ipynb` §11.1, `Resultados/deltas_m3.csv` |
| Lectura honesta | `INFORME_M3.md` §8 |

## La arquitectura (resumen)

| Pieza | Elección |
|---|---|
| Corpus | fichas de todos los productos del split de test en español (título, descripción, viñetas, marca, color) |
| Unidad de recuperación | una ficha por producto (no se parte) |
| Texto indexado | `ficha`: título + marca + color + viñetas |
| Embeddings y base vectorial | `paraphrase-multilingual-MiniLM-L12-v2` en Chroma persistente |
| Búsqueda léxica | BM25 (`rank_bm25`) sobre todo el catálogo |
| Fusión | Reciprocal Rank Fusion, k = 60 |
| Reranker | el modelo de M1 como cross-encoder sobre los 30 candidatos |
| Generador | `Qwen/Qwen2.5-1.5B-Instruct`, greedy |

### Escalera de sistemas

| Sistema | Qué cambia | Técnica |
|---|---|---|
| **A** ingenuo | búsqueda densa, top-5 al prompt | baseline |
| **B** | + BM25 con RRF | hybrid search |
| **C** | + reranker de M1 | reranking |
| **D** | + el LLM elige la herramienta | tool use |

## Resultado global

El sistema completo (D) mejora al RAG ingenuo (A) en **+0,273 de nDCG@10** en existencia y **+0,265 en aciertos de respuesta**, sin costo neto de latencia (2,08 s vs. 2,02 s). Evaluado con 49 preguntas, IC 95% por bootstrap.

> Para los resultados completos, la lectura honesta y el análisis de errores, ver [`INFORME_M3.md`](INFORME_M3.md).

## Cómo se corre

```bash
# desde Entregables/M3/
jupyter lab ENTREGABLE.ipynb        # el sistema y su evaluación, de arriba a abajo
jupyter lab ABLACIONES_M1.ipynb     # aparte: la respuesta a la retroalimentación de M1 (LoRA y E5-base)
```

**Requisitos previos:**

- `Entregables/M1/modelo_e5_small_finetuned/` y los parquet de ESCI en `Entregables/M1/` (los mismos que usa M2).
- `Entregables/M2/Resultados/eval_set.json`, `rubrica_juez.txt` y las anotaciones de `Entregables/M2/Validacion/`.
- GPU. La corrida de referencia es la de M1 y M2 (RTX 5060 Ti 16 GB, Python 3.11.9, torch 2.11.0+cu128, transformers 4.57.1). Los modelos grandes se cargan y descargan por fases para caber en 16 GB.
- Descargas la primera vez: Qwen2.5-1.5B, Qwen2.5-3B, Phi-3.5-mini, `multilingual-e5-small` y MiniLM.

**Validación del eval set:** el equipo validó las 49 preguntas en `Validacion/eval_set_m3_para_validar.xlsx`. El notebook lee ese archivo, aplica las correcciones que haya y avisa si alguna pregunta queda sin validar.

## Artefactos que produce

| Archivo | Qué es |
|---|---|
| `Resultados/scorecard_m3.csv`, `.png` | el scorecard con IC 95% |
| `Resultados/deltas_m3.csv` | qué movió cada peldaño |
| `Resultados/ragas_manual.csv` | RAGAS con el cálculo del Lab C |
| `Resultados/eval_set_m3.json` | las 49 preguntas con intención y referencia |
| `Resultados/salidas_sistemas.json` | cada respuesta de cada sistema |
| `Resultados/detalle_m3.csv` | cada pregunta por cada sistema: dimensiones, RAGAS y latencia |
| `Resultados/calibracion_humana_m3.csv` | calibración con 3 anotadores |
| `Resultados/umbrales_m3.json` | umbrales de exacto y similares |
| `Resultados/metricas_m3.json` | configuración completa y todas las métricas |

## Material de referencia

| Sesión | Material | Qué cubre |
|---|---|---|
| S07 | `SI4006_S07_Semana7_Sesion7.pdf`, `S07_Lab_RAG_ingenuo.ipynb` | el pipeline de siete etapas, el RAG ingenuo |
| S08 | `SI4006_S08_Semana8_Sesion8.pdf`, `S08_Lab_RAG_avanzado.ipynb` | hybrid search con RRF, reranking, tabla de deltas |
| S10 | `SI4006_S10_Semana10_Sesion10.pdf`, `S10_Lab_Agentic_RAG_RAGAS_RESUELTO.ipynb` | tool use, ReAct y RAGAS |

---

Ver [`ENTREGABLE.ipynb`](ENTREGABLE.ipynb) para el desarrollo completo, [`ABLACIONES_M1.ipynb`](ABLACIONES_M1.ipynb) para las ablaciones, e [`INFORME_M3.md`](INFORME_M3.md) para los resultados, la lectura honesta y el análisis de errores.
