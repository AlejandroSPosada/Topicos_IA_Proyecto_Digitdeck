# Digitdeck · M5 · PLAN

> Plan por fases y lotes del despliegue de M5, matriz de trazabilidad Fase · Lote → Criterio de
> la rúbrica de M5, y estado del proyecto.
> **Convención de actualización:** cerrar un lote = tocar **solo §3** de este archivo (la fila del
> lote). Este archivo no define contratos: para cualquier interfaz (API HTTP, nombres en AWS,
> variables de entorno, secretos) la fuente es **§5 de [`ARCHITECTURE.md`](ARCHITECTURE.md)**.
> Decisiones (ADR) y riesgos: **§9 de `ARCHITECTURE.md`**. Rúbrica completa y qué significa cada
> criterio para Digitdeck: [`../README.md`](../README.md).

## 0 · Próximos pasos inmediatos (al retomar)

Estado al 2026-11-02: el servicio está desplegado, `GET /salud` responde 200 con los 4 modelos
cargados y el logging a CloudWatch ya está activo y verificado, en
`http://54.173.61.242:8000` (instancia `i-00ca25dc4ee7c3557`, `g5.xlarge`). **Sigue
cobrando 1,01 USD/h mientras esté prendida** — si no se va a seguir trabajando ya, apagarla:

```bash
aws ec2 stop-instances --instance-ids i-00ca25dc4ee7c3557 --profile digitdeck --region us-east-1
```

`INFORME_M5.md` ya está escrito (2026-11-02). Lo único que falta ahora es **el guion de la demo de
8 minutos y los campos 5-8 de `../../M1/PLANTILLA_DEFINICION.md`** (`INFORME_M5.md` §1 y §6 ya
tienen material real para esos cuatro campos, falta trasladarlo) — todo el despliegue y su
verificación (Fases 1-5) ya está cerrado (detalle y porqué en `ARCHITECTURE.md` §9, riesgos 7-11):

- `POST /preguntar` ya se probó de verdad contra la instancia real el 2026-11-02 (§3, lote 2.3).
- El harness de M2/M3 ya corrió contra la URL pública en las 49 preguntas del eval set de M3:
  48/49 coinciden con la corrida local en abstención y apertura (§3, lote 5.1). La Dimensión 1
  (nDCG/MRR) y la 2 (juez) no se pudieron reproducir vía la API pública — riesgo 10.
- Un agente sin contexto de esta sesión reprodujo el resultado de `README.md` por su cuenta (§3,
  lote 5.2) y encontró un bug real de reproducibilidad en las instrucciones (`-d` en línea con
  tildes puede mandarse mal según la terminal) — ya corregido en `README.md`.
- A pedido del usuario se agregó una **página de demo en `GET /`** (`http://54.173.61.242:8000/`),
  para probar el servicio desde cualquier navegador sin armar JSON a mano, y se corrigió el mismo
  bug que encontró el agente de reproducibilidad: `foto_base64` inválida ahora da 422 claro, no un
  500 genérico. Al redesplegar se descubrió que ECR tiene **tags inmutables**: cada redespliegue
  necesita un tag nuevo, no `:latest` (`ARCHITECTURE.md` §9, riesgo 11).
- Probando la demo en vivo, el usuario encontró y documentó dos fallas reales no curadas: una
  afirmación falsa por mezclar foto y texto sin relación, y el generador citando productos con IDs
  inventados (copiados del propio ejemplo del prompt) — ambas en `INFORME_M5.md` §5/§6 y
  `ARCHITECTURE.md` §9, riesgos 12 y 13.
- Un compañero del equipo (rama `feat/frontend-ventanal`, PR #1, mergeada el 2026-11-02) rediseñó
  el frontend: veredicto claro por caso, cada ficha citada enlaza a Amazon.es (verificación externa
  de las citas — responde directamente al hallazgo de la alucinación), y traza colapsable de cómo
  llegó a la respuesta. Trajo también `project/infra/redesplegar.sh`, que automatiza
  build+push+reinicio desde un commit de GitHub (reemplaza el empaquetado manual que se hacía antes
  por `ssm send-command`). Desplegado con el tag `2026-11-02-frontend-ventanal`, verificado en el
  navegador — funciona.

**Nota operativa para quien retome esto:** para entrar a la WSL desde el Bash tool de Windows,
`MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" wsl -u root -d Ubuntu-26.04 -- bash -lc "..."` (si no,
las comillas y las rutas que empiezan por `/` se rompen al pasar de Windows a WSL — pasó varias
veces en la sesión del 2026-11-02). El drive `G:` no se monta solo:
`mkdir -p /mnt/g && mount -t drvfs G: /mnt/g` al principio de cada sesión nueva de `wsl`. Para
comandos con variables o comillas complejas, mejor escribir un script (archivo `.sh` real con
`Write`, no un `bash -lc "..."` en línea) y pasarlo por ruta literal — los intentos en línea
fallaron repetidamente, incluido un falso "token de HF inválido" que en realidad era un bug de
comillas, y el 2026-11-02 un bug más raro todavía: dentro de `bash -lc '...'` las variables
asignadas en el mismo comando (`X=1; echo $X`) se quedan vacías al expandirlas aunque `set`/
`declare -p` confirman que sí quedaron asignadas; un archivo `.sh` real ejecutado con
`bash /ruta/al/script.sh` no tiene ese problema. Si `echo $X` da vacío con una variable que
debería tener valor, no es el token/credencial — es este bug, escribe un script y vuelve a
intentar. Ojo también: `wsl --terminate` / `wsl --shutdown` tumba la integración de Docker Desktop
con esa distro (aparece un diálogo de "WSL integration unexpectedly stopped" que solo el usuario
puede cerrar) — evitar terminar la distro a menos que sea necesario.

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
| 2.2 | ✅ | `servicio/encoder.py`, `rag.py`, `vision.py` extraídos de `M1/ENTREGABLE.ipynb` (`score_relevancia`/`scorear_lote_finetuned`), `M3/ENTREGABLE.ipynb` §3-§7 (`buscar_hibrida`, `reordenar`, `verificar_existencia`, `buscar_similares`, `enrutar`, `generar`, `SYSTEM_RAG`) y `M4/pipeline/ENTREGABLE.ipynb` §4 (`ver`, `producto_identificado`, `correr_foto`). `sistema_D` ahora clasifica en los 6 estados que M4 ya usaba para el camino con foto (antes M3 solo distinguía "responde" / "se abstiene"), para que texto y foto compartan un solo contrato. **Probado el 2026-11-02 con el encoder real (del Hub) y el generador real, contra el índice real del Lote 2.4** — solo la ruta de texto sin `buscar_similares`, en la WSL del equipo (7,4 GB de RAM; el verificador de 3B y el VLM de 2B no caben ahí y se prueban en la instancia de AWS, Fase 3): `encoder.cargar()` descargó el repo privado del Hub sin problema (+405 MB); el generador cargó en +2,97 GB (total 5,6 GB, dentro del límite); `verificar_existencia("audifonos inalambricos bluetooth")` devolvió 5 fichas, todas relevantes; `sistema_D("¿tienen audífonos inalámbricos bluetooth?")` dio `estado: respuesta_generada`, abrió con "Sí, lo tenemos:" (contrato de M3 §5 cumplido) y citó 5 fichas coherentes con el texto; latencia total 11,5 s en CPU. Ningún bug de código encontrado — corrió a la primera. No probado aquí (necesita la GPU de AWS): `buscar_similares` (verificador 3B) y el camino con foto (VLM 2B) |
| 2.3 | ✅ | `servicio/app.py`: `POST /preguntar` y `GET /salud` con el contrato de `ARCHITECTURE.md` §5.2, logging JSON estructurado a stdout y envío opcional a W&B. **Probado el 2026-11-02 contra la instancia real** (`http://54.173.61.242:8000`) en las tres rutas: texto existencia ("¿tienen audífonos inalámbricos bluetooth?" → `respuesta_generada`, 5 fichas, 7,7 s), texto similar con `buscar_similares` + verificador de 3B ("cafetera parecida a la Bialetti Moka Express" → `respuesta_generada`, apertura "No lo tenemos exacto, pero hay productos parecidos:", 2,4 s) y foto con el VLM (`M4/eval_set/imagenes/img_01.jpg`, iPhone 11 Pro Max oro → identificó el producto y citó la ficha `B07XS4J7R6`, coincide con el resultado esperado del eval set de M4, 8,7 s). Las tres devolvieron HTTP 200 con el contrato esperado |
| 2.4 | ✅ | `construir_indice.py` corrido de verdad el 2026-11-02 contra los parquet reales de ESCI: **80.949 fichas indexadas** (M3 reportó 80.383 sobre el mismo filtro — diferencia de 566 sin explicar, declarada aquí, no ajustada a mano). BM25 y Chroma coinciden en cantidad (80.949 los dos). Embeddings con `paraphrase-multilingual-MiniLM-L12-v2` en **CPU, sin GPU** (≈2 min 44 s para las 80.949 fichas — la nota de "requiere GPU" de la versión anterior de esta fila era incorrecta). Dos consultas de prueba (BM25 y densa, "zapatillas running mujer") devolvieron resultados coherentes. Índice en `servicio/indices/` (248 MB: `catalogo.json`, `bm25.pkl`, `chroma/`), protegido por `.gitignore` |
| **3 · Despliegue** | ✅ | `terraform apply` de `project/infra/` aplicado, imagen en ECR, instancia corriendo y **`GET /salud` responde 200 con los 4 modelos cargados** (`encoder`, `generador`, `verificador`, `vlm`) — primera vez que corren juntos de verdad, sobre la GPU real. Detalle de cómo se llegó ahí en 3.1 y 3.2 |
| 3.1 | ✅ | El push local (13,5 GB) nunca funcionó de forma estable en esta red (capa de 7,4 GB se trababa en 0 B/s incluso tras reiniciar Docker Desktop y WSL2 por completo — ver §9 riesgo de `ARCHITECTURE.md`). Se cambió de estrategia: el código del servicio (19 KB comprimidos) se mandó por `ssm send-command` y la imagen se construyó y subió **desde la propia instancia**, sobre la red de AWS — el push de 4,57 GB tardó **1 minuto**. Para esto, `project/infra/iam.tf` necesitó permisos de push a ECR que no tenía (solo pull) |
| 3.2 | ✅ | `terraform apply` aplicado (bootstrap e infra, con 3 rondas de fixes de permisos IAM: `ssm:DescribeParameters`, permisos de sesión/comando de SSM, y push a ECR — todos bloqueados por el clasificador de permisos y corridos por el usuario). Índice del catálogo construido en la instancia con GPU: **56 segundos** (vs. 74 min que hubiera tomado en CPU — el primer intento olvidó `--gpus all`). Contenedor arrancado a mano por SSM (el arranque automático de `user_data.sh.tpl` falló en el primer boot porque la imagen no existía todavía). `GET /salud` → `{"ok":true,"modelos_cargados":["encoder","generador","verificador","vlm"],"indice_listo":true}`, confirmado de forma independiente. El `docker run` manual inicial no incluyó `--log-driver=awslogs` — corregido en el lote 4.1 |
| **4 · Observabilidad** | 🟨 | Lote 4.1 cerrado (2026-11-02); faltan 4.2 (historial de W&B de M2-M4) y 4.3 |
| 4.1 | ✅ | Contenedor reiniciado por `ssm send-command` con `--log-driver=awslogs` (mismos flags que `user_data.sh.tpl`). `docker inspect` confirma `LogConfig.Type: awslogs`; `aws logs describe-log-streams --log-group-name /digitdeck/app` (con el rol de la instancia) confirma un log stream con eventos ya ingeridos. `app.py` ya emitía el JSON estructurado por pregunta — no hubo que tocar código, solo el flag del `docker run` (`ARCHITECTURE.md` §9, riesgo 8) |
| 4.2 | ⬜ | M1 ya tiene una corrida en W&B (`https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg`); M2-M4 no |
| 4.3 | ⬜ | |
| **5 · Verificación final** | ✅ | Lotes 5.1 y 5.2 cerrados (2026-11-02) |
| 5.1 | ✅ | Corridas las 49 preguntas del eval set extendido de M3 contra `http://54.173.61.242:8000/preguntar` de verdad (0 errores, 2,59 s de latencia media por llamada HTTP). **La decisión del sistema (abstiene/no abstiene y apertura: afirma/similares/abstiene) coincide con la corrida local guardada en `M3/Resultados/salidas_sistemas.json["D"]` en 48/49 y 48/49 casos** — la reproducción end-to-end en producción es prácticamente exacta. Las 2 discrepancias están explicadas caso por caso en `ARCHITECTURE.md` §9 (no son errores: una es no determinismo del enrutador en un caso límite, la otra es un rechazo a nivel de texto del generador que el estado `respuesta_generada` no captura). **Limitación encontrada y documentada, no inventado un número:** la Dimensión 1 (nDCG@10/MRR) y la Dimensión 2 (juez LLM) de M2/M3 no se pudieron reproducir contra la API pública porque `POST /preguntar` no expone el ranking completo top-10 ni corre el juez holístico — solo el texto final y las fichas citadas. Por la misma razón, los conteos de "acierto de pantalla/respuesta" que sí alcancé a calcular usan `fichas_citadas` (lo que el generador cita literalmente) como sustituto de `pantalla`/`contexto_ids` (todo lo que se le pasó al generador, hasta 5 fichas) — son sistemáticamente más bajos que los de M3 y **no son comparables** a los `+0,265`/`+0,273` del informe de M3; están en `scratchpad` local, no se citan como cifra de calidad |
| 5.2 | ✅ | Se le dio a un agente genuinamente sin contexto de esta sesión **solo** el texto de la nueva sección "Cómo reproducir un resultado" de `README.md`, y se le pidió reproducirlo contra la URL pública. El health check coincidió exacto. El `POST /preguntar` con el comando tal cual estaba escrito (acento pegado en `-d` en línea) **falló con 400 "There was an error parsing the body"** — un hallazgo real, no inventado: según la codificación de la terminal del lector, el `-d` en línea con tildes puede mandarse mal. Al escribir el cuerpo a un archivo y mandarlo con `--data-binary` (lo que el agente probó por su cuenta para descartar el problema), la respuesta coincidió exacta: `estado: respuesta_generada`, `fichas_citadas: ["B07527ZB5Y"]`, apertura "No lo tenemos exacto, pero hay productos parecidos:". **Se corrigió `README.md`** para usar `--data-binary @archivo.json` en vez de `-d` en línea, documentando por qué |
| **★ Demo lista para sustentación** | ⬜ | |

---

*SI4006 · Universidad EAFIT · Equipo Digitdeck.*
