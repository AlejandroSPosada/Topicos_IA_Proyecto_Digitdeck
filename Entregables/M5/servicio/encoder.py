"""Encoder ajustado de M1: carga desde el Hub y reranking de fichas.

Fiel a `M1/ENTREGABLE.ipynb` (celda de `score_relevancia`/`scorear_lote_finetuned`, RUTA_MODELO)
y a `M3/ENTREGABLE.ipynb` §4.2 (`reordenar`), con una sola adaptación: los pesos se cargan de un
repo_id del HF Hub en vez de la ruta local `modelo_e5_small_finetuned/` (ARCHITECTURE.md §5.3,
Lote 2.1 de PLAN.md — subido el 2026-11-02, repo privado).
"""
import os

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ENCODER_REPO_ID = os.environ.get("DIGITDECK_ENCODER_REPO", "ateneaxvalac/digitdeck-m1-e5-small-esci-es")
MAX_LENGTH = 64  # M1 HIPERPARAMETROS["max_length"]

_device = "cuda" if torch.cuda.is_available() else "cpu"
_tok = None
_modelo = None


def cargado():
    return _modelo is not None


def cargar():
    global _tok, _modelo
    if _modelo is None:
        token = os.environ.get("HF_TOKEN")
        _tok = AutoTokenizer.from_pretrained(ENCODER_REPO_ID, token=token)
        _modelo = AutoModelForSequenceClassification.from_pretrained(ENCODER_REPO_ID, token=token).to(_device).eval()
    return _tok, _modelo


@torch.no_grad()
def reordenar(consulta, titulos, batch=128):
    """[(posición en `titulos`, score)] ordenado por la probabilidad de la clase "relevante"."""
    tok, modelo = cargar()
    salidas = []
    for i in range(0, len(titulos), batch):
        lote = titulos[i:i + batch]
        ent = tok([f"query: {consulta}"] * len(lote), [f"passage: {t}" for t in lote],
                   truncation=True, max_length=MAX_LENGTH, padding=True, return_tensors="pt").to(_device)
        salidas.append(F.softmax(modelo(**ent).logits.float(), dim=-1)[:, 1].cpu().numpy())
    scores = np.concatenate(salidas) if salidas else np.array([])
    orden = np.argsort(-scores, kind="stable")
    return [(int(j), float(scores[j])) for j in orden]
