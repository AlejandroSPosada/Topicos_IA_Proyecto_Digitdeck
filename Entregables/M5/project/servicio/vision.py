"""Componente visual de M4: `ver()`, su válvula, y el camino completo con foto.

Extraído de `M4/pipeline/ENTREGABLE.ipynb` §4 (`ver`, `preguntar`, `parsear_json`,
`producto_identificado`, `consulta_desde_json`) y de `correr_foto`/`sistema_multimodal` (el
"enchufe" que decide, arma la consulta, llama al enrutador de M3 y — alcance de M4, M4 §2.4 —
solo `verificar_existencia`, nunca `buscar_similares`). La única pieza de M4 que no se reutiliza
aquí es M4.1 (la variante post hoc con dos llamadas al VLM): el informe la marca como optimista
porque se ajustó mirando los mismos 12 casos de prueba, así que M5 despliega M4, no M4.1.
"""
import json
import time

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

import rag

VLM_ID = "Qwen/Qwen2-VL-2B-Instruct"
MIN_PIXELS, MAX_PIXELS = 256 * 28 * 28, 1024 * 28 * 28

VALVULA = ("Responde SOLO con lo que se ve en la imagen. Si un dato no se aprecia en la imagen, escribe null en ese campo. "
           "Si en la imagen no hay un producto que se pueda identificar, responde exactamente: {\"es_producto\": false}")
INSTRUCCION_DOMINIO = ("Un comprador te muestra esta foto para saber si una tienda en línea tiene ese producto. "
                       "Devuelve SOLO un JSON, en español, con estos campos: "
                       "{\"es_producto\": true o false, \"tipo_producto\": \"qué es, en pocas palabras\", "
                       "\"marca\": \"marca o null\", \"modelo\": \"modelo o null\", \"color\": \"color o null\", "
                       "\"texto_visible\": \"texto legible en el producto o null\"}")
MENSAJE_VALVULA = "No se aprecia en la imagen un producto que pueda buscar."
VACIOS = {"", "null", "none", "no se aprecia", "no se aprecia en la imagen", "desconocido", "n/a", "ninguno"}
NOTA_CATALOGO = "Las fichas son del catálogo histórico de Amazon España (ESCI), no del inventario actual de la tienda."

_device = "cuda" if torch.cuda.is_available() else "cpu"
_vlm = None
_vproc = None


def cargado():
    return _vlm is not None


def _cargar():
    global _vlm, _vproc
    if _vlm is None:
        dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if _device == "cuda" else torch.float32
        _vlm = Qwen2VLForConditionalGeneration.from_pretrained(VLM_ID, dtype=dtype).to(_device).eval()
        _vproc = AutoProcessor.from_pretrained(VLM_ID, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
    return _vlm, _vproc


@torch.no_grad()
def preguntar(imagen, pregunta, system=None, max_new_tokens=200):
    vlm, vproc = _cargar()
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": pregunta}]}]
    texto = vproc.apply_chat_template(msgs, add_generation_prompt=True)
    ent = vproc(text=[texto], images=[imagen], return_tensors="pt").to(vlm.device)
    out = vlm.generate(**ent, max_new_tokens=max_new_tokens, do_sample=False)
    return vproc.batch_decode(out[:, ent["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()


def parsear_json(t):
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        return None
    try:
        return json.loads(t[i:j + 1])
    except Exception:
        return None


def _valor(js, campo):
    v = js.get(campo) if isinstance(js, dict) else None
    if v is None or isinstance(v, bool):
        return v
    v = str(v).strip()
    return None if rag._normal(v) in VACIOS else v


def ver(imagen, instruccion=None):
    """foto -> {crudo, json, valido, segundos}."""
    t = time.perf_counter()
    crudo = preguntar(imagen, instruccion or INSTRUCCION_DOMINIO, system=VALVULA)
    seg = time.perf_counter() - t
    js = parsear_json(crudo)
    return {"crudo": crudo, "json": js, "valido": isinstance(js, dict) and "es_producto" in js, "segundos": seg}


def producto_identificado(v):
    if not v["valido"]:
        return False
    es = v["json"].get("es_producto")
    if isinstance(es, str):
        es = rag._normal(es) in ("true", "si", "yes")
    return bool(es) and _valor(v["json"], "tipo_producto") is not None


def consulta_desde_json(js):
    """tipo + marca + modelo + color, normalizado como M1 y sin palabras repetidas."""
    partes = [_valor(js, c) for c in ("tipo_producto", "marca", "modelo", "color")]
    vistas, palabras = set(), []
    for w in rag.limpiar_texto(" ".join(str(p) for p in partes if p and not isinstance(p, bool))).split():
        if w not in vistas:
            vistas.add(w); palabras.append(w)
    return " ".join(palabras)


def lo_que_se_ve(js):
    partes = [_valor(js, c) for c in ("tipo_producto", "marca", "modelo", "color")]
    return ", ".join(str(x) for x in partes if x and not isinstance(x, bool))


def nota_foto_ficha(js):
    return f"\n\nEn la foto se ve: {lo_que_se_ve(js)}. {NOTA_CATALOGO}"


def responder_con_foto(pregunta, foto_bytes):
    """El enchufe de M4 (`correr_foto`): foto -> ver() -> consulta -> enrutador -> verificar_existencia -> generador.

    Alcance de M4: solo `verificar_existencia`, nunca `buscar_similares` con foto (M4 §2.4)."""
    lat, t_total = {}, time.perf_counter()
    try:
        import io
        imagen = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
        v = ver(imagen)
        lat["vision"] = v["segundos"]
        if not v["valido"]:
            raise rag.ErrorFormato("ver() no devolvió un JSON válido")
        if not producto_identificado(v):
            lat["total"] = time.perf_counter() - t_total
            return rag._resultado("sin_producto", None, None, [], f"{rag.APERTURAS['abstiene']} {MENSAJE_VALVULA}", lat)

        consulta = consulta_desde_json(v["json"])
        if not consulta.strip():
            raise rag.ErrorFormato("la consulta armada desde la foto quedó vacía")
        pregunta_aum = f"{pregunta} (En la foto se ve: {consulta_desde_json(v['json'])})"

        t = time.perf_counter(); herramienta, _, crudo, _ = rag.enrutar(pregunta_aum); lat["enrutamiento"] = time.perf_counter() - t
        if rag.decision_enrutador(herramienta, crudo) == "ninguna":  # p. ej. un medicamento con receta
            lat["total"] = time.perf_counter() - t_total
            return rag._resultado("abstencion_dominio", consulta, None, [], rag.APERTURAS["abstiene"], lat)

        obs = rag.verificar_existencia(consulta)  # alcance M4: siempre verificar_existencia, nunca buscar_similares
        rag.validar_observacion(obs)
        lat["recuperacion_reranking"] = obs["t_rec"] + obs["t_rr"]
        if not obs["resultado"]:
            lat["total"] = time.perf_counter() - t_total
            return rag._resultado("sin_resultados", consulta, "verificar_existencia", [], rag.APERTURAS["abstiene"], lat)

        catalogo, _, _, _, _ = rag.cargar_indice()
        ctx_ids = [catalogo["ids"][i] for i in obs["resultado"]]
        encabezado = "Usaste la herramienta verificar_existencia con lo que se ve en la foto y obtuviste estas fichas del catálogo:"
        t = time.perf_counter()
        respuesta = rag.generar(rag.SYSTEM_RAG, rag.armar_prompt(obs["resultado"], pregunta_aum, encabezado))
        lat["generacion"] = time.perf_counter() - t
        if not isinstance(respuesta, str) or not respuesta.strip():
            raise rag.ErrorFormato("el generador no devolvió texto")
        respuesta = rag.completar_nombres(respuesta, obs["resultado"])
        respuesta += nota_foto_ficha(v["json"])  # foto y ficha por separado, sin inferir stock (M4 §3.1, paso 8)

        lat["total"] = time.perf_counter() - t_total
        return rag._resultado("respuesta_generada", consulta, "verificar_existencia", ctx_ids, respuesta, lat)
    except Exception as exc:
        lat["total"] = time.perf_counter() - t_total
        estado = "error_formato" if isinstance(exc, rag.ErrorFormato) else "error_operativo"
        return rag._resultado(estado, None, None, [], rag.MENSAJE_ERROR, lat)


def responder(pregunta, foto_bytes=None):
    """pregunta (+ foto) -> resultado. Sin foto es sistema_D de M3, sin tocar (M4 §3.1: "Sin foto")."""
    if foto_bytes is None:
        return rag.sistema_D(pregunta)
    return responder_con_foto(pregunta, foto_bytes)
