"""Backfill: reclasifica el `type` de los prospectos existentes a la lista
CERRADA que usa scoring.py (Dimensión 4 del score_auto), en vez del texto
libre que traían hoy (la enorme mayoría, cargados antes de que la búsqueda
con IA generara `type` de la lista cerrada).

Cómo clasifica: heurística por palabras clave sobre `type` + `name` actuales
(sin llamar a la API de Claude). Con ~100+ prospectos y su `type` ya escrito
a mano/por una búsqueda vieja, un matching de texto es instantáneo, gratis y
100% reproducible — no hace falta gastar una llamada a la IA (con web search)
por fila para decidir entre 8 categorías a partir de un string que ya existe.
Es deliberadamente CONSERVADOR: si no hay una señal clara de una de las 7
categorías específicas, cae en "Otro" (la misma categoría — y el mismo
puntaje — que ya tenía el texto libre sin matchear). Nunca inventa una
categoría de más para inflar el score.

Uso:
    python scripts/reclassify_types.py --dry-run   # solo muestra, no escribe
    python scripts/reclassify_types.py              # aplica los cambios

Actualiza `type` vía database.update_prospect_partial(), que ya recalcula
score_auto solo (recalculate_score_auto) como parte de su comportamiento
normal — no hace falta un paso separado.
"""
import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

import database as db   # noqa: E402
import scoring as sc    # noqa: E402

# (categoría canónica, patrones regex — case-insensitive, cualquiera matchea)
# Orden: de más específico a más genérico. "Restaurante Italiano" va último
# entre las que matchean italiano/trattoria/etc. porque es el catch-all más
# amplio — así una señal más puntual (vinoteca, pastas, pizza-subtipo,
# parrilla premium) gana si está presente.
_RULES = (
    ("Vinoteca", (r"\bvinoteca\b", r"\bwine\s*bar\b")),
    ("Casa de Pastas", (r"\bcasa de pastas\b", r"f[aá]brica de pastas", r"pastas caseras")),
    ("Focacciería", (r"focaccer[ií]a",)),
    # Gourmet va ANTES que Napolitana: si dice "gourmet" tiene que ganar esa
    # categoría, no la napolitana/italiana-genérica de abajo.
    ("Pizzería Gourmet", (r"pizzer[ií]a.*gourmet", r"gourmet.*pizzer[ií]a")),
    ("Pizzería Napolitana", (r"napolitana", r"napoletana")),
    ("Parrilla Premium", (r"parrilla.*premium", r"premium.*parrilla")),
    # Restaurante Italiano ANTES del fallback de "pizzería italiana/tradicional"
    # de más abajo: una descripción compuesta tipo "Restaurante italiano /
    # Pizzería romana artesanal" tiene que ganar acá (es un restaurante
    # italiano con una pizzería de estilo romano, NO napolitana) — si no,
    # el fallback la agarraría por matchear "italiano" en la mitad que
    # describe el restaurante, no la pizzería.
    ("Restaurante Italiano", (
        r"restaurante italiano", r"\btrattoria\b", r"\bosteria\b", r"\bostería\b",
        r"cantina italiana",
    )),
)

# Separadores de cláusula para el fallback de abajo ("/", "," o " y ").
_CLAUSE_SPLIT_RE = re.compile(r"\s*/\s*|\s*,\s*|\s+y\s+")


def _pizzeria_italiana_o_tradicional(haystack: str) -> bool:
    """True si ALGUNA cláusula (separada por "/", "," o " y ") menciona
    "pizzer..." junto con "italian..." o "tradicional" EN LA MISMA cláusula.
    Evita el falso positivo de una descripción compuesta tipo "Restaurante
    italiano / Pizzería romana artesanal", donde "italiano" califica al
    restaurante y no a la pizzería (esa ya la agarra la regla de Restaurante
    Italiano, más arriba, antes de llegar acá)."""
    for clause in _CLAUSE_SPLIT_RE.split(haystack):
        if "pizzer" in clause and ("italian" in clause or "tradicional" in clause):
            return True
    return False


def classify_type(prospect: dict) -> str:
    """`type` canónico según palabras clave en `type` + `name` actuales.
    'Otro' si ninguna regla matchea (conservador a propósito)."""
    haystack = f"{prospect.get('type', '')} {prospect.get('name', '')}".lower()
    for canonical, patterns in _RULES:
        if any(re.search(p, haystack) for p in patterns):
            return canonical
    # Fallback relajado: "pizzería italiana" / "pizzería tradicional" (sin
    # calificador de napolitana/gourmet, que ya se probaron arriba) también
    # cuenta como Pizzería Napolitana — en la práctica es la pizza
    # "italiana"/tradicional por excelencia acá.
    if _pizzeria_italiana_o_tradicional(haystack):
        return "Pizzería Napolitana"
    return "Otro"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="solo muestra el resultado, no escribe nada")
    args = parser.parse_args()

    db.init_db()
    prospects = db.get_all_prospects()
    print(f"{len(prospects)} prospectos\n")

    tiers_before = Counter(sc.priority_tier(p["score_auto"]) for p in prospects if p.get("score_auto") is not None)

    changes = []          # (id, name, type_viejo, type_nuevo)
    tiers_after = Counter()
    type_moves = Counter()  # (type_viejo_canónico_o_libre, type_nuevo) -> n

    for p in prospects:
        old_type = p.get("type") or ""
        new_type = classify_type(p)
        changed = old_type.strip() != new_type

        # score_auto simulado con el type nuevo, sin tocar nada todavía —
        # para el resumen de tiers "antes/después" en dry-run.
        simulated = {**p, "type": new_type}
        new_score_auto = sc.calculate_priority_score(simulated)
        tiers_after[sc.priority_tier(new_score_auto)] += 1

        if changed:
            changes.append((p["id"], p["name"], old_type, new_type))
            type_moves[(old_type.strip() or "(vacío)", new_type)] += 1
            if not args.dry_run:
                db.update_prospect_partial(p["id"], {"type": new_type})

    # Distinción importante: cambiar el STRING de `type` no es lo mismo que
    # cambiar de CATEGORÍA de scoring. La mayoría de los cambios son texto
    # libre que normaliza a "Otro" (mismo puntaje que ya tenía, 0.5) — el
    # número que importa es cuántos matchearon una de las 7 categorías reales.
    to_scored_category = sum(1 for _, _, _, new in changes if new != "Otro")
    normalized_to_otro = len(changes) - to_scored_category

    print(f"{len(changes)} de {len(prospects)} prospectos cambian el string de `type`"
          f"{' (dry-run, no se escribió nada)' if args.dry_run else ' — actualizados'}:")
    print(f"  - {to_scored_category:3} matchearon una categoría real (High/Mid) -> SUBE el puntaje de categoría")
    print(f"  - {normalized_to_otro:3} solo se normalizaron a 'Otro' (texto libre sin match -> mismo puntaje que ya tenían, 0.5)\n")

    print("Movimientos de categoría más comunes:")
    for (old, new), n in type_moves.most_common(20):
        print(f"  {n:3}  {old[:45]:45} -> {new}")
    if len(type_moves) > 20:
        print(f"  ... y {len(type_moves) - 20} combinaciones más (una sola vez cada una)")

    def _fmt(counter):
        total = sum(counter.values()) or 1
        return ("A={a:3} ({ap}%)  B={b:3} ({bp}%)  C={c:3} ({cp}%)".format(
            a=counter.get('A', 0), b=counter.get('B', 0), c=counter.get('C', 0),
            ap=counter.get('A', 0) * 100 // total, bp=counter.get('B', 0) * 100 // total,
            cp=counter.get('C', 0) * 100 // total,
        ))

    print(f"\nDistribución de tiers ANTES:                {_fmt(tiers_before)}")
    print(f"Distribución de tiers DESPUÉS{' (simulada)' if args.dry_run else ''}:"
          f"{'' if args.dry_run else '        '} {_fmt(tiers_after)}")


if __name__ == "__main__":
    main()
