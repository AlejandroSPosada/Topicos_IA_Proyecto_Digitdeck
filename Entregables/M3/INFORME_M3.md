# INFORME M3 — Digitdeck: RAG con herramientas para ecommerce

**SI4006 - Universidad EAFIT - 2026-2** — Maximiliano Bustamante, Valeria Frances Hornung, Sebastián Castaño, Alejandro Posada

---

## 1. Resumen ejecutivo

**Digitdeck M3** extiende el motor de ranking de M1 y el harness de evaluación de M2 con un sistema RAG completo para ecommerce en español. El sistema recibe preguntas de un comprador sobre el catálogo y responde con información verificada, citando la ficha de cada producto.

**Resultado global:** el sistema completo (D) mejora al RAG ingenuo (A) en **+0,273 de nDCG@10** en existencia y **+0,265 en aciertos de respuesta**, sin costo neto de latencia (2,08 s vs. 2,02 s). Evaluado con el harness propio de M2 (3 dimensiones, IC 95%) y las cuatro métricas de RAGAS.

---

## 2. Qué se hizo con la retroalimentación de M1 y M2

| Punto de la retroalimentación | Qué se hizo | Dónde |
|---|---|---|
| M1: "entrenen un adaptador LoRA sobre el mismo split y compárenlo contra este fine-tuning completo" | LoRA `r=8` con la configuración del lab S04, mismo split (verificado por hash), evaluado en las 3.844 consultas de test | `ABLACIONES_M1.ipynb` §5 y §7 |
| M1: "la ablación con E5-base quedó implementada pero sin ejecutar; díganlo en la tabla de resultados" | Se ejecutó, y está en la tabla con su estado | `ABLACIONES_M1.ipynb` §6 y §7 |
| M1: el modelo no quedó publicado en el Hub | **No se sube al Hub** (decisión del equipo). El adaptador LoRA queda guardado en `modelos/e5_small_lora/` | `ABLACIONES_M1.ipynb` §5 |
| M1: encoding cp1252 de los JSON | Todos los JSON de M3 se escriben en UTF-8 explícito y los de M1 se leen con un cargador tolerante | ambos notebooks |
| M2: "completen la anotación con los cuatro integrantes y amplíen a 20-25 gold" | **22 gold y 6 adversariales**: 12 gold nuevos elegidos al azar con regla fija, 3 adversariales nuevos. Anotación humana con **tercera anotación** (Sebastián): con tres personas hay mayoría real | `ENTREGABLE.ipynb` §3 |
| M2: "un segundo juez de otra familia sobre las mismas 39 filas" | `microsoft/Phi-3.5-mini-instruct` sobre las mismas 39 filas de M2 | `ENTREGABLE.ipynb` §8.2 y §9.1 |
| M2: "reporten el nDCG contra las dos varas" | Dimensión 1 contra ESCI y contra **ESCI corregido por la mayoría humana** | `ENTREGABLE.ipynb` §3.2 y §11 |
| M2: los números del scorecard no tenían margen calculado | IC 95% por bootstrap en cada número, y bootstrap pareado en cada delta | `ENTREGABLE.ipynb` §11 |
| M2: atacar el fallo de atributo fino con los campos que M1 dejó fuera | Se indexa la ficha completa (título, marca, color y viñetas) | `ENTREGABLE.ipynb` §2.2 |

**Un hallazgo al revisar M2:** M2 reportó que el hash del split de test "no coincide" con el de M1. La causa es que M2 lo calculó con otra fórmula (dos columnas, ordenadas), no que el split sea distinto. M3 verifica con la fórmula original de M1 y el `assert` lo confirma.

---

## 3. Arquitectura del sistema

### Pipeline de 7 etapas (S07)

| Pieza | Elección | Por qué |
|---|---|---|
| Corpus | fichas de todos los productos del split de test en español (título, descripción, viñetas, marca, color) | cada consulta del eval set tiene su pool etiquetado mezclado con miles de productos de otras consultas |
| Unidad de recuperación | una ficha por producto | una ficha es un documento corto; no se parte |
| Texto indexado | `ficha`: título + marca + color + viñetas; el generador recibe la ficha completa | incluye los campos que M1 dejó fuera |
| Embeddings y base vectorial | `paraphrase-multilingual-MiniLM-L12-v2` en Chroma persistente | el modelo del harness y la base del curso |
| Búsqueda léxica | BM25 (`rank_bm25`) sobre todo el catálogo | corrige la limitación 5 de M2 (IDF degenerado) |
| Fusión | Reciprocal Rank Fusion, k = 60 | S08 lámina 14: fusionar por puestos, no por puntajes |
| Reranker | el modelo de M1 como cross-encoder sobre los 30 candidatos | clasifica el par (consulta, producto), que es lo que hace un cross-encoder |
| Generador | `Qwen/Qwen2.5-1.5B-Instruct`, greedy | el de los labs S07, S08 y S10 |
| Prompt | las cuatro partes de S07 lámina 10, con dos válvulas de escape y tres frases de apertura obligatorias | "no está" y "no está exacto, pero hay parecidos" son dos respuestas honestas distintas |

### La escalera de sistemas (protocolo S08 lámina 25)

Cada peldaño cambia **una sola pieza**, con el mismo eval set, generador, prompt y harness.

| Sistema | Qué cambia respecto al anterior | Técnica |
|---|---|---|
| **A** ingenuo | búsqueda densa, top-5 al prompt | baseline de M3 |
| **B** | + BM25 con RRF | hybrid search |
| **C** | + reranker de M1 | reranking |
| **D** | + el LLM elige la herramienta, que filtra con umbrales calibrados y, en similares, con un verificador de exacto | tool use |

**Lo que D mezcla:** en D el modelo elige la herramienta **y** escribe la consulta de búsqueda; la herramienta filtra con los umbrales y, en similares, con el verificador de exacto. El delta de C a D mezcla esas cuatro cosas y así se lee.

### Las herramientas

El modelo no ejecuta nada: lee el esquema de las herramientas, propone una llamada en JSON y el código la ejecuta (S10 láminas 6 a 8). **Una sola acción por pregunta**, sin ciclo ReAct.

| Herramienta | Por dentro | Devuelve |
|---|---|---|
| `verificar_existencia(consulta)` | híbrida + reranker, y se quedan las fichas con score ≥ **umbral de exacto** | el producto pedido, o nada |
| `buscar_similares(consulta)` | la misma recuperación; las candidatas que pasan el **piso de similares** van al **verificador de exacto**: las que son exactamente lo pedido se descartan y las demás son alternativas | alternativas |
| ninguna | no se busca | abstención |

**Sin herramienta no hay fuente, y sin fuente no se responde:** si el modelo no elige herramienta o la herramienta no devuelve nada, la respuesta es la frase de abstención.

---

## 4. Corpus: procedencia, licencia y riesgos

**Dataset:** ESCI (Amazon Shopping Queries Dataset)

| Aspecto | Detalle |
|---|---|
| **Origen** | Publicado por Amazon como benchmark de relevancia de búsqueda en ecommerce |
| **Licencia** | Apache 2.0 (dataset público en Hugging Face y GitHub) |
| **Alcance** | Fichas de productos del marketplace de Amazon España en español |
| **Vigencia** | Datos recopilados circa 2022; no se actualizan. ESCI no trae fecha por ficha |
| **Quién responde** | El equipo, con el catálogo heredado de M1 |
| **Contenido indexado** | Título, marca, color, viñetas (campo `ficha`). El generador recibe además la descripción |
| **Tamaño** | 80.383 fichas (todos los productos del split de test en español) |

**¿Qué pasa si el corpus está mal?**

1. **Productos descontinuados:** el catálogo es de ~2022 y no se actualiza. El sistema puede recomendar productos que ya no existen en la tienda real.
2. **Sesgos de las etiquetas ESCI:** las etiquetas de relevancia fueron anotadas por personas en Amazon. Si esas anotaciones tienen sesgos (e.g., favorecen productos populares, penalizan nichos), el sistema hereda esos sesgos en la evaluación y en la calibración de los umbrales.
3. **Productos sin etiquetar:** el RAG recupera de todo el catálogo (80.383 fichas), pero solo una fracción está etiquetada para cada consulta. Un producto que no está en el pool etiquetado cuenta como no relevante en la Dimensión 1, aunque pueda serlo. Esto subestima el rendimiento real del sistema.
4. **Catálogo de Amazon España:** no es el catálogo de una tienda real. Las consultas, los productos y las etiquetas vienen de un benchmark, no de un entorno de producción.
5. **Sin fecha por ficha:** S07 pide citar "fuente y fecha"; la fuente citable es el `product_id` pero no hay fecha. Queda declarado como limitación.

---

## 5. Técnicas avanzadas de retrieval

### 5.1 Búsqueda híbrida (BM25 + densa con RRF)

- **Componente léxico:** BM25 (`rank_bm25`) sobre todo el catálogo
- **Componente denso:** `paraphrase-multilingual-MiniLM-L12-v2` en Chroma persistente
- **Fusión:** Reciprocal Rank Fusion (RRF) con k=60 (S08 lámina 14: fusionar por puestos, no por puntajes)

**Impacto medido (A→B):**
- nDCG existencia: **+0,162 [0,080; 0,247]** 
- nDCG similar: +0,026 [0,001; 0,056]
- Latencia adicional: +0,15 s
- Sube las afirmaciones falsas de 7 a 9

### 5.2 Reranking con cross-encoder de M1

- **Modelo:** E5-small fine-tuned de M1, usado como cross-encoder sobre los top-30 candidatos
- **Justificación:** clasifica el par (consulta, producto), que es lo que hace un cross-encoder (S08 lámina 16). Lee el **título**, que es con lo que se entrenó; el generador recibe la ficha completa.

**Impacto medido (B→C):**
- nDCG existencia: **+0,175 [0,101; 0,255]** 
- Aciertos de respuesta: +0,143 [0,000; 0,286]
- Latencia adicional: 0,012 s (prácticamente gratis)
- Baja las afirmaciones falsas de 9 a 3
- **Costo:** context recall baja de 0,512 a 0,372 (el reranker, entrenado para separar `E` del resto, deja fuera las alternativas)

### 5.3 Técnica explorada y descartada: query transformation

Se implementó reescritura de consulta con el LLM de 1,5B. Con prompt simple: -0,053 en nDCG. Con prompt corregido (reglas, ejemplos, JSON): +0,041 [-0,024; 0,112] — no distinguible del azar. Se descartó porque con la híbrida y el reranker ya se cumplen las dos técnicas mínimas.

---

## 6. Evaluación

### 6.1 El eval set

**28 casos: los 13 de M2 y 15 nuevos.** Cada gold se pregunta de dos formas (existencia y similar); `g02` no tiene productos `S` y solo va como existencia. Total: **49 preguntas** (22 de existencia, 21 de similar, 6 adversariales).

- **Los 12 gold nuevos se eligieron con una regla fijada antes de correr:** consultas del split de test en español con al menos 2 productos `E` y 2 `S`, no en el eval set de M2 ni en las 300 consultas de calibración. De las 2.123 que cumplen, se tomaron 12 al azar con la semilla del proyecto.
- **Los 3 adversariales nuevos:** premisa falsa (PlayStation 7), pregunta de logística, intento de inyección.
- **Quién escribió qué:** las preguntas de M2 las redactó el equipo. Las 27 nuevas las redactó el asistente (Claude) y Sebastián las aceptó. Todas validadas en `Validacion/eval_set_m3_para_validar.xlsx`.
- **Un caso que tensiona la política:** `n10` pide licor de horchata, legal para adultos. En la corrida final el enrutador no lo bloqueó.

### 6.2 El harness de M2, adaptado a dos intenciones

| Dimensión | Qué mide en M3 |
|---|---|
| **1. Métrica clásica** | nDCG@10 del ranking. Relevante = `E` en existencia, `S` en similar. Contra ESCI y contra ESCI corregido por el equipo |
| **2. LLM-as-a-judge** | el juez de M2 **sin cambios** (`Qwen2.5-3B`, misma rúbrica, logits, 3-2-1) sobre los tres primeros productos. **Solo en existencia y adversariales** |
| **3. Aciertos de dominio** | *acierto de pantalla*, *acierto de respuesta*, abstención en adversariales, afirmaciones falsas de existencia, fallas de formato |
| Latencia | por etapa y total, media y p95 |
| Enrutamiento | exactitud de la herramienta elegida en D |

### 6.3 RAGAS (cálculo a mano, juez Phi-3.5)

Las cuatro métricas del Lab C de S10, con Phi-3.5 como juez (otra familia que el generador Qwen). El sí/no se lee de los logits (lección de M2 §6).

### 6.4 Calibración con tres personas

Con tres anotaciones completas (Valeria, Alejandro y Sebastián):

| Medida | Valor |
|---|---|
| Kappa de Fleiss, las tres personas | 0,804 (fuerte) |
| Unánimes | 43 de 50 |
| Productos que acepta la mayoría | 20 de 50 |
| Etiquetas de ESCI que la mayoría cambia | 14 de 50 |
| Contra la mayoría: Phi kappa | 0,545 (78% acuerdo) |
| Contra la mayoría: Qwen kappa | 0,474 (76% acuerdo) |
| Contra la mayoría: ESCI kappa | 0,462 (72% acuerdo) |

---

## 7. Resultados

Corrida final de `ENTREGABLE.ipynb` en la RTX 5060 Ti. 28 casos, 49 preguntas, todas validadas. El umbral de exacto volvió a dar 0,5993, el de M2. La corrida es determinista.

### 7.1 Scorecard de M3

| Medida | A ingenuo | B + híbrida | C + reranker | D + herramientas |
|---|---|---|---|---|
| D1 nDCG@10 existencia (ESCI) | 0,180 [0,096; 0,285] | 0,342 [0,240; 0,457] | 0,518 [0,392; 0,646] | 0,453 [0,306; 0,599] |
| D1 nDCG@10 existencia (vara del equipo) | 0,180 [0,096; 0,289] | 0,335 [0,227; 0,451] | 0,513 [0,391; 0,637] | 0,439 [0,297; 0,582] |
| D1 nDCG@10 similar (ESCI `S`) | 0,073 [0,024; 0,137] | 0,099 [0,046; 0,160] | 0,091 [0,050; 0,133] | 0,139 [0,065; 0,235] |
| D2 juez, existencia (1-5) | 1,68 [1,32; 2,14] (22/22) | 2,14 [1,73; 2,59] (22/22) | 3,09 [2,50; 3,68] (22/22) | 2,95 [2,29; 3,57] (21/22) |
| D2 juez, adversariales (1-5) | 1,00 (5/6) | 1,00 (6/6) | 1,00 (4/6) | sin nota: se abstiene en las 6 |
| D3 aciertos de respuesta, existencia | 1/22 | 6/22 | 12/22 | 10/22 |
| D3 aciertos de respuesta, similar | 2/21 | 2/21 | 1/21 | 1/21 |
| D3 abstención adversarial | 1/6 | 0/6 | 2/6 | 6/6 |
| D3 aciertos de respuesta, total | 4/49 (0,08) | 8/49 (0,16) | 15/49 (0,31) | 17/49 (0,35) |
| Afirmaciones falsas de existencia | 7 | 9 | 3 | 6 |
| Formato de respuesta roto | 1 | 1 | 0 | 0 |
| Enrutamiento correcto | no aplica | no aplica | no aplica | 49/49 |
| Latencia media (s) | 2,02 | 2,18 | 2,15 | 2,08 |
| Latencia p95 (s) | 4,75 | 4,17 | 4,97 | 4,04 |

### 7.2 Tabla de deltas (bootstrap pareado)

| Paso | Técnica | Δ nDCG exist. | Δ nDCG similar | Δ aciertos resp. | Δ latencia |
|---|---|---|---|---|---|
| A→B | Híbrida | **+0,162** [0,080; 0,247] | +0,026 [0,001; 0,056] | +0,082 [-0,020; 0,204] | +0,15 s |
| B→C | Reranker | **+0,175** [0,101; 0,255] | -0,008 [-0,069; 0,047] | +0,143 [0,000; 0,286] | -0,03 s |
| C→D | Herramientas | -0,065 [-0,166; 0,020] | +0,048 [-0,010; 0,123] | +0,041 [-0,082; 0,163] | -0,07 s |
| **A→D** | **Total** | **+0,273** [0,145; 0,409] | +0,066 [-0,026; 0,177] | **+0,265** [0,102; 0,429] | +0,06 s |

Latencia media por etapa (segundos):

| | recuperación | reranking | enrutamiento | verificador | generación | total |
|---|---|---|---|---|---|---|
| A | 0,010 | - | - | - | 2,014 | 2,02 |
| B | 0,155 | - | - | - | 2,023 | 2,18 |
| C | 0,156 | 0,012 | - | - | 1,983 | 2,15 |
| D | 0,090 | 0,012 | 0,595 | 0,371 | 1,402 | 2,08 |

### 7.3 Casos de M2 contra casos nuevos

Los casos de M2 son los que se miraron para ajustar el enrutador y el verificador; los nuevos no se usaron para ajustar nada.

| Subconjunto | Sistema | nDCG existencia | Aciertos exist. | Aciertos similar | Abstención adv. | Afirmaciones falsas | Enrutamiento |
|---|---|---|---|---|---|---|---|
| Casos de M2 (22) | C | 0,516 [0,322; 0,711] | 5/10 | 1/9 | 1/3 | 0 | no aplica |
| Casos de M2 (22) | D | 0,549 [0,341; 0,748] | 6/10 | 0/9 | 3/3 | 1 | 22/22 |
| Casos nuevos (27) | C | 0,519 [0,338; 0,686] | 7/12 | 0/12 | 1/3 | 3 | no aplica |
| Casos nuevos (27) | D | 0,373 [0,165; 0,595] | 4/12 | 1/12 | 3/3 | 5 | 27/27 |

| Subconjunto | Paso | Δ nDCG existencia |
|---|---|---|
| Casos de M2 | C→D | +0,033 [-0,036; 0,119] |
| Casos nuevos | C→D | **-0,147 [-0,300; -0,010]** |
| Casos de M2 | A→D | +0,333 [0,158; 0,537] |
| Casos nuevos | A→D | +0,223 [0,043; 0,412] |

### 7.4 RAGAS (cálculo del Lab C, juez Phi-3.5)

| Sistema | Faithfulness | Context Precision | Context Recall | Answer Relevancy |
|---|---|---|---|---|
| A | 0,866 (48) | 0,633 (43) | 0,395 (43) | 0,567 (48) |
| B | 0,871 (49) | 0,786 (43) | 0,512 (43) | 0,526 (49) |
| C | 0,883 (47) | 0,833 (43) | 0,372 (43) | 0,533 (47) |
| D | **0,940** (42) | **0,848** (43) | 0,395 (43) | 0,543 (42) |

**Efecto del paso de nombres** (medido en las 22 preguntas de M2): la answer relevancy pasa de 0,395 a 0,543 en D. En esta corrida, 23 de las 42 respuestas de D que no son abstención venían del generador solo con identificadores; después del paso, ninguna.

### 7.5 Cruce RAGAS ↔ Scorecard

| Sistema | nDCG ↑ | Aciertos ↑ | Faithfulness ↑ | Ctx Precision ↑ | Ctx Recall | Interpretación |
|---|---|---|---|---|---|---|
| A (base) | 0,180 | 0,08 | 0,866 | 0,633 | 0,395 | Recuperación pobre, pero el modelo no inventa (faithfulness alta) |
| B (+híbrida) | 0,342 | 0,16 | 0,871 | 0,786 | **0,512** | BM25 aporta documentos que la densa no encontraba (recall sube) |
| C (+reranker) | **0,518** | 0,31 | 0,883 | **0,833** | 0,372 | El reranker sube precisión pero **baja recall**: entrenado para E, deja fuera alternativas |
| D (+tools) | 0,453 | **0,35** | **0,940** | 0,848 | 0,395 | Faithfulness máxima: herramientas + abstención fuerzan al modelo a pegarse al contexto |

**Hallazgo clave:** tensión entre context precision y context recall. El reranker maximiza la primera a costa de la segunda.

### 7.6 Jueces, auto-preferencia y calibración

- **Puertas de entrada.** Qwen: 7 mejor, 3 empates, 0 inversiones. Phi: 8 mejor, 2 empates, 0 inversiones.
- **Auto-preferencia sobre las 39 filas de M2:**

| Sistema de M2 | Nota media Qwen | Nota media Phi |
|---|---|---|
| BM25 | 2,00 | 2,38 |
| E5 congelado | 2,33 | 3,08 |
| E5 ajustado (M1) | 3,40 | 3,80 |

Los dos jueces ordenan igual los tres sistemas; Phi pone notas más altas. Concordancia producto por producto: kappa 0,548 (débil).

- **Fracción de productos que cada uno acepta, por etiqueta de ESCI:**

| Etiqueta | n | Mayoría humana | Qwen | Phi |
|---|---|---|---|---|
| `E` | 30 | 0,60 | 0,40 | 0,60 |
| `S` | 18 | 0,11 | 0,11 | 0,17 |
| `I` | 2 | 0,00 | 0,00 | 0,00 |

### 7.7 El peldaño D por dentro

- **Enrutamiento: 49 de 49**, incluidos los 27 de los casos nuevos.
- **La consulta que escribe el enrutador** cambió el sentido en `n11-E` (escribió "merienda" donde la persona dijo "merida") y quitó las tildes en `n09-E` ("maquina de deporte multifuncion").
- **Verificador de `buscar_similares`:** revisó 160 candidatas en las 21 preguntas de similar y descartó 59 como exactas. Aceptó 5 alternativas en 20 de las 21.
- **Qué terminó en las pantallas de similar de D:** 101 productos, de los cuales 31 son `E`, 12 son `S` y 58 no etiquetados.
- **Afirmaciones falsas de D (6):** `g08-E`, `n02-E`, `n04-E`, `n05-E`, `n09-E` y `n11-E`. Cinco de las seis están en los casos nuevos.

### 7.8 Ablaciones de M1

`ABLACIONES_M1.ipynb`, corrido en la RTX 5060 Ti. Los tres splits reconstruidos tienen los mismos hashes de M1. Test: 92.739 pares, 3.844 consultas.

| Variante | nDCG@10 | Δ vs. FT completo [IC 95%] | Parámetros | Peso |
|---|---|---|---|---|
| BM25 (M1) | 0,7508 | — | 0 | índice |
| E5-small congelado (M1) | 0,7885 | — | 0 | 448,8 MB |
| **E5-small FT completo (M1)** | **0,8369** | referencia | 117,6 M | 448,8 MB |
| E5-small LoRA r=8 | 0,8305 | -0,0065 [-0,0095; -0,0034] | 148 K (0,13%) | **0,57 MB** |
| E5-base FT completo | 0,8459 | +0,0089 [+0,0055; +0,0125] | 278 M | 1.060,7 MB |

**Lectura:** LoRA recupera el **87%** de la ganancia del fine-tuning completo con un adaptador **785× más liviano**. E5-base gana por poco (+0,0089), a costa de 2,4× los parámetros y 3,3× el tiempo.

---

## 8. Lectura honesta

### Qué movió cada técnica

1. **Búsqueda híbrida (A→B).** +0,162 [0,080; 0,247] en nDCG de existencia. Cuesta 0,15 s por pregunta. Sube las afirmaciones falsas de 7 a 9.
2. **Reranker de M1 (B→C).** +0,175 [0,101; 0,255] en nDCG de existencia y +0,143 [0,000; 0,286] en aciertos, sin costo de latencia (0,012 s). Baja las afirmaciones falsas de 9 a 3. Su costo: el context recall baja de 0,512 a 0,372.
3. **Herramientas (C→D).** En el promedio no se distinguen del azar. Lo que sí generaliza: enrutamiento (49/49) y abstención adversarial (6/6). Lo que no generaliza: en los casos nuevos D queda por debajo de C en nDCG de existencia (-0,147 [-0,300; -0,010]).
4. **El sistema completo (A→D).** +0,273 [0,145; 0,409] en nDCG de existencia y +0,265 [0,102; 0,429] en aciertos.

### Lo que dice RAGAS junto con el scorecard

La faithfulness sube a lo largo de la escalera (0,866 a 0,940): las respuestas se pegan al contexto. La context precision también sube (0,633 a 0,848). El context recall es el más alto en B (0,512) y baja con el reranker (0,372).

### Qué costó en latencia

La generación domina (1,40-2,02 s). La recuperación híbrida cuesta 0,15 s y el reranker 0,012 s. D agrega enrutamiento (0,595 s) y verificador (0,371 s), pero se ahorra la generación al abstenerse.

### Análisis de errores

| Patrón de error | Ejemplos | Causa raíz | Sistemas |
|---|---|---|---|
| Consulta reescrita mal por el enrutador | n11-E: "merida"→"merienda"; n09-E: quita tildes | Modelo de 1,5B generaliza mal con consultas no vistas | Solo D |
| Afirmación falsa de existencia | g08-E: filtro de aceite por gasoil | El pool no tiene el título correcto; el reranker lee solo títulos | A, B, C, D |
| Similares devuelve complementos u homónimos | Switches HDMI para "parecido a Matrix" | Reranker binario no distingue S de C/I | D |
| Sustitutos con score de exacto | Redmi Note 7 de otro color tiene score ≥ umbral | Los sustitutos ESCI son variantes del mismo producto | C, D |

**Casos concretos:**
- **g08-E** (filtro gasoil Renault Trafic): falla en los 4 sistemas. Los filtros correctos no dicen "Renault Trafic" en el título.
- **n11-E** (productos de Mérida): D lo rompe porque el enrutador escribió "merienda". nDCG pasa de 0,753 en C a 0 en D.
- **n09-E** (máquina de deporte): el enrutador quitó tildes y BM25 no lematiza.

### Qué falla queda pendiente

1. **La consulta del enrutador** pierde información en casos no vistos. La corrección obvia: que la búsqueda use la pregunta del comprador, no la reescritura.
2. **Similares: 1/21.** El reranker binario no distingue sustitutos. El arreglo de fondo: reentrenar con `S` como clase propia. Queda para M4 o M5.
3. **Afirmaciones falsas en D (6).** `g08-E` falla en los 4 sistemas.
4. **La Dimensión 2 no cubre similares**, y la fórmula 1-5 sigue sin poder validarse (rango medio 1,50).
5. **Todo lo ajustado mirando los casos de M2** no generaliza del todo a los casos nuevos.

---

## 9. Cambios hechos después de ver resultados

Las corridas anteriores sacaron a la luz fallas de diseño. Todo se decidió **después de ver resultados sobre el mismo eval set**, y por eso se declara aquí.

### Fallas corregidas

| Qué falló | Por qué | Qué se cambió |
|---|---|---|
| `buscar_similares` no devolvió nada (D se abstuvo en las 9 de similar) | el umbral de similar quedó por encima del de exacto (0,9121 vs 0,5993) | el piso separa la misma categoría de C e I, calibrado solo bajo el umbral de exacto |
| El enrutador mandó a similares dos preguntas de existencia y escribió consultas sin el tipo de producto | reglas generales sin ejemplos para un modelo de 1,5B | reglas nuevas y seis ejemplos (ajuste hecho mirando el eval set) |
| `buscar_similares` mostraba complementos y homónimos | los sustitutos tienen puntaje de exacto y quedaban excluidos | verificador de exacto con la rúbrica del juez de M2 |
| D solo citaba el identificador en 8 de 18 respuestas | el generador de 1,5B no siempre sigue la instrucción | paso de presentación sin LLM: inserta título corto antes de cada ID |

### Lo que se quitó por no ser obligatorio

| Pieza | Qué pasó |
|---|---|
| Peldaño C+R, reescritura de la consulta | bajó el nDCG en la primera corrida; con prompt corregido, el IC cruzaba el cero |
| Comparación de chunking (`titulo` vs `ficha`) | empate práctico (0,162 vs 0,163) |
| Comparación de cuatro rerankers en C | los intervalos se solapaban |
| Librería `ragas` y DSPy | el endpoint respondió 403 de Cloudflare |
| Registro en W&B y comparación RAG vs sin RAG | extras no obligatorios |

---

## 10. Limitaciones declaradas

1. **28 casos y 49 preguntas.** Un delta cuyo IC 95% cruza el cero no se distingue del azar.
2. **Productos sin etiquetar** cuentan como no relevantes aunque puedan serlo.
3. **La vara del equipo es parcial.** Solo 50 pares están auditados por personas.
4. **"Similar" sale de un modelo binario.** No distingue `S` de `C`/`I` (exactitud balanceada 0,506).
5. **La Dimensión 2 no aplica a similar** (decisión del equipo).
6. **Decisiones tomadas mirando el eval set** (declaradas en §9).
7. **El delta C→D mezcla cuatro cosas.**
8. **El modelo evaluador se usa dentro del sistema.** Qwen2.5-3B es juez y verificador.
9. **El reranker lee solo el título.**
10. **Generador y juez de M2 son Qwen**; por eso RAGAS usa Phi.
11. **ESCI no trae fecha por ficha.**
12. **El catálogo sigue siendo de Amazon España.**

---

*Generado el 27 de septiembre de 2026.*
