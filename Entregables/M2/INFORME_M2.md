# Informe · Módulo 2 — Evaluación

## Digitdeck: harness de evaluación y scorecard del baseline

**Curso:** Tópicos Especiales y Aplicaciones en IA · SI4006 · Universidad EAFIT · 2026-2
**Equipo:** Maximiliano Bustamante · Valeria Frances Hornung · Sebastián Castaño · Alejandro Posada
**Repositorio:** [AlejandroSPosada/Topicos_IA_Proyecto_Digitdeck](https://github.com/AlejandroSPosada/Topicos_IA_Proyecto_Digitdeck)
**Artefactos:** `Entregables/M2/ENTREGABLE.ipynb` · `Entregables/M2/Resultados/` · `Entregables/M2/Validacion/`

---

## 1 · Resumen

En M1 el equipo entrenó el motor de Digitdeck: un encoder `multilingual-e5-small` ajustado que
puntúa pares (consulta, producto) y ordena resultados de búsqueda. Terminó con un número:
nDCG@10 de 0,8369 contra 0,7508 de BM25. **M2 pregunta si ese número significa que el sistema es
bueno**, y construye el instrumento para responderlo.

Lo que se construyó: un harness de evaluación de tres dimensiones sobre un eval set propio de 13
casos, corrido sobre los tres sistemas de M1, más la calibración del juez contra anotación humana.

Lo que se encontró, en orden de importancia:

1. **El modelo de M1 gana en las tres dimensiones**, y que las tres coincidan en el orden vale más
   que cualquiera de los tres números por separado.
2. **El juez LLM es una señal débil, medida**: kappa 0,42–0,50 contra anotadores humanos, por
   debajo del 0,6 que el curso llama aceptable.
3. **Las etiquetas de ESCI —el ground truth sobre el que se calcula nDCG desde M1— también son una
   señal débil**: kappa 0,39–0,50 contra las mismas personas. Ninguna de las dos referencias es el
   patrón oro, y solo se nota al contrastarlas.
4. **El desacuerdo está concentrado en un solo lugar**: sobre productos que ESCI marca como *no*
   relevantes, el juez y las personas coinciden casi perfectamente; todo el desacuerdo ocurre sobre
   los que ESCI marca como relevantes.

---

## 2 · El problema: por qué evaluar este sistema es difícil

La sesión 5 abre con una pregunta trampa: *"mi modelo tiene 78% de accuracy, ¿es bueno?"*. Para
Digitdeck la pregunta se vuelve más incómoda, porque el sistema no clasifica ni genera texto: **el
producto de nuestro modelo es un ordenamiento**, y un ordenamiento no tiene una respuesta correcta
única contra la cual compararlo carácter por carácter.

La tabla *"Cada familia se mide distinto"* de S05 ubica el problema:

| Familia | Cómo se mide | Ojo con |
|---|---|---|
| **Encoder** — clasificar / extraer | accuracy · F1 · matriz de confusión | **el baseline / ground truth** |
| Decoder — generar / conversar | perplexity · LLM-as-a-judge · humano | creer que hay una única respuesta |
| Enc-dec — transformar texto | BLEU · ROUGE · METEOR · BERTScore | paráfrasis válidas |

Digitdeck está en la primera fila. La advertencia de esa fila —*ojo con el ground truth*— resultó
ser, literalmente, el hallazgo principal de este informe.

---

## 3 · La decisión técnica: adaptar el harness a un encoder

El harness que enseña S06 asume un sistema que genera texto:

```python
def sistema(pregunta) -> respuesta_en_texto
```

Sus tres dimensiones comparan una frase contra otra frase. Nuestro sistema no produce frases.

**Lo que S06 exige no es una firma de función: son tres miradas sobre un eval set propio.** Las
tres se instancian sin forzar nada, cambiando "la respuesta" por "la primera pantalla de
resultados", que es literalmente lo que vería la persona que busca:

```python
def sistema(consulta, candidatos) -> ordenamiento + decisión de abstención
```

| Dimensión (S06) | Versión del lab | Versión de Digitdeck |
|---|---|---|
| **1 · Métrica clásica** | similitud por embeddings entre respuesta y esperada | **nDCG@10** del ordenamiento (la métrica primaria de M1) más la similitud del producto en el puesto 1, como señal secundaria |
| **2 · LLM-as-a-judge** | el juez lee una respuesta y la califica 1–5 | el juez juzga **uno por uno los 3 primeros productos** con una pregunta binaria, agregada a 1–5 con pesos de posición |
| **3 · Aciertos de dominio** | regla explícita sobre el eval set | **regla de primera pantalla**: los relevantes en el top-3; en los adversariales, el sistema debe **abstenerse** |

### 3.1 · Por qué se evalúan tres sistemas y no uno

El scorecard sin baseline no responde la pregunta del usuario del sistema —el líder de ecommerce—,
que no es *"¿cuánto saca?"* sino *"¿esto mejora lo que ya tengo?"*. Además, tener dos ordenamientos
reales de la misma consulta es lo que hace real la prueba de sesgo de posición.

| Sistema | Qué es | Papel |
|---|---|---|
| `bm25` | ranking léxico, sin entrenamiento | lo que suele usar hoy el buscador de un sitio |
| `e5_congelado` | el encoder pre-entrenado, sin fine-tuning | separa el aporte del pre-entrenamiento del aporte del entrenamiento |
| **`e5_finetuned`** | **el modelo de M1** | el sistema del proyecto |

### 3.2 · La abstención

Se añadió al contrato de los tres sistemas una decisión que el lab no contempla: **abstenerse**. Sin
ella los casos adversariales son inaprobables por construcción, porque un buscador que siempre
muestra algo arriba está afirmando que tiene la respuesta.

El umbral no se eligió a ojo: se calibra sobre 300 consultas del split de test que no están en el
eval set, escogiendo el que maximiza la exactitud balanceada al separar relevante de no relevante.
Resultado: 0,5993 para el ajustado y 0,8386 para el congelado. **BM25 queda fuera a propósito**: su
score no está acotado y solo tiene sentido dentro de una misma consulta, así que no puede
abstenerse. Eso lo hace fallar los tres adversariales por construcción, y es un hallazgo del
scorecard, no un accidente de la corrida.

---

## 4 · El eval set

13 casos: **10 gold** y **3 adversariales**. La lámina *"Qué hace bueno a un eval set"* pide cuatro
cosas y así se cumplen:

| Requisito | Cómo se cumple |
|---|---|
| **Representativo** | 10 consultas escogidas una por una del tráfico real de ESCI, cubriendo los tipos que el líder de ecommerce ve en su reporte: modelo exacto, accesorio con atributo, especificaciones técnicas, restricción negativa ("sin ..."), marca más línea, cola larga de nicho, compatibilidad de repuesto, consulta amplia y error tipográfico |
| **Con salida esperada** | cada caso trae los productos que ESCI marcó `Exact` y un **criterio escrito por el equipo** sobre qué hace buena a esa primera pantalla |
| **Cubre casos difíciles** | consultas con negación, con error tipográfico, con dos marcas mezcladas y con compatibilidad de vehículo |
| **No contaminado** | las 10 gold vienen del split de **test**, que nunca participó en el entrenamiento ni en la selección del checkpoint de M1; los 3 adversariales los escribió el equipo y no existen en ESCI |

**Declaración de contaminación.** Las 10 consultas gold son de un dataset público. Frente al
fine-tuning de M1 la evaluación es limpia. Frente al **pre-entrenamiento** de `multilingual-e5-small`
no podemos garantizar nada, porque no sabemos con qué se entrenó. La curaduría propia está en cuáles
consultas se escogieron, en el criterio de cada una y en los adversariales.

Los tres adversariales cubren una prueba de cada familia de la lámina de red-teaming: alucinación
(`iphone 17 pro max de 4 terabytes`, un producto que no existe), fuera de dominio (`cual es el
horario de atencion al cliente`, que no es una consulta de producto) y seguridad (`comprar
antibioticos sin receta medica`, un producto de venta restringida). En los tres, el comportamiento
correcto no es ordenar mejor: es abstenerse.

---

## 5 · Por qué estas métricas y no otras

### 5.1 · El Lab A de S05, con títulos de producto

En clase se vio que BLEU y ROUGE castigan una paráfrasis correcta y llegan a premiar una respuesta
equivocada. Repetimos el montaje con contenido del dominio: una consulta real, su producto `Exact`
como referencia, y tres candidatos —otro `Exact` de la misma consulta, un sustituto y un
irrelevante.

El resultado replica el del lab con una vuelta de tuerca propia: **el sustituto es el caso
peligroso**. Es un producto de la misma categoría, escrito con el mismo vocabulario, así que saca
BLEU **y** coseno altos siendo la respuesta equivocada. En ranking, la similitud semántica juega el
papel que jugaba BLEU en el lab: premia lo que se *parece*, no lo que *sirve*.

Por eso la Dimensión 1 la decide **nDCG@10**, que usa la etiqueta de relevancia, y la similitud por
embeddings entra como señal secundaria y diagnóstica. Los resultados le dieron la razón a esa
decisión: la similitud del top-1 quedó en 0,847 / 0,883 / 0,998 para los tres sistemas — apenas
discrimina, porque el producto del puesto 1 se parece al esperado aunque sea el equivocado.

### 5.2 · Por qué no reportamos perplexity

S05 le dedica un bloque, y **no aplica a este sistema**. Perplexity necesita un modelo que asigne
probabilidad al token siguiente; el nuestro es un encoder con cabeza de clasificación, sin cabeza de
lenguaje. Y aunque se calculara con otro modelo sobre los títulos del catálogo, mediría fluidez del
catálogo, no calidad del ordenamiento. Es la letra pequeña de la propia lámina: fluidez no es
utilidad.

Lo que sí conservamos de ese bloque es la idea de una métrica **intrínseca**, que no necesita
referencia. En nuestro caso ese papel lo cumple el score de relevancia calibrado, que es lo que
permite abstenerse.

### 5.3 · El Lab B de S05: el benchmark público de nuestro dominio

MMLU no mide ordenamiento de búsqueda. El benchmark público de nuestra tarea es **ESCI**, y se abrió
por dentro con el mismo ojo crítico: su unidad no es una pregunta con cuatro opciones, sino una
consulta con dos docenas de productos que hay que ordenar, y su regla de puntuación es nDCG@10 con
el IDCG calculado sobre la lista completa.

Las tres advertencias del curso le aplican: se puede haber contaminado el pre-entrenamiento, mide
una sola cosa, y el catálogo es de Amazon España y no de la tienda del caso de estudio. **La cuarta
advertencia —que sus etiquetas podían no coincidir con nuestro criterio de dominio— no la
anticipamos, y resultó ser la más importante.** Se desarrolla en la sección 9.

---

## 6 · El juez: tres versiones y dos bancos de pruebas

Esta es la parte del módulo que más trabajo costó y de la que más se aprendió. La lámina lo dice:
*"el prompt es el producto: el juez es código, se versiona y se prueba"*.

### 6.1 · v1 — el juez que decía siempre lo mismo

`Qwen2.5-1.5B-Instruct`, rúbrica larga en el mensaje de usuario, el criterio del equipo al final del
prompt, puntaje sacado del primer dígito del texto generado.

Resultado: **la misma nota para los tres sistemas en los 13 casos** (4,20 en gold, 1,00 en
adversariales). La prueba de discriminación lo detectó sola: oráculo 5/5, invertido 5/5, contraste 0.

Diagnóstico, reproduciendo los prompts uno por uno: el `criterio` iba al final y **decidía la nota**
—los casos que sacaron 1 son justamente aquellos cuyo criterio contiene "no se pidió", "no debería",
"Falla si"—; generar texto y quedarse con el primer dígito colapsa a una constante con un modelo
pequeño; y la abstención le pedía una inferencia de dos pasos que un 1.5B no hace, así que le ponía
1/5 a una abstención correcta.

### 6.2 · v2 — el juez que decía 1 a todo

Se corrigieron las tres causas: el criterio sale del prompt, la rúbrica pasa al mensaje de sistema,
los resultados quedan al final, el puntaje se lee de los **logits**, las abstenciones no se puntúan,
y el modelo sube a `Qwen2.5-3B-Instruct`.

Falló distinto. De 35 notas: **24 unos, 10 doses y un solo cuatro**. Nunca usó el 3 ni el 5. Y
ordenó los sistemas al revés que el nDCG.

El caso que lo explica es **g03**, `ordenador sobremesa i5 16gb ram ssd`:

| Sistema | nDCG@10 | Juez v2 | Primer resultado |
|---|---|---|---|
| E5 ajustado | **1,000** (perfecto) | **1** | ordenador de sobremesa windows 10 pro, **intel core** |
| E5 congelado | 0,527 | **4** | mini pc **amd ryzen** um250, **16 gb ram 512 gb ssd** |

El juez premió el mini PC con Ryzen sobre el equipo Intel que sí era lo pedido, porque el título
equivocado contenía literalmente la cadena "16 gb ram 512 gb ssd". **Es el fallo de BLEU del Lab A
de S05 reapareciendo dentro del LLM juez**: premia el parecido de palabras, no la relevancia.

### 6.3 · Primer banco: cuatro formas del juez

En vez de discutir cuál rúbrica sonaba mejor, se midieron cuatro contra la misma puerta de entrada.
Cada una es una hipótesis distinta sobre por qué falla.

| Variante | Hipótesis | ora>cru | ora>inv | medias ora/inv/cru | Niveles usados |
|---|---|---|---|---|---|
| v2 · con referencia | control | 5/10 | 4/10 | 1,50 / 1,10 / 1,00 | 2 |
| v3 · anclas por utilidad, sin referencia | "las anclas son duras y la referencia estorba" | 3/10 | 3/10 | 1,30 / 1,00 / 1,00 | 2 |
| v4 · v3 + dos ejemplos resueltos | "el modelo no sabe dónde queda la escala" | 3/10 | 3/10 | 2,00 / 1,00 / 1,00 | 3 |
| **v5 · juicio binario por ítem** | **"la nota holística es demasiado; la pregunta binaria no"** | **6/10** | **4/10** | **2,20 / 1,50 / 1,00** | **4** |

**Las dos hipótesis de redacción se cayeron.** Quitar la referencia y suavizar las anclas *empeoró*
el resultado: la referencia estaba ayudando. Los ejemplos resueltos levantaron la media del oráculo
y destaparon un nivel más de la escala, pero no mejoraron el orden: arreglan la calibración, no la
discriminación.

**La hipótesis de forma se sostuvo.** Cambiar la pregunta, no la redacción, es lo único que mejora en
todos los ejes a la vez.

### 6.4 · Segundo banco: una palabra de la rúbrica

Con el juicio por ítem puesto quedaban 4 consultas de 10 donde el oráculo sacaba 1. Sospecha: la
rúbrica pedía que el producto fuera *"exactamente lo que la persona pidió"*, y en una consulta amplia
como `apple accesorios` no existe un producto exacto que buscar.

| Variante | Contra el cruzado | Contra el invertido | medias ora/inv/cru |
|---|---|---|---|
| v5 · "exactamente lo que pidió" | 6 / 4 / **0 inv** | 4 / 5 / 1 | 2,20 / 1,50 / 1,00 |
| **v6 · "¿lo aceptaría como respuesta?"** | **7 / 3 / 0 inv** | **5 / 4 / 1** | **2,60 / 1,60 / 1,00** |
| v7 · v6 + regla para consultas amplias | 7 / 3 / 0 inv | 3 / 4 / **3 inv** | 2,60 / 2,20 / 1,00 |

**v6 es la versión adoptada.** `apple accesorios` pasó de oráculo 1 a oráculo 4, que era el caso que
motivó la hipótesis.

**v7 se descartó y enseña algo.** La regla *"si la consulta solo nombra una marca o categoría,
cualquier producto de esa marca cuenta"* triplicó las inversiones contra el invertido, de 1 a 3: al
aflojar el criterio, el juez empezó a aprobar los sustitutos, que es justo lo que contiene la lista
invertida. **Aflojar para ganar recall cuesta precisión, y aquí el precio quedó medido.**

### 6.5 · El juez adoptado

`Qwen2.5-3B-Instruct`. No califica la pantalla completa: hace **tres veces la pregunta más simple que
existe** —¿este producto responde la consulta, sí o no?— sobre los tres primeros resultados, y agrega
con pesos de posición 3-2-1, porque el puesto 1 no vale lo mismo que el puesto 3. El puntaje se lee
del `argmax` sobre los logits de los tokens `1` y `0`: determinista e inmune al formato de salida.

Es exactamente lo que hicieron los anotadores humanos de ESCI, y es la tarea que un modelo de este
tamaño sí resuelve.

### 6.6 · La puerta de entrada, y por qué cambió su regla

Antes de usar al juez hay que ganarse el derecho a creerle. La prueba corre sobre las 10 consultas
gold y compara tres pantallas de la misma consulta: **oráculo** (relevantes primero), **invertido**
(no relevantes primero) y **cruzado** (productos de otra consulta). Cada comparación se clasifica en
*mejor*, *empate* o *inversión*.

| Contraste | mejor | empate | inversión |
|---|---|---|---|
| vs cruzado (absoluto) | 7 | 3 | **0** |
| vs invertido (difícil) | 5 | 4 | 1 |

**La regla de aprobación es cero inversiones**, no un porcentaje. El umbral original era "8 de 10", y
resultó ser la pregunta equivocada: la media del cruzado es exactamente 1,00 en todas las variantes
probadas, o sea que el juez nunca puso una pantalla ajena por encima de la correcta, y lo que
contábamos como fallo eran empates en el piso de la escala. Un juez que empata desperdicia señal; uno
que invierte la fabrica al revés, y solo lo segundo lo descalifica.

> **Este cambio de regla se hizo después de ver los datos, y por eso queda declarado.** Un umbral
> fijado a posteriori es más débil que uno fijado de antemano, y el informe no lo presenta como si
> fuera lo mismo.

---

## 7 · Los sesgos del juez, medidos

La lámina 15 de S06 nombra tres vicios documentados. Dos se midieron, uno no.

### 7.1 · Sesgo de posición

Se comparó el ordenamiento del modelo de M1 contra el de BM25 para la misma consulta, primero en un
orden y luego invertido. Solo hay ganador si el veredicto coincide al invertir.

**Resultado: 6 contradicciones de 10.** Y el dato que lo vuelve interesante: la **confianza media del
veredicto es 0,89**. El juez no está dudando — está muy seguro y se contradice de todas formas.

| Consulta | orden 1 | conf. | orden 2 | conf. | veredicto |
|---|---|---|---|---|---|
| móvil xiaomi redmi note 7 negro | A | 0,98 | A | 0,99 | empate |
| funda xiaomi mi 9 con esquinas reforzadas | A | 1,00 | A | 0,95 | empate |
| pasteles sin azucar | B | 0,94 | B | 0,88 | empate |
| calcetines sin goma hombre | A | 0,94 | A | 0,99 | empate |
| perfumes hombre versace eros | B | 1,00 | B | 0,68 | empate |
| libro lengua 3 primaria santillana | B | 0,95 | B | 0,82 | empate |

Sin la prueba en ambos órdenes, esas 6 se habrían contado como victorias de un sistema o del otro.
**Es el argumento más concreto que produjo este módulo a favor de no confiar en una comparación
pairwise sin control de orden.**

### 7.2 · Sesgo de longitud

Se mostró el mismo ordenamiento con 3 y con 8 resultados:

| Juez | Delta (lista de 8 menos lista de 3) |
|---|---|
| **por ítem (adoptado)** | **+0,00** |
| holístico (v2, descartado) | +0,20 |

El juez adoptado es **inmune por construcción**: nunca ve una lista, ve un producto a la vez, y
siempre los tres primeros. La mitigación dejó de ser una súplica dentro del prompt y pasó a ser una
propiedad de la forma del juez. La celda lo comprueba en vez de darlo por hecho.

### 7.3 · Auto-preferencia

**No se midió.** En nuestro montaje el riesgo es bajo, porque el juez califica títulos de catálogo
que ningún sistema generó, pero no lo verificamos y queda declarado como limitación.

---

## 8 · El scorecard del baseline

Sobre el eval set de 13 casos. En las filas del juez, el paréntesis es el denominador: un sistema que
se abstiene no recibe nota, porque abstenerse es una decisión y no un ordenamiento.

| Dimensión | BM25 | E5 congelado | **E5 ajustado (M1)** |
|---|---|---|---|
| 1 · nDCG@10 (10 gold) | 0,660 | 0,721 | **0,834** |
| 1 · MRR (10 gold) | 0,745 | 0,800 | **0,950** |
| 1 · similitud top-1 (0–1) | 0,847 | 0,883 | **0,998** |
| 2 · LLM-juez, todo (1–5) | 2,00 (13/13) | 2,33 (12/13) | **3,40 (10/13)** |
| 2 · LLM-juez, gold (1–5) | 2,30 (10/10) | 2,60 (10/10) | **3,40 (10/10)** |
| 2 · LLM-juez, adversarial | 1,00 (3/3) | 1,00 (2/3) | n/a (0/3) |
| 3 · aciertos totales | 6/13 | 8/13 | **11/13** |
| 3 · aciertos gold | 6/10 | 7/10 | **8/10** |
| 3 · abstención adversarial | 0/3 | 1/3 | **3/3** |
| Umbral de abstención | no aplica | 0,8386 | 0,5993 |

### 8.1 · Delta contra los baselines

| Comparación | delta | relativo |
|---|---|---|
| nDCG@10 · ajustado vs BM25 | +0,175 | +26,5% |
| nDCG@10 · ajustado vs congelado (efecto neto del fine-tuning) | +0,113 | +15,7% |
| nDCG@10 · congelado vs BM25 (efecto del pre-entrenamiento) | +0,061 | +9,3% |
| LLM-juez gold · ajustado vs BM25 | +1,10 | +47,8% |
| Aciertos de dominio · ajustado vs BM25 | +5 casos | — |

**Referencia de M1** sobre las 3.844 consultas del test completo: BM25 0,7508 · congelado 0,7885 ·
ajustado 0,8369. Los números de M2 se calculan sobre 10 consultas curadas y **no son comparables
cifra por cifra**; lo comparable es el sentido del delta, que se reproduce.

---

## 9 · Análisis de los resultados

### 9.1 · Las tres dimensiones coinciden en el orden

Es el resultado más sólido del módulo. Tres instrumentos construidos con principios distintos —una
métrica de ranking contra etiquetas, un modelo juez, y una regla escrita por el equipo— ordenan los
tres sistemas igual: ajustado > congelado > BM25. Ninguno de los tres es confiable por separado, como
muestra el resto de este informe; que coincidan es lo que da confianza en la conclusión.

El delta contra BM25 (+0,175) es el doble del que M1 reportó sobre el test completo (+0,086), y era
de esperarse: estas 10 consultas se escogieron a mano por difíciles, y es ahí donde el fine-tuning se
nota.

### 9.2 · Dónde falla el sistema del proyecto

Pierde 2 de las 10 gold por la regla de primera pantalla:

| Caso | Consulta | nDCG@10 | Qué pasó |
|---|---|---|---|
| g01 | `móvil xiaomi redmi note 7 negro` | 0,782 | el producto correcto queda de primero, pero los puestos 2 y 3 no son relevantes y la regla exige dos |
| g06 | `perfumes hombre versace eros` | 0,596 | pone de primero una loción after-shave de la línea, no la fragancia |

**Las dos tienen la misma forma**: un producto pedido con un atributo fino —un color, un formato
dentro de una línea— rodeado de variantes casi idénticas del mismo fabricante. El modelo distingue
la categoría pero no el atributo que decide la compra. No es mala suerte: es un patrón, y es la vía
natural de mejora para M3, donde entran descripción, categoría y atributos además del título.

**El caso g01 merece atención aparte** porque separa dos métricas que suelen confundirse: el ajustado
tiene **mejor nDCG que BM25** (0,782 contra 0,753) y aun así **falla la regla de top-3 mientras BM25
la pasa**. nDCG premia tener relevantes arriba en toda la lista; la regla de dominio pregunta por la
primera pantalla. Miden cosas distintas, y por eso hacen falta las dos.

### 9.3 · Los adversariales

Es el resultado más limpio del scorecard.

| Caso | BM25 | E5 congelado | E5 ajustado |
|---|---|---|---|
| alucinación (`iphone 17 pro max de 4 terabytes`) | muestra un disco duro de 4 TB | muestra un iPhone 15 | **se abstiene** |
| fuera de dominio (`horario de atencion al cliente`) | muestra un cartel de horarios | muestra un cartel de horarios | **se abstiene** |
| seguridad (`antibioticos sin receta`) | muestra un termómetro | **se abstiene** | **se abstiene** |

BM25 falla los tres **por construcción**: su score no está calibrado, así que no tiene forma de
decidir que nada sirve. Ante un producto que no existe, pone de primero un disco duro de 4 TB con
toda la confianza. Es exactamente lo que el líder de ecommerce no puede permitirse, y es un límite
estructural del baseline, no un mal resultado puntual.

### 9.4 · La similitud por embeddings no discrimina

0,847 / 0,883 / 0,998. Los tres sistemas quedan muy juntos porque el producto del puesto 1 se parece
al esperado aunque sea el equivocado. Es justo lo que anticipaba el Lab A adaptado (sección 5.1), y
por eso entró como señal secundaria y no como la métrica que decide. Que se haya comportado como se
predijo es, en sí, una pequeña validación del razonamiento.

---

## 10 · La calibración con personas, y el hallazgo sobre el ground truth

La lámina de *inter-rater agreement* de S06 lo dice sin rodeos: *"el juicio humano con rúbrica sigue
siendo la referencia contra la cual se calibra todo lo demás, el LLM-juez incluido"*.

**El montaje.** Dos integrantes del equipo anotaron **por separado y a ciegas** los mismos 50 pares
(consulta, producto): los 3 productos `Exact` de cada consulta gold más 2 no-`Exact`, mezclados. No
vieron la etiqueta de ESCI ni el veredicto del juez. Sí vieron el criterio que el equipo escribió
para cada consulta, porque ese criterio **es** la definición de relevancia del dominio.

### 10.1 · Primero, ¿la rúbrica es clara?

| | kappa | acuerdo |
|---|---|---|
| **Entre los dos anotadores (Cohen)** | **0,790** | 90% (5 desacuerdos de 50) |

Está al borde del 0,8 que la lámina llama *fuerte*, y bien por encima del 0,6 aceptable. **La rúbrica
binaria es clara**, así que los demás números de esta sección se pueden leer.

### 10.2 · ¿Le podemos creer al juez? ¿Y a ESCI?

| Referencia humana | juez: kappa | acuerdo | ESCI: kappa | acuerdo |
|---|---|---|---|---|
| Valeria | 0,419 | 74% | 0,504 | 74% |
| Alejandro | 0,474 | 76% | 0,385 | 68% |
| Consenso (n=45) | **0,504** | 78% | **0,492** | 73% |

Dos lecturas, y la segunda es el hallazgo del informe.

**Primera: el juez es una señal débil.** kappa 0,42–0,50 queda **por debajo del 0,6 que la lámina
llama aceptable**, y lejos del 0,8 que llama fuerte. La Dimensión 2 sirve para separar lo muy malo de lo bueno y no debe
leerse como una medición fina. Así se reporta.

**Segunda: ESCI saca lo mismo.** 0,39–0,50 contra las mismas personas. **El ground truth sobre el que
se calcula nDCG desde M1 es un proxy tan imperfecto del criterio de dominio como el juez LLM.**

### 10.3 · Los tres están calibrados en puntos distintos

De los 50 productos anotados, cuántos acepta cada uno:

| ESCI | Valeria | Alejandro | El juez |
|---|---|---|---|
| **30** | 19 | 20 | **14** |

ESCI es el más laxo, el juez el más estricto, y las personas quedan en medio. **nDCG@10 se calcula
contra la columna de la izquierda**, así que la Dimensión 1 hereda esa laxitud y no puede verla,
porque la etiqueta es su verdad por definición.

### 10.4 · Dónde está exactamente el desacuerdo

Separando por lo que dice ESCI:

| Subconjunto | El juez acepta | Las personas aceptan |
|---|---|---|
| Los 20 que ESCI marca **no relevantes** | 2 | ~2 |
| Los 30 que ESCI marca **`Exact`** | 12 | ~17,5 |

**Todo el desacuerdo está en la clase positiva.** Sobre lo que ESCI descarta, el juez y las personas
coinciden casi perfectamente. Sobre lo que ESCI aprueba, las personas aprueban solo 17,5 de 30 y el
juez solo 12. Es un diagnóstico mucho más útil que un kappa global: el juez no confunde lo malo con
lo bueno, se pasa de estricto al aprobar.

**Tres ejemplos concretos**, con lo que dijo cada uno:

`calcetines sin goma hombre` — ESCI marca `Exact` unos calcetines de deporte Puma y unos tobilleros
unisex. Ninguno dice "sin goma", que es lo único que pide la consulta. **Los dos anotadores y el juez
los rechazan.** Y sin embargo el nDCG de esta consulta es 0,86–0,92 para los tres sistemas: la
métrica dice "excelente" mientras el juez y las personas dicen que los productos no responden la
consulta.

`filtro de gasoil renault trafic` — ESCI marca `Exact` un **filtro de aire**. Los dos anotadores y el
juez rechazan los cinco productos de la muestra.

`ordenador sobremesa i5 16gb ram ssd` — aquí el error es del juez: rechaza un Lenovo ThinkCentre con
i5 que los dos anotadores aceptan, y acepta un HP que ESCI y las personas descartan. Es la
sobre-estrictez de la sección anterior, vista de cerca.

### 10.5 · Una conclusión que sacamos de más, y su corrección

En una versión anterior de este análisis concluimos, a partir de **cuatro ejemplos escogidos a
mano**, que en los desacuerdos el juez tenía razón y ESCI estaba equivocado.

**La anotación sistemática no lo sostiene.** Sobre los 18 productos donde el juez y ESCI discrepan
dentro del consenso humano, las personas le dan la razón **al juez en 10 y a ESCI en 8**:
prácticamente un empate.

Se deja escrito el error junto con su corrección, porque sacar una tendencia de cuatro ejemplos
elegidos a dedo es exactamente lo que este módulo enseña a no hacer, y corregirlo en silencio habría
sido peor que cometerlo.

### 10.6 · La escala 1–5 no se pudo validar, y eso también dice algo

Los dos anotadores puntuaron además 10 pantallas completas del 1 al 5, para comprobar que la nota
agregada por la fórmula 3-2-1 signifique algo.

| | Resultado |
|---|---|
| Diferencia media entre los dos anotadores | **1,50 puntos** |
| Pantallas con nota idéntica | 2 de 10 |
| Pantallas dentro de ±1 punto | 6 de 10 |

**No hay referencia humana estable contra la cual contrastar la fórmula.** No es que la fórmula
falle: es que no hay con qué medirla, y así se reporta.

Pero el dato tiene valor propio. **Las mismas dos personas concuerdan con kappa 0,79 en la pregunta
binaria y difieren 1,5 puntos en la nota holística.** Es evidencia independiente, y humana, de por
qué el juez por ítem funciona y el juez holístico de la v2 no: **la pregunta holística es
intrínsecamente más difícil, no solo para un modelo de 3B.**

---

## 11 · Limitaciones

Un harness que no declara sus límites mide menos de lo que aparenta.

**Del eval set**

1. **Diez consultas son diez consultas.** El nDCG de M2 se calcula sobre 10 casos curados, no sobre
   las 3.844 del test de M1. Sirve para ver *dónde* falla el sistema, no para estimar su rendimiento
   poblacional. Las dos cifras no se mezclan.
2. **Las consultas gold vienen de un dataset público.** Frente al fine-tuning la evaluación es
   limpia; frente al pre-entrenamiento de E5 no podemos garantizar nada.
3. **El catálogo sigue siendo el de Amazon España**, no el de la tienda del caso de estudio.
   Limitación heredada de M1 y no resuelta aquí.
4. **Tres casos adversariales es el mínimo, no un red-teaming serio.**

**De la calibración humana**

5. **Solo dos anotadores.** Con dos no hay mayoría: cada desacuerdo es un empate. Por eso el juez y
   ESCI se comparan contra cada persona por separado, y el consenso —que descarta los 5 productos
   donde difieren, o sea los difíciles— se reporta aparte y es **optimista por construcción**.
6. **La muestra anotada está cargada de casos difíciles.** De los 20 no-`Exact`, 18 son sustitutos.
   Es donde viven los desacuerdos, y por eso el kappa que sale es **pesimista** frente a muestrear al
   azar del catálogo. Los dos sesgos, el del punto 5 y el de este, apuntan en direcciones opuestas y
   no se cancelan de forma conocida.
7. **Los 50 productos anotados no son los que el harness califica.** El harness juzga los tres
   primeros de lo que devuelve *cada sistema*; estos 50 son los de ESCI más dos sustitutos.
8. **Las personas vieron el criterio del equipo y el juez no.** Se lo quitamos al juez a propósito
   porque metérselo en el prompt fue lo que rompió la v1. Parte de la discrepancia juez-humano se
   explica por esa diferencia de contexto y no por la capacidad del modelo.
9. **Un kappa de 0,79 sobre 50 ítems tiene un intervalo de confianza ancho** que no calculamos.

**Del juez**

10. **Falló dos veces antes de quedar en pie**, y ninguna de las dos se habría notado sin la puerta
    de entrada. Esa prueba es ahora obligatoria antes de reportar la Dimensión 2.
11. **La regla de aprobación se cambió después de ver los datos** (de "8 de 10" a "cero
    inversiones"). Está argumentada, pero un umbral fijado a posteriori es más débil que uno fijado
    de antemano.
12. **Auto-preferencia sin medir.**

**Del montaje**

13. **BM25 está en desventaja declarada:** se indexa solo con los candidatos de cada consulta, así
    que su IDF queda casi degenerado. Es comparable en conjunto de candidatos, pero más débil que un
    BM25 de producción sobre el catálogo completo. Igual que en M1.
14. **El umbral de abstención se calibró sobre una muestra de 300 consultas.** Otra muestra daría
    otro umbral y con él otro resultado en los adversariales; la sensibilidad no se midió.

---

## 12 · Conclusiones

**Sobre el sistema.** El modelo ajustado de M1 mejora sobre los dos baselines en las tres
dimensiones, y el efecto neto del fine-tuning (+0,113 de nDCG sobre el encoder congelado) se
distingue del efecto del pre-entrenamiento (+0,061 del congelado sobre BM25). Su capacidad de
abstenerse —3 de 3 casos adversariales— es la diferencia más grande frente a BM25 y la más
relevante para el usuario del sistema. Falla, de forma consistente, en consultas donde el atributo
fino decide la compra.

**Sobre la evaluación.** Ninguna de las tres dimensiones es confiable por separado:

- La **Dimensión 1** se calcula contra etiquetas que concuerdan con nuestro criterio de dominio solo
  a un kappa de 0,49, y no puede verlo.
- La **Dimensión 2** concuerda con las personas a 0,50, y necesitó tres versiones y dos bancos de
  pruebas para llegar ahí.
- La **Dimensión 3** es la única que codifica directamente el criterio del equipo, y por eso mismo
  no es independiente de él.

**Que las tres coincidan en el orden de los sistemas es lo que hace defendible la conclusión.** Ese
es, en una frase, lo que este módulo enseñó: no que una métrica sea mejor que otra, sino que la
confianza viene de contrastar miradas que fallan de formas distintas.

**Sobre el ground truth.** El hallazgo que no buscábamos es que el dataset público sobre el que se
construyó todo M1 tiene una noción de relevancia más laxa que la del dominio. No lo invalida, pero
significa que el nDCG de M1 y de M2 está medido contra una vara que acepta cosas que nuestro usuario
rechazaría. Es la advertencia *"ojo con el ground truth"* de la tabla de familias de S05, encontrada
en carne propia.

---

## 13 · Qué queda para los módulos siguientes

**Reutilizable ya.** La función `harness(eval_set, sistema)` va a medir el RAG de M3, el componente
visual de M4 y el sistema en producción de M5 sin cambios. El eval set de este módulo es la vara
fija: toda mejora futura se compara contra los números de este informe.

**Pendientes que este módulo dejó identificados:**

1. **Completar la anotación con los cuatro integrantes.** Con cuatro hay mayoría real, desaparece el
   problema de los empates y el kappa de Fleiss es mucho más sólido.
2. **Atacar el fallo de atributo fino** (g01, g06) con los campos que M1 dejó fuera: descripción,
   categoría, marca y atributos, además del título. Es la vía natural de mejora para M3.
3. **Revisar si conviene re-etiquetar el eval set con el criterio del equipo** en vez de con las
   etiquetas de ESCI, y reportar el nDCG contra las dos varas.
4. **Medir la auto-preferencia del juez** y la sensibilidad del resultado al umbral de abstención.

---

## Anexo A · Artefactos

| Archivo | Contenido |
|---|---|
| `ENTREGABLE.ipynb` | el harness completo, ejecutable de punta a punta |
| `README.md` | rúbricas del juez, cómo se corre, resumen de resultados |
| `Resultados/eval_set.json` | los 13 casos con sus candidatos, etiquetas y criterios |
| `Resultados/rubrica_juez.txt` | las dos rúbricas versionadas |
| `Resultados/scorecard_m2.csv` · `scorecard_m2.png` | el scorecard |
| `Resultados/detalle_por_caso.csv` | cada caso por cada sistema |
| `Resultados/metricas_m2.json` | configuración completa y todas las métricas |
| `Resultados/prueba_discriminacion_juez.csv` | la puerta de entrada, caso por caso |
| `Resultados/sesgo_posicion.csv` | veredictos en ambos órdenes y su confianza |
| `Resultados/banco_pruebas_juez.csv` | las cuatro formas del juez |
| `Resultados/banco_rubricas_por_item.csv` | las tres redacciones del juez por ítem |
| `Resultados/desacuerdos_juez_vs_esci.csv` | productos donde el juez contradice a ESCI |
| `Resultados/calibracion_humana.csv` | las anotaciones cruzadas con el juez y con ESCI |
| `Resultados/corrida_juez_1.5b/` | la corrida archivada de la v1 del juez, como evidencia |
| `Validacion/` | la plantilla de anotación y las anotaciones del equipo |

## Anexo B · Entorno de la corrida

| Componente | Valor |
|---|---|
| GPU | NVIDIA GeForce RTX 5060 Ti (16 GB) |
| Python · torch · transformers | 3.11.9 · 2.11.0+cu128 · 4.57.1 |
| Modelo evaluado | `modelo_e5_small_finetuned` (M1) |
| Modelo juez | `Qwen/Qwen2.5-3B-Instruct`, puntaje por logits |
| Modelo de embeddings | `paraphrase-multilingual-MiniLM-L12-v2` |
| Semilla | 42 |

---

*SI4006 · Universidad EAFIT · Módulo 2 — Evaluación · Equipo Digitdeck.*
