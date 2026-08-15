# M1 · Fine-tuning de encoder para ranking de relevancia (S02–S04)

## Sobre el proyecto

**Digitdeck** es un copiloto de calidad de búsqueda para ecommerce en español. Su objetivo es
detectar consultas con resultados deficientes, **ordenar productos por relevancia** y preparar
recomendaciones trazables para la persona responsable de ecommerce. El proyecto se desarrolla
como entregable de **Tópicos Especiales y Aplicaciones en IA** (Universidad EAFIT, SI4006), y
cada módulo del curso (`M1 → M5`) corresponde a una capa del sistema.

El motor del sistema es la capacidad del modelo de **asignar un score de relevancia a un par
(consulta, producto)**. M1 es donde ese motor se construye y valida por primera vez.

## Decisión técnica de M1

El equipo fine-tunea `intfloat/multilingual-e5-small` sobre pares ESCI en español y lo compara
contra tres variantes bajo el mismo split y presupuesto GPU T4:

| Variante | Entrenamiento | Métrica primaria | Guardrails |
|---|---|---|---|
| BM25 | Ninguno | nDCG@10 | latencia, tamaño de índice |
| E5-small congelado | Ninguno | nDCG@10 | memoria, p95 |
| **E5-small ajustado** ← candidato | Pares/grados ESCI es | nDCG@10 | MRR, Recall@10, memoria, p95 |
| E5-base ajustado *(opcional)* | Mismo split; mayor presupuesto | nDCG@10 | mejora por costo |

> **BGE-M3 + reranker** queda descartado de M1: su arquitectura de dos etapas no permite
> comparación bajo las mismas condiciones, y la p95 en T4 es prohibitiva. Candidato natural
> para M2/M3.

| Componente | Elección |
|---|---|
| **Modelo base** | `intfloat/multilingual-e5-small` (~117 M params, encoder, multilingüe) |
| **Técnica** | Fine-tuning con cabeza de clasificación binaria sobre el encoder |
| **Tarea** | Dado un par `(consulta, product_title)` → predecir `relevante / no relevante` |
| **Dataset** | [Amazon ESCI](https://github.com/amazon-science/esci-data) · Apache 2.0 · ~218 k pares en español |
| **Métrica primaria** | nDCG@10 |
| **Guardrails** | MRR · Recall@10 · memoria · p95 latencia |

> **E5-small congelado** actúa como baseline semántico sin entrenamiento — separa el efecto del
> encoder pre-entrenado del efecto del fine-tuning. Si el congelado supera a BM25, el argumento
> de fine-tuning se fortalece; si no, también es un hallazgo honesto que se reporta.

## Qué se espera en M1

M1 cubre la primera capa del sistema: elegir un encoder base, construir el dataset de
entrenamiento/evaluación del dominio, hacer fine-tuning eficiente, y demostrar con métricas
de ranking que el modelo resultante mejora (o no) sobre los baselines.

Concretamente, el equipo debe producir cuatro cosas verificables:

1. **Un modelo base elegido y justificado con evidencia** — argumentar la decisión con datos
   sobre tamaño, licencia, cobertura de idioma y comportamiento del tokenizador sobre texto
   de ecommerce en español. El candidato eficiente se compara con BM25 y su variante congelada
   antes de adoptarlo.
2. **Un dataset documentado y reproducible** — origen, licencia, tamaño, criterios de inclusión,
   limpieza aplicada, limitaciones conocidas, y splits que cualquiera pueda regenerar.
3. **Un fine-tuning de encoder que efectivamente corre** — entrenamiento reproducible, con
   hiperparámetros registrados, cuyo modelo resultante carga y produce scores coherentes.
4. **Baselines y métricas comparables** — comparar el encoder fine-tuned contra BM25 y E5-small
   congelado sobre el mismo split de test con nDCG@10 como métrica primaria, con una lectura
   honesta de dónde sí y dónde no hay mejora.

> **Estado actual:** Criterio 2 (dataset ESCI) — implementado en el notebook. Criterios 1, 3
> y 4 — en curso. Las rúbricas detalladas aún no han sido publicadas; nunca se inventan
> requisitos faltantes.

## Material de referencia (Clases/M1)

| Sesión | Notebook | Qué cubre |
|---|---|---|
| S01 | [S01_Demo_Capacidades.ipynb](../../Clases/M1/S01_Demo_Capacidades.ipynb) | Demo LLM + RAG + multimodal; introducción a `multilingual-e5-small` |
| S02 | [S02_Lab_Abrir_la_caja.ipynb](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) | Tokenizadores (BPE, WordPiece, SentencePiece), self-attention, positional encoding |
| S03 | [S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb) | Bloque transformer, conexión residual, tres familias (encoder/decoder/enc-dec) |
| S04 | [S04_Lab_Fine_tuning_SOLUCION.ipynb](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb) | Fine-tuning de encoders; baseline antes/después |

## Entorno requerido

- **Google Colab** con GPU **T4** (`Runtime → Change runtime type → T4 GPU`)
- Librerías principales: `transformers`, `datasets`, `accelerate`, `evaluate`, `sentence-transformers`
- Instalación (ver celda de setup del ENTREGABLE):
  ```bash
  pip install -q transformers datasets accelerate evaluate sentence-transformers
  ```

## Criterios de aceptación

Cada criterio se puntúa de 0 a 5, para un total de 20.

| Criterio | Nivel 4 (5 puntos) | Nivel 3 (3.5 puntos) | Nivel 2 (2 puntos) | Nivel 1 (0 puntos) |
|---|---|---|---|---|
| **Selección y justificación del modelo base** | Escoge un encoder base y argumenta con evidencia: tamaño, licencia, idioma y tokenizador sobre el dominio. Compara con BM25 y E5-small congelado | Justificación parcial o sin datos | Escoge sin argumentar | No hay modelo base identificable |
| **Dataset: construcción y documentación** | Documentado: origen, licencia, tamaño, criterios, limpieza y limitaciones. Splits reproducibles | Faltan licencia, limitaciones o criterios de split | Sin documentar o splits no reproducibles | No hay dataset |
| **Implementación del fine-tuning** | Reproducible; hiperparámetros registrados; modelo resultante produce scores coherentes | Funciona pero sin configuración registrada | Corre con errores o no reproducible | No entrenó |
| **Baselines y reporte de métricas** | nDCG@10 sobre los cuatro sistemas; guardrails (MRR, Recall@10); lectura honesta del delta | Hay métricas pero comparación superficial | Métricas sin baseline comparable | Sin métricas |

**Total: /20**

---

Ver [`TODO.md`](TODO.md) para el paso a paso que el equipo debe seguir para cumplir cada criterio.