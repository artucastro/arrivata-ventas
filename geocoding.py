import random
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "ArrivataSalesApp/1.0 (+https://arrivata.com.ar)"}

# Nominatim permite 1 request/segundo. Dejamos un colchón por encima de ese límite.
REQUEST_DELAY = 1.3          # segundos de pausa entre prospectos en el batch
MAX_RATELIMIT_ATTEMPTS = 3   # intentos totales ante HTTP 429
RATELIMIT_WAIT_RANGE = (5, 10)  # espera (segundos) entre reintentos por 429


def _nominatim_get(params: dict) -> tuple[list | None, str]:
    """GET a Nominatim con reintento automático ante 429 (rate limit).

    Devuelve (resultados, status) donde status es:
      'ok'          -> hay resultados
      'not_found'   -> respuesta válida pero sin resultados
      'error'       -> error de red, o 429 que persiste tras los reintentos
    """
    for attempt in range(1, MAX_RATELIMIT_ATTEMPTS + 1):
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=8)
        except requests.RequestException:
            return None, 'error'

        if resp.status_code == 429:
            if attempt == MAX_RATELIMIT_ATTEMPTS:
                print(f"  [geocoding] 429 persistente tras {attempt} intentos — se deja pendiente", flush=True)
                return None, 'error'
            retry_after = (resp.headers.get('Retry-After') or '').strip()
            wait = float(retry_after) if retry_after.isdigit() else random.uniform(*RATELIMIT_WAIT_RANGE)
            print(f"  [geocoding] HTTP 429 (rate limit) — reintento {attempt}/{MAX_RATELIMIT_ATTEMPTS - 1} en {wait:.0f}s", flush=True)
            time.sleep(wait)
            continue

        try:
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None, 'error'
        return (data, 'ok') if data else (None, 'not_found')

    return None, 'error'


def geocode_status(address: str, neighborhood: str = "",
                   city: str = "Buenos Aires") -> tuple[float | None, float | None, str]:
    """Como geocode(), pero devuelve además el estado:
       'ok' | 'error' (rate limit / red — conviene reintentar) | 'not_found'.
    """
    parts = [p for p in [address, neighborhood, city, "Argentina"] if p]
    query = ", ".join(parts)

    data, status = _nominatim_get(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "ar"}
    )
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"]), 'ok'
    hard_error = status == 'error'

    # Fallback: solo barrio + ciudad
    if neighborhood:
        time.sleep(REQUEST_DELAY)
        data, status = _nominatim_get(
            {"q": f"{neighborhood}, {city}, Argentina", "format": "json", "limit": 1}
        )
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"]), 'ok'
        hard_error = hard_error or status == 'error'

    return None, None, ('error' if hard_error else 'not_found')


def geocode(address: str, neighborhood: str = "",
            city: str = "Buenos Aires") -> tuple[float | None, float | None]:
    lat, lng, _ = geocode_status(address, neighborhood, city)
    return lat, lng
