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

**Interfaces** (código escrito y compila; todavía no se corrió de punta a punta con los modelos
reales — ver §7 y `PLAN.md` §3):

| Pieza | Dónde queda |
|---|---|
| `project/servicio/encoder.py` | carga del encoder de M1 (desde el Hub, §9 ADR-1) y el reranking |
| `project/servicio/rag.py` | búsqueda híbrida, las dos herramientas, el verificador de exacto |
| `project/servicio/vision.py` | `ver()` y su válvula |
| `project/servicio/app.py` | FastAPI: `POST /preguntar`, `GET /salud` — contrato en §5.2 |
| `project/servicio/construir_indice.py` | Lote 2.4: construye y persiste el índice del catálogo |
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
   estado final) y se registra en W&B — contrato en §5.7, todavía sin implementar.

---

## 5 · Contratos de comunicación

> Como en TrendAnalyzer: esta es la sección que hace innecesario reenviar código para saber cómo
> hablarle a una pieza del sistema.

### 5.1 · Convenciones globales

| Convención | Valor |
|---|---|
| Nube | AWS, cuenta `648617469176`, región `us-east-1` (confirmado el 2026-11-01) |
| Prefijo de nombres | `digitdeck-dev-*` para recursos de este proyecto, `digitdeck-tfstate-*` para el estado — nunca `campus-locator-*` ni `ta-*` (son de los otros dos proyectos en la misma cuenta) |
| Repositorio de imágenes | ECR `digitdeck/app`, tags **inmutables** |
| Etiqueta de costo | `Project = digitdeck` en todo recurso de `project/infra/` (para el presupuesto de §5.4 y para no confundirse con el gasto de los otros proyectos) |
| Terraform | ≥1.9, proveedor `hashicorp/aws ~> 5.0`. Dos stacks: `project/bootstrap/` (estado local, se aplica una sola vez) y `project/infra/` (estado en S3, backend con candado en DynamoDB) |
| Autenticación de Terraform | perfil de AWS CLI `digitdeck` (usuario IAM dedicado creado por `bootstrap/`), nunca las llaves root `default`/`campus-admin` que ya había en la cuenta |
| Acceso a la instancia | **SSM Session Manager**, no SSH (el security group no abre el puerto 22) |
| Secretos | **SSM Parameter Store** (`SecureString`), nunca Secrets Manager (evita ~0,40 USD/secreto/mes) ni variables quemadas en la imagen |
| Tiempo | UTC en logs y en W&B |

### 5.2 · API HTTP del servicio (propuesta — `app.py` aún no existe)

**`POST /preguntar`**

```json
// request
{
  "pregunta": "¿tienen el Xiaomi Redmi Note 7 negro?",
  "foto_base64": null
}
```

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

### 5.4 · AWS: recursos y nombres (los que ya crea `project/infra/`)

| Recurso | Nombre | Terraform |
|---|---|---|
| Bucket de estado | `digitdeck-tfstate-648617469176` | `project/bootstrap/main.tf` |
| Tabla de candado | `digitdeck-tfstate-lock` | idem |
| Usuario IAM de Terraform | `digitdeck-terraform` (sin access key en el estado — se crea a mano, `project/bootstrap/README.md`) | idem |
| Instancia | `digitdeck-dev-app`, tipo `g5.xlarge`, AMI Deep Learning de AWS | `project/infra/ec2.tf` |
| IP elástica | asociada a la instancia | idem |
| Security group | `digitdeck-dev-ec2` — solo el puerto de la app, nada de SSH | `project/infra/security.tf` |
| Rol/perfil de la instancia | `digitdeck-dev-ec2` — SSM, CloudWatch Logs, pull de ECR, lectura de `/digitdeck/*` en SSM | `project/infra/iam.tf` |
| Repositorio de imágenes | `digitdeck/app` | `project/infra/ecr.tf` |
| Presupuesto | `digitdeck-mensual`, 40 USD/mes (ajustable), filtrado por la etiqueta `Project=digitdeck` | `project/infra/budget.tf` |

### 5.5 · Secretos

| Parámetro SSM | Contiene | Quién lo lee |
|---|---|---|
| `/digitdeck/hf_token` | token de HF con lectura al repo privado del encoder | el contenedor, en `user_data.sh.tpl`, al arrancar |
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
        │   └── servicio/            # encoder.py, rag.py, vision.py, app.py, construir_indice.py
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

### Riesgos

1. ~~**El encoder de M1 solo existe en un disco.**~~ **Cerrado el 2026-11-02.** Se recuperaron los
   pesos de la máquina de origen y se subieron al Hub (`ateneaxvalac/digitdeck-m1-e5-small-esci-es`,
   privado) — ver §5.3 y `PLAN.md` lote 2.1.
2. **Cuenta de AWS compartida con 4U_project y TrendAnalyzer.** Confirmado el 2026-11-01: los
   perfiles `default` y `campus-admin` son la misma cuenta root. Un error de alcance en el
   Terraform de Digitdeck podría, en teoría, afectar recursos `campus-locator-*` o `ta-*` si se
   usaran las llaves equivocadas — de ahí ADR-5.
3. **Docker no está disponible en la WSL del equipo** (confirmado el 2026-11-01): hace falta
   activar la integración de Docker Desktop con `Ubuntu-26.04`, o instalar Docker nativo, antes de
   poder construir la imagen de M5.f.
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
   la demo pública a solo existencia, como ya hizo M4).

### Preguntas abiertas

- ¿Dominio propio para la URL, o queda como la IP elástica sola? (`PLAN.md` Fase 3)
- ¿Se completa en W&B el historial de M2-M4, que hoy solo está en CSV/JSON? (§5.7, `PLAN.md` lote 4.2)

---

## 10 · Estado del proyecto

| Módulo | Estado |
|---|---|
| M1 — Encoder ajustado | ✅ cerrado, nDCG@10 0,8369 (`../../M1/README.md`) |
| M2 — Harness de evaluación | ✅ cerrado (`../../M2/INFORME_M2.md`) |
| M3 — RAG con herramientas | ✅ cerrado, +0,273 nDCG@10 sobre el RAG ingenuo (`../../M3/INFORME_M3.md`) |
| M4 — Componente visual | ✅ cerrado, 4/12 con foto vs. 3/12 con la pregunta sola (`../../M4/INFORME_M4.md`) |
| M5 — Demo desplegada | 🟨 en curso |

Estado detallado de M5 (fase y lote, qué se cerró, con qué verificación): **única fuente de
verdad en [`PLAN.md`](PLAN.md) §3** — no se duplica aquí.

---

*SI4006 · Universidad EAFIT · Equipo Digitdeck.*
