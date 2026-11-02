"""Construye el índice del catálogo una sola vez y lo persiste (Lote 2.4 de PLAN.md).

Reproduce `M3/ENTREGABLE.ipynb` §2.1-§2.2 y §4 (descarga de ESCI, filtro `product_locale == 'es'`,
el campo `ficha` y el `contexto` que ve el generador, BM25 y Chroma) y escribe en
`DIGITDECK_INDICES_DIR` (por defecto `servicio/indices/`) lo que `rag.py` carga en caliente. Se
corre una vez en el build de la imagen, no en cada arranque del contenedor (ARCHITECTURE.md §9,
riesgo 5): con 80.383 fichas, reconstruirlo en cada arranque son minutos, no segundos.

Requiere que M1 ya haya descargado (o se descarguen aquí) `shopping_queries_dataset_examples.parquet`
y `shopping_queries_dataset_products.parquet` de amazon-science/esci-data (M1/ENTREGABLE.ipynb,
sección de descarga del dataset).
"""
import html
import os
import pickle
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

import rag

BASE_URL = "https://github.com/amazon-science/esci-data/raw/main/shopping_queries_dataset"
ARCHIVOS = ("shopping_queries_dataset_examples.parquet", "shopping_queries_dataset_products.parquet")

DIR_DATASET = Path(os.environ.get("DIGITDECK_DATASET_DIR", Path(__file__).parent / "datos" / "esci"))
DIR_INDICES = Path(os.environ.get("DIGITDECK_INDICES_DIR", Path(__file__).parent / "indices"))

MAX_VINETAS_INDICE = 400
MAX_VINETAS_CONTEXTO = 300
MAX_DESCRIPCION_CONTEXTO = 300
COLUMNAS_DESEADAS = ["product_id", "product_title", "product_description", "product_bullet_point",
                     "product_brand", "product_color", "product_locale"]


def descargar_esci():
    """M1/ENTREGABLE.ipynb, descarga del dataset: los parquet están en Git LFS, se bajan con la
    URL de medios crudos de GitHub, no con `git clone` (el clon trae solo los punteros)."""
    import urllib.request
    DIR_DATASET.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS:
        destino = DIR_DATASET / nombre
        if destino.exists():
            continue
        print(f"Descargando {nombre} ...")
        urllib.request.urlretrieve(f"{BASE_URL}/{nombre}", destino)
        print(f"Descargado: {nombre} ({destino.stat().st_size / 1e6:.1f} MB)")


def campo(fila, c):
    return fila[c] if c in fila and isinstance(fila[c], str) else ""


def texto_indice_ficha(fila):
    partes = [campo(fila, "product_title")]
    if campo(fila, "product_brand"):
        partes.append(f"marca: {campo(fila, 'product_brand')}")
    if campo(fila, "product_color"):
        partes.append(f"color: {campo(fila, 'product_color')}")
    if campo(fila, "product_bullet_point"):
        partes.append(campo(fila, "product_bullet_point")[:MAX_VINETAS_INDICE])
    return ". ".join(partes)


def texto_contexto(fila):
    partes = [f"[{fila['product_id']}] {campo(fila, 'product_title')}"]
    if campo(fila, "product_brand"):
        partes.append(f"marca: {campo(fila, 'product_brand')}")
    if campo(fila, "product_color"):
        partes.append(f"color: {campo(fila, 'product_color')}")
    if campo(fila, "product_bullet_point"):
        partes.append(f"características: {campo(fila, 'product_bullet_point')[:MAX_VINETAS_CONTEXTO]}")
    if campo(fila, "product_description"):
        partes.append(f"descripción: {campo(fila, 'product_description')[:MAX_DESCRIPCION_CONTEXTO]}")
    return " | ".join(partes)


def _limpiar_campo(texto):
    if not isinstance(texto, str):
        return ""
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto))
    return rag.limpiar_texto(texto)


def construir_catalogo():
    ruta_examples = DIR_DATASET / ARCHIVOS[0]
    ruta_products = DIR_DATASET / ARCHIVOS[1]

    df_ex = pd.read_parquet(ruta_examples, columns=["query_id", "product_id", "query", "esci_label", "split", "product_locale"])
    df_es = df_ex[df_ex["product_locale"] == "es"].copy()
    df_test = df_es[df_es["split"] == "test"].reset_index(drop=True)
    ids_catalogo = set(df_test["product_id"])

    columnas_parquet = pq.ParquetFile(ruta_products).schema_arrow.names
    cols_ficha = [c for c in COLUMNAS_DESEADAS if c in columnas_parquet]
    df_fichas = pd.read_parquet(ruta_products, columns=cols_ficha, filters=[("product_locale", "==", "es")])
    df_fichas = df_fichas[df_fichas["product_id"].isin(ids_catalogo)].drop_duplicates("product_id").reset_index(drop=True)
    for c in cols_ficha:
        if c not in ("product_id", "product_locale"):
            df_fichas[c] = df_fichas[c].map(_limpiar_campo)

    registros = df_fichas.to_dict("records")
    return {
        "ids": df_fichas["product_id"].tolist(),
        "titulo": df_fichas["product_title"].tolist(),
        "texto_ficha": [texto_indice_ficha(f) for f in registros],
        "contexto": [texto_contexto(f) for f in registros],
    }


def construir_y_persistir():
    DIR_INDICES.mkdir(parents=True, exist_ok=True)
    descargar_esci()

    print("Construyendo catálogo (fichas del split de test en español)...")
    catalogo_completo = construir_catalogo()
    print(f"{len(catalogo_completo['ids']):,} fichas indexables")

    catalogo = {"ids": catalogo_completo["ids"], "titulo": catalogo_completo["titulo"], "contexto": catalogo_completo["contexto"]}
    import json
    with open(DIR_INDICES / "catalogo.json", "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False)

    print("Indexando BM25...")
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi([rag.tokenizar_bm25(t) for t in catalogo_completo["texto_ficha"]])
    with open(DIR_INDICES / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)

    print("Indexando Chroma (embeddings densos)...")
    import chromadb
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(rag.MODELO_EMB)
    cliente = chromadb.PersistentClient(path=str(DIR_INDICES / "chroma"))
    nombre = f"catalogo_{rag.CONFIG}"
    try:
        cliente.delete_collection(nombre)
    except Exception:
        pass
    coleccion = cliente.create_collection(nombre, metadata={"hnsw:space": "cosine"})
    lote = 4000
    emb = st.encode(catalogo_completo["texto_ficha"], batch_size=256, show_progress_bar=True)
    for i in range(0, len(catalogo["ids"]), lote):
        coleccion.add(ids=catalogo["ids"][i:i + lote], embeddings=emb[i:i + lote].tolist())

    print(f"Índice persistido en {DIR_INDICES}")


if __name__ == "__main__":
    construir_y_persistir()
