# Plantilla de definición del proyecto integrador

**Proyecto:** Digitdeck — copiloto de calidad de búsqueda para ecommerce en español
**Curso:** Tópicos Especiales y Aplicaciones en IA · SI4006 · Universidad EAFIT · 2026-2
**Equipo:** Maximiliano Bustamante · Valeria Frances Hornung · Sebastián Castaño · Alejandro Posada
**Repositorio:** https://github.com/AlejandroSPosada/Topicos_IA_Proyecto_Digitdeck

> **Estado:** diligenciados los campos 1 a 4. Los campos 5 a 8 quedan con su encabezado
> para completarse en los módulos siguientes.

---

## 1. Dominio

> Búsqueda interna de producto en un ecommerce de retail en español. El foco no es el
> catálogo ni el checkout, sino un punto concreto del embudo: **el ordenamiento de resultados
> que devuelve el buscador del sitio cuando una persona escribe una consulta en lenguaje
> libre.** Cuando ese ordenamiento falla, el producto correcto existe en el catálogo pero
> queda fuera de la primera pantalla, y la venta se pierde sin dejar rastro visible.


---

## 2. Usuario + decisión

> **Si la respuesta a "qué decide el usuario con esto" es "se informa", el
> proyecto no está definido. Un sistema útil cambia una decisión concreta de
> una persona concreta.**

> **Usuario concreto:** el **líder de ecommerce** de la tienda. Es una persona, no un área:
> responde por la conversión del canal digital y tiene autoridad para cambiar cómo se
> presentan los productos. No es ingeniero, no lee código y no va a reentrenar nada.
>
> **Qué hace hoy, sin el sistema:** abre el reporte de consultas con más tráfico, ve cuáles
> tuvieron pocos clics, y revisa a mano las que alcanza en el tiempo que tiene. La selección
> la hace por volumen de tráfico y por intuición, porque no tiene forma de saber si el
> ordenamiento de una consulta está mal salvo mirándolo caso por caso. Consultas de cola
> larga con mal ordenamiento nunca llegan a su lista.
>
> **Qué decide distinto con Digitdeck:** **cuáles consultas intervenir y en qué orden.**
> El sistema puntúa la relevancia de cada par (consulta, producto) y le entrega dos cosas:
> la lista de consultas cuyo ordenamiento actual está por debajo del umbral de calidad, y
> para cada una, el reordenamiento que el modelo propone frente al que hoy muestra el sitio.
> Con eso, sobre cada consulta el líder toma una de tres decisiones: **aprobar** el
> reordenamiento propuesto, **corregir la ficha** del producto que quedó mal posicionado
> porque su título no describe lo que es, o **descartar** el caso porque el problema es de
> inventario y no de búsqueda.
>
> El cambio no es que se entere de que hay un problema: es que pasa de *"reviso las diez
> consultas más grandes que alcance esta semana"* a *"intervengo estas consultas concretas,
> priorizadas por cuánto mejora su ordenamiento, con una acción propuesta para cada una"*.
>
> **Alcance en M1:** este módulo construye únicamente el motor de scoring que hace posible
> esa priorización. La interfaz donde el líder aprueba o descarta, y la trazabilidad de cada
> recomendación, se construyen en los módulos siguientes.
>
> **Advertencia que M1 ya dejó documentada:** en el 20,7% de las consultas del test hay 5
> productos relevantes o menos, y ahí la métrica de calidad de ordenamiento es inestable. La priorización que vea el líder no puede basarse en el nDCG de una
> sola consulta aislada; ese es un requisito de diseño para el módulo de interfaz.

---

## 3. Tarea del modelo (M1)

> **Clasificación binaria de pares (consulta, título de producto):** dado el par, predecir si
> ese producto es relevante para esa consulta.
>
> Se implementa como **fine-tuning del encoder `intfloat/multilingual-e5-small`** (118 M
> parámetros, multilingüe, licencia MIT) con una **cabeza de clasificación de dos clases**
> sobre el token de agregación. Las entradas llevan los prefijos que el modelo exige por
> diseño: `query: ` para la consulta y `passage: ` para el título del producto, tanto en
> entrenamiento como en inferencia.
>
> **Del clasificador al ranking:** la **probabilidad de la clase "relevante"** (softmax sobre
> los logits) se usa como score continuo para ordenar los productos candidatos de cada
> consulta. Por eso la métrica primaria del módulo es de ranking, **nDCG@10**, y no accuracy:
> al líder de ecommerce no le sirve saber qué porcentaje de pares se clasificó bien, le sirve
> que los productos correctos queden arriba. Accuracy y F1 se reportan como diagnóstico
> secundario.
>
> **Mapeo de etiquetas ESCI a binario:**
>
> | ESCI | Significado | Etiqueta |
> |---|---|---|
> | `E` (Exact) | Responde directamente la consulta | relevante (1) |
> | `S` (Substitute) | Producto alternativo | no relevante (0) |
> | `C` (Complement) | Producto complementario | no relevante (0) |
> | `I` (Irrelevant) | Sin relación | no relevante (0) |
>
> **Contra qué se compara:** dos baselines medidos sobre el mismo split y el mismo
> presupuesto de GPU. **BM25**, que es el techo léxico y lo que un buscador de sitio suele
> usar hoy; y **E5-small congelado**, sin entrenar, que separa cuánto aporta el encoder
> pre-entrenado de cuánto aporta el fine-tuning. Sin el congelado no se puede afirmar que la
> mejora vino de entrenar.
>
> **Resultado obtenido en M1** (test: 92.739 pares, 3.844 consultas):
>
> | Sistema | nDCG@10 | MRR | Recall@10 |
> |---|---|---|---|
> | BM25 | 0,7508 | 0,8258 | 0,5877 |
> | E5-small congelado | 0,7885 | 0,8685 | 0,6121 |
> | E5-small ajustado | **0,8369** | **0,9091** | **0,6445** |
>
> El efecto neto del fine-tuning, aislado del pre-entrenamiento, es **+0,0485 de nDCG@10
> sobre el congelado** (6,1% relativo). La lectura completa está en §4.10 del notebook.

---

## 4. Dataset + licencia

> **Amazon Shopping Queries Dataset (ESCI)**, publicado por Amazon Science en
> https://github.com/amazon-science/esci-data. **Licencia Apache 2.0**, que permite uso y
> redistribución incluyendo fines comerciales, con atribución. Es la razón por la que se
> eligió sobre alternativas con licencia restringida: el proyecto puede versionarse en un
> repositorio público sin problema legal.
>
> **Qué se usa:** el subconjunto con `product_locale == 'es'`. Son **15.180 consultas únicas y
> 356.410 pares consulta-producto** antes de limpiar, y **354.288 pares** después. El balance
> tras el mapeo binario es 56,7% relevante y 43,3% no relevante.
>
> **Campos:** `query`, `product_title`, `product_locale`, `esci_label`, `split`.
>
> **Limpieza aplicada** (reproducible, en la sección 2.3 del notebook): descarte de nulos,
> descarte de títulos de menos de 3 palabras (2.122 pares), deduplicación de pares, paso a
> minúsculas y colapso de espacios.
>
> **Splits:**
>
> | Split | Pares | Consultas | Origen |
> |---|---|---|---|
> | train | 235.354 | 10.203 | split `train` de ESCI menos el 10% de consultas de validación |
> | validación | 26.195 | 1.133 | 10% de las **consultas** de train, semilla 42 |
> | test | 92.739 | 3.844 | split `test` de ESCI, sin tocar |
>
> Train y test vienen predefinidos en el dataset y se respetan. La validación se separa del
> train **por `query_id`**, no por par, para que ninguna consulta aparezca en dos splits y no
> haya fuga de información; el notebook lo verifica con un `assert` y reporta cero consultas
> compartidas. La selección del checkpoint se hace por pérdida en validación; **el split de
> test no participa en ninguna decisión de entrenamiento.**
>
> **Reproducibilidad:** semilla fija `SEMILLA = 42` y hash MD5 por split, para que cualquiera
> pueda regenerar exactamente los mismos datos.
>
> | Split | Hash MD5 |
> |---|---|
> | train | `e5f8baa5f301d5c5cbc2bdb79c7dfff5` |
> | validación | `ee5ffaeedf8796119758c32670304dc1` |
> | test | `4d31950e81340999c4cbda611b4256c9` |
>
> **Limitaciones conocidas**, declaradas en la sección 2.8:
>
> 1. El catálogo es de Amazon, no de la tienda del caso de estudio. El vocabulario de marcas
>    y categorías no es idéntico al de un retailer local.
> 2. El mapeo binario colapsa `S`, `C` e `I` en una sola clase, y con eso se pierde el matiz
>    entre "producto sustituto razonable" y "producto sin ninguna relación". **M1 encontró
>    evidencia de que esta simplificación está costando métrica**: en varias consultas donde el
>    modelo ajustado pierde, lo que pone arriba son sustitutos razonables etiquetados como no
>    relevantes (§4.9). La verificación pendiente es recalcular nDCG@10 con relevancia graduada
>    (`E`=3, `S`=2, `C`=1, `I`=0) sobre los mismos scores ya guardados.
> 3. Hay desbalance de clases hacia "relevante" (56,7%); se compensa con pesos por frecuencia
>    inversa en la pérdida: 1,186 para "no relevante" y 0,864 para "relevante".
> 4. Solo se usa el **título** del producto, truncado a 64 tokens. Descripción, categoría,
>    marca, precio y atributos quedan fuera de M1 y son la vía natural de mejora para los
>    módulos siguientes.

---

## 5. Métrica de éxito

<!-- Ejemplo: F1 macro > 0.80 en enrutamiento; y que el funcionario acepte la
sugerencia en ≥ 70% de los casos en la prueba con usuarios. -->

> _¿Cómo mides que el sistema sirve? Métrica técnica y señal de valor real._

---

## 6. Componente visual (M4)

<!-- Ejemplo: leer el documento escaneado que adjunta el ciudadano y verificar
que corresponde al trámite. -->

> _¿Qué aporta el componente multimodal/visual del Módulo 4 al sistema?_

---

## 7. Riesgos éticos

<!-- Ejemplo: sesgo contra solicitudes mal redactadas; riesgo de negar un
trámite por un error del modelo. Mitigación: el sistema sugiere, el funcionario
decide. -->

> _¿Qué puede salir mal para una persona real? ¿Cómo lo mitigas?_

---

## 8. Compromisos del equipo

<!-- Ejemplo: reuniones los martes; repositorio compartido; cada integrante es
dueño de un módulo pero todos revisan. -->

> _¿Cómo se organizan? ¿Quién responde por qué? ¿Cómo se comunican?_
