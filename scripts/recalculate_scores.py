"""Recalcula score_auto para TODOS los prospectos con la vara de prioridad
(scoring.calculate_priority_score) y persiste el resultado.

Uso:
    python scripts/recalculate_scores.py          # aplica los cambios
    python scripts/recalculate_scores.py --dry-run # solo muestra, no escribe

Corre contra el backend que indique DATABASE_URL (Postgres si está seteada,
si no el SQLite local). No toca el campo `score` (ajuste manual).
Es idempotente: el cálculo es determinístico, re-correrlo no cambia nada.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

import database as db      # noqa: E402
import scoring as sc       # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="no escribe, solo muestra la distribución resultante")
    args = parser.parse_args()

    db.init_db()
    prospects = db.get_all_prospects()
    print(f"{len(prospects)} prospectos\n")

    tiers = {"A": 0, "B": 0, "C": 0}
    changed = 0
    for p in prospects:
        old = p.get("score_auto")
        new = sc.calculate_priority_score(p)
        if not args.dry_run:
            db.recalculate_score_auto(p["id"])
        if old is None or round(float(old), 1) != new:
            changed += 1
        tiers[sc.priority_tier(new)] += 1

    total = len(prospects) or 1
    print("Distribución de tiers (por score_auto):")
    print(f"  Tier A (8–10) : {tiers['A']:3}  ({tiers['A']*100//total}%)")
    print(f"  Tier B (5–7.9): {tiers['B']:3}  ({tiers['B']*100//total}%)")
    print(f"  Tier C (<5)   : {tiers['C']:3}  ({tiers['C']*100//total}%)")
    print(f"\n{changed} prospectos con score_auto distinto al anterior"
          f"{' (dry-run, no se escribió)' if args.dry_run else ' — actualizados'}.")


if __name__ == "__main__":
    main()
