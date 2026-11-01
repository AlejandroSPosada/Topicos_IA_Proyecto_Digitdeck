# M5 · Demo desplegada, presentación y reporte final (S14–S15)

## Sobre el proyecto

**Digitdeck** es un copiloto de calidad de búsqueda para ecommerce en español. Hasta aquí el
equipo construyó, módulo a módulo, las piezas del sistema:

| Módulo | Qué construyó | Resultado clave |
|---|---|---|
| **M1** | El motor: `multilingual-e5-small` ajustado, que puntúa pares (consulta, producto) | nDCG@10 0,8369 vs. 0,7508 de BM25 |
| **M2** | La vara: un harness propio de tres dimensiones, calibrado contra anotación humana | las tres dimensiones coinciden en el orden; el ground truth de ESCI también es un proxy imperfecto |
| **M3** | El conocimiento: RAG con búsqueda híbrida, reranking con el modelo de M1 y dos herramientas (`verificar_existencia`, `buscar_similares`) | +0,273 de nDCG@10 y +0,265 en aciertos de respuesta frente al RAG ingenuo |
| **M4** | Los ojos: un VLM (`Qwen2-VL-2B-Instruct`) que traduce una foto del comprador en una consulta para el sistema de M3 | 4/12 aciertos con foto (3/12 con la pregunta sola, techo 8/10); el componente visual no rompe ninguno de los 49 casos de M3 |

**M5 no agrega una capa técnica nueva.** Es el cierre: tomar lo que ya existe —el modelo de M1,
el harness de M2, el RAG con herramientas de M3, la visión de M4— y entregarlo como **un solo
sistema desplegado, verificable y explicado en 8 minutos a alguien que no sabe de IA.**

## Qué pide la entrega M5

> **Proyecto final — demo desplegada + presentación + reporte.**
> **Nota: penalización por inasistencia.**

Tres entregables, no tres proyectos distintos:

1. **Demo desplegada** — el sistema integrado (M1–M4) corriendo en una URL pública, no en un
   notebook ni en el Colab.
2. **Presentación** — 8 minutos, en vivo, para una audiencia sin formación en IA. **Asistencia
   obligatoria de todo el equipo**: la nota penaliza la inasistencia, así que esto no es opcional
   para quien no presente.
3. **Reporte** — el documento que cierra el proyecto: qué se construyó, con qué evidencia, qué
   falla y qué haría falta antes de usarlo con compradores reales.

Las rúbricas detalladas de M1 a M4 las publicó la docente por módulo. **La de M5 ya está
publicada** (abajo) y es la que cierra el semestre; no se inventan requisitos adicionales a los
que ahí aparecen.

## Rúbrica de evaluación

| Criterios | Nivel 4 (5 pts) | Nivel 3 (4 pts) | Nivel 2 (3 pts) | Nivel 1 (1,5 pts) | Nuevo nivel (0 pts) | Puntuación |
|---|---|---|---|---|---|:---:|
| **Definición del problema y usuario** | El usuario es una persona concreta y la decisión que toma con el sistema es específica y verificable. La métrica de éxito mide esa decisión, no el modelo. Sabe qué pasa si el sistema se equivoca y quién asume ese costo. | Usuario y decisión claros, métrica conectada. Falta el análisis del costo del error, o la métrica mide el sistema más que la decisión. | Hay un usuario y una decisión, pero genéricos. La métrica es técnica y no se conecta con el usuario. | El usuario "se informa". No hay decisión: hay un buscador con lenguaje natural. | No se identifica usuario ni decisión. | /5 |
| **Solidez técnica** | El sistema corre end-to-end sin intervención. Cada decisión —modelo base, chunking, retrieval, técnica de eficiencia— está justificada con evidencia propia, no con lo que dice un tutorial. Descartaron alternativas y saben decir por qué. | Sistema funcional end-to-end y decisiones justificadas, pero alguna se sostiene en la práctica común y no en evidencia que ellos midieron. | El sistema funciona, pero con pasos manuales o partes frágiles. Las decisiones se explican pero no se justifican. | Componentes que funcionan por separado. No hay sistema end-to-end. | No corre. | /5 |
| **Rigor de evaluación** | Están las tres cosas: baseline, ablation y análisis de errores. El harness es reproducible por un tercero. Reportan dónde el sistema falla y qué intentaron que no funcionó. Saben qué no mide su evaluación. | Baseline, ablation y análisis de errores presentes, pero alguno superficial. Solo reportan lo que salió bien. | Hay harness y métricas, y hay baseline. Falta ablation o falta análisis de errores. | Métricas sin baseline, o números que no se pueden reproducir. | Sin evaluación. | /5 |
| **Integración entre módulos** | Un solo sistema. El modelo de M1, el harness de M2, el RAG de M3 y el componente visual de M4 se usan entre sí y el harness evalúa el conjunto. Se nota que fue una decisión, no un ensamble. | Sistema integrado, pero un componente está pegado con alambre o se evalúa por separado. | Los componentes conviven y el sistema corre, pero no se ven las costuras: cada módulo mantiene su propia lógica y su propia evaluación. | Cuatro entregas en un repositorio. No hay sistema: hay carpetas. | Los módulos no se hablan. | /5 |
| **Comunicación de la demo** | En 8 minutos, alguien sin formación en IA entiende qué problema resuelve, ve el sistema funcionando y sale sabiendo cuándo no confiar en él. Cero jerga sin traducir. Cabe en el tiempo sin correr. | Demo clara y en tiempo, pero se apoya en jerga o dedica más minutos a la arquitectura que al problema. | Se entiende, pero está contada para el profesor, no para el usuario. O se pasa del tiempo. | Recorrido por el código. La audiencia no técnica se perdió en el minuto dos. | Sin demo, o la demo no corre en vivo. | /5 |
| **Producción verificable** | Las cuatro cosas: URL pública que abro yo desde mi computador; W&B con el historial de experimentos del semestre; logging estructurado; health check que responde. Reproduzco un resultado del reporte sin ayuda de ellos. | Desplegado y funcionando, con W&B y health check. Falla una de las cuatro — normalmente el logging estructurado. | Desplegado y accesible, pero sin observabilidad real: W&B vacío o con dos corridas del último día. | Corre en el Colab. | No hay URL, o no abre. | /5 |
| **Reflexión sobre limitaciones y ética** | Limitaciones específicas y demostradas con casos de su sistema, no genéricas. Identifican al menos un sesgo con evidencia de dónde degrada el desempeño y para quién. Dicen qué haría falta antes de que esto se use con personas de verdad. | Limitaciones concretas y sesgos identificados, pero sin medir la degradación o sin aterrizar las implicaciones del despliegue. | Reconocen limitaciones reales pero genéricas ("puede alucinar", "el corpus es limitado"). La ética aparece como un párrafo al final. | Un párrafo de ética que aplicaría a cualquier proyecto del salón. | Sin reflexión. | /5 |
| **Total** | | | | | | **/35** |

## Qué significa cada criterio para Digitdeck

### 1 · Definición del problema y usuario

Ya respondido en gran parte en
[`../M1/PLANTILLA_DEFINICION.md`](../M1/PLANTILLA_DEFINICION.md): el usuario es **el líder de
ecommerce**, y la decisión es **cuáles consultas intervenir y en qué orden** (aprobar el
reordenamiento, corregir la ficha, o descartar por inventario). Eso cubre Nivel 3.

Para Nivel 4 falta, puntualmente:

- **Costo del error y quién lo asume** — campo 5 de la plantilla (métrica de éxito), sin
  diligenciar desde M1. No basta con nDCG o aciertos del harness: hace falta la señal de valor
  real (p. ej. "el líder acepta o actúa sobre la recomendación en X% de los casos").
- **Campo 6** (qué aporta el componente visual de M4 al usuario del sistema) y **campo 7**
  (riesgos éticos) de la misma plantilla siguen con su encabezado.
- **Campo 8** (compromisos del equipo) también pendiente.

### 2 · Solidez técnica

Las decisiones de modelo base, chunking, retrieval y eficiencia **ya están justificadas con
evidencia propia** en M1–M3, no hay que rehacerlas:

| Decisión | Evidencia | Dónde |
|---|---|---|
| Modelo base (`multilingual-e5-small`) | comparación de tokenizador contra BETO y DistilBERT sobre 18 consultas de dominio | `../M1/README.md` §"Material de referencia", celda 1.4 del notebook de M1 |
| Chunking (ficha completa vs. solo título) | empate práctico (0,162 vs. 0,163 de nDCG) | `../M3/INFORME_M3.md` §9, "Lo que se quitó por no ser obligatorio" |
| Retrieval (híbrida BM25 + densa con RRF) | +0,162 de nDCG@10 medido contra el RAG ingenuo | `../M3/INFORME_M3.md` §5.1 y §7.2 |
| Técnica de eficiencia (LoRA r=8 vs. fine-tuning completo) | LoRA recupera 87% de la ganancia con un adaptador 785× más liviano | `../M3/INFORME_M3.md` §7.8, `ABLACIONES_M1.ipynb` |

Lo que **no existe todavía** es el sistema corriendo **end-to-end sin intervención manual**: hoy
M3 y M4 son notebooks separados (`ENTREGABLE.ipynb` de cada módulo) que se ejecutan a mano, con
rutas que apuntan a artefactos de otras carpetas. M5 tiene que convertir eso en un servicio único
que arranca, carga lo que necesita y responde sin que alguien del equipo mueva celdas.

### 3 · Rigor de evaluación

Baseline, ablation y análisis de errores **ya existen por módulo** (BM25/E5-congelado en M1,
A/B/C/D en M3, M3-sin-foto/M4/M4.1/techo en M4). Lo que pide M5 es que esto se sostenga sobre el
**sistema final desplegado**, no sobre una corrida local de un notebook: correr el harness de M2
contra el servicio en producción y que un tercero pueda reproducirlo con las instrucciones del
reporte, no con contexto que solo tiene el equipo.

### 4 · Integración entre módulos

Es el criterio donde más trabajo nuevo hace falta. Hoy Digitdeck es, literalmente, "cuatro
entregas en un repositorio" (Nivel 1 del criterio): cada módulo tiene su propio notebook, su
propia carpeta de `Resultados/` y se corre por separado. Para Nivel 4 hace falta:

- **Un solo punto de entrada** que reciba una pregunta (con o sin foto) y use el pipeline completo
  de M4 (que ya envuelve a M3, que ya envuelve al reranker de M1).
- **Un solo harness** que evalúe ese sistema único de punta a punta, no un scorecard por módulo.
- Que se note que fue **una decisión de arquitectura**, no un ensamble de última hora: documentar
  cómo se conectan las piezas (ya hay un precedente de esto en `../M4/INFORME_M4.md` §3, "dónde se
  enchufó", que M5 puede extender en vez de reinventar).

### 5 · Comunicación de la demo

No hay una demo en vivo todavía — M1 a M4 se mostraron en notebooks. Para los 8 minutos:

- Guion escrito y cronometrado de antemano (como `../M3/`'s menciones de `DEMO.md` en proyectos
  hermanos del equipo son un patrón útil, aunque aquí no existe ese archivo aún).
- Casos elegidos para la demo que ya tienen criterio declarado y evidencia: por ejemplo los
  adversariales de M2/M3 (abstención) y los casos espejo de M4 (con y sin foto) comunican mejor
  "cuándo no confiar en el sistema" que un caso que siempre funciona bien.
- Nada de JSON de configuración, nombres de modelos en HuggingFace, ni "nDCG@10" sin traducir a
  qué significa para el líder de ecommerce.

### 6 · Producción verificable

Las cuatro cosas que pide el Nivel 4, ninguna existe hoy:

| Pieza | Estado actual |
|---|---|
| URL pública | no hay despliegue; todo corre en máquina local (RTX 5060 Ti) o Colab |
| W&B con historial del semestre | existe una corrida de W&B de M1 (`https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg`); M2, M3 y M4 no se registraron en W&B — hay que decidir si se completa el historial retroactivamente o se declara la limitación |
| Logging estructurado | no existe |
| Health check | no existe |

### 7 · Reflexión sobre limitaciones y ética

Esta es la que más material reutilizable tiene. M1 a M4 ya identificaron sesgos concretos,
medidos con casos propios, no genéricos:

- **El ground truth de ESCI es un proxy imperfecto** del criterio de dominio (kappa 0,39–0,50
  contra anotación humana) — `../M2/INFORME_M2.md` §10.
- **El sistema falla en atributo fino** (color, variante dentro de una línea) de forma consistente,
  no al azar — `../M1/README.md` y `../M2/INFORME_M2.md` §9.2.
- **El VLM falla en colores cercanos, generaciones de producto y fotos sin producto**, con casos
  concretos y por qué — `../M4/INFORME_M4.md` §6.4 y §7.
- **Sesgo de contexto**: catálogo de Amazon España, no de la tienda real; un producto
  latinoamericano (Pony Malta) como caso de prueba — `../M4/INFORME_M4.md` §10.

Lo que falta para M5 es **consolidar esto en una sola reflexión** sobre el sistema integrado (no
una lista de limitaciones por módulo) y responder explícitamente "qué haría falta antes de que
esto se use con compradores reales", que hoy no está respondido en ningún informe.

## Qué falta construir para M5

- [ ] Servicio único que integra M1 (reranker) + M2 (harness) + M3 (RAG + herramientas) + M4
      (visión), con un solo punto de entrada.
- [ ] Despliegue en una URL pública y accesible sin VPN ni credenciales del equipo.
- [ ] Logging estructurado del servicio desplegado.
- [ ] Endpoint o comando de health check.
- [ ] W&B con el historial de experimentos del semestre (decidir qué hacer con M2–M4, que no se
      registraron).
- [ ] Harness de M2 corrido contra el sistema desplegado, no contra una corrida local.
- [ ] Guion de demo de 8 minutos, cronometrado, para audiencia sin formación en IA.
- [ ] Reporte final (`INFORME_M5.md`) que cierra el proyecto.
- [ ] Completar los campos 5, 6, 7 y 8 de
      [`../M1/PLANTILLA_DEFINICION.md`](../M1/PLANTILLA_DEFINICION.md).
- [ ] Confirmar con la docente el canal/fecha de la demo y quién debe asistir (nota: penalización
      por inasistencia).

## Estructura esperada de la entrega

```
Entregables/M5/
├── README.md            # este documento: contexto, rúbrica, qué falta
├── TODO.md              # paso a paso del equipo, como en M1–M4
├── INFORME_M5.md         # reporte final: sistema integrado, evaluación, límites y ética
├── servicio/             # el sistema desplegado (código del servicio único)
├── Resultados/           # scorecard final, evidencia de W&B, logs, capturas del health check
└── Validacion/           # lo que haga falta para que un tercero reproduzca un resultado
```

---

*SI4006 · Universidad EAFIT · Módulo 5 — Demo desplegada, presentación y reporte final · Equipo
Digitdeck.*
