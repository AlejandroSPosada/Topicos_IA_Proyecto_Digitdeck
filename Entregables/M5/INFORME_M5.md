# Digitdeck · INFORME_M5 · Reporte final

> Equipo Digitdeck · SI4006 · Universidad EAFIT · 2026-2
> Demo en vivo: **http://54.173.61.242:8000** (`GET /salud`, `POST /preguntar` — contrato completo
> en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §5.2). Cómo reproducir un resultado sin ayuda
> del equipo: [`README.md`](README.md)#cómo-reproducir-un-resultado-sin-ayuda-del-equipo.
> Rúbrica de M5 y qué significa cada criterio para Digitdeck: [`README.md`](README.md).

## Resumen ejecutivo

Digitdeck es un copiloto de calidad de búsqueda para ecommerce en español. M1 a M4 construyeron,
por separado, el motor de ranking (encoder ajustado), la vara de evaluación (harness de tres
dimensiones), el conocimiento (RAG con dos herramientas) y los ojos (un VLM que traduce una foto en
consulta). **M5 no agrega una capa técnica nueva: integra las cuatro en un solo servicio y lo
despliega en una URL pública**, y es el módulo donde, por primera vez, el sistema completo corre
sobre GPU real, sin notebooks ni intervención manual.

El sistema está desplegado y verificado de punta a punta: `GET /salud` responde 200 con los cuatro
modelos cargados, `POST /preguntar` se probó en sus tres rutas (existencia, similar con verificador
de 3B, foto con VLM) y se corrió el harness de M2/M3 contra la URL pública en 49 preguntas —
**la decisión del sistema coincide con la corrida local en 48 de 49 casos**. Un agente sin ningún
contexto del equipo reprodujo un resultado del reporte solo con las instrucciones del README y
encontró un bug real de reproducibilidad, ya corregido. Lo que falta para cerrar M5 es el guion de
la demo de 8 minutos y completar los campos 5-8 de `../M1/PLANTILLA_DEFINICION.md`.

---

## 1 · Problema y usuario

Ya definido en [`../M1/PLANTILLA_DEFINICION.md`](../M1/PLANTILLA_DEFINICION.md) (campos 1-4,
diligenciados desde M1): el dominio es el ordenamiento de resultados de búsqueda interna en un
ecommerce en español; el usuario es **el líder de ecommerce**, una persona concreta que hoy revisa
consultas a mano por volumen de tráfico e intuición; la decisión que Digitdeck le cambia es **cuáles
consultas intervenir y en qué orden**, con tres acciones posibles por caso: aprobar el
reordenamiento, corregir la ficha, o descartar por inventario.

**Lo que falta para Nivel 4 del criterio** (campo 5 de la plantilla, sin diligenciar todavía): una
métrica de éxito que no sea solo nDCG o aciertos del harness, sino una señal de valor real — por
ejemplo, en qué porcentaje de los casos que Digitdeck prioriza el líder efectivamente actúa
(aprueba, corrige o descarta) en vez de ignorar la recomendación. Eso requiere una prueba con un
usuario real que este proyecto, en el tiempo del semestre, no alcanzó a correr; queda declarado
como el siguiente paso, no inventado un número.

---

## 2 · Arquitectura del sistema integrado

Detalle completo, contratos exactos y decisiones de diseño (15 ADR) en
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Resumen del flujo:

```
pregunta (+ foto opcional)
  → ¿hay foto? → M4 (ver): foto → JSON de atributos → consulta en texto
  → M3 (enrutador): consulta → verificar_existencia | buscar_similares | ninguna
      verificar_existencia → M1 (reranker) sobre búsqueda híbrida BM25+densa
      buscar_similares     → M1 (reranker) + verificador de 3B (filtra lo que sí es exacto)
  → M3 (generador): fichas del catálogo → respuesta en lenguaje natural, con cita [ID]
  → logging JSON estructurado (stdout → CloudWatch) + W&B
```

Un solo punto de entrada (`POST /preguntar`), un solo contrato de 6 estados compartido entre el
camino con y sin foto (`respuesta_generada`, `sin_resultados`, `abstencion_dominio`, `sin_producto`,
`error_formato`, `error_operativo` — definidos originalmente por separado en M3 y M4, unificados
aquí), y una sola base de código (`project/servicio/`) que reutiliza literalmente las funciones de
M1 (`encoder.py`), M3 (`rag.py`) y M4 (`vision.py`), no una reimplementación.

**Qué se integró y qué no:** `buscar_similares` nunca se probó con foto (alcance declarado de M4,
§3.4 de `ARCHITECTURE.md`) — el camino con foto siempre usa `verificar_existencia`. El harness de
M2 no se integró como código (no corre dentro del servicio); se usó para *evaluar* el servicio
desde afuera (§4).

---

## 3 · Despliegue

AWS, instancia `g5.xlarge` (GPU A10G, 24 GB VRAM) para que los cuatro modelos convivan en memoria,
Terraform para toda la infraestructura (dos stacks: `bootstrap/` para el usuario IAM dedicado y el
estado remoto, `infra/` para la instancia, ECR, SSM y el presupuesto propio de 40 USD/mes),
contenedor Docker con `--restart unless-stopped` y logging `awslogs` a CloudWatch
(`/digitdeck/app`). URL pública fija por una IP elástica: **http://54.173.61.242:8000**.

| Pieza | Estado |
|---|---|
| URL pública, sin VPN ni credenciales | ✅ — accesible desde cualquier máquina, verificado por un tercero sin contexto (§5) |
| W&B con historial del semestre | 🟨 — M1 tiene una corrida (`https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg`); M2-M4 no se registraron, decisión pendiente de completarlo retroactivamente |
| Logging estructurado | ✅ — JSON por pregunta a CloudWatch, verificado con eventos reales ingeridos |
| Health check | ✅ — `GET /salud` responde 200 con los 4 modelos cargados |

**Costo:** ~1,01 USD/hora mientras la instancia está prendida; se apaga entre sesiones de trabajo
para no quemar el presupuesto. El historial completo de decisiones de infraestructura (por qué GPU
y no CPU, por qué construir la imagen en la instancia y no en local, los 5 bloqueos de permisos IAM
que se fueron encontrando) está en `docs/PLAN.md` y los ADR de `docs/ARCHITECTURE.md` §9 — no se
repite aquí para no duplicar la fuente de verdad.

---

## 4 · Evaluación

### 4.1 · Lo que ya midió cada módulo por separado

| Módulo | Métrica | Resultado | Baseline/ablation | Fuente |
|---|---|---|---|---|
| M1 | nDCG@10 (test, 92.739 pares) | **0,8369** | BM25 0,7508; E5-small congelado 0,7885 | `../M1/README.md` |
| M2 | Harness de 3 dimensiones, calibrado contra anotación humana | kappa inter-anotador 0,79 (fuerte); kappa juez vs. humanos 0,42-0,50 y kappa ESCI vs. humanos 0,39-0,50 (ambos débiles) | — | `../M2/INFORME_M2.md` §10 |
| M3 | nDCG@10 y aciertos de respuesta, sistema A (RAG ingenuo) → D (con herramientas) | **+0,273** nDCG@10 existencia, **+0,265** aciertos, IC 95%, sin costo neto de latencia (2,08 s vs. 2,02 s) | RAG ingenuo (A); ablaciones B (+híbrida) y C (+reranker) | `../M3/INFORME_M3.md` §7 |
| M4 | Aciertos con foto vs. solo pregunta (eval set propio, 12 casos) | **4/12** con foto vs. **3/12** solo pregunta; techo (pregunta perfecta) 8/10 | M3 sin foto; techo | `../M4/INFORME_M4.md` §9 |

**Lectura honesta de M4, no solo el titular:** la ganancia con foto es pequeña (4/12 vs. 3/12) y lo
que más mejora es la *calidad* del error, no la cantidad — con solo la pregunta, M3 afirma
productos al azar en 8 de 12 casos; con foto baja a 5. Pero **en los adversariales el VLM empeora**
(1/4 vs. 2/4 de M3 sin foto): afirma en una foto de playa, en unos AirPods borrosos y en un iPhone
cuya capacidad no se ve. El VLM añade una capa de riesgo nueva (afirmar con más confianza de la que
la foto sostiene), no solo una capa de ayuda.

### 4.2 · Verificación contra el sistema desplegado (lo nuevo de M5)

Todo lo de 4.1 se midió en notebooks locales. M5 repite una parte de esa verificación **contra el
servicio real en producción**, lo que pide el Nivel 4 de "Rigor de evaluación": *"el harness es
reproducible por un tercero"*.

**Salud del servicio** — `GET /salud`, verificado el 2026-11-02:

```json
{"ok":true,"modelos_cargados":["encoder","generador","verificador","vlm"],"indice_listo":true}
```

**Las tres rutas de `POST /preguntar`, probadas manualmente contra la URL pública:**

| Ruta | Pregunta | Resultado | Latencia |
|---|---|---|---|
| Texto, existencia | "¿tienen audífonos inalámbricos bluetooth?" | `respuesta_generada`, "Sí, lo tenemos:", 5 fichas citadas | 7,7 s |
| Texto, similar (`buscar_similares` + verificador 3B) | "¿Qué cafetera me recomiendan parecida a la Bialetti Moka Express de 6 tazas?" | `respuesta_generada`, "No lo tenemos exacto, pero hay productos parecidos:", cita la Bialetti 6356 `[B07527ZB5Y]` | 2,4 s |
| Foto (VLM) | `M4/eval_set/imagenes/img_01.jpg` (iPhone 11 Pro Max oro) + "¿Tienen este celular?" | VLM leyó "smartphone, Apple, iPhone 11 Pro Max, oro"; el sistema citó exactamente `[B07XS4J7R6]` — coincide con el resultado esperado documentado en el eval set de M4 | 8,7 s |

**El harness de M2/M3 contra la URL pública** (49 preguntas del eval set extendido de M3, 2026-11-02):

- 49/49 respondidas, 0 errores, latencia HTTP media **2,59 s**.
- **La decisión del sistema (abstención y apertura: afirma/similares/abstiene) coincidió con la
  corrida local guardada (`../M3/Resultados/salidas_sistemas.json["D"]`) en 48 de 49 casos para
  ambas comparaciones.** Los 2 casos que no coincidieron están explicados caso por caso en
  `docs/ARCHITECTURE.md` §9 (riesgo 10): uno es no determinismo del enrutador en un caso límite
  donde, además, la respuesta de producción es la más correcta según la rúbrica; el otro es un
  rechazo a nivel de texto del generador ("No tengo esa información...") que el estado de la
  máquina (`respuesta_generada`) no captura — vale la pena que el equipo lo tenga presente.
- **Limitación encontrada y declarada, no un número inventado:** `POST /preguntar` no expone el
  ranking completo top-10 ni corre un juez holístico, así que la Dimensión 1 (nDCG@10/MRR) y la
  Dimensión 2 (juez LLM) de M2/M3 no se pudieron reproducir contra la API pública tal cual. Un
  intento de aproximar la Dimensión 3 (aciertos de dominio) usando `fichas_citadas` como sustituto
  de `pantalla` subestimó sistemáticamente (porque el generador no siempre cita cada ficha que sí
  usó) y **no se reporta como cifra de calidad** — solo queda en el detalle de la corrida, en
  `docs/PLAN.md` lote 5.1.

**Reproducibilidad por un tercero real, no simulado:** se le dio a un agente de IA sin ningún
contexto de esta sesión o del equipo *solo* el texto de la sección "Cómo reproducir un resultado"
de `README.md`, y se le pidió seguirla. El health check coincidió exacto. **El comando `curl`
documentado, tal cual estaba escrito, falló con `400 "There was an error parsing the body"`** —
las tildes en línea en `-d '...'` se codificaron mal según su terminal. Escribiendo el mismo cuerpo
a un archivo y mandándolo con `--data-binary` sí funcionó, con resultado idéntico al documentado.
Esto **no es un bug del servicio** (aceptó el mismo contenido sin problema) — era un bug real en
las instrucciones del README, que ya se corrigió (`docs/PLAN.md` lote 5.2, `docs/ARCHITECTURE.md`
§9 riesgo 11). Encontrarlo es, en sí mismo, la prueba de que valía la pena correr este lote: un
tercero real habría tropezado con exactamente esto.

---

## 5 · Qué falla

Consolidado de lo que M1-M4 ya encontraron por separado, más lo nuevo de esta verificación en
producción:

- **El ground truth es un proxy imperfecto en dos niveles**: las etiquetas de ESCI (kappa 0,39-0,50
  contra anotación humana) y el juez LLM de M2 (kappa 0,42-0,50) — ninguno de los dos es la vara
  real, solo se nota al compararlos entre sí (`../M2/INFORME_M2.md` §10).
- **El sistema falla en atributo fino** (color, variante dentro de una línea) de forma consistente,
  no al azar (`../M1/README.md`, `../M2/INFORME_M2.md` §9.2).
- **El VLM falla en colores cercanos, generaciones de un mismo producto y fotos sin producto**, y
  en los adversariales empeora respecto a no tener foto (1/4 vs. 2/4) — afirma con más confianza de
  la que la imagen sostiene (`../M4/INFORME_M4.md` §6.4, §7 y §10).
- **Afirmaciones falsas no se eliminaron, solo bajaron**: con solo texto, M3 puede afirmar un
  producto al azar; con foto, M4 lo reduce pero no lo quita (8→5 de 12 en el eval set de M4). **Caso
  real, no curado, encontrado en vivo el 2026-11-02 por un usuario probando la demo desplegada**:
  con una foto de unos AirPods Pro y una pregunta de texto que había quedado de una prueba anterior
  y no tenía relación con la foto (sobre una cafetera), el sistema primero citó con confianza un
  iPhone XR —cuya ficha dice "incluye earpods", los alámbricos de regalo, no los AirPods Pro—, una
  afirmación falsa real sobre el sistema en producción. **Repetir la misma foto con una pregunta
  que sí correspondía ("¿tienes estos audífonos?") encontró de inmediato el producto correcto**
  (`[B07ZPNLGDP] apple airpods pro`, que sí está en el catálogo). La causa no fue que el catálogo
  no tuviera el producto — es que **cuando el texto y la foto piden cosas distintas, el sistema no
  siempre lo detecta** y puede responder sobre la señal equivocada en vez de abstenerse o pedir
  aclaración; a veces se abstiene (caso de la cafetera + foto de celular) y a veces afirma algo
  incorrecto (este caso), sin que el usuario tenga ninguna señal de que mezcló las dos cosas.
- **Un estado `respuesta_generada` no garantiza que el texto no sea, en el fondo, una abstención**
  — hallazgo nuevo de esta corrida en producción (`docs/ARCHITECTURE.md` §9, riesgo 10, caso
  `g09-E`): la recuperación encontró candidatos, pero el generador igual escribió "no tengo esa
  información".
- **El generador puede inventar productos completos, no solo citar mal uno real.** M3 ya había
  medido esto en agregado, no lo descubrimos hoy de la nada: *faithfulness* de RAGAS en sistema D
  es 0,940, no 1,0 (`../M3/INFORME_M3.md` §7.4) — un 6% de lo generado no está anclado al contexto.
  Lo nuevo es un caso concreto de ese 6%, encontrado en vivo el 2026-11-02: con una foto de un
  celular, el generador respondió "Sí, lo tenemos" y citó **cuatro productos con IDs que no existen
  en el catálogo** (`B07XYZ1234`–`B07XYZ1237`, verificado contra las 80.949 fichas). La causa
  probable: el propio prompt del generador (`SYSTEM_RAG` en `project/servicio/rag.py`) usa
  justo ese patrón de ID como ejemplo de formato de cita — "cita cada producto... por ejemplo
  `[B07XYZ1234]`" — y el modelo copió el ejemplo en vez de usar el contexto real. Confirmado que no
  fue un error de búsqueda: `fichas_citadas` volvió vacío, porque ninguno de los IDs inventados
  coincidía con lo que sí se había recuperado. Ni `ids_citados()` ni `completar_nombres()` (las dos
  funciones de `rag.py` que tocan las citas) validan que un ID exista — se construyeron para otra
  cosa (completar el nombre corto junto a una cita, no para detectar alucinaciones), así que hoy no
  hay ninguna barrera de código contra esto, solo la medición agregada de M3.
- **Sesgo de contexto**: el catálogo es de Amazon España, no de la tienda real del caso de uso; un
  producto latinoamericano (Pony Malta) sirve de caso de prueba precisamente porque no está en ese
  catálogo (`../M4/INFORME_M4.md` §10).
- **La API pública no expone suficiente información para una auditoría externa completa** — no hay
  forma de que un tercero verifique el ranking completo o la calidad del juez sin acceso al código
  (§4.2, riesgo 10 de `docs/ARCHITECTURE.md`).
- **Brechas operativas del despliegue, menores pero reales**: ni el usuario IAM del equipo ni el
  rol de la instancia pueden leer logs de CloudWatch por CLI (solo escribir); el push de Docker
  desde la máquina del equipo a ECR es estructuralmente poco confiable en esta red (se construye y
  sube desde la propia instancia en su lugar); dos credenciales quedaron expuestas en el chat
  durante el despliegue (una rotada, una que el equipo decidió no rotar) — todo declarado en
  `docs/ARCHITECTURE.md` §9.

---

## 6 · Reflexión ética y qué haría falta antes de usarlo con compradores reales

**Quién puede salir perjudicado y cómo:** un comprador que confía en una "afirmación falsa" (el
sistema dice "sí, lo tenemos" sobre algo que no está, o no es exactamente eso) pierde tiempo o
dinero. Es un riesgo medido, no hipotético: ocurre en ambos caminos (texto y foto), con mayor
frecuencia cuando hay foto de por medio y la pregunta del comprador coincide poco con el producto
real. El sesgo de contexto (catálogo de Amazon España) significa que el sistema puede ser
sistemáticamente peor para productos o marcas latinoamericanas — una inequidad geográfica
concreta, no abstracta, con un caso de prueba real que la demuestra (Pony Malta).

**Qué haría falta antes de producción real con compradores:**

1. **Catálogo real de la tienda, no ESCI.** ESCI sirvió para construir y medir el sistema con un
   dataset público y con licencia clara, pero el vocabulario de marcas y categorías de un retailer
   local no es el de Amazon España. Reentrenar/reindexar sobre el catálogo real es el paso previo
   obligatorio, no opcional.
2. **Una interfaz que impida mezclar foto y texto sin relación.** El caso real de los AirPods Pro
   (§5) no fue un problema del catálogo — fue que el texto y la foto pedían cosas distintas y el
   sistema no lo detectó. Antes de producción real hace falta una señal clara (en la interfaz o en
   el propio sistema) de que la pregunta de texto debe ser sobre la foto adjunta, o una validación
   que lo verifique antes de responder.
3. **Validar que cada ID citado exista de verdad en el catálogo antes de mostrarlo.** El caso real
   del generador inventando cuatro productos (§5) pasó sin que ninguna capa del sistema lo
   detectara — ni `ids_citados()` ni `completar_nombres()` verifican que un ID sea real, solo le dan
   formato. Es una validación barata (un `if ID in catalogo`) y evitaría mostrarle a un comprador un
   producto que no existe con la misma confianza que uno real.
3. **Una vara de verdad para "afirmación falsa", no solo el juez LLM o ESCI.** Dado que ambos
   proxies tienen kappa débil contra humanos (§5), una decisión de negocio como "el sistema puede
   decirle a un comprador que sí lo tenemos" necesita una revisión humana en el loop, al menos
   hasta que se mida esa tasa de afirmación falsa contra anotación humana de verdad, sobre el
   catálogo real.
5. **Medir la métrica de valor del campo 5** (§1): no basta con que el sistema tenga buen nDCG, hay
   que confirmar que el líder de ecommerce efectivamente actúa sobre lo que el sistema le prioriza.
6. **Resolver el gap de auditoría externa** (§4.2, riesgo 10): si un tercero (auditor, comprador
   técnico, otro equipo) va a verificar el sistema en producción, la API debería exponer lo
   suficiente del ranking para que esa verificación sea posible sin tener que correr el notebook.
7. **Monitoreo del VLM en producción**, no solo en el eval set de 12 casos: la muestra es pequeña a
   propósito (es cara de anotar a mano) y el informe de M4 ya lo declara — antes de producción real
   hace falta un conjunto de validación más grande, idealmente con fotos reales de compradores, no
   solo imágenes curadas por el equipo.

---

## 7 · Qué queda pendiente para cerrar M5

- [ ] Guion de demo de 8 minutos, cronometrado, para audiencia sin formación en IA.
- [ ] Campos 5-8 de `../M1/PLANTILLA_DEFINICION.md` (métrica de éxito, aporte de M4, riesgos
      éticos, compromisos del equipo) — este informe ya da material real para los cuatro (§1, §6),
      falta trasladarlo a la plantilla.
- [ ] Decidir si se completa el historial de W&B de M2-M4 (§3).
- [ ] Confirmar con la docente el canal/fecha de la demo.

Estado detallado, fase por fase, con evidencia de cada paso: [`docs/PLAN.md`](docs/PLAN.md) §3.
Decisiones de diseño y riesgos abiertos: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §9.

---

*SI4006 · Universidad EAFIT · Módulo 5 — Demo desplegada, presentación y reporte final · Equipo
Digitdeck.*
