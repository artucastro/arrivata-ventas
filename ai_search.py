import json
import os
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()

_PRODUCTS_DESC = """- Burrata, Bocconcino Fior di Latte, Bocconcino De Bufala
- Stracciatella Fior di Latte, Stracciatella De Bufala
- Provola Ahumada, Ricotta, Sfoglia, Trenza Ahumada
- Polpetta Fior di Latte, Polpetta De Bufala, Bocha de Muzarella"""

_JSON_FIELDS = """{
  "nombre": "nombre completo del local",
  "tipo": "tipo exacto (ej: Pizzería napolitana, Restaurante italiano, Hotel boutique, etc.)",
  "municipio": "partido o localidad donde está ubicado",
  "direccion": "dirección completa con calle y número",
  "telefono": "teléfono si está disponible, null si no",
  "instagram": "usuario de instagram SIN el @, null si no",
  "website": "URL completa o null",
  "es_premium": true si es gourmet/premium, false si no,
  "productos_recomendados": ["lista de productos Arrivata relevantes"],
  "justificacion": "1-2 oraciones explicando por qué sería buen cliente de Arrivata"
}"""


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
                'type': r.get('tipo', ''),
                'municipio': r.get('municipio', ''),
                'address': r.get('direccion', ''),
                'phone': r.get('telefono') or '',
                'instagram': r.get('instagram') or '',
                'website': r.get('website') or '',
                'is_premium': bool(r.get('es_premium', False)),
                'products_interest': '|'.join(x for x in r.get('productos_recomendados', []) if x),
                'notes': r.get('justificacion', ''),
            })
        return cleaned
    except (json.JSONDecodeError, KeyError):
        return []
