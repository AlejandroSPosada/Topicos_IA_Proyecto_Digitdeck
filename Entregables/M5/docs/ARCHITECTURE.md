# Digitdeck · ARCHITECTURE

> Documento maestro de arquitectura, contratos y despliegue. Última actualización: 2026-11-01.
> Plan de despliegue paso a paso: [`PLAN.md`](PLAN.md). Rúbrica y estado de M5:
> [`../README.md`](../README.md). Visión general del repo: [`../../../README.md`](../../../README.md).
> El detalle interno de cada módulo **no se repite aquí**: vive en el `README.md`/`INFORME_Mx.md`
> de cada uno y este documento enlaza a él. Formato inspirado en el `ARCHITECTURE.md` de
> TrendAnalyzer (otro proyecto del equipo), adaptado a la escala de un proyecto de curso de un
> semestre, no de una plataforma de datos en producción continua.

---

## 0 · Cómo usar este documento

Pensado para que **baste con leerlo para entender cómo encajan M1-M4 y qué hace falta para
desplegarlos como un solo sistema**, sin tener que abrir los cuatro notebooks.

| Si quieres… | Lee |
|---|---|
| Entender el problema, el usuario y la decisión que resuelve Digitdeck | §1, y `../../M1/PLANTILLA_DEFINICION.md` §1-2 |
| Ver el sistema completo de un vistazo | §2 |
| Saber qué hace cada módulo y cómo usarlo sin leer su notebook | §3 (una subsección por módulo) |
| Seguir una pregunta desde que entra hasta que sale una respuesta | §4 |
| Saber **cómo se habla con cada pieza** (variables de entorno, la API HTTP, los nombres en AWS, los secretos) | **§5 (contratos)** |
| Ver la estructura completa del repositorio | §6 |
| Saber qué falta y en qué orden construirlo | §7, y el detalle en [`PLAN.md`](PLAN.md) |
| Qué comprobar antes de desplegar o antes de la demo | §8 |
| Por qué se decidió algo, qué riesgos quedaron declarados y qué sigue sin decidirse | §9 |
| En qué estado está cada módulo hoy | §10 |

**Regla de oro (tomada de TrendAnalyzer):** si dos piezas se comunican, su interfaz vive en §5.
Si algo no está en §5, no es un contrato todavía y ningún otro componente debería depender de él.

---

## 1 · Qué es Digitdeck, en una frase

**Copiloto de calidad de búsqueda para ecommerce en español.** El usuario es el **líder de
ecommerce** de la tienda; la decisión que cambia con el sistema es **cuáles consultas intervenir y
en qué orden** (aprobar el reordenamiento que propone el modelo, corregir la ficha de un producto
mal descrito, o descartar el caso). Detalle completo, con el costo del error y el resto de la
definición del proyecto: `../../M1/PLANTILLA_DEFINICION.md`.

De cara al comprador (M3-M4), el sistema es un asistente al que se le pregunta si la tienda tiene
un producto — por texto o con una foto — y responde citando la ficha del catálogo, o se abstiene.

---

## 2 · Arquitectura objetivo

```
                         ┌─────────────────────────────────────────────┐
                         │              Servicio único (M5)              │
                         │                                                │
  pregunta (texto) ─────►│  ¿hay foto?                                    │
  + foto opcional ───────►│    sí → ver() [M4: Qwen2-VL-2B]                │
                         │         └─ válvula: ¿hay producto? ────────┐   │
                         │    no  → la pregunta tal cual               │   │
                         │                                            ▼   │
                         │  enrutador [M3: Qwen2.5-1.5B] ── elige herramienta
                         │     │                                          │
                         │     ├─ verificar_existencia ─┐                 │
                         │     └─ buscar_similares ──────┤                │
                         │     └─ ninguna → abstención   │                │
                         │                               ▼                │
                         │  búsqueda híbrida (BM25 + densa, RRF)          │
                         │  reranker [M1: e5-small ajustado]              │
                         │  verificador de exacto [Qwen2.5-3B] (solo      │
                         │    en buscar_similares)                        │
                         │                               │                │
                         │  generador [Qwen2.5-1.5B] ◄────┘               │
                         │     con el prompt + fichas citadas             │
                         └─────────────────────┬─────────────────────────┘
                                                ▼
                                   respuesta + estado + citas
```

Cuatro modelos (encoder de M1, generador, verificador/juez, VLM), un índice léxico+denso sobre el
catálogo de ESCI, y la lógica de enrutamiento/abstención de M3 extendida por M4. Hoy esas piezas
viven en 4 notebooks ejecutados a mano; M5 las empaqueta en el servicio de la izquierda.

### 2.1 · Presupuesto de memoria de GPU

| Pieza | Tamaño en fp16 | De dónde sale hoy |
|---|---|---|
| Encoder ajustado (M1) | ≈450 MB | HF Hub, privado (`ateneaxvalac/digitdeck-m1-e5-small-esci-es`) |
| Generador (`Qwen2.5-1.5B-Instruct`) | ≈3 GB | HF Hub, público |
| Verificador/juez (`Qwen2.5-3B-Instruct`) | ≈6 GB | HF Hub, público |
| VLM (`Qwen2-VL-2B-Instruct`) | ≈4-5 GB | HF Hub, público |
| **Total si las cuatro están cargadas a la vez** | **≈13-14 GB** | |

M4 nunca cargó las cuatro a la vez (alternaba verificador y VLM en dos fases) y aun así llegó a un
pico de 9,95 GB en una tarjeta de 16 GB (`../../M4/INFORME_M4.md` §3.3). Un servicio con tráfico
real y las dos intenciones activas (existencia y similar) no puede repetir ese malabar: de ahí
ADR-6 (§9), una GPU con ≥24 GB en vez de quedar al límite de una T4 de 16 GB.

---

## 3 · Componentes

### 3.1 · M1 — el motor: encoder ajustado

Fine-tuning de `intfloat/multilingual-e5-small` (118 M parámetros) sobre pares `(consulta,
producto)` del dataset ESCI, con cabeza de clasificación binaria. La **probabilidad de la clase
"relevante"** se usa como score de ranking.

**Interfaces — cómo usarlo sin leer el notebook:**

| Qué | Valor |
|---|---|
| Pesos | `ateneaxvalac/digitdeck-m1-e5-small-esci-es` en el HF Hub (privado, 448 MB), subidos el 2026-11-02 |
| Entrada | prefijos obligatorios: `"query: " + consulta`, `"passage: " + título del producto` |
| Salida | softmax sobre 2 logits; se usa la probabilidad de la clase 1 (relevante) como score continuo |
| Métrica de referencia | nDCG@10 = 0,8369 sobre el split de test completo (92.739 pares, 3.844 consultas) — `../../M1/README.md` |
| Variante liviana (no desplegada) | adaptador LoRA r=8, 0,57 MB, nDCG@10 0,8305 (-0,78%) — `../../M3/INFORME_M3.md` §7.8. Se descartó para producción en favor de los pesos completos (decisión de este módulo, §9 ADR-1) |

### 3.2 · M2 — la vara: harness de evaluación

Tres dimensiones (nDCG@10 contra ESCI, LLM-as-a-judge por ítem con `Qwen2.5-3B`, regla de dominio
de primera pantalla), calibradas contra anotación humana (kappa 0,79 entre anotadores).

**Interfaces:**

| Qué | Valor |
|---|---|
| Función reutilizable | `harness(eval_set, sistema)` — mide cualquier sistema que exponga `sistema(consulta, candidatos) -> ordenamiento + abstención`, sin cambios entre módulos (`../../M2/INFORME_M2.md` §13) |
| Eval set base | 13 casos (10 gold + 3 adversariales) en `../../M2/Resultados/eval_set.json`, ampliado a 49 preguntas en M3 |
| Umbral de abstención | calibrado sobre 300 consultas de test (fuera del eval set): 0,5993 para el modelo ajustado |

### 3.3 · M3 — el conocimiento: RAG con herramientas

Búsqueda híbrida (BM25 + densa, RRF k=60) + reranking con el encoder de M1 + dos herramientas que
el generador elige por function calling.

**Interfaces:**

| Qué | Valor |
|---|---|
| Punto de entrada | `sistema_D(pregunta)` → ordenamiento + texto de respuesta + estado |
| `verificar_existencia(consulta)` | híbrida + reranker; se quedan las fichas con score ≥ umbral de exacto (0,5993) |
| `buscar_similares(consulta)` | idem, más un **verificador de exacto** (`Qwen2.5-3B`) que descarta las candidatas que sí son exactas |
| Generador | `Qwen/Qwen2.5-1.5B-Instruct`, greedy, prompt de 4 partes con 2 válvulas y 3 aperturas obligatorias |
| Corpus | 80.383 fichas de ESCI en español (título + marca + color + viñetas); se reconstruye desde los parquet de `amazon-science/esci-data` — no persistido en el repo |
| Umbrales | `../../M3/Resultados/umbrales_m3.json` |
| Resultado medido | A→D: +0,273 nDCG@10 en existencia, +0,265 en aciertos de respuesta, sin costo neto de latencia (2,08 s vs 2,02 s) — `../../M3/INFORME_M3.md` §7 |

### 3.4 · M4 — los ojos: componente visual

Un VLM traduce una foto a un JSON de atributos del producto; esos atributos arman la consulta que
entra al enrutador de M3. Alcance: **solo `verificar_existencia`** (no se probó `buscar_similares`
con foto).

**Interfaces:**

| Qué | Valor |
|---|---|
| Punto de entrada | `ver(foto)` → JSON (`es_producto`, `tipo_producto`, `marca`, `modelo`, `color`, `texto_visible`) |
| Modelo | `Qwen2-VL-2B-Instruct`, resolución acotada (`min_pixels`/`max_pixels`), salida greedy |
| Válvula | si `es_producto` es falso o no hay tipo de producto, el sistema se abstiene antes de buscar |
| **Contrato de estado de salida** (reusado tal cual en §5.2 como contrato de la API) | `respuesta_generada` · `sin_resultados` · `abstencion_dominio` · `sin_producto` · `error_formato` · `error_operativo` — `../../M4/INFORME_M4.md` §3.4 |
| Sin foto | `sistema_multimodal(pregunta)` llama a `sistema_D` de M3 tal cual, sin cambios |
| Resultado medido | con la vara oficial de M3 (D3): 4/12 aciertos con foto vs. 3/12 con la pregunta sola; +1,44 s por caso (el VLM) — `../../M4/README.md` |

### 3.5 · M5 — el servicio y el despliegue (lo nuevo de este módulo)

Lo único que M5 construye de cero: el empaquetado de 3.1-3.4 en un servicio, y la infraestructura
que lo corre.

**Interfaces** (desplegado y corriendo desde el 2026-11-02: `GET /salud` y `POST /preguntar`
verificados contra la instancia real — `PLAN.md` §3, Fases 3 y 5 — y `GET /` sirve una página de
demo para probarlo desde el navegador, §5.2):

| Pieza | Dónde queda |
|---|---|
| `project/servicio/encoder.py` | carga del encoder de M1 (desde el Hub, §9 ADR-1) y el reranking |
| `project/servicio/rag.py` | búsqueda híbrida, las dos herramientas, el verificador de exacto |
| `project/servicio/vision.py` | `ver()` y su válvula |
| `project/servicio/app.py` | FastAPI: `POST /preguntar`, `GET /salud`, `GET /` (demo) — contrato en §5.2 |
| `project/servicio/static/index.html` | página de demo servida en `GET /`, HTML/JS puro sin build (§5.2) |
| `project/servicio/construir_indice.py` | Lote 2.4: construye y persiste el índice del catálogo |
| `project/servicio/Dockerfile`, `.dockerignore` | imagen de 4,57 GB; `indices/` y `datos/esci/` no viajan en ella (§9, riesgo 5) |
| `project/bootstrap/` | estado remoto de Terraform + usuario IAM dedicado (se corre una vez) |
| `project/infra/` | EC2 con GPU, ECR, IAM de la instancia, secretos, presupuesto — contrato en §5.4 |

---

## 4 · Flujo extremo a extremo

1. Llega una pregunta al servicio, con o sin foto adjunta (§5.2).
2. **Si hay foto:** `ver()` (M4) la convierte en un JSON de atributos. Si la válvula decide que no
   hay producto identificable, el sistema responde `sin_producto` y termina aquí — no se busca
   nada.
3. Se arma la consulta: con foto, a partir de tipo + marca + modelo + color del JSON (M4 §3.1,
   fila 4); sin foto, la pregunta tal cual.
4. El **enrutador** (M3, `Qwen2.5-1.5B`) decide: `verificar_existencia`, `buscar_similares`, o
   ninguna (abstención de dominio — p. ej. una pregunta de logística o un producto de venta
   restringida).
5. La herramienta elegida corre la búsqueda híbrida + el reranker de M1; `buscar_similares` además
   pasa las candidatas por el verificador de exacto (`Qwen2.5-3B`).
6. Si ninguna ficha pasa el umbral, el estado es `sin_resultados`.
7. Si hay fichas, el **generador** (`Qwen2.5-1.5B`) escribe la respuesta citando las fichas, con
   las tres aperturas del contrato de M3 ("Sí, lo tenemos" / "No lo tenemos exacto, pero..." /
   "No tengo esa información en mis fuentes").
8. Con foto, la respuesta cierra aclarando qué se vio en la imagen y que las fichas son del
   catálogo histórico de ESCI, no del inventario actual (M4 §3.1, paso 8).
9. Cada pregunta se loguea (intención, herramienta, score contra el umbral, latencia por etapa,
   estado final) y se registra en W&B — contrato en §5.7. El código de `app.py` ya lo hace, y desde
   el 2026-11-02 esos logs llegan a CloudWatch en la instancia real (§9, riesgo 8, resuelto).

---

## 5 · Contratos de comunicación

> Como en TrendAnalyzer: esta es la sección que hace innecesario reenviar código para saber cómo
> hablarle a una pieza del sistema.

### 5.1 · Convenciones globales

| Convención | Valor |
|---|---|
| Nube | AWS, cuenta `648617469176`, región `us-east-1` (confirmado el 2026-11-01) |
| Prefijo de nombres | `digitdeck-dev-*` para recursos de este proyecto, `digitdeck-tfstate-*` para el estado — nunca `campus-locator-*` ni `ta-*` (son de los otros dos proyectos en la misma cuenta) |
| Repositorio de imágenes | ECR `digitdeck/app`, tags **inmutables** — cada redespliegue necesita un tag nuevo, no se puede re-pushear `:latest` (§9, riesgo 11) |
| Etiqueta de costo | `Project = digitdeck` en todo recurso de `project/infra/` (para el presupuesto de §5.4 y para no confundirse con el gasto de los otros proyectos) |
| Terraform | ≥1.9, proveedor `hashicorp/aws ~> 5.0`. Dos stacks: `project/bootstrap/` (estado local, se aplica una sola vez) y `project/infra/` (estado en S3, backend con candado en DynamoDB) |
| Autenticación de Terraform | perfil de AWS CLI `digitdeck` (usuario IAM dedicado creado por `bootstrap/`), nunca las llaves root `default`/`campus-admin` que ya había en la cuenta |
| Acceso a la instancia | **SSM**, no SSH (el security group no abre el puerto 22). En la práctica, `aws ssm send-command` (`AWS-RunShellScript`) para correr comandos puntuales desde un script, no `start-session` interactivo — más fácil de automatizar. El usuario `digitdeck-terraform` necesita permisos de sesión/comando de SSM además de `/digitdeck/*` (§9, ADR-15) |
| Secretos | **SSM Parameter Store** (`SecureString`), nunca Secrets Manager (evita ~0,40 USD/secreto/mes) ni variables quemadas en la imagen |
| Tiempo | UTC en logs y en W&B |

### 5.2 · API HTTP del servicio

`app.py` ya existe y está desplegado. `GET /salud` y `POST /preguntar` verificados en producción
(ver §9, verificación de producción). Desde el 2026-11-02 el servicio también sirve **`GET /`**,
una página de demo en HTML/JS puro (`project/servicio/static/index.html`, sin build ni
dependencias) para probar el sistema desde cualquier navegador sin armar JSON a mano — pregunta de
texto, adjuntar foto opcional, respuesta formateada con apertura/estado/latencia. No reemplaza el
contrato HTTP: `/docs` (Swagger, autogenerado por FastAPI) sigue siendo la API real para
integraciones.

**`POST /preguntar`**

```json
// request
{
  "pregunta": "¿tienen el Xiaomi Redmi Note 7 negro?",
  "foto_base64": null
}
```

Si `foto_base64` no es base64 válido, responde **422** con el detalle del error (antes del
2026-11-02 tiraba un 500 genérico sin explicación — lo encontró un agente externo probando la
reproducibilidad del README, `PLAN.md` lote 5.2).

```json
// response
{
  "respuesta": "Sí, lo tenemos: ...",
  "estado": "respuesta_generada",
  "fichas_citadas": ["product_id_1", "product_id_2"],
  "latencia_ms": {
    "vision": null,
    "enrutamiento": 630,
    "recuperacion_reranking": 110,
    "verificador": null,
    "generacion": 1402,
    "total": 2142
  }
}
```

`estado` toma uno de los seis valores del contrato de M4 §3.4: `respuesta_generada` ·
`sin_resultados` · `abstencion_dominio` · `sin_producto` · `error_formato` · `error_operativo`.
Los dos de error quedan **fuera de la nota** del harness (M4 §3.4) pero sí se loguean y se cuentan
en la cobertura.

**`GET /salud`**

```json
{
  "ok": true,
  "modelos_cargados": ["encoder", "generador", "verificador", "vlm"],
  "indice_listo": true
}
```

Confirma que los cuatro modelos están en memoria y el índice responde, **sin** correr una
inferencia completa — es el "health check que responde" de la rúbrica de M5.

### 5.3 · Modelos: dónde viven

| Modelo | Repo | Acceso |
|---|---|---|
| Encoder ajustado (M1) | `ateneaxvalac/digitdeck-m1-e5-small-esci-es` (HF Hub, subido el 2026-11-02) | privado, token en SSM (`/digitdeck/hf_token`) |
| Generador | `Qwen/Qwen2.5-1.5B-Instruct` | público |
| Verificador / juez | `Qwen/Qwen2.5-3B-Instruct` | público |
| VLM | `Qwen/Qwen2-VL-2B-Instruct` | público |

### 5.4 · AWS: recursos y nombres (ya aplicados — valores reales del 2026-11-02)

| Recurso | Nombre / valor | Terraform |
|---|---|---|
| Bucket de estado | `digitdeck-tfstate-648617469176` | `project/bootstrap/main.tf` |
| Tabla de candado | `digitdeck-tfstate-lock` | idem |
| Usuario IAM de Terraform | `digitdeck-terraform` (access key creada a mano, rotada una vez por exposición accidental en consola — §9 riesgo) | idem |
| Instancia | `i-00ca25dc4ee7c3557`, `g5.xlarge`, AMI `ami-0529e66637fd15e6e` ("Deep Learning OSS Nvidia Driver AMI GPU PyTorch ... (Ubuntu 24.04)" — el nombre cambió desde que se escribió el filtro, §9 ADR-13) | `project/infra/ec2.tf` |
| IP elástica | `54.173.61.242` → `http://54.173.61.242:8000` | idem |
| Security group | `digitdeck-dev-ec2` (`sg-0edbc8f4579579da4`) — solo el puerto 8000, nada de SSH | `project/infra/security.tf` |
| Rol/perfil de la instancia | `digitdeck-dev-ec2` — SSM, CloudWatch Logs, pull **y push** de ECR (§9 ADR-14), lectura de `/digitdeck/*` en SSM | `project/infra/iam.tf` |
| Repositorio de imágenes | `digitdeck/app`, imágenes subidas **desde la propia instancia**, no en local (§9 ADR-12). Tags inmutables (§9 riesgo 11): la instancia corre hoy el tag `2026-11-02-frontend`, no `:latest` — `:latest` quedó congelado en la versión sin el frontend/sin el fix 422, y `user_data.sh.tpl`/Terraform siguen apuntando a `:latest` por defecto | `project/infra/ecr.tf` |
| Presupuesto | `digitdeck-mensual`, 40 USD/mes (ajustable), filtrado por la etiqueta `Project=digitdeck` | `project/infra/budget.tf` |
| Índice del catálogo | en `/data/digitdeck/indices` de la instancia (montado como volumen, no en la imagen), construido ahí mismo con GPU en 56 s | `project/infra/user_data.sh.tpl` |

### 5.5 · Secretos

| Parámetro SSM | Contiene | Quién lo lee |
|---|---|---|
| `/digitdeck/hf_token` | token de HF con lectura al repo privado del encoder (rotado dos veces el 2026-11-02 por exposición accidental, §9 riesgo) | se lee al arrancar el contenedor — por `user_data.sh.tpl` en el primer boot automático, o a mano por `ssm send-command` si el contenedor se reinicia manualmente (como pasó el 2026-11-02, §9 ADR-14) |
| `/digitdeck/wandb_api_key` | API key de W&B | idem |

Ninguno de los dos se pasa por variable de Terraform hacia el estado en texto plano más allá de lo
estrictamente necesario para crear el `SecureString`; `terraform.tfvars` con los valores reales
**nunca se commitea** (`project/infra/.gitignore`).

### 5.6 · Salidas de Terraform

`terraform output` en `project/infra/`: `url` (URL pública del servicio), `health_check_url`,
`instance_id`, `ecr_repository_url`, `ssm_session_command`.

### 5.7 · W&B y logging (propuesto — todavía no implementado)

| Qué | Valor |
|---|---|
| Proyecto de W&B | `digitdeck-m5` |
| Qué se loguea por pregunta | intención, herramienta elegida, score contra el umbral, latencia por etapa (§5.2), estado final |
| Logging estructurado | JSON por línea a stdout; el contenedor lo manda a CloudWatch Logs vía el driver `awslogs` de Docker (grupo `/digitdeck/app`, `project/infra/user_data.sh.tpl`) |
| Historial del semestre | M1 ya tiene una corrida en W&B (`https://wandb.ai/scastano/digitdeck-m1/runs/uve9istg`); M2-M4 no se registraron — pendiente decidir si se completa (§9, pregunta abierta) |

---

## 6 · Estructura del repositorio

```
gitEquipos/
├── README.md
├── Clases/                      # material de la docente (M1, M2; M3-M5 aún no publicado)
└── Entregables/
    ├── M1/                       # encoder ajustado — ENTREGABLE.ipynb, README, PLANTILLA_DEFINICION
    ├── M2/                       # harness de evaluación — ENTREGABLE.ipynb, INFORME_M2.md
    ├── M3/                       # RAG + herramientas — ENTREGABLE.ipynb, INFORME_M3.md
    ├── M4/                       # visión — pipeline/ENTREGABLE.ipynb, INFORME_M4.md
    └── M5/                       # este módulo
        ├── README.md             # rúbrica de M5 y qué falta por criterio
        ├── docs/
        │   ├── PLAN.md            # plan de despliegue, paso a paso
        │   └── ARCHITECTURE.md    # este documento
        ├── project/               # el código de M5: Terraform + el servicio que despliega
        │   ├── README.md
        │   ├── bootstrap/          # estado remoto + IAM dedicado (una vez)
        │   ├── infra/               # EC2 GPU, ECR, presupuesto, outputs
        │   └── servicio/            # encoder.py, rag.py, vision.py, app.py, construir_indice.py, Dockerfile
        ├── Resultados/             # pendiente: scorecard final, evidencia de W&B
        └── Validacion/             # pendiente
```

---

## 7 · Plan por fases

Movido a [`PLAN.md`](PLAN.md): §1 fases y lotes del despliegue de M5 con sus criterios de la
rúbrica y marcador ★, y §2 matriz de trazabilidad Fase · Lote → Criterio. Los contratos no viven
allí: para cualquier interfaz, §5 de este documento.

---

## 8 · Antes de desplegar o de la demo (preflight)

**Antes de `terraform apply` en `project/infra/`:**
- [ ] `project/bootstrap/` ya se corrió y el perfil `digitdeck` está configurado (§5.1).
- [ ] La imagen `digitdeck/app:latest` ya existe en ECR (`PLAN.md` Fase 3).
- [ ] `terraform.tfvars` tiene el token de HF, la API key de W&B y el correo del equipo — y no está
      commiteado.
- [ ] Alguien revisó `terraform plan`: son recursos con costo real.

**Antes de la demo:**
- [ ] La instancia está **encendida** (`aws ec2 start-instances`, no se asume que sigue prendida de
      la última sesión).
- [ ] `GET /salud` responde `ok: true` con los cuatro modelos cargados.
- [ ] El harness de M2 corrió contra la URL pública en las últimas 24h (`PLAN.md` Fase 5).
- [ ] Después de la demo: apagar con `stop-instances`, no `destroy` (ADR-10, `project/infra/README.md`).

**Antes de validar cualquier pieza de M1-M4 por separado:** sus propios notebooks siguen siendo la
fuente de verdad de cómo correrlos — `../../M1/README.md`, `../../M2/INFORME_M2.md`,
`../../M3/README.md`, `../../M4/README.md`.

---

## 9 · Decisiones (ADR), riesgos y preguntas abiertas

### Decisiones

- **ADR-1 (M5, 2026-11-01).** Desplegar los **pesos completos** del encoder de M1, no el adaptador
  LoRA de la ablación de M3. *Por qué:* es el resultado oficial de M1 (nDCG@10 0,8369 contra 0,8305
  de LoRA); la diferencia de tamaño (448 MB vs 0,57 MB) no es un problema en una instancia con
  150 GB de disco. *Costo:* depende de que alguien del equipo suba esos pesos al Hub — hoy no están
  en ningún otro lugar (riesgo, abajo).
- **ADR-2 (M5, 2026-11-01).** La demo pública despliega el **sistema completo** (existencia +
  similar, con y sin foto), no una versión recortada. *Por qué:* es lo que pide "Integración entre
  módulos" de la rúbrica — un sistema recortado dejaría `buscar_similares` fuera de la demo.
  *Costo:* obliga a una GPU con ≥24 GB (ADR-6), porque las cuatro piezas pueden estar activas a la
  vez.
- **ADR-3 (M5, 2026-11-01).** Desplegar en la cuenta de AWS existente (`648617469176`), no pedir
  una cuenta nueva. *Por qué:* ya tiene GPU habilitada y es donde está el presupuesto del equipo.
  *Costo:* comparte cuenta y región con 4U_project y TrendAnalyzer (riesgo, abajo).
- **ADR-4 (M5, 2026-11-01).** Presupuesto de AWS **propio** para Digitdeck (40 USD/mes), separado
  del compartido `campus-locator-mensual` (100 USD/mes). *Por qué:* sin esto, el gasto de
  Digitdeck sería invisible dentro del límite que ya vigilan los otros dos proyectos.
- **ADR-5 (M5, 2026-11-01).** Usuario IAM dedicado (`digitdeck-terraform`), no las llaves root que
  ya había configuradas en WSL. *Por qué:* las llaves `default`/`campus-admin` son credenciales
  root de toda la cuenta; un error en el Terraform de Digitdeck no debería poder tocar los recursos
  de los otros proyectos.
- **ADR-6 (M5, 2026-11-01).** Instancia `g5.xlarge` (A10G, 24 GB VRAM), no `g4dn.2xlarge` (T4,
  16 GB). *Por qué:* el presupuesto de memoria del sistema completo (§2.1) es ~13-14 GB; M4 ya tuvo
  que repartir sus modelos en dos fases en una tarjeta de 16 GB (`../../M4/INFORME_M4.md` §3.3), y
  un servicio con tráfico real no puede repetir ese malabar.
- **ADR-7 (M5, 2026-11-01).** VPC por defecto de la cuenta, no una VPC propia con subredes
  privadas. *Por qué:* es una sola instancia pública sin backend privado — un NAT Gateway no
  aportaría nada y sí costaría (a diferencia de 4U_project, que sí tiene un backend y un worker
  privados).
- **ADR-8 (M5, 2026-11-01).** Acceso a la instancia por **SSM Session Manager**, sin puerto 22
  abierto. *Por qué:* menos superficie expuesta en una cuenta que ya comparte presupuesto con otros
  dos proyectos activos.
- **ADR-9 (M5, 2026-11-01).** Secretos en **SSM Parameter Store** (`SecureString`), no en Secrets
  Manager. *Por qué:* Parameter Store estándar es gratis; Secrets Manager cuesta
  ~0,40 USD/secreto/mes — no aporta nada aquí que Parameter Store no dé.
- **ADR-10 (M5, 2026-11-01).** Apagar la instancia con `stop-instances` entre sesiones, no
  `terraform destroy`. *Por qué:* el volumen raíz (índice del catálogo, modelos ya descargados) se
  pierde con `destroy`; apagada, el volumen sigue existiendo y solo cobra almacenamiento
  (~12 USD/mes de 150 GB), no cómputo.
- **ADR-11 (M5, 2026-11-02).** Construir y subir la imagen Docker **desde la propia instancia
  EC2**, no desde la máquina local. *Por qué:* el push local (4,57 GB reales) se trabó
  repetidamente a 0 B/s — confirmado con el contador de bytes de la interfaz de red, no una
  impresión — incluso después de reiniciar Docker Desktop y WSL2 por completo (`wsl --shutdown`).
  Un push de prueba de pocos MB al mismo repositorio sí funcionó, así que no era ni la red en
  general ni ECR: fue estructural a transferencias grandes y sostenidas sobre esta configuración de
  WSL2. Desde la instancia, el mismo push tardó **1 minuto**. *Cómo:* el código del servicio
  (19 KB comprimidos en base64) se manda por `aws ssm send-command`, y la instancia construye y
  sube su propia imagen. *Costo:* si el servicio cambia de código más adelante, probablemente haya
  que repetir esta estrategia en vez de asumir que un push local va a funcionar (riesgo 7).
- **ADR-12 (M5, 2026-11-02).** El rol de la instancia (`digitdeck-dev-ec2`) tiene permisos de
  **push** a ECR, no solo de pull. *Por qué:* consecuencia directa de ADR-11 — si la instancia
  construye y sube su propia imagen, necesita `ecr:InitiateLayerUpload`, `UploadLayerPart`,
  `CompleteLayerUpload`, `PutImage` y `BatchCheckLayerAvailability`, que el diseño original (solo
  pensado para que la instancia *bajara* una imagen ya construida en local) no contemplaba.
- **ADR-13 (M5, 2026-11-02).** Filtro de la AMI corregido a `"Deep Learning OSS Nvidia Driver AMI
  GPU PyTorch * (Ubuntu 24.04)*"`, con un filtro explícito de arquitectura `x86_64`. *Por qué:* el
  nombre documentado originalmente (`"Deep Learning AMI GPU PyTorch * (Ubuntu 22.04) *"`) ya no
  existía — AWS lo renombró y migró de Ubuntu 22.04 a 24.04/26.04 en algún punto. Confirmado contra
  `aws ec2 describe-images` en vivo el 2026-11-02, no adivinado. El filtro de arquitectura es
  necesario porque el mismo prefijo de nombre también aparece en variantes ARM64.
- **ADR-14 (M5, 2026-11-02).** La subred se elige cruzando contra las zonas de disponibilidad que
  sí ofrecen el tipo de instancia (`data.aws_ec2_instance_type_offerings`), no tomando la primera
  subred por defecto al azar. *Por qué:* el primer `terraform apply` de la instancia falló porque
  `g5.xlarge` no está disponible en `us-east-1e`, que es la que salió primera de
  `data.aws_subnets.default.ids[0]`.
- **ADR-15 (M5, 2026-11-02).** `digitdeck-terraform` necesita permisos de **sesión y comando de
  SSM** (`ssm:StartSession`, `SendCommand`, `GetCommandInvocation`, `DescribeInstanceInformation`,
  etc.), además de los de `/digitdeck/*` que ya tenía desde el bootstrap original. *Por qué:* el
  diseño original solo le dio permisos de SSM al **rol de la instancia** (para que ella pudiera
  leer sus propios secretos); nadie le había dado permiso al usuario que *inicia* las sesiones o
  comandos *desde fuera* — un hueco que solo apareció al intentar usarlo de verdad.

### Riesgos

1. ~~**El encoder de M1 solo existe en un disco.**~~ **Cerrado el 2026-11-02.** Se recuperaron los
   pesos de la máquina de origen y se subieron al Hub (`ateneaxvalac/digitdeck-m1-e5-small-esci-es`,
   privado) — ver §5.3 y `PLAN.md` lote 2.1.
2. **Cuenta de AWS compartida con 4U_project y TrendAnalyzer.** Confirmado el 2026-11-01: los
   perfiles `default` y `campus-admin` son la misma cuenta root. Un error de alcance en el
   Terraform de Digitdeck podría, en teoría, afectar recursos `campus-locator-*` o `ta-*` si se
   usaran las llaves equivocadas — de ahí ADR-5.
3. ~~**Docker no está disponible en la WSL del equipo.**~~ **Cerrado el 2026-11-02.** Se activó la
   integración de Docker Desktop con `Ubuntu-26.04`. Nota operativa: Docker Desktop no sobrevive a
   que la máquina se suspenda — hay que volver a abrirlo (y a veces `wsl --shutdown` completo) cada
   vez que la máquina duerme.
4. **El repositorio tiene un problema de finales de línea CRLF/LF** entre el git de Windows y el de
   WSL: `git status` desde WSL marca como modificados casi todos los notebooks y CSV de M1-M4 sin
   que nadie los haya tocado. Un `git add -A` hecho sin mirar desde WSL reescribiría esos archivos.
   No es un problema de M5, pero cualquiera que trabaje desde WSL en este repo debería saberlo.
5. **El índice del catálogo (BM25 + Chroma) no está persistido en ningún lado.** Hoy cada notebook
   lo reconstruye desde los parquet de ESCI. Si M5.e no se hace antes de M5.f, cada arranque del
   contenedor tarda minutos en estar listo.
6. **`buscar_similares` depende del verificador de 3B**, que es el modelo más pesado del sistema
   (§2.1). Si el presupuesto de memoria de la GPU resulta más ajustado de lo calculado, la primera
   palanca para liberar memoria es volver a la opción descartada en ADR-2 (recortar el alcance de
   la demo pública a solo existencia, como ya hizo M4). *Actualización 2026-11-02:* con los 4
   modelos cargados a la vez en la `g5.xlarge` real, `GET /salud` responde `ok: true` — el
   presupuesto de memoria calculado en §2.1 resultó correcto, este riesgo no se materializó.
7. **El push local de Docker a ECR no es confiable en esta red** (ver ADR-11). Si el servicio
   cambia de código y hay que reconstruir la imagen, no asumir que `docker push` desde la máquina
   del equipo va a funcionar — puede trabarse indefinidamente a 0 B/s sin ningún mensaje de error.
   La solución que funcionó fue construir y subir desde la propia instancia por `ssm send-command`.
8. ~~El logging a CloudWatch no está activo en el contenedor desplegado.~~ **Resuelto 2026-11-02:**
   se reinició el contenedor por `ssm send-command` con `--log-driver=awslogs` (mismos flags que
   `user_data.sh.tpl`). Verificado en dos pasos: `docker inspect digitdeck --format
   '{{json .HostConfig.LogConfig}}'` confirma `{"Type":"awslogs","Config":{"awslogs-group":
   "/digitdeck/app", ...}}`, y `aws logs describe-log-streams --log-group-name /digitdeck/app`
   (ejecutado con el rol de la instancia, no con el usuario `digitdeck-terraform` — ver nota abajo)
   muestra un log stream con `firstEventTimestamp`/`lastEventTimestamp`/`lastIngestionTime`
   poblados, es decir, ya hay eventos reales llegando a CloudWatch. `app.py` ya emite el JSON
   estructurado por pregunta (§5.7) a stdout, que el driver reenvía solo — no hubo que tocar
   código. *Gap menor encontrado de paso:* ni el usuario IAM `digitdeck-terraform` ni el rol de la
   instancia (`CloudWatchAgentServerPolicy`) tienen permiso de **lectura** de logs
   (`logs:GetLogEvents`/`logs:DescribeLogGroups` le falta al usuario CLI, `logs:GetLogEvents` al
   rol de la instancia) — ambos sí pueden escribir. Si se quiere leer el contenido de los logs
   desde la CLI más adelante (no solo confirmar que llegan), hay que añadir esos permisos de
   lectura a `bootstrap/main.tf` o a `iam.tf` y aplicar; por ahora no bloquea nada — para leer el
   contenido real de los logs sin tocar permisos, usar la consola de AWS (CloudWatch Logs →
   `/digitdeck/app`).
9. **Dos credenciales quedaron expuestas en el chat durante el despliegue del 2026-11-02**: una
   access key de AWS (`digitdeck-terraform`, pegada completa) y dos tokens de Hugging Face (uno
   pegado completo, otro mostrado parcialmente en una captura de pantalla de credenciales
   S3-compatibles). La access key de AWS se rotó. El primer token de HF se intentó rotar pero no
   era en realidad el problema (ver nota de la sesión: el error real era un bug de comillas
   anidadas en un comando de diagnóstico, no el token). El segundo token de HF quedó expuesto y el
   usuario decidió explícitamente **no rotarlo** después de que se le planteó el riesgo — queda
   declarado aquí, no es un descuido sin más.
10. **`POST /preguntar` no expone el ranking completo ni corre un juez holístico** — solo el texto
    final y `fichas_citadas` (lo que el generador citó literalmente, un subconjunto de lo que de
    verdad se le pasó como contexto). Al correr el harness de M2/M3 contra la URL pública
    (`PLAN.md` lote 5.1, 2026-11-02) esto impidió reproducir la Dimensión 1 (nDCG@10/MRR) y la
    Dimensión 2 (juez) tal cual; sí se pudo reproducir la Dimensión 3 (aciertos de dominio), con
    `fichas_citadas` como sustituto imperfecto de `pantalla`/`contexto_ids` — los conteos de
    acierto de esa corrida subestiman sistemáticamente y no son comparables a los `+0,265`/`+0,273`
    del informe de M3 (quedan solo en `scratchpad` local, no citados como cifra de calidad). Lo que
    sí es comparable y sí se verificó: **la decisión del sistema (abstención y apertura) coincidió
    con la corrida local guardada (`M3/Resultados/salidas_sistemas.json["D"]`) en 48 de 49 y 48 de
    49 casos respectivamente** — producción reproduce el comportamiento local casi exacto. Los 2
    casos que no coincidieron, explicados:
    - `g04-S` ("¿hay algo parecido a unos pasteles sin azúcar?", intención *similar*): producción
      respondió "similares" (lo correcto para esa intención); la corrida local guardada había dado
      "afirma". No es un bug de despliegue — el enrutador no es determinista al 100% entre
      corridas, y aquí el resultado de producción es el más alineado con la rúbrica.
    - `g09-E` ("¿Qué accesorios de Apple tienen?"): el estado fue `respuesta_generada` (la
      recuperación sí encontró candidatos sobre el umbral, así que el sistema no clasifica esto
      como abstención), pero el generador escribió de todas formas "No tengo esa información..."
      — una abstención a nivel de texto que el estado de la máquina no captura. Vale la pena que el
      equipo lo tenga presente para `INFORME_M5.md`: el estado `respuesta_generada` no garantiza
      que el texto no sea, en el fondo, una abstención.
11. **El repositorio ECR tiene tags inmutables** (`digitdeck/app`) — descubierto el 2026-11-02 al
    intentar re-publicar `:latest` con el frontend nuevo: `error from registry: The image tag
    'latest' already exists ... and cannot be overwritten because the tag is immutable`. Cada
    redespliegue de código necesita un **tag nuevo** (se usó `2026-11-02-frontend`), no re-usar
    `:latest`. `project/infra/variables.tf` sigue con `image_tag` por defecto en `"latest"` para el
    arranque automático de una instancia nueva (`user_data.sh.tpl`), así que si se reemplaza la
    instancia desde cero con `terraform apply`, va a buscar `:latest`, que ya quedó desactualizado
    frente a los tags nuevos — pendiente decidir si se vuelve mutable el repo o se actualiza
    `image_tag` en Terraform cada vez que se re-publica.
12. **El `curl -d` en línea con tildes puede fallar según la terminal del lector** — descubierto el
    2026-11-02 al probar la reproducibilidad externa (`PLAN.md` lote 5.2): un agente sin ningún
    contexto de esta sesión, siguiendo el `README.md` al pie de la letra, recibió `400 "There was
    an error parsing the body"` con el comando original (acentos pegados en `-d '...'`); mandando
    el mismo cuerpo JSON desde un archivo con `--data-binary` funcionó y coincidió exacto con lo
    documentado. No es un bug del servicio (aceptó el mismo contenido sin problema) — es que el
    shell del lector puede codificar mal los caracteres no-ASCII al pasarlos como argumento en
    línea. `README.md` ya se corrigió para usar el archivo en vez de `-d` en línea.
13. **El generador puede inventar productos con IDs que no existen**, no solo citar mal uno real
    (riesgo distinto al 10). M3 ya medía esto en agregado — *faithfulness* de RAGAS en sistema D es
    0,940, no 1,0 (`../M3/INFORME_M3.md` §7.4) — pero nunca se había visto el caso concreto ni su
    causa. Encontrado en vivo el 2026-11-02 (probando la demo con una foto): el generador respondió
    "Sí, lo tenemos" citando `B07XYZ1234`–`B07XYZ1237`, cuatro IDs que **no existen** en las 80.949
    fichas del catálogo (verificado con `catalogo.json` en la instancia). Causa probable: el prompt
    `SYSTEM_RAG` (`project/servicio/rag.py`) usa exactamente ese patrón de ID como ejemplo de
    formato — *"cita... por ejemplo `[B07XYZ1234]`"* — y el modelo copió el ejemplo en vez del
    contexto real. `fichas_citadas` volvió vacío porque ninguno de los IDs inventados coincidía con
    lo recuperado de verdad, lo que confirma que no fue un error de búsqueda. Ni `ids_citados()` ni
    `completar_nombres()` validan que un ID citado exista — están para dar formato, no para
    detectar esto. **Decisión del equipo (2026-11-02): documentar, no corregir el prompt todavía**
    (`INFORME_M5.md` §5 y §6 tienen el detalle completo y la mitigación propuesta: validar cada ID
    citado contra el catálogo antes de mostrarlo).

### Preguntas abiertas

- ¿Dominio propio para la URL, o queda como la IP elástica sola? (`PLAN.md` Fase 3)
- ¿Se completa en W&B el historial de M2-M4, que hoy solo está en CSV/JSON? (§5.7, `PLAN.md` lote 4.2)
- ¿Vale la pena añadir `logs:GetLogEvents`/`logs:DescribeLogGroups` al usuario `digitdeck-terraform`
  y al rol de la instancia, para poder leer logs desde la CLI (hoy solo escriben, no leen — riesgo 8)?
- ¿Vale la pena que `POST /preguntar` exponga `contexto_ids` (no solo `fichas_citadas`), para que
  una futura corrida del harness contra la URL pública sí pueda medir Dimensión 3 de forma
  comparable a las corridas locales (riesgo 10)?

---

## 10 · Estado del proyecto

| Módulo | Estado |
|---|---|
| M1 — Encoder ajustado | ✅ cerrado, nDCG@10 0,8369 (`../../M1/README.md`) |
| M2 — Harness de evaluación | ✅ cerrado (`../../M2/INFORME_M2.md`) |
| M3 — RAG con herramientas | ✅ cerrado, +0,273 nDCG@10 sobre el RAG ingenuo (`../../M3/INFORME_M3.md`) |
| M4 — Componente visual | ✅ cerrado, 4/12 con foto vs. 3/12 con la pregunta sola (`../../M4/INFORME_M4.md`) |
| M5 — Demo desplegada | 🟨 en curso — servicio corriendo en `http://54.173.61.242:8000`, `GET /salud` y `POST /preguntar` verificados de verdad (tres rutas manuales + 49 preguntas del eval set de M3, 48/49 coinciden con la corrida local), logging a CloudWatch activo, y reproducibilidad externa verificada por un agente sin contexto de la sesión (2026-11-02). Falta: informe final y demo |

Estado detallado de M5 (fase y lote, qué se cerró, con qué verificación): **única fuente de
verdad en [`PLAN.md`](PLAN.md) §3** — no se duplica aquí.

---

*SI4006 · Universidad EAFIT · Equipo Digitdeck.*
