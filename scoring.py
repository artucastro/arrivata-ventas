PRODUCTS = [
    "Bocconcino Fior Di Latte",
    "Bocconcino De Bufala",
    "Burrata",
    "Bocha de Muzarella",
    "Polpetta Fior Di Latte",
    "Polpetta De Bufala",
    "Provola Ahumada",
    "Ricotta",
    "Sfoglia",
    "Trenza Ahumada",
    "Strachiatella Fior Di Latte",
    "Strachiatella De Bufala",
]

BUSINESS_TYPES = [
    "Pizzería napolitana",
    "Pizzería gourmet",
    "Restaurante italiano",
    "Ostería / Trattoria",
    "Restaurante mediterráneo",
    "Restaurante gourmet / Fine dining",
    "Hotel boutique",
    "Rooftop / Bar gourmet",
    "Wine bar",
    "Panadería artesanal / Deli",
    "Catering gourmet",
    "Bistró / Café gourmet",
    "Pizzería",
    "Restaurante",
    "Bar",
    "Cafetería",
    "Otro",
]

CONTACT_STATUSES = [
    "Pendiente",
    "Contactado",
    "Interesado",
    "Reunión programada",
    "En negociación",
    "Cliente",
    "No interesado",
]

NEIGHBORHOODS_CABA = [
    "Palermo", "Palermo Soho", "Palermo Hollywood", "Palermo Chico", "Las Cañitas",
    "Recoleta", "Puerto Madero", "Belgrano", "Núñez", "Saavedra",
    "San Telmo", "Colegiales", "Villa Crespo", "Chacarita", "Almagro",
    "Flores", "Floresta", "Caballito", "Boedo", "Villa del Parque",
    "Villa Devoto", "Villa Urquiza", "Paternal", "Villa Pueyrredón",
    "Barracas", "La Boca", "Constitución", "Montserrat", "Centro / Microcentro",
    "Retiro", "Parque Patricios", "Liniers", "Mataderos",
]

NEIGHBORHOODS_AMBA_NORTE = [
    "San Isidro", "Vicente López", "Olivos", "Tigre", "San Fernando",
    "General San Martín", "Tres de Febrero", "Malvinas Argentinas",
    "José C. Paz", "San Miguel", "Escobar", "Pilar",
]

NEIGHBORHOODS_AMBA_OESTE = [
    "Morón", "Hurlingham", "Ituzaingó", "La Matanza", "Merlo", "Moreno",
]

NEIGHBORHOODS_AMBA_SUR = [
    "Avellaneda", "Lanús", "Lomas de Zamora", "Quilmes",
    "Berazategui", "Florencio Varela", "Almirante Brown",
    "Esteban Echeverría", "Ezeiza", "La Plata",
]

NEIGHBORHOODS_AMBA = NEIGHBORHOODS_AMBA_NORTE + NEIGHBORHOODS_AMBA_OESTE + NEIGHBORHOODS_AMBA_SUR

AMBA_TODA = "Toda la provincia (AMBA)"
CABA_TODOS = "Todos los barrios (CABA)"

ZONES = ["CABA", "GBA Norte", "GBA Oeste", "GBA Sur"]

# Score weights: tipo (1–5) + barrio (0–3) + premium (0–2) = 1–10
TIPO_SCORE_MAP = {
    "pizzería napolitana": 5,
    "pizzería gourmet": 5,
    "restaurante italiano": 5,
    "ostería": 5,
    "trattoria": 5,
    "fine dining": 5,
    "restaurante gourmet": 4,
    "cantina": 4,
    "restaurante mediterráneo": 4,
    "hotel boutique": 4,
    "catering gourmet": 4,
    "rooftop": 3,
    "wine bar": 3,
    "bar gourmet": 3,
    "panadería artesanal": 3,
    "deli": 3,
    "bistró": 3,
    "café gourmet": 3,
    "pizzería": 3,
    "restaurante": 2,
    "bar": 2,
    "cafetería": 1,
}

HIGH_SCORE_NEIGHBORHOODS = {
    "palermo soho", "palermo chico", "palermo hollywood", "las cañitas",
    "palermo", "recoleta", "puerto madero",
    "san isidro", "vicente lópez", "pilar", "nordelta", "tigre",
}

MED_SCORE_NEIGHBORHOODS = {
    "belgrano", "núñez", "nunez", "san telmo", "colegiales",
    "saavedra", "villa crespo", "chacarita",
    "olivos", "la plata", "quilmes", "lomas de zamora", "morón", "avellaneda",
}


_GBA_NORTE = {"san isidro", "vicente lópez", "vicente lopez", "olivos", "tigre", "san fernando",
               "general san martín", "general san martin", "tres de febrero", "malvinas argentinas",
               "josé c. paz", "jose c. paz", "san miguel", "escobar", "pilar", "nordelta"}
_GBA_OESTE = {"morón", "moron", "hurlingham", "ituzaingó", "ituzaingo", "la matanza", "merlo", "moreno"}
_GBA_SUR   = {"avellaneda", "lanús", "lanus", "lomas de zamora", "quilmes", "berazategui",
               "florencio varela", "almirante brown", "esteban echeverría", "esteban echeverria",
               "ezeiza", "la plata"}


def _detect_amba_zone(neighborhood: str) -> str:
    n = neighborhood.lower()
    if any(x in n for x in _GBA_NORTE):
        return "GBA Norte"
    if any(x in n for x in _GBA_OESTE):
        return "GBA Oeste"
    if any(x in n for x in _GBA_SUR):
        return "GBA Sur"
    return "GBA Norte"


def calculate_auto_score(tipo: str, neighborhood: str, is_premium: bool) -> int:
    tipo_lower = tipo.lower()
    barrio_lower = neighborhood.lower()

    tipo_score = 1
    for key, score in TIPO_SCORE_MAP.items():
        if key in tipo_lower:
            tipo_score = score
            break

    barrio_score = 0
    if any(n in barrio_lower for n in HIGH_SCORE_NEIGHBORHOODS):
        barrio_score = 3
    elif any(n in barrio_lower for n in MED_SCORE_NEIGHBORHOODS):
        barrio_score = 2
    elif barrio_lower:
        barrio_score = 1

    premium_bonus = 2 if is_premium else 0

    return min(10, max(1, tipo_score + barrio_score + premium_bonus))


# ═══════════════════════════════════════════════════════════════════════════════
# score_auto — vara de evaluación de prioridad comercial (0–10)
# ═══════════════════════════════════════════════════════════════════════════════
# Se recalcula solo cada vez que se crea / actualiza / importa un prospecto
# (ver database.calculate en create_prospect / update_prospect / update_prospect_partial).
# El campo `score` (ajuste manual, 1–10) NO lo toca esta función: sigue 100% a mano
# y protegido en database.IMPORT_PROTECTED_FIELDS.
#
# 5 dimensiones, pesos fijos. Cada mapeo vive en una constante con nombre para
# poder reajustar un peso sin cazar números mágicos por el código.

# ── Opciones de los dos campos que se cargan a mano tras visitar el local ──────
# (value en DB, label legible en el form). El primero es el default.
CURRENT_SUPPLIERS = [
    ("desconocido", "Sin evaluar todavía"),
    ("ninguno",     "No tiene proveedor"),
    ("competencia", "Compra a la competencia"),
    ("la_meson",    "La Mesón (indirecto Arrivata)"),
]
POTENTIAL_VOLUMES = [
    ("desconocido", "Sin evaluar"),
    ("alto",        "Alto"),
    ("medio",       "Medio"),
    ("bajo",        "Bajo"),
]

# ── Dimensión 1 — Potencial de volumen (hasta 3 pts) ──────────────────────────
VOLUME_POINTS = {
    "alto":        3.0,
    "medio":       2.0,
    "bajo":        1.0,
    "desconocido": 0.0,
}

# ── Dimensión 2 — Facilidad de contacto (hasta 2.5 pts, automática) ───────────
CONTACT_PHONE_POINTS          = 2.5   # tiene teléfono
CONTACT_INSTAGRAM_POINTS      = 1.5   # si no, tiene instagram
CONTACT_WEB_OR_ADDRESS_POINTS = 0.5   # si no, tiene website o dirección
CONTACT_NONE_POINTS           = 0.0   # nada

# ── Dimensión 3 — Situación de proveedor (hasta 2 pts) ────────────────────────
SUPPLIER_POINTS = {
    "ninguno":     2.0,
    "competencia": 1.5,
    "la_meson":    0.5,
    "desconocido": 0.0,
}

# ── Dimensión 4 — Categoría del local (hasta 1.5 pts, por el campo `type`) ─────
# Match por string completo, case-insensitive (no substring). Lo que no cae en
# ninguna lista puntúa como "otro".
CATEGORY_HIGH_POINTS  = 1.5
CATEGORY_MID_POINTS   = 1.0
CATEGORY_OTHER_POINTS = 0.5
CATEGORY_HIGH_TYPES = frozenset(t.lower() for t in (
    "Restaurante Italiano", "Vinoteca", "Casa de Pastas",
))
CATEGORY_MID_TYPES = frozenset(t.lower() for t in (
    "Pizzería Napolitana", "Pizzería Gourmet", "Parrilla Premium", "Focacciería",
))

# ── Dimensión 5 — Señales premium (hasta 1 pt) ───────────────────────────────
PREMIUM_FLAG_POINTS = 1.0   # is_premium == 1
PREMIUM_ZONE_POINTS = 0.5   # no es premium pero está en una zona premium
PREMIUM_NONE_POINTS = 0.0
PREMIUM_ZONES = frozenset(z.lower() for z in (
    "Palermo", "Recoleta", "Villa Crespo", "Colegiales", "Belgrano",
))

# ── Rango y tiers ────────────────────────────────────────────────────────────
SCORE_AUTO_MIN = 0.0
SCORE_AUTO_MAX = 10.0
TIER_A_MIN = 8.0   # Tier A: 8–10
TIER_B_MIN = 5.0   # Tier B: 5–7.9  (Tier C: < 5)


def _is_truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "si", "sí", "on")
    return bool(value)


def _volume_points(prospect) -> float:
    return VOLUME_POINTS.get(prospect.get("potential_volume") or "desconocido", 0.0)


def _contact_points(prospect) -> float:
    if (prospect.get("phone") or "").strip():
        return CONTACT_PHONE_POINTS
    if (prospect.get("instagram") or "").strip():
        return CONTACT_INSTAGRAM_POINTS
    if (prospect.get("website") or "").strip() or (prospect.get("address") or "").strip():
        return CONTACT_WEB_OR_ADDRESS_POINTS
    return CONTACT_NONE_POINTS


def _supplier_points(prospect) -> float:
    return SUPPLIER_POINTS.get(prospect.get("current_supplier") or "desconocido", 0.0)


def _category_points(prospect) -> float:
    tipo = (prospect.get("type") or "").strip().lower()
    if tipo in CATEGORY_HIGH_TYPES:
        return CATEGORY_HIGH_POINTS
    if tipo in CATEGORY_MID_TYPES:
        return CATEGORY_MID_POINTS
    return CATEGORY_OTHER_POINTS


def _premium_points(prospect) -> float:
    if _is_truthy(prospect.get("is_premium")):
        return PREMIUM_FLAG_POINTS
    zone = (prospect.get("zone") or "").strip().lower()
    hood = (prospect.get("neighborhood") or "").strip().lower()
    if zone in PREMIUM_ZONES or hood in PREMIUM_ZONES:
        return PREMIUM_ZONE_POINTS
    return PREMIUM_NONE_POINTS


def calculate_priority_score(prospect) -> float:
    """score_auto (0–10, 1 decimal) a partir de las 5 dimensiones de la vara.

    `prospect` es cualquier dict/Row con las claves: potential_volume, phone,
    instagram, website, address, current_supplier, type, is_premium, zone,
    neighborhood. Las que falten se tratan como vacío / 'desconocido'."""
    total = (
        _volume_points(prospect)
        + _contact_points(prospect)
        + _supplier_points(prospect)
        + _category_points(prospect)
        + _premium_points(prospect)
    )
    total = max(SCORE_AUTO_MIN, min(SCORE_AUTO_MAX, total))
    return round(total, 1)


def priority_tier(score_auto) -> str:
    """'A' (8–10) | 'B' (5–7.9) | 'C' (<5)."""
    if score_auto >= TIER_A_MIN:
        return "A"
    if score_auto >= TIER_B_MIN:
        return "B"
    return "C"


# Mismo esquema de color que la ficha individual (prospect_detail.html):
# verde = A, ámbar = B, gris = C (no rojo: Tier C no es "problema", es "sin evaluar").
TIER_BADGE_CLASS = {"A": "success", "B": "warning", "C": "neutral"}


def tier_badge_class(score_auto) -> str:
    """'success' | 'warning' | 'neutral' según el tier de score_auto (para
    `badge-{{ ... }}` / `score-{{ ... }}-display`)."""
    return TIER_BADGE_CLASS[priority_tier(score_auto)]


def score_color(score: int) -> str:
    if score >= 8:
        return "success"
    if score >= 5:
        return "warning"
    return "danger"


def score_label(score: int) -> str:
    if score >= 8:
        return "Alta"
    if score >= 5:
        return "Media"
    return "Baja"
