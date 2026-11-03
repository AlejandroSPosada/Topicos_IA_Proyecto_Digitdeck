"""Servicio FastAPI de Digitdeck M5. Contrato: ARCHITECTURE.md §5.2.

`POST /preguntar` y `GET /salud` envuelven `vision.responder()`, que ya decide internamente si hay
foto (M4) o no (M3 `sistema_D`). No hay lógica de negocio aquí: este módulo solo traduce HTTP <->
el resultado de `vision.responder()` y logea cada pregunta en JSON estructurado (ARCHITECTURE.md
§5.7) y en W&B.
"""
import base64
import binascii
import json
import logging
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import encoder
import rag
import vision

APP_PORT = int(os.environ.get("APP_PORT", "8000"))
WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "digitdeck-m5")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Digitdeck")

logger = logging.getLogger("digitdeck")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)

_wandb = None


def _wandb_run():
    """W&B es opcional: si no hay WANDB_API_KEY el servicio igual responde (ARCHITECTURE.md §5.7)."""
    global _wandb
    if _wandb is None and os.environ.get("WANDB_API_KEY"):
        import wandb
        _wandb = wandb.init(project=WANDB_PROJECT, job_type="serving")
    return _wandb


class Pregunta(BaseModel):
    pregunta: str
    foto_base64: str | None = None


@app.on_event("startup")
def startup():
    # Carga los cuatro modelos y el índice al arrancar, no en la primera pregunta: así /salud
    # refleja el estado real del servicio en vez de mentir mientras el primer request calienta todo.
    rag.cargar_indice()
    encoder.cargar()
    rag._generador_cargado()
    rag._verificador_cargado()
    vision._cargar()


@app.get("/", include_in_schema=False)
def demo():
    # Página de demo para probar el servicio desde el navegador, sin armar JSON a mano
    # (ARCHITECTURE.md §5.2). No reemplaza el contrato HTTP: /docs sigue siendo la API real.
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/preguntar")
def preguntar(cuerpo: Pregunta):
    t0 = time.perf_counter()
    try:
        foto_bytes = base64.b64decode(cuerpo.foto_base64, validate=True) if cuerpo.foto_base64 else None
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"foto_base64 no es base64 válido: {exc}")
    resultado = vision.responder(cuerpo.pregunta, foto_bytes)

    logger.info(json.dumps({
        "evento": "pregunta",
        "intencion": "foto" if foto_bytes else "texto",
        "herramienta": resultado.get("herramienta"),
        "estado": resultado.get("estado"),
        "latencia_ms": resultado.get("latencia_ms"),
        "latencia_total_s": round(time.perf_counter() - t0, 3),
    }, ensure_ascii=False))

    run = _wandb_run()
    if run is not None:
        run.log({
            "intencion": "foto" if foto_bytes else "texto",
            "herramienta": resultado.get("herramienta") or "ninguna",
            "estado": resultado.get("estado"),
            "latencia_total_ms": resultado.get("latencia_ms", {}).get("total"),
        })

    return {
        "respuesta": resultado["respuesta"],
        "estado": resultado["estado"],
        "fichas_citadas": resultado["fichas_citadas"],
        "latencia_ms": resultado["latencia_ms"],
    }


@app.get("/salud")
def salud():
    modelos = []
    if encoder.cargado():
        modelos.append("encoder")
    if rag._gen_model is not None:
        modelos.append("generador")
    if rag._verificador is not None:
        modelos.append("verificador")
    if vision.cargado():
        modelos.append("vlm")
    return {
        "ok": encoder.cargado() and rag.indice_listo() and vision.cargado(),
        "modelos_cargados": modelos,
        "indice_listo": rag.indice_listo(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
