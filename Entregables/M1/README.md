# M1 · Fine-tuning con LoRA

## Sobre el proyecto

**Digitdeck** es un copiloto de calidad de búsqueda para ecommerce en español. Su objetivo es
detectar consultas con resultados deficientes, **evaluar la relevancia de pares (consulta,
producto)** y preparar recomendaciones trazables para la persona responsable de ecommerce. El
proyecto se desarrolla como entregable de **Tópicos Especiales y Aplicaciones en IA** (Universidad
EAFIT, SI4006), y cada módulo del curso (`M1 → M5`) corresponde a una capa del sistema.

El motor del sistema es la capacidad del modelo de **juzgar si un producto es relevante para una
consulta**. M1 es donde ese motor se construye y valida por primera vez.

## Decisión técnica de M1

El equipo aplica **fine-tuning con LoRA** sobre un decoder multilingüe pequeño:

| Componente | Elección |
|---|---|
| **Modelo base** | `Qwen/Qwen2.5-0.5B` (decoder, multilingüe, entrena en Colab T4) |
| **Técnica** | LoRA — `r=8`, `lora_alpha=16`, `target_modules=["q_proj","v_proj"]` |
| **Tarea fine-tuning** | Dado un par `(consulta, descripción_producto)` → generar etiqueta de relevancia |
| **Dataset** | [Amazon ESCI](https://github.com/amazon-science/esci-data) · Apache 2.0 · ~218 k pares en español · etiquetas E/S/C/I → `relevante / no relevante` |
| **Baseline A** | BM25 léxico sobre el mismo corpus |
| **Baseline B** | El mismo modelo `Qwen/Qwen2.5-0.5B` **antes** del fine-tuning |

> **Justificación del modelo base (criterio 1 — confirmado):** se compararon 5 tokenizadores
> sobre 15 consultas reales de ecommerce en español. `Salamandra-2b` obtuvo el menor costo total
> (126 tokens, 8.4 prom/frase) pero fue descartado por su cobertura exclusivamente monolingüe y
> mayor costo de cómputo (2 B params). `Qwen/Qwen2.5-0.5B` fue seleccionado por ser el segundo
> más eficiente (149 tokens, 9.9 prom/frase), multilingüe, Apache 2.0, y el más liviano del grupo
> (0.49 B params / 1 GB disco) — garantizando ciclos de experimentación cortos en la T4 de Colab.

## Qué se espera en M1

M1 cubre la primera capa del sistema: elegir un modelo base **decoder**, construir el dataset de
entrenamiento/evaluación del dominio, hacer fine-tuning eficiente con **LoRA**, y demostrar con
métricas que el modelo resultante mejora (o no) sobre un baseline razonable.

Concretamente, el equipo debe producir cuatro cosas verificables:

1. **Un modelo base elegido y justificado con evidencia** — no basta con nombrar un modelo; hay
   que argumentar la decisión con datos sobre tamaño, licencia, cobertura de idioma y
   comportamiento del tokenizador frente al dominio de ecommerce en español.
2. **Un dataset documentado y reproducible** — origen, licencia, tamaño, criterios de inclusión,
   limpieza aplicada, limitaciones conocidas, y splits que cualquiera pueda regenerar.
3. **Un fine-tuning con LoRA que efectivamente corre** — entrenamiento reproducible, con
   hiperparámetros registrados, cuyo modelo resultante carga y produce salidas coherentes.
4. **Un baseline y métricas comparables** — no solo reportar números del modelo propio, sino
   compararlo contra un baseline explícito (BM25) y el modelo antes del fine-tuning, con una
   lectura honesta de dónde sí y dónde no hay mejora.

> **Estado actual:** Criterio 1 (selección del modelo) — **confirmado con evidencia empírica**.
> Criterios 2, 3 y 4 — en curso. No se atribuyen a la docente formatos, fechas o criterios
> no publicados oficialmente.

## Material de referencia (Clases/M1)

| Sesión | Notebook | Qué cubre |
|---|---|---|
| S01 | [S01_Demo_Capacidades.ipynb](../../Clases/M1/S01_Demo_Capacidades.ipynb) | Demo LLM + RAG + multimodal; introducción a `multilingual-e5-small` |
| S02 | [S02_Lab_Abrir_la_caja.ipynb](../../Clases/M1/S02_Lab_Abrir_la_caja.ipynb) | Tokenizadores (BPE, WordPiece, SentencePiece), self-attention, positional encoding |
| S03 | [S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb](../../Clases/M1/S03_Lab_El_bloque_y_las_familias_SOLUCIONES.ipynb) | Bloque transformer, conexión residual, tres familias (encoder/decoder/enc-dec) |
| S04 | [S04_Lab_Fine_tuning_SOLUCION.ipynb](../../Clases/M1/S04_Lab_Fine_tuning_SOLUCION.ipynb) | Fine-tuning con LoRA usando `peft` + `Trainer`; baseline antes/después |

## Entorno requerido

- **Google Colab** con GPU **T4** (`Runtime → Change runtime type → T4 GPU`)
- Librerías principales: `transformers`, `peft`, `datasets`, `accelerate`, `evaluate`
- Instalación (ver celda de setup de S04):
  ```bash
  pip install -q transformers datasets peft accelerate evaluate bitsandbytes
  ```

## Criterios de aceptación

Esta es la rúbrica de evaluación de M1. Cada criterio se puntúa de 0 a 5, para un total de 20.

| Criterios | Nivel 4 (5 puntos) | Nivel 3 (3.5 puntos) | Nivel 2 (2 puntos) | Nivel 1 (0 puntos) |
|---|---|---|---|---|
| **Selección y justificación del modelo base** | Escoge un modelo base y argumenta la decisión con evidencia: tamaño, licencia, idioma y comportamiento del tokenizador sobre el dominio | Escoge con criterio pero la justificación es parcial o no está respaldada con datos | Escoge sin argumentar, o el argumento no resiste una pregunta | No hay modelo base identificable |
| **Dataset: construcción y documentación** | Dataset documentado: origen, licencia, tamaño, criterios de inclusión, limpieza y limitaciones conocidas. Splits reproducibles | Documentado en lo esencial; faltan licencia, limitaciones o criterios de split | Dataset sin documentar, o splits no reproducibles | No hay dataset o no es del dominio declarado |
| **Implementación del fine-tuning con LoRA** | Entrenamiento correcto y reproducible; hiperparámetros registrados; el modelo resultante carga y produce salidas coherentes | Entrena y funciona, pero con configuración no registrada o parcialmente reproducible | Corre con errores, o no se puede reproducir | No entrenó |
| **Baseline y reporte de métricas** | Hay baseline explícito, métricas comparables y una lectura honesta del delta, incluidos los casos donde no mejoró | Hay baseline y métricas, pero la comparación es superficial o solo reporta lo favorable | Reporta métricas sin baseline, o el baseline no es comparable | Sin métricas |

**Total: /20**

---

Ver [`TODO.md`](TODO.md) para el paso a paso que el equipo debe seguir para cumplir cada criterio.