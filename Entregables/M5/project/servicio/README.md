# servicio/ — el sistema desplegado

Código extraído de `M1/ENTREGABLE.ipynb`, `M3/ENTREGABLE.ipynb` y `M4/pipeline/ENTREGABLE.ipynb`
(Lotes 2.2-2.4 de [`../../docs/PLAN.md`](../../docs/PLAN.md)). Contrato completo de la API, de los
modelos y de las variables de entorno: [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) §5.

| Archivo | Qué es |
|---|---|
| `encoder.py` | el encoder ajustado de M1: carga desde el Hub y reranking |
| `rag.py` | búsqueda híbrida + RRF, las dos herramientas, el enrutador, el generador, y `sistema_D` (camino sin foto) con el contrato de 6 estados |
| `vision.py` | `ver()` del VLM de M4 y el camino con foto (`responder_con_foto`); `responder()` decide cuál de los dos usar |
| `app.py` | FastAPI: `POST /preguntar`, `GET /salud`, logging estructurado y W&B |
| `construir_indice.py` | Lote 2.4: construye el catálogo + BM25 + Chroma una sola vez y los persiste en `indices/` |
| `datos/umbrales_m3.json`, `datos/rubrica_juez.txt` | copias de los artefactos ya calibrados en M2/M3 — no se recalculan aquí |

## No está hecho todavía (ver `../../docs/PLAN.md` §3)

- **Lote 2.1 cerrado**: el encoder ya está en `ateneaxvalac/digitdeck-m1-e5-small-esci-es` (Hub,
  privado) — `encoder.py` puede cargarlo con un `HF_TOKEN` válido.
- **Lote 2.4 sin correr**: `construir_indice.py` no se ha ejecutado contra los parquet reales de
  ESCI (son ~1,1 GB; se corre una vez, con GPU, no en cada arranque).
- Nada de esto se probó de punta a punta: no hay GPU local con los ~13-14 GB que piden los cuatro
  modelos a la vez (`ARCHITECTURE.md` §2.1). Sí se verificó que los cinco `.py` compilan
  (`python -m py_compile`) y que las dependencias entre módulos son consistentes.

## Cómo correrlo en local, cuando 2.1 y 2.4 ya estén hechos

```bash
pip install -r requirements.txt
python construir_indice.py          # una sola vez; descarga ESCI si hace falta
export HF_TOKEN=...                  # lectura al repo privado del encoder
export WANDB_API_KEY=...             # opcional: sin esto, /preguntar igual responde, solo no loguea a W&B
export DIGITDECK_ENCODER_REPO=ateneaxvalac/digitdeck-m1-e5-small-esci-es
python app.py                        # sirve en 0.0.0.0:8000 (APP_PORT)
```

```bash
curl -X POST localhost:8000/preguntar -H "Content-Type: application/json" \
  -d '{"pregunta": "¿tienen el Xiaomi Redmi Note 7 negro?"}'
curl localhost:8000/salud
```

## Variables de entorno

| Variable | Qué es | Default |
|---|---|---|
| `HF_TOKEN` | token del Hub para el repo privado del encoder | — |
| `WANDB_API_KEY` | API key de W&B | — (si falta, no se loguea a W&B) |
| `WANDB_PROJECT` | proyecto de W&B | `digitdeck-m5` |
| `APP_PORT` | puerto del servicio | `8000` |
| `DIGITDECK_ENCODER_REPO` | repo del Hub del encoder | `ateneaxvalac/digitdeck-m1-e5-small-esci-es` |
| `DIGITDECK_INDICES_DIR` | dónde están `catalogo.json`, `bm25.pkl` y `chroma/` | `./indices` |
| `DIGITDECK_DATOS_DIR` | dónde están `umbrales_m3.json` y `rubrica_juez.txt` | `./datos` |
| `DIGITDECK_DATASET_DIR` | dónde `construir_indice.py` guarda los parquet de ESCI | `./datos/esci` |
