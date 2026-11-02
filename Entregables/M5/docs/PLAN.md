# Digitdeck · M5 · PLAN

> Plan por fases y lotes del despliegue de M5, matriz de trazabilidad Fase · Lote → Criterio de
> la rúbrica de M5, y estado del proyecto.
> **Convención de actualización:** cerrar un lote = tocar **solo §3** de este archivo (la fila del
> lote). Este archivo no define contratos: para cualquier interfaz (API HTTP, nombres en AWS,
> variables de entorno, secretos) la fuente es **§5 de [`ARCHITECTURE.md`](ARCHITECTURE.md)**.
> Decisiones (ADR) y riesgos: **§9 de `ARCHITECTURE.md`**. Rúbrica completa y qué significa cada
> criterio para Digitdeck: [`../README.md`](../README.md).

---

## 1 · Plan por fases (lotes)

> Sin fechas: lo que importa es el orden y las dependencias. Responsable: equipo Digitdeck, sin
> repartir por persona todavía — se asigna al empezar cada fase. Las fases 2 a 5 son secuenciales:
> cada una depende de que la anterior esté cerrada.

### Fase 0 · Investigación y decisiones
**Criterios cubiertos:** insumo de Producción verificable

- **Lote 0.1** → inventario de la cuenta de AWS: cuotas de GPU, precios reales (API de Pricing),
  presupuesto existente, recursos de 4U_project y TrendAnalyzer en la misma cuenta, estado de
  Docker en la WSL del equipo.
- **Lote 0.2** → decisiones de despliegue con el equipo: presupuesto propio, credenciales IAM
  dedicadas, tipo de instancia. Quedan como ADR-1 a ADR-10 en `ARCHITECTURE.md` §9.
- **Listo cuando:** decisiones tomadas y documentadas en ADR, sin preguntas abiertas que bloqueen
  la Fase 1.

### Fase 1 · Infraestructura (Terraform)
**Criterios:** Producción verificable

- **Lote 1.1** → `project/bootstrap/`: estado remoto (S3 + DynamoDB) y usuario IAM dedicado
  `digitdeck-terraform`, sin access key en el estado.
- **Lote 1.2** → `project/infra/`: EC2 `g5.xlarge`, ECR, IAM de la instancia (SSM, sin SSH),
  secretos en SSM Parameter Store, presupuesto propio con alerta.
- **Listo cuando:** `terraform validate` en verde en los dos stacks (cumplido el 2026-11-01) y
  `terraform apply` corrido sin errores, con los outputs de `ARCHITECTURE.md` §5.6 disponibles.

### Fase 2 · Servicio (de notebooks a código servible)
**Criterios:** Solidez técnica, Integración entre módulos

- **Lote 2.1** → ✅ subido al Hugging Face Hub: `ateneaxvalac/digitdeck-m1-e5-small-esci-es`,
  privado (`ARCHITECTURE.md` §5.3).
- **Lote 2.2** → `encoder.py`, `rag.py`, `vision.py`: extracción de la lógica ya escrita y medida
  en M1/M3/M4 (`ARCHITECTURE.md` §3.1-§3.4), sin reescribirla.
- **Lote 2.3** → `app.py`: servicio FastAPI con `POST /preguntar` y `GET /salud` (contrato:
  `ARCHITECTURE.md` §5.2) y logging estructurado por pregunta.
- **Lote 2.4** → `construir_indice.py`: BM25 + Chroma sobre las 80.383 fichas de ESCI, construido
  una sola vez y persistido (no reconstruido en cada arranque).
- **Listo cuando:** el servicio corre localmente de punta a punta con los cuatro modelos y
  responde igual que los notebooks de M3/M4 sobre el mismo eval set de 49 preguntas.

### Fase 3 · Despliegue
**Criterios:** Producción verificable

- **Lote 3.1** → `Dockerfile`, build y push a ECR (`digitdeck/app`).
- **Lote 3.2** → `terraform apply` en `project/infra/` con la imagen ya publicada.
- **Listo cuando:** `GET /salud` responde `ok: true` desde la URL pública (`terraform output url`).

### Fase 4 · Observabilidad
**Criterios:** Producción verificable

- **Lote 4.1** → logging estructurado a CloudWatch Logs (el driver `awslogs` ya está en
  `project/infra/user_data.sh.tpl`; falta que `app.py` emita el JSON por pregunta).
- **Lote 4.2** → W&B: proyecto `digitdeck-m5` con cada pregunta a la demo; decidir si se completa
  el historial de M2-M4, que hoy solo está en CSV/JSON.
- **Lote 4.3** → comprobación externa del health check (cron o servicio gratuito tipo UptimeRobot).
- **Listo cuando:** las cuatro cosas del Nivel 4 de "Producción verificable" están comprobadas a la
  vez: URL, W&B, logging estructurado, health check.

### Fase 5 · Verificación final
**Criterios:** Rigor de evaluación, Producción verificable

- **Lote 5.1** → correr el harness de M2 (`harness(eval_set, sistema)`, `ARCHITECTURE.md` §3.2)
  contra la URL pública, no contra una corrida local.
- **Lote 5.2** → reproducir, desde una máquina fuera del equipo, un resultado puntual del reporte
  solo con las instrucciones del `README.md`/`INFORME_M5.md`.
- **Listo cuando:** los dos lotes dan el mismo resultado que las corridas locales de M2-M4
  documentadas en sus `INFORME_Mx.md`.

> ### ★ Demo lista para sustentación
> Debe poder demostrarse: una pregunta por texto y una con foto respondidas en vivo desde la URL
> pública, `GET /salud` en verde, el historial de W&B visible, y un resultado del reporte
> reproducido sin ayuda de quien lo construyó. Nota: penalización por inasistencia — todo el
> equipo presente el día de la sustentación.

---

## 2 · Matriz de trazabilidad Fase · Lote → Criterio de la rúbrica

> Rúbrica completa en [`../README.md`](../README.md). Si un lote cambia de alcance, se actualiza
> esta matriz en el mismo commit.

| Fase | Lote | Criterio(s) de la rúbrica de M5 |
|---|---|---|
| 0 | 0.1 | — (investigación, sin criterio propio) |
| 0 | 0.2 | — (decisiones, sin criterio propio) |
| 1 | 1.1 | Producción verificable |
| 1 | 1.2 | Producción verificable |
| 2 | 2.1 | Integración entre módulos |
| 2 | 2.2 | Solidez técnica, Integración entre módulos |
| 2 | 2.3 | Solidez técnica, Producción verificable |
| 2 | 2.4 | Solidez técnica |
| 3 | 3.1 | Producción verificable |
| 3 | 3.2 | Producción verificable |
| 4 | 4.1 | Producción verificable |
| 4 | 4.2 | Producción verificable |
| 4 | 4.3 | Producción verificable |
| 5 | 5.1 | Rigor de evaluación |
| 5 | 5.2 | Producción verificable |

**Cobertura:** de los 7 criterios de la rúbrica de M5, este plan de despliegue cubre directamente
**Producción verificable**, **Solidez técnica**, **Integración entre módulos** y **Rigor de
evaluación**. Los otros tres — **Definición del problema y usuario**, **Comunicación de la demo**
y **Reflexión sobre limitaciones y ética** — no tienen lotes de despliegue propios: se resuelven en
`../../M1/PLANTILLA_DEFINICION.md` (campos 5-8), el guion de la demo y `INFORME_M5.md`
respectivamente, fuera del alcance de este documento.

---

## 3 · Estado del proyecto

> Única tabla de estado (✅ cerrado · 🟨 en curso · ⬜ pendiente). Las filas en negrita son las
> fases; debajo van sus lotes. Al cerrar un lote solo se edita su fila (y la de su fase si
> cambia).

| Fase · Lote | Estado | Notas |
|---|---|---|
| **0 · Investigación y decisiones** | ✅ | Cuenta, cuotas, precios y presupuesto confirmados el 2026-11-01; 10 decisiones tomadas con el equipo |
| 0.1 | ✅ | Cuenta `648617469176` (la misma de 4U_project y TrendAnalyzer); cuota G/VT 8 vCPU; `g5.xlarge` = 1,01 USD/h (API de precios, no estimado); presupuesto compartido `campus-locator-mensual` de 100 USD/mes ya existente; Docker no disponible en la WSL del equipo; hallazgo aparte: problema de CRLF/LF en el repo visto desde WSL (`ARCHITECTURE.md` §9, riesgo 4) |
| 0.2 | ✅ | Presupuesto propio (`digitdeck-mensual`, 40 USD/mes), IAM dedicado (`digitdeck-terraform`), instancia `g5.xlarge` — ADR-1 a ADR-10 en `ARCHITECTURE.md` §9 |
| **1 · Infraestructura** | 🟨 | `bootstrap/` e `infra/` escritos y en verde con `terraform validate`; **ningún `apply` corrido todavía** |
| 1.1 | ✅ (escrito) | `project/bootstrap/main.tf`: bucket `digitdeck-tfstate-648617469176`, tabla `digitdeck-tfstate-lock`, usuario `digitdeck-terraform`. `terraform validate`: éxito. `apply`: pendiente |
| 1.2 | ✅ (escrito) | `project/infra/`: EC2 `g5.xlarge`, ECR `digitdeck/app`, SSM Session Manager sin SSH, secretos en Parameter Store, presupuesto `digitdeck-mensual`. `terraform validate`: éxito. `apply`: pendiente (bloqueado por 1.1 y por no tener todavía una imagen que desplegar, Fase 3) |
| **2 · Servicio** | 🟨 | `servicio/` existe y compila; el encoder ya está en el Hub y el índice del catálogo ya se construyó de verdad; falta correr `app.py` de punta a punta con los cuatro modelos (sin GPU local de sobra para eso) |
| 2.1 | ✅ | Pesos reales (448,8 MB, `transformers_version 4.57.1`, confirmados contra `M1/README.md`) recuperados de la máquina de origen y subidos a `ateneaxvalac/digitdeck-m1-e5-small-esci-es` (privado) el 2026-11-02, vía `hf upload` desde un venv dedicado en WSL (`~/.venvs/digitdeck`). Riesgo 1 de `ARCHITECTURE.md` §9 cerrado |
| 2.2 | ✅ (sin correr) | `servicio/encoder.py`, `rag.py`, `vision.py` extraídos de `M1/ENTREGABLE.ipynb` (`score_relevancia`/`scorear_lote_finetuned`), `M3/ENTREGABLE.ipynb` §3-§7 (`buscar_hibrida`, `reordenar`, `verificar_existencia`, `buscar_similares`, `enrutar`, `generar`, `SYSTEM_RAG`) y `M4/pipeline/ENTREGABLE.ipynb` §4 (`ver`, `producto_identificado`, `correr_foto`). `sistema_D` ahora clasifica en los 6 estados que M4 ya usaba para el camino con foto (antes M3 solo distinguía "responde" / "se abstiene"), para que texto y foto compartan un solo contrato. Los tres módulos compilan (`py_compile`) y sus referencias cruzadas se verificaron estáticamente; nada se corrió con los modelos reales |
| 2.3 | ✅ (sin correr) | `servicio/app.py`: `POST /preguntar` y `GET /salud` con el contrato de `ARCHITECTURE.md` §5.2, logging JSON estructurado a stdout y envío opcional a W&B (si no hay `WANDB_API_KEY`, el servicio igual responde). Sin probar contra un servidor real |
| 2.4 | ✅ | `construir_indice.py` corrido de verdad el 2026-11-02 contra los parquet reales de ESCI: **80.949 fichas indexadas** (M3 reportó 80.383 sobre el mismo filtro — diferencia de 566 sin explicar, declarada aquí, no ajustada a mano). BM25 y Chroma coinciden en cantidad (80.949 los dos). Embeddings con `paraphrase-multilingual-MiniLM-L12-v2` en **CPU, sin GPU** (≈2 min 44 s para las 80.949 fichas — la nota de "requiere GPU" de la versión anterior de esta fila era incorrecta). Dos consultas de prueba (BM25 y densa, "zapatillas running mujer") devolvieron resultados coherentes. Índice en `servicio/indices/` (248 MB: `catalogo.json`, `bm25.pkl`, `chroma/`), protegido por `.gitignore` |
| **3 · Despliegue** | ⬜ | Bloqueada por la Fase 2 (no hay imagen que construir) |
| 3.1 | ⬜ | |
| 3.2 | ⬜ | |
| **4 · Observabilidad** | ⬜ | Bloqueada por la Fase 3 |
| 4.1 | ⬜ | El driver `awslogs` ya está declarado en `project/infra/user_data.sh.tpl` |
| 4.2 | ⬜ | M1 ya tiene una corrida en W&B (`https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg`); M2-M4 no |
| 4.3 | ⬜ | |
| **5 · Verificación final** | ⬜ | Bloqueada por la Fase 4 |
| 5.1 | ⬜ | |
| 5.2 | ⬜ | |
| **★ Demo lista para sustentación** | ⬜ | |

---

*SI4006 · Universidad EAFIT · Equipo Digitdeck.*
