"""RAG con herramientas de M3, extendido con el contrato de 6 estados que M4 ya definió.

Extraído de `M3/ENTREGABLE.ipynb` §3-§7 (búsqueda híbrida, reranker, umbrales, herramientas,
enrutador, generador) y de `M4/pipeline/ENTREGABLE.ipynb` (`correr_foto`, `_cerrar`,
`_salida_error`, `ErrorFormato`, los 6 estados). M3 solo distinguía "responde" / "se abstiene"
(un único `APERTURAS["abstiene"]` para "ninguna herramienta" y para "sin resultados"); M4 ya
separaba esos dos casos en `abstencion_dominio` y `sin_resultados` para su propio flujo con foto
(M4 §3.1, paso 3-6). Aquí se aplica la misma distinción al camino sin foto, para que la API
(ARCHITECTURE.md §5.2) use un solo contrato de estado en los dos casos — es la pieza que faltaba
para que texto y foto respondan con la misma forma.

Las rutas de los índices y de los artefactos de M3 son configurables por variable de entorno; los
valores por defecto asumen que `construir_indice.py` (Lote 2.4) ya corrió y que `datos/` trae las
copias de `umbrales_m3.json` y `rubrica_juez.txt` empaquetadas con el servicio.
"""
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import numpy as np
import torch
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer

import encoder

BASE_DIR = Path(__file__).parent
DIR_INDICES = Path(os.environ.get("DIGITDECK_INDICES_DIR", BASE_DIR / "indices"))
DIR_DATOS = Path(os.environ.get("DIGITDECK_DATOS_DIR", BASE_DIR / "datos"))

MODELO_EMB = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GEN_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
JUEZ_MODEL = "Qwen/Qwen2.5-3B-Instruct"
RERANKER_SISTEMA = "e5_small_ft"
CONFIG = "ficha"

K_RECUPERAR = 30
K_CONTEXTO = 5
K_RRF = 60
N_REVISAR_SIMILARES = 15
PALABRAS_NOMBRE = 8

APERTURAS = {"afirma": "Sí, lo tenemos:",
             "similares": "No lo tenemos exacto, pero hay productos parecidos:",
             "abstiene": "No tengo esa información en mis fuentes."}

MENSAJE_ERROR = "No pude completar la consulta por un error del sistema. No se verificó si el producto está en el catálogo."
NOMBRES_HERRAMIENTAS = ("verificar_existencia", "buscar_similares")

_device = "cuda" if torch.cuda.is_available() else "cpu"


class ErrorFormato(ValueError):
    """Una salida de un modelo o de una herramienta no cumple el contrato declarado. M4 §3.4."""


# --- Catálogo e índices (construidos por construir_indice.py, Lote 2.4) ---

_catalogo = None
_bm25 = None
_coleccion = None
_st = None
_umbrales = None


def indice_listo():
    return _catalogo is not None and _bm25 is not None and _coleccion is not None


def cargar_indice():
    global _catalogo, _bm25, _coleccion, _st, _umbrales
    if _catalogo is None:
        with open(DIR_INDICES / "catalogo.json", encoding="utf-8") as f:
            _catalogo = json.load(f)
        import pickle
        with open(DIR_INDICES / "bm25.pkl", "rb") as f:
            _bm25 = pickle.load(f)
        import chromadb
        cliente = chromadb.PersistentClient(path=str(DIR_INDICES / "chroma"))
        _coleccion = cliente.get_collection(f"catalogo_{CONFIG}")
    if _st is None:
        _st = SentenceTransformer(MODELO_EMB, device=_device)
    if _umbrales is None:
        with open(DIR_DATOS / "umbrales_m3.json", encoding="utf-8") as f:
            _umbrales = json.load(f)
    return _catalogo, _bm25, _coleccion, _st, _umbrales


def _normal(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(ch for ch in t if unicodedata.category(ch) != "Mn")).strip()


def limpiar_texto(texto):
    if not isinstance(texto, str):
        return ""
    return re.sub(r"\s+", " ", texto.lower()).strip()


def tokenizar_bm25(texto):
    return re.findall(r"\w+", texto.lower())


# --- Las tres búsquedas (M3 §4.1) ---

def buscar_densa(consulta, k=K_RECUPERAR):
    catalogo, _, coleccion, st, _ = cargar_indice()
    r = coleccion.query(query_embeddings=st.encode([consulta]).tolist(), n_results=k)
    pos = {pid: i for i, pid in enumerate(catalogo["ids"])}
    return [pos[pid] for pid in r["ids"][0]]


def buscar_bm25(consulta, k=K_RECUPERAR):
    _, bm25, _, _, _ = cargar_indice()
    scores = bm25.get_scores(tokenizar_bm25(consulta))
    top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
    return [int(i) for i in top[np.argsort(-scores[top])]]


def buscar_hibrida(consulta, k=K_RECUPERAR, krrf=K_RRF):
    puntos = {}
    for lista in (buscar_densa(consulta, k), buscar_bm25(consulta, k)):
        for puesto, idx in enumerate(lista):
            puntos[idx] = puntos.get(idx, 0.0) + 1.0 / (krrf + puesto + 1)
    return [idx for idx, _ in sorted(puntos.items(), key=lambda x: -x[1])][:k]


def reordenar_catalogo(consulta, indices):
    """[(posición del catálogo, score)] — envoltura de encoder.reordenar sobre índices del catálogo."""
    catalogo, _, _, _, _ = cargar_indice()
    if not indices:
        return []
    titulos = [catalogo["titulo"][i] for i in indices]
    return [(indices[j], s) for j, s in encoder.reordenar(consulta, titulos)]


def _recuperar_y_reordenar(consulta):
    consulta_n = limpiar_texto(consulta)
    t = time.perf_counter(); cands = buscar_hibrida(consulta_n); t_rec = time.perf_counter() - t
    t = time.perf_counter(); orden = reordenar_catalogo(consulta_n, cands); t_rr = time.perf_counter() - t
    return orden, t_rec, t_rr


# --- El verificador de exacto (juez por logits, M2/M3 §6-§7, usado dentro de buscar_similares) ---

class JuezLogits:
    def __init__(self, modelo_id):
        self.tok = AutoTokenizer.from_pretrained(modelo_id)
        self.model = AutoModelForCausalLM.from_pretrained(modelo_id, dtype="auto").to(_device).eval()
        self.ids = {d: [self.tok.encode(d, add_special_tokens=False)[0]] for d in ("0", "1")}
        self.cache = {}

    @torch.no_grad()
    def _logits(self, system, user):
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        prompt = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ent = self.tok(prompt, return_tensors="pt").to(self.model.device)
        return self.model(**ent).logits[0, -1].float().cpu()

    def binario(self, system, user):
        lg = self._logits(system, user)
        return int(max(lg[i] for i in self.ids["1"]) > max(lg[i] for i in self.ids["0"]))

    def es_relevante(self, consulta, titulo):
        clave = (consulta, titulo)
        if clave not in self.cache:
            self.cache[clave] = self.binario(_rubrica_juez(), f"Consulta: {consulta}\nProducto: {titulo}\n\n1 o 0:")
        return self.cache[clave]


_verificador = None
_rubrica_juez_texto = None


def _rubrica_juez():
    global _rubrica_juez_texto
    if _rubrica_juez_texto is None:
        texto = (DIR_DATOS / "rubrica_juez.txt").read_text(encoding="utf-8").split("\n\n\n")[0]
        _rubrica_juez_texto = texto.split("\n", 2)[-1].strip()  # quita el encabezado "# Rúbrica ..."
    return _rubrica_juez_texto


def _verificador_cargado():
    global _verificador
    if _verificador is None:
        _verificador = JuezLogits(JUEZ_MODEL)
    return _verificador


# --- Las dos herramientas (M3 §7) ---

def verificar_existencia(consulta):
    orden, t_rec, t_rr = _recuperar_y_reordenar(consulta)
    _, _, _, _, umbrales = cargar_indice()
    u = umbrales[RERANKER_SISTEMA]["exacto"]
    return {"ranking": [i for i, _ in orden], "resultado": [i for i, s in orden if s >= u][:K_CONTEXTO],
            "t_rec": t_rec, "t_rr": t_rr}


def buscar_similares(consulta):
    orden, t_rec, t_rr = _recuperar_y_reordenar(consulta)
    catalogo, _, _, _, umbrales = cargar_indice()
    u_piso = umbrales[RERANKER_SISTEMA]["similar"]
    candidatas = [i for i, s in orden if s >= u_piso]
    verificador = _verificador_cargado()
    t = time.perf_counter()
    alternativas, exactas, revisadas = [], [], 0
    for i in candidatas[:N_REVISAR_SIMILARES]:
        if len(alternativas) == K_CONTEXTO:
            break
        revisadas += 1
        (exactas if verificador.es_relevante(consulta, catalogo["titulo"][i]) else alternativas).append(i)
    t_verif = time.perf_counter() - t
    ranking = alternativas + [i for i, _ in orden if i not in alternativas and i not in exactas]
    return {"ranking": ranking, "resultado": alternativas, "t_rec": t_rec, "t_rr": t_rr, "t_verif": t_verif}


HERRAMIENTAS = {"verificar_existencia": verificar_existencia, "buscar_similares": buscar_similares}

ESQUEMAS = [
    {"name": "verificar_existencia",
     "description": "Busca en el catálogo si la tienda tiene exactamente el producto que pide el comprador. Devuelve solo las fichas que son ese producto.",
     "args": {"consulta": "string: tipo de producto y características que dijo la persona, sin saludos"}},
    {"name": "buscar_similares",
     "description": "Busca en el catálogo productos parecidos o alternativos al que menciona el comprador. Devuelve alternativas, no el producto exacto.",
     "args": {"consulta": "string: tipo y características del producto de referencia, sin saludos"}},
]
SYSTEM_ENRUTADOR = (
    "Eres el enrutador de un asistente de compras de una tienda en línea. Tienes estas herramientas:\n"
    + json.dumps(ESQUEMAS, ensure_ascii=False, indent=2) + "\n\n"
    "Reglas:\n"
    "- Si la persona pregunta si la tienda tiene o vende un producto, o qué productos de un tipo o de una marca tiene, "
    "usa verificar_existencia. Vale aunque describa cómo debe ser el producto (\"que tenga...\", \"sin...\", \"de color...\").\n"
    "- Usa buscar_similares solo si la persona pide algo parecido, similar o alternativo a un producto, o una "
    "recomendación con base en otro producto.\n"
    "- Si la pregunta no es sobre productos del catálogo, o pide un producto de venta restringida (que exige "
    "receta, licencia o una edad mínima), no uses herramientas y responde exactamente: NINGUNA\n"
    "- En \"consulta\" escribe el tipo de producto y todas las características que dijo la persona (marca, modelo, "
    "color, talla, \"sin...\", \"para...\"), sin quitarlas ni cambiarlas, y sin saludos ni signos de pregunta.\n"
    "Responde SOLO con un JSON de la forma {\"tool\": \"nombre\", \"args\": {\"consulta\": \"...\"}} o con la palabra NINGUNA.\n\n"
    "Ejemplos:\n"
    "Pregunta: ¿Venden cargadores para portátil HP que sean de 65 W?\n"
    "{\"tool\": \"verificar_existencia\", \"args\": {\"consulta\": \"cargador para portátil HP de 65 W\"}}\n"
    "Pregunta: ¿tienen galletas sin gluten?\n"
    "{\"tool\": \"verificar_existencia\", \"args\": {\"consulta\": \"galletas sin gluten\"}}\n"
    "Pregunta: ¿Qué zapatillas de running de mujer tienen?\n"
    "{\"tool\": \"verificar_existencia\", \"args\": {\"consulta\": \"zapatillas de running de mujer\"}}\n"
    "Pregunta: ¿Qué cafetera me recomiendan parecida a la Bialetti Moka Express de 6 tazas?\n"
    "{\"tool\": \"buscar_similares\", \"args\": {\"consulta\": \"cafetera Bialetti Moka Express de 6 tazas\"}}\n"
    "Pregunta: ¿Tienen alguna mochila parecida a la Eastpak Padded negra?\n"
    "{\"tool\": \"buscar_similares\", \"args\": {\"consulta\": \"mochila Eastpak Padded negra\"}}\n"
    "Pregunta: ¿Hacen envíos a Canarias?\n"
    "NINGUNA"
)


def _extraer_json(t):
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            return None
    return None


def enrutar(pregunta):
    crudo = generar(SYSTEM_ENRUTADOR, f"Pregunta: {pregunta}", 80)
    pedido = _extraer_json(crudo)
    if isinstance(pedido, dict) and pedido.get("tool") in NOMBRES_HERRAMIENTAS:
        args = pedido.get("args") if isinstance(pedido.get("args"), dict) else {}
        consulta = str(args.get("consulta") or pregunta).strip() or pregunta
        return pedido["tool"], consulta, crudo, True
    return "ninguna", None, crudo, (pedido is None and "NINGUNA" in crudo.upper())


def decision_enrutador(herramienta, crudo):
    """M3-01 (revisión de M3): solo NINGUNA, sin texto adicional, es la decisión de no buscar."""
    if herramienta in NOMBRES_HERRAMIENTAS:
        return herramienta
    if isinstance(crudo, str) and crudo.strip().upper() == "NINGUNA":
        return "ninguna"
    raise ErrorFormato("el enrutador no devolvió una herramienta válida ni NINGUNA")


def validar_observacion(obs):
    if not isinstance(obs, dict) or not isinstance(obs.get("ranking"), list) or not isinstance(obs.get("resultado"), list):
        raise ErrorFormato("la herramienta no devolvió ranking y resultado como listas")
    if not set(obs["resultado"]) <= set(obs["ranking"]):
        raise ErrorFormato("el resultado de la herramienta no está dentro de su ranking")


# --- El generador (M3 §5) ---

_gen_tok = None
_gen_model = None


def _generador_cargado():
    global _gen_tok, _gen_model
    if _gen_model is None:
        _gen_tok = AutoTokenizer.from_pretrained(GEN_MODEL)
        _gen_model = AutoModelForCausalLM.from_pretrained(GEN_MODEL, dtype="auto").to(_device).eval()
    return _gen_tok, _gen_model


@torch.no_grad()
def generar(system, user, max_new_tokens=220):
    tok, modelo = _generador_cargado()
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ent = tok(prompt, return_tensors="pt").to(_device)
    out = modelo.generate(**ent, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ent["input_ids"].shape[1]:], skip_special_tokens=True).strip()


SYSTEM_RAG = (
    "Eres el asistente de compras de una tienda en línea. Respondes SOLO con base en las fichas de producto "
    "del contexto; no uses lo que sepas por tu cuenta.\n"
    "Empieza tu respuesta con UNA de estas tres frases, exactamente como están escritas:\n"
    f"1. \"{APERTURAS['afirma']}\" si al menos una ficha es exactamente el producto que la persona pide. Luego nombra esos productos.\n"
    f"2. \"{APERTURAS['similares']}\" si ninguna ficha es exactamente lo pedido pero alguna sirve como alternativa, "
    "o si la persona pide algo parecido. Luego nombra esas alternativas.\n"
    f"3. \"{APERTURAS['abstiene']}\" si ninguna ficha sirve o si la pregunta no es sobre productos de la tienda. "
    "En ese caso no agregues nada más.\n"
    "Cita cada producto que nombres con su identificador entre corchetes, por ejemplo [B07XYZ1234].\n"
    "Nunca presentes un producto parecido como si fuera exactamente lo pedido. Sé breve."
)


def armar_prompt(indices, pregunta, encabezado="Contexto (fichas del catálogo):"):
    catalogo, _, _, _, _ = cargar_indice()
    contexto = "\n\n".join(catalogo["contexto"][i] for i in indices)
    return f"{encabezado}\n\n{contexto}\n\nPregunta del comprador: {pregunta}"


def leer_apertura(respuesta):
    r = _normal(respuesta)[:120]
    if r.startswith(_normal(APERTURAS["abstiene"])[:25]) or "no tengo esa informacion" in r[:60]:
        return "abstiene"
    if r.startswith("no lo tenemos exacto") or "hay productos parecidos" in r[:80]:
        return "similares"
    if r.startswith("si, lo tenemos") or r.startswith("si lo tenemos"):
        return "afirma"
    return "otro"


def ids_citados(respuesta, contexto_ids):
    texto = (respuesta or "").upper()
    return [pid for pid in contexto_ids if pid.upper() in texto]


def nombre_corto(catalogo, i):
    palabras = catalogo["titulo"][i].split()
    return " ".join(palabras[:PALABRAS_NOMBRE]).rstrip(" ,;:-|/")


def completar_nombres(respuesta, ctx):
    catalogo, _, _, _, _ = cargar_indice()
    texto = respuesta or ""
    for i in ctx:
        marca = f"[{catalogo['ids'][i]}]"
        pos = texto.upper().find(marca.upper())
        if pos == -1:
            continue
        clave = _normal(" ".join(catalogo["titulo"][i].split()[:3]))
        entorno = _normal(texto[max(0, pos - 120):pos + len(marca) + 120])
        if clave and clave in entorno:
            continue
        texto = texto[:pos] + nombre_corto(catalogo, i) + " " + texto[pos:]
    return texto


# --- El sistema unificado: texto o foto, con el contrato de 6 estados (M4 §3.4) ---

def _resultado(estado, consulta, herramienta, ctx_ids, respuesta, lat, extra=None):
    s = {"estado": estado, "consulta": consulta, "herramienta": herramienta, "respuesta": respuesta,
         "fichas_citadas": ids_citados(respuesta, ctx_ids) if ctx_ids else [],
         "latencia_ms": {k: round(v * 1000) for k, v in lat.items()}}
    s.update(extra or {})
    return s


def sistema_D(pregunta):
    """Camino sin foto: M3 §7 `sistema_D`, con los 6 estados de M4 §3.4 en vez de solo "abstiene"."""
    lat, t_total = {}, time.perf_counter()
    try:
        t = time.perf_counter(); herramienta, consulta, crudo, json_ok = enrutar(pregunta); lat["enrutamiento"] = time.perf_counter() - t
        if decision_enrutador(herramienta, crudo) == "ninguna":
            lat["total"] = time.perf_counter() - t_total
            return _resultado("abstencion_dominio", None, None, [], APERTURAS["abstiene"], lat)
        obs = HERRAMIENTAS[herramienta](consulta)
        validar_observacion(obs)
        lat["recuperacion_reranking"] = obs["t_rec"] + obs["t_rr"]
        if "t_verif" in obs:
            lat["verificador"] = obs["t_verif"]
        if not obs["resultado"]:
            lat["total"] = time.perf_counter() - t_total
            return _resultado("sin_resultados", consulta, herramienta, [], APERTURAS["abstiene"], lat)
        catalogo, _, _, _, _ = cargar_indice()
        ctx_ids = [catalogo["ids"][i] for i in obs["resultado"]]
        encabezado = f"Usaste la herramienta {herramienta} y obtuviste estas fichas del catálogo:"
        t = time.perf_counter(); respuesta = generar(SYSTEM_RAG, armar_prompt(obs["resultado"], pregunta, encabezado)); lat["generacion"] = time.perf_counter() - t
        if not isinstance(respuesta, str) or not respuesta.strip():
            raise ErrorFormato("el generador no devolvió texto")
        respuesta = completar_nombres(respuesta, obs["resultado"])
        lat["total"] = time.perf_counter() - t_total
        return _resultado("respuesta_generada", consulta, herramienta, ctx_ids, respuesta, lat)
    except Exception as exc:
        lat["total"] = time.perf_counter() - t_total
        estado = "error_formato" if isinstance(exc, ErrorFormato) else "error_operativo"
        return _resultado(estado, None, None, [], MENSAJE_ERROR, lat)
