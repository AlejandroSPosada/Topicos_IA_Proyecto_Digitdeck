# INFORME M3 — Digitdeck: RAG con herramientas para ecommerce

---

## 1. Resumen ejecutivo

**Digitdeck M3** extiende el motor de ranking de M1 y el harness de evaluación de M2 con un sistema RAG (Retrieval-Augmented Generation) completo para ecommerce en español. El sistema recibe preguntas de un comprador sobre el catálogo de productos y responde con información verificada, citando la ficha de cada producto.

**Resultado global:** el sistema completo (D) mejora al RAG ingenuo (A) en +0,273 de nDCG@10 en existencia y +0,265 en aciertos de respuesta, sin costo neto de latencia (2,08 s vs. 2,02 s). Evaluado con el harness propio de M2 y las cuatro métricas de RAGAS.

---

## 2. Objetivo y contexto

| Momento | Qué se construyó |
|---|---|
| **M1** | Motor de ranking: encoder `intfloat/multilingual-e5-small` ajustado, nDCG@10 = 0,8369 |
| **M2** | Harness de evaluación: 3 dimensiones, eval set de 13 casos, LLM-as-a-judge |
| **M3** | Sistema RAG con técnicas avanzadas, tool use, evaluación RAGAS + harness propio |

**Usuario final:** comprador que pregunta si la tienda tiene un producto o qué alternativas hay.

**Decisiones que habilita el sistema:**
- Comprar el producto exacto que pidió
- Aceptar una alternativa presentada como tal
- Irse a buscar en otra parte cuando el sistema dice que no lo tiene

---

## 3. Arquitectura del sistema

### Pipeline de 7 etapas (S07)

```
Pregunta del comprador
        │
        ▼
  ┌─────────────┐
  │  Enrutador   │  ← Qwen2.5-1.5B decide: verificar_existencia / buscar_similares / abstención
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Retrieval   │  ← Búsqueda híbrida: BM25 + densa (MiniLM) con RRF (k=60)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Reranking   │  ← Cross-encoder de M1 (E5-small fine-tuned) sobre top-30
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Filtrado    │  ← Umbrales calibrados + verificador de exacto (Qwen2.5-3B)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Generación  │  ← Qwen2.5-1.5B con prompt de 4 partes + válvulas de escape
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Presentación │  ← Paso de nombres: inserta título corto antes de cada ID
  └─────────────┘
```

### Escalera de sistemas (protocolo S08)

Cada peldaño cambia **una sola pieza**, con el mismo eval set, generador, prompt y harness:

| Sistema | Qué agrega | Técnica |
|---|---|---|
| **A** (ingenuo) | Búsqueda densa, top-5 al prompt | Baseline |
| **B** | + BM25 con RRF | Hybrid search |
| **C** | + Reranker de M1 | Reranking |
| **D** | + Enrutador + herramientas con umbrales | Tool use |

### Herramientas implementadas

| Herramienta | Función | Criterio de invocación | Manejo de falla |
|---|---|---|---|
| `verificar_existencia(consulta)` | Busca el producto exacto; filtra por umbral de exacto (0,5993) | El enrutador detecta intención de existencia | Si no pasa el umbral: responde "no lo tenemos" |
| `buscar_similares(consulta)` | Busca alternativas; filtra con piso de similares + verificador de exacto | El enrutador detecta intención de similar | Si no hay alternativas: responde "no hay parecidos" |
| ninguna | Abstención | Pregunta fuera de dominio | Frase de abstención predefinida |

---

## 4. Corpus

**Dataset:** ESCI (Amazon Shopping Queries Dataset)
- **Origen:** publicado por Amazon como benchmark de relevancia de búsqueda
- **Licencia:** Apache 2.0
- **Alcance:** fichas de productos del marketplace de Amazon España en español
- **Vigencia:** datos recopilados circa 2022; no se actualizan
- **Contenido indexado por producto:** título, marca, color, viñetas (campo `ficha`)
- **Tamaño del catálogo:** todos los productos del split de test en español

**Riesgos si el corpus está mal:**
- Productos descontinuados pueden ser recomendados como disponibles
- Sesgos de las etiquetas ESCI se heredan en la evaluación (limitación 2 del README)
- Los productos sin etiquetar para una consulta cuentan como irrelevantes aunque no lo sean (limitación 2)
- El catálogo es de Amazon España, no de una tienda real (limitación 12)

---

## 5. Técnicas avanzadas de retrieval

### 5.1 Búsqueda híbrida (BM25 + densa con RRF)

- **Componente léxico:** BM25 (`rank_bm25`) sobre todo el catálogo
- **Componente denso:** `paraphrase-multilingual-MiniLM-L12-v2` en Chroma persistente
- **Fusión:** Reciprocal Rank Fusion (RRF) con k=60, como indica S08 lámina 14

**Impacto medido (A→B):**
- nDCG existencia: **+0,162 [0,080; 0,247]** ✅ significativo
- nDCG similar: +0,026 [0,001; 0,056]
- Latencia adicional: +0,15 s

### 5.2 Reranking con cross-encoder de M1

- **Modelo:** E5-small fine-tuned de M1, usado como cross-encoder sobre los top-30 candidatos
- **Justificación:** clasifica el par (consulta, producto), que es lo que hace un cross-encoder (S08 lámina 16)

**Impacto medido (B→C):**
- nDCG existencia: **+0,175 [0,101; 0,255]** ✅ significativo
- Aciertos de respuesta: +0,143 [0,000; 0,286]
- Latencia adicional: 0,012 s (prácticamente gratis)

### 5.3 Técnica explorada y descartada: query transformation

Se implementó reescritura de consulta con el LLM de 1,5B. Con un prompt simple, bajó el nDCG (-0,053). Con prompt corregido (reglas, ejemplos, JSON), el delta fue +0,041 [-0,024; 0,112] — no distinguible del azar. Se descartó porque con la híbrida y el reranker ya se cumplen las dos técnicas mínimas.

---

## 6. Evaluación

### 6.1 Eval set

- **28 casos gold** (13 de M2 + 12 nuevos elegidos con regla fija + 3 adversariales)
- **49 preguntas** (22 de existencia, 21 de similar, 6 adversariales)
- **Validación:** todas aprobadas en `Validacion/eval_set_m3_para_validar.xlsx`

### 6.2 Scorecard propio (harness de M2 adaptado)

| Medida | A ingenuo | B + híbrida | C + reranker | D + herramientas |
|---|---|---|---|---|
| nDCG@10 existencia (ESCI) | 0,180 | 0,342 | 0,518 | 0,453 |
| nDCG@10 similar (ESCI `S`) | 0,073 | 0,099 | 0,091 | 0,139 |
| D2 juez existencia (1-5) | 1,68 | 2,14 | 3,09 | 2,95 |
| D3 aciertos respuesta total | 4/49 (0,08) | 8/49 (0,16) | 15/49 (0,31) | 17/49 (0,35) |
| Abstención adversarial | 1/6 | 0/6 | 2/6 | **6/6** |
| Afirmaciones falsas | 7 | 9 | 3 | 6 |
| Latencia media (s) | 2,02 | 2,18 | 2,15 | 2,08 |

### 6.3 Tabla de deltas (bootstrap pareado)

| Paso | Técnica | Δ nDCG exist. | Δ nDCG similar | Δ aciertos resp. | Δ latencia |
|---|---|---|---|---|---|
| A→B | Híbrida | **+0,162** [0,080; 0,247] | +0,026 | +0,082 | +0,15 s |
| B→C | Reranker | **+0,175** [0,101; 0,255] | -0,008 | +0,143 | -0,03 s |
| C→D | Herramientas | -0,065 [-0,166; 0,020] | +0,048 | +0,041 | -0,07 s |
| **A→D** | **Total** | **+0,273** [0,145; 0,409] | +0,066 | **+0,265** | +0,06 s |

### 6.4 RAGAS (cálculo a mano, juez Phi-3.5)

| Sistema | Faithfulness | Context Precision | Context Recall | Answer Relevancy |
|---|---|---|---|---|
| A | 0,866 | 0,633 | 0,395 | 0,567 |
| B | 0,871 | 0,786 | 0,512 | 0,526 |
| C | 0,883 | 0,833 | 0,372 | 0,533 |
| D | **0,940** | **0,848** | 0,395 | 0,543 |

### 6.5 Cruce RAGAS ↔ Scorecard: interpretación conjunta

| Sistema | nDCG ↑ | Aciertos ↑ | Faithfulness ↑ | Ctx Precision ↑ | Ctx Recall | Interpretación |
|---|---|---|---|---|---|---|
| A (base) | 0,180 | 0,08 | 0,866 | 0,633 | 0,395 | Recuperación pobre, pero el modelo no se inventa cosas (faithfulness alta) |
| B (+híbrida) | 0,342 | 0,16 | 0,871 | 0,786 | **0,512** | BM25 aporta documentos relevantes que la densa sola no encontraba (recall sube) |
| C (+reranker) | **0,518** | 0,31 | 0,883 | **0,833** | 0,372 | El reranker sube la precisión pero **baja el recall**: entrenado para separar E del resto, deja fuera alternativas |
| D (+tools) | 0,453 | **0,35** | **0,940** | 0,848 | 0,395 | Faithfulness máxima: las herramientas + abstención fuerzan al modelo a pegarse al contexto. Cae nDCG por la consulta reescrita del enrutador |

**Hallazgo clave:** hay una tensión entre **context precision** (qué tan relevante es lo que se recupera) y **context recall** (qué tanto de lo relevante se recuperó). El reranker maximiza la primera a costa de la segunda, porque filtra agresivamente.

---

## 7. Análisis de errores

### Errores por patrón

| Patrón de error | Ejemplos | Causa raíz | Sistemas afectados |
|---|---|---|---|
| **Consulta reescrita mal por el enrutador** | n11-E: "merida"→"merienda"; n09-E: quita tildes | Modelo de 1,5B generaliza mal con consultas no vistas | Solo D |
| **Afirmación falsa de existencia** | g08-E: filtro de aceite por gasoil | El pool no tiene el título correcto; el reranker lee solo títulos | A, B, C, D |
| **Similares devuelve complementos u homónimos** | Switches HDMI para "parecido a Matrix" | Reranker binario (E vs. resto) no distingue S de C/I | D |
| **Sustitutos con score de exacto** | Redmi Note 7 de otro color tiene score ≥ umbral | Los sustitutos ESCI son variantes del mismo producto | C, D |

### Errores concretos más informativos

- **g08-E** (filtro gasoil Renault Trafic): falla en los 4 sistemas. En el pool de ESCI, los filtros correctos no dicen "Renault Trafic" en el título, que es lo único que lee el reranker.
- **n11-E** (productos de Mérida): D lo rompe porque el enrutador escribió "merienda" en vez de "merida". nDCG pasa de 0,753 en C a 0 en D.
- **n09-E** (máquina de deporte): el enrutador quitó tildes ("maquina"), y BM25 no lematiza, así que "maquina" ≠ "máquina".

---

## 8. Lectura honesta

### Qué movió cada técnica
1. **Búsqueda híbrida:** el delta más claro en nDCG (+0,162), pero también sube las afirmaciones falsas (de 7 a 9).
2. **Reranker:** el mejor peldaño (+0,175 nDCG, +0,143 aciertos), prácticamente gratis en latencia. Su costo: baja el context recall.
3. **Herramientas:** no distinguible del azar en el promedio. Lo que sí generaliza: enrutamiento (49/49) y abstención adversarial (6/6). Lo que no: la consulta reescrita pierde información en casos no vistos (-0,147 en nDCG de existencia para casos nuevos).
4. **El sistema completo (A→D):** positivo y significativo (+0,273 nDCG, +0,265 aciertos).

### Qué costó en latencia
- La generación domina (1,40-2,02 s).
- La recuperación híbrida cuesta 0,15 s y el reranker 0,012 s.
- D agrega enrutamiento (0,595 s) y verificador (0,371 s), pero se ahorra la generación al abstenerse.

### Qué falla queda pendiente
1. La consulta del enrutador pierde información en casos no vistos.
2. Similares: 1/21 aciertos. El reranker binario no distingue sustitutos.
3. Afirmaciones falsas en D: 6 de 49 preguntas.
4. La Dimensión 2 no cubre similares.
5. Todo lo ajustado mirando los casos de M2 no generaliza del todo.

---

## 9. Ablaciones de M1 (respuesta a retroalimentación)

| Variante | nDCG@10 | Δ vs. FT completo | Parámetros | Peso |
|---|---|---|---|---|
| BM25 | 0,7508 | — | 0 | índice |
| E5-small congelado | 0,7885 | — | 0 | 448,8 MB |
| **E5-small FT completo (M1)** | **0,8369** | referencia | 117,6 M | 448,8 MB |
| E5-small LoRA r=8 | 0,8305 | -0,0065 | 148 K (0,13%) | **0,57 MB** |
| E5-base FT completo | 0,8459 | +0,0089 | 278 M | 1.060,7 MB |

**Conclusión:** LoRA recupera el 87% de la ganancia del fine-tuning completo con un adaptador 785× más liviano. E5-base gana por poco (+0,0089), a costa de 2,4× los parámetros y 3,3× el tiempo.

---

## 10. Retroalimentación atendida

| Punto | Qué se hizo | Estado |
|---|---|---|
| M1: entrenar LoRA y comparar | LoRA r=8 entrenado y evaluado con IC 95% | ✅ |
| M1: completar ablación E5-base | Ejecutada y reportada | ✅ |
| M2: ampliar a 20-25 gold | 22 gold + 6 adversariales | ✅ |
| M2: segundo juez de otra familia | Phi-3.5-mini sobre las 39 filas de M2 | ✅ |
| M2: reportar nDCG contra dos varas | ESCI y ESCI corregido por mayoría humana | ✅ |
| M2: IC en scorecard | Bootstrap 95% en cada número y delta pareado | ✅ |
| M2: atacar fallo de atributo fino | Indexa ficha completa (título, marca, color, viñetas) | ✅ |

---

## 11. Limitaciones declaradas

1. 28 casos / 49 preguntas: muestra pequeña; deltas con IC que cruzan cero no se distinguen del azar.
2. Productos sin etiquetar cuentan como irrelevantes aunque no lo sean.
3. La vara del equipo solo cubre 50 pares auditados.
4. "Similar" sale de un modelo binario que no distingue `S` de `C`/`I`.
5. La Dimensión 2 no aplica a preguntas de similar.
6. Decisiones tomadas mirando el eval set (declaradas en "Cambios hechos después de ver resultados").
7. El delta C→D mezcla cuatro cosas.
8. El modelo evaluador (Qwen2.5-3B) se usa también como verificador dentro del sistema.
9. El reranker lee solo el título.
10. Generador y juez de M2 son de la misma familia (Qwen); por eso RAGAS usa Phi.
11. ESCI no trae fecha por ficha.
12. El catálogo sigue siendo de Amazon España.

---

## 12. Artefactos producidos

| Archivo | Contenido |
|---|---|
| `ENTREGABLE.ipynb` | Sistema RAG completo y evaluación |
| `ABLACIONES_M1.ipynb` | LoRA y E5-base (respuesta a retro M1) |
| `Resultados/scorecard_m3.csv`, `.png` | Scorecard con IC 95% |
| `Resultados/deltas_m3.csv` | Tabla de deltas por peldaño |
| `Resultados/ragas_manual.csv` | Las cuatro métricas RAGAS |
| `Resultados/eval_set_m3.json` | Eval set completo (28 casos, 49 preguntas) |
| `Resultados/salidas_sistemas.json` | Todas las respuestas de los 4 sistemas |
| `Resultados/detalle_m3.csv` | Detalle por pregunta y sistema |
| `Resultados/calibracion_humana_m3.csv` | Calibración con 3 anotadores |

---

*Generado el 27 de septiembre de 2026.*
