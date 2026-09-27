# TODO — Lo que falta para un 20/20 perfecto en la rúbrica de M3

> Análisis criterio por criterio contra la rúbrica. Se marca con ✅ lo que ya está, con ⚠️ lo que está parcial, y con ❌ lo que falta.

---

## 1. Corpus: procedencia y responsabilidad (apunta a Nivel 4 — 5/5)

### ✅ Ya está
- **Origen documentado:** ESCI de Amazon, se menciona en README §Arquitectura y en el notebook.
- **Licencia:** Apache 2.0 (implícita por ser ESCI público).
- **Quién responde:** el equipo, con el catálogo heredado de M1.

### ⚠️ Parcial / Mejorable
- [ ] **Licencia explícita.** El README no dice "Apache 2.0" con esas palabras. Agregar una línea en §Arquitectura o en una sección nueva "Corpus" que diga: _"El corpus es el dataset ESCI de Amazon (Shopping Queries Dataset), publicado bajo licencia Apache 2.0 en [enlace al paper/repo]."_
- [ ] **Vigencia.** Se menciona que "ESCI no trae fecha por ficha" (limitación 11) y que es "el catálogo de Amazon España" (limitación 12), pero no hay una declaración directa de vigencia tipo: _"Los datos fueron recopilados por Amazon circa 2022; no se actualizan y pueden contener productos descontinuados o precios obsoletos."_
- [ ] **Qué pasa si el corpus está mal.** Se aborda en las limitaciones 2, 3 y en la lectura honesta (productos sin etiquetar, vara parcial), pero conviene consolidar en un párrafo dedicado: _"Si el corpus está sesgado (e.g., sobrerrepresenta ciertas categorías) o desactualizado, el sistema puede: (a) no encontrar productos que ya existen, (b) recomendar productos descontinuados, (c) heredar sesgos de las etiquetas ESCI."_

### Recomendación
Agregar una subsección **"Corpus: procedencia, licencia y riesgos"** al README con 3-4 párrafos que consoliden todo lo anterior. Es lo que más fácilmente separa un Nivel 4 de un Nivel 3.

---

## 2. Técnicas avanzadas de retrieval (apunta a Nivel 4 — 5/5)

### ✅ Ya está
- **Dos técnicas implementadas:** búsqueda híbrida (BM25 + densa con RRF) y reranking (cross-encoder de M1).
- **Delta medido contra el RAG ingenuo:** bootstrap pareado, deltas con IC 95% (A→B +0,162, B→C +0,175).
- **Escalera de sistemas** con una sola pieza cambiada por peldaño.
- **Tabla de deltas** con latencia (`Resultados/deltas_m3.csv`).

### ✅ Completo
Este criterio ya está en Nivel 4. No hay gaps significativos.

### Mejora opcional (no necesaria para el 5/5)
- [ ] La query transformation (reescritura) se intentó y se descartó por no mejorar significativamente. La documentación de ese intento ya está en "Cambios hechos después de ver resultados". Podría mencionarse brevemente que se exploró una tercera técnica como evidencia de rigor.

---

## 3. Integración de tool use (apunta a Nivel 4 — 5/5)

### ✅ Ya está
- **Dos herramientas:** `verificar_existencia` y `buscar_similares`.
- **Criterio explícito de invocación:** el enrutador con reglas decide cuándo invocar cada una.
- **Manejo de fallas:** abstención con frase de escape cuando la herramienta no devuelve resultados.
- **Documentación de qué pasa si falla:** "sin herramienta no hay fuente, y sin fuente no se responde".

### ✅ Completo
Este criterio ya está en Nivel 4. La documentación es clara y el comportamiento ante fallas está definido.

### Mejora opcional
- [ ] Podrían documentarse más explícitamente los casos de falla observados (e.g., "en N de 49 preguntas la herramienta no devolvió nada y el sistema se abstuvo correctamente"). Esto ya se menciona en el scorecard (D se abstiene en las 6 adversariales), pero un resumen dedicado en el README reforzaría.

---

## 4. Evaluación con RAGAS + harness propio (apunta a Nivel 4 — 5/5)

### ✅ Ya está
- **Las cuatro métricas RAGAS:** faithfulness, context precision, context recall, answer relevancy.
- **Cálculo a mano** con funciones del Lab C y juez Phi-3.5.
- **Cruce con el harness propio:** la lectura honesta cruza RAGAS con el scorecard (e.g., "la context precision sube pero el context recall baja con el reranker").
- **Análisis de dónde falla:** similares (1/21), afirmaciones falsas (6 en D), consulta del enrutador, limitaciones del reranker binario.

### ⚠️ Parcial / Mejorable
- [ ] **Cruce más explícito RAGAS ↔ harness.** La lectura honesta menciona las métricas RAGAS en un párrafo ("Lo que dice RAGAS junto con el scorecard"), pero podría beneficiarse de una **tabla de cruce** que muestre, para cada sistema, las métricas RAGAS junto a las métricas del scorecard lado a lado, con una columna de "interpretación" que explique la relación.
- [ ] **Análisis de errores por caso.** Se analizan los patrones de falla (similares, afirmaciones falsas), pero no hay un análisis caso por caso tipo: _"g08-E falla en los 4 sistemas porque el pool no tiene el título correcto; n11-E falla en D porque el enrutador cambió 'merida' por 'merienda'."_ Algo de esto está disperso en "El peldaño D por dentro" y la lectura honesta, pero un resumen consolidado lo haría más claro.

### Recomendación
Agregar al README o al notebook una subsección **"Cruce RAGAS ↔ scorecard"** con una tabla comparativa y 3-4 viñetas de análisis de errores concretos. Ya tienen la información; solo falta consolidarla.

---

## Resumen de acciones priorizadas

### 🔴 Prioridad alta (diferencia entre Nivel 3 y Nivel 4)
1. **Corpus: agregar sección dedicada** con licencia explícita (Apache 2.0), vigencia (~2022, no se actualiza), y párrafo de riesgos si el corpus está mal.

### 🟡 Prioridad media (refuerza el Nivel 4)
2. **Cruce RAGAS ↔ scorecard:** tabla comparativa y análisis de errores concretos consolidado.
3. **Análisis de errores por caso:** consolidar los ejemplos que ya están dispersos.

### 🟢 Prioridad baja (ya está cubierto, solo pulir)
4. Mencionar la query transformation como tercera técnica explorada (ya está en "Cambios").
5. Resumen de abstenciones y fallas de herramientas (ya está en scorecard).

---

## Estado estimado actual

| Criterio | Nivel estimado | Puntos | Gap para Nivel 4 |
|---|---|---|---|
| Corpus | **3-4** | 3.5-5 | Falta consolidar licencia, vigencia y riesgos |
| Técnicas avanzadas | **4** | 5 | Completo |
| Tool use | **4** | 5 | Completo |
| Evaluación RAGAS + harness | **3-4** | 3.5-5 | Falta tabla de cruce explícita |
| **Total estimado** | | **17-20 / 20** | |

> **Acción mínima para asegurar el 20/20:** resolver los puntos 🔴 y 🟡 (la sección de corpus dedicada y la tabla de cruce RAGAS ↔ scorecard).
