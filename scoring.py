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
