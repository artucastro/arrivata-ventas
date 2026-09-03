import json
import os
import re
import anthropic
from dotenv import load_dotenv

import scoring as sc

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

_PRODUCTS_DESC = """- Burrata, Bocconcino Fior di Latte, Bocconcino De Bufala
- Stracciatella Fior di Latte, Stracciatella De Bufala
- Provola Ahumada, Ricotta, Sfoglia, Trenza Ahumada
- Polpetta Fior di Latte, Polpetta De Bufala, Bocha de Muzarella"""

_TYPE_LIST_STR = ", ".join(sc.CLOSED_TYPES)

_JSON_FIELDS = f"""{{
  "nombre": "nombre completo del local",
  "tipo": "EXACTAMENTE uno de esta lista, sin variantes: {_TYPE_LIST_STR}",
  "municipio": "partido o localidad donde está ubicado",
  "direccion": "dirección completa con calle y número",
  "telefono": "teléfono si está disponible, null si no",
  "instagram": "usuario de instagram SIN el @, null si no",
  "website": "URL completa o null",
  "es_premium": true si es gourmet/premium, false si no,
  "rango_precio": "uno de: $, $$, $$$, $$$$, desconocido",
  "rating_google": 4.3 (número de 0 a 5 según Google Maps/reseñas, null si no se encuentra),
  "cantidad_resenas_google": 210 (número entero, null si no se encuentra),
  "estado_redes_sociales": "uno de: activa (publicó en los últimos ~3 meses), inactiva (la cuenta existe pero sin actividad reciente), sin_datos",
  "tamano_cadena": "uno de: único_local, cadena_chica (2 a 5 sucursales), cadena_grande (6 o más), desconocido",
  "notas_menu_quesos": "qué platos con queso tiene la carta, texto corto (ej: 'provoleta, 2 pizzas con bocconcino'), string vacío si no encontrás la carta",
  "potencial_volumen_estimado": "'alto'/'medio'/'bajo'/'desconocido' — estimalo a partir de notas_menu_quesos + rango_precio + tamano_cadena (más platos con queso, precio más alto y más sucursales = mayor volumen potencial)",
  "proveedor_actual_inferido": "'ninguno'/'competencia'/'la_meson'/'desconocido' — ver instrucciones abajo, es una INFERENCIA de baja confianza",
  "productos_recomendados": ["lista de productos Arrivata relevantes"],
  "justificacion": "1-2 oraciones explicando por qué sería buen cliente de Arrivata",
  "resumen_ia": "2-3 líneas explicando por qué vale (o no) la pena visitar este local, considerando todo lo anterior"
}}"""

_EXTRA_GUIDANCE = f"""
Para el campo "tipo": elegí EXACTAMENTE uno de esta lista cerrada, sin inventar variantes ni agregar adjetivos propios: {_TYPE_LIST_STR}. Si el local no encaja claramente en ninguna categoría específica, usá "Otro" — nunca describas el tipo con texto libre.

Para "proveedor_actual_inferido": es una INFERENCIA DE BAJA CONFIANZA, no un dato confirmado por una visita. Marcá "ninguno", "competencia" o "la_meson" únicamente si encontrás una señal razonablemente clara (reseñas que mencionen productos o marcas, publicaciones en redes, menú publicado que lo indique). Si no hay ninguna señal concreta, respondé "desconocido" — no adivines ni asumas."""


def search_prospects(
    neighborhood: str,
    business_type: str = "",
    extra_keywords: str = "",
    api_key: str = "",
    zone_type: str = "caba",
) -> list[dict]:
    key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
    if not key:
        raise ValueError("Configurá tu API key de Anthropic para usar la búsqueda IA.")

    client = anthropic.Anthropic(api_key=key)
    tipo_hint = f"especialmente {business_type}" if business_type else "restaurantes, pizzerías, hoteles boutique y locales gastronómicos"
    keywords_hint = f"\nPalabras clave adicionales: {extra_keywords}" if extra_keywords else ""

    from scoring import AMBA_TODA, CABA_TODOS
    is_amba_all = zone_type == "amba" and neighborhood == AMBA_TODA
    is_caba_all = zone_type == "caba" and neighborhood == CABA_TODOS

    if is_amba_all:
        prompt = f"""Eres un asistente de investigación de mercado para Arrivata, empresa argentina que produce quesos artesanales italianos premium:
{_PRODUCTS_DESC}

Buscá {tipo_hint} en toda el Área Metropolitana de Buenos Aires (AMBA / GBA) —excluyendo CABA— que podrían ser clientes ideales para estos productos.{keywords_hint}

Cubrí distintos partidos: GBA Norte (San Isidro, Vicente López, Tigre, Pilar, etc.), GBA Oeste (Morón, La Matanza, Merlo, etc.) y GBA Sur (Avellaneda, Lomas de Zamora, Quilmes, La Plata, etc.). Priorizá los partidos con mayor concentración de restaurantes premium.

{_EXTRA_GUIDANCE}

Para cada establecimiento usá este formato JSON:
{_JSON_FIELDS}

Respondé ÚNICAMENTE con un objeto JSON válido:
{{
  "barrio": "AMBA",
  "resultados": [
    ...al menos 15 establecimientos distribuidos en distintos partidos...
  ]
}}

No incluyas texto fuera del JSON."""

    elif is_caba_all:
        prompt = f"""Eres un asistente de investigación de mercado para Arrivata, empresa argentina que produce quesos artesanales italianos premium:
{_PRODUCTS_DESC}

Buscá {tipo_hint} en toda la Ciudad Autónoma de Buenos Aires (CABA) que podrían ser clientes ideales para estos productos.{keywords_hint}

Cubrí distintos barrios: Palermo, Recoleta, Belgrano, San Telmo, Puerto Madero, Villa Crespo, Colegiales, Chacarita, etc. Priorizá los de mayor concentración gastronómica premium.

{_EXTRA_GUIDANCE}

Para cada establecimiento usá este formato JSON:
{_JSON_FIELDS}

Respondé ÚNICAMENTE con un objeto JSON válido:
{{
  "barrio": "CABA",
  "resultados": [
    ...al menos 15 establecimientos distribuidos en distintos barrios...
  ]
}}

No incluyas texto fuera del JSON."""

    elif zone_type == "amba":
        prompt = f"""Eres un asistente de investigación de mercado para Arrivata, empresa argentina que produce quesos artesanales italianos premium:
{_PRODUCTS_DESC}

Buscá {tipo_hint} en el partido/localidad de **{neighborhood}**, Gran Buenos Aires, Argentina que podrían ser clientes ideales.{keywords_hint}

{_EXTRA_GUIDANCE}

Para cada establecimiento usá este formato JSON:
{_JSON_FIELDS}

Respondé ÚNICAMENTE con un objeto JSON válido:
{{
  "barrio": "{neighborhood}",
  "resultados": [
    ...al menos 8 establecimientos...
  ]
}}

No incluyas texto fuera del JSON."""

    else:
        prompt = f"""Eres un asistente de investigación de mercado para Arrivata, empresa argentina que produce quesos artesanales italianos premium:
{_PRODUCTS_DESC}

Buscá {tipo_hint} en el barrio de **{neighborhood}**, Buenos Aires (CABA), Argentina que podrían ser clientes ideales.{keywords_hint}

{_EXTRA_GUIDANCE}

Para cada establecimiento usá este formato JSON:
{_JSON_FIELDS}

Respondé ÚNICAMENTE con un objeto JSON válido:
{{
  "barrio": "{neighborhood}",
  "resultados": [
    ...al menos 8 establecimientos...
  ]
}}

No incluyas texto fuera del JSON."""

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=8192,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Server-side web search can pause the turn; resume until the model is done.
    guard = 0
    while response.stop_reason == "pause_turn" and guard < 5:
        guard += 1
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=8192,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ],
        )

    result_text = ""
    for block in response.content:
        if getattr(block, 'type', None) == 'text' and getattr(block, 'text', None):
            result_text += block.text

    return _parse_results(result_text)


def _clamp_choice(value, allowed: tuple, default: str) -> str:
    """`value` si matchea (case-insensitive) alguna de `allowed`; `default` si
    no — nunca se confía a ciegas en lo que devuelve el modelo para un campo
    de vocabulario cerrado."""
    v = (value or '').strip().lower() if isinstance(value, str) else ''
    for option in allowed:
        if v == option.lower():
            return option
    return default


def _clamp_float(value, lo: float, hi: float):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if lo <= f <= hi else None


def _clamp_int(value, lo: int = 0):
    try:
        i = int(value)
    except (TypeError, ValueError):
        return None
    return i if i >= lo else None


def _parse_results(text: str) -> list[dict]:
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return []

    try:
        data = json.loads(match.group())
        results = data.get('resultados', [])
        cleaned = []
        for r in results:
            cleaned.append({
                'name': r.get('nombre', ''),
                # `type` SIEMPRE de la lista cerrada — nunca texto libre, sin
                # importar lo que haya devuelto el modelo (ver scoring.py).
                'type': sc.normalize_closed_type(r.get('tipo')),
                'municipio': r.get('municipio', ''),
                'address': r.get('direccion', ''),
                'phone': r.get('telefono') or '',
                'instagram': r.get('instagram') or '',
                'website': r.get('website') or '',
                'is_premium': bool(r.get('es_premium', False)),
                'products_interest': '|'.join(x for x in r.get('productos_recomendados', []) if x),
                'notes': r.get('justificacion', ''),
                # ── Datos nuevos ────────────────────────────────────────
                'price_range': _clamp_choice(r.get('rango_precio'), ('$', '$$', '$$$', '$$$$'), 'desconocido'),
                'google_rating': _clamp_float(r.get('rating_google'), 0, 5),
                'google_review_count': _clamp_int(r.get('cantidad_resenas_google')),
                'social_media_status': _clamp_choice(r.get('estado_redes_sociales'), ('activa', 'inactiva'), 'sin_datos'),
                'chain_size': _clamp_choice(r.get('tamano_cadena'), ('único_local', 'cadena_chica', 'cadena_grande'), 'desconocido'),
                'cheese_menu_notes': (r.get('notas_menu_quesos') or '').strip(),
                'ai_summary': (r.get('resumen_ia') or '').strip(),
                # ── Inferencias — ver protección condicional en app.py:
                # solo pisan un valor 'desconocido' ya cargado, nunca uno real. ──
                'potential_volume': _clamp_choice(r.get('potencial_volumen_estimado'), ('alto', 'medio', 'bajo'), 'desconocido'),
                'current_supplier': _clamp_choice(r.get('proveedor_actual_inferido'), ('ninguno', 'competencia', 'la_meson'), 'desconocido'),
            })
        return cleaned
    except (json.JSONDecodeError, KeyError):
        return []
