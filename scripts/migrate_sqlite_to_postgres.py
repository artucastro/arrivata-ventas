"""Migra los prospectos de la base SQLite local a PostgreSQL (Neon).

Uso:
    # DATABASE_URL tiene que estar seteada (normalmente ya está en .env)
    python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py --sqlite ruta/a/arrivata.db

Qué hace:
  1. Crea el esquema en Postgres si no existe (migrations/001_init_postgres.sql).
  2. Copia TODAS las filas de `prospects` preservando id y valores exactos
     (is_premium 0/1, products_interest como string con '|', lat/lng como float).
  3. Resetea la secuencia del id para que los ALTA futuros no colisionen.
  4. Compara el conteo origen vs destino y FALLA (exit 1) si no coinciden.

Es seguro re-ejecutarlo: usa INSERT ... ON CONFLICT (id) DO NOTHING, no duplica.
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT, ".env"))
except Exception:
    pass

import database as db  # noqa: E402

COLUMNS = (
    "id", "name", "type", "neighborhood", "zone", "address", "phone", "email",
    "instagram", "website", "products_interest", "score", "score_auto",
    "is_premium", "contact_status", "notes", "lat", "lng", "geocode_status",
    "created_at", "updated_at",
)


def _clean_row(row: sqlite3.Row) -> list:
    d = dict(row)
    out = []
    for col in COLUMNS:
        v = d.get(col)
        if col == "is_premium":
            v = 1 if v else 0
        elif col in ("lat", "lng"):
            v = None if v in (None, "") else float(v)
        elif col in ("score", "score_auto"):
            v = 5 if v in (None, "") else int(v)
        elif col == "id":
            v = int(v)
        else:
            v = "" if v is None else v
        out.append(v)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=os.path.join(PROJECT, "arrivata.db"),
                        help="ruta al archivo SQLite de origen")
    args = parser.parse_args()

    if not db.USE_POSTGRES:
        sys.exit("ERROR: DATABASE_URL no está seteada. No hay Postgres destino.")
    if not os.path.exists(args.sqlite):
        sys.exit(f"ERROR: no existe el SQLite de origen: {args.sqlite}")

    # ── Origen: SQLite ──────────────────────────────────────────────────────
    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM prospects ORDER BY id").fetchall()
    src_count = src.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    src.close()
    print(f"SQLite  ({args.sqlite}): {src_count} prospectos")

    # ── Destino: Postgres ──────────────────────────────────────────────────
    db.init_db()  # crea la tabla si no existe

    placeholders = ", ".join(["?"] * len(COLUMNS))
    collist = ", ".join(COLUMNS)
    insert_sql = (
        f"INSERT INTO prospects ({collist}) VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO NOTHING RETURNING id"
    )

    conn = db.get_db()
    inserted = 0
    for row in rows:
        cur = conn.execute(insert_sql, _clean_row(row))
        if cur.fetchone() is not None:
            inserted += 1
    conn.commit()

    # Resetear la secuencia del IDENTITY al MAX(id) para que los próximos ALTA
    # no choquen con los ids preservados.
    conn.execute(
        "SELECT setval(pg_get_serial_sequence('prospects', 'id'), "
        "COALESCE((SELECT MAX(id) FROM prospects), 1), true)"
    )
    conn.commit()

    dst_count = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    conn.close()

    print(f"Postgres: {inserted} filas nuevas insertadas en esta corrida")
    print(f"Postgres: {dst_count} prospectos en total")

    if dst_count != src_count:
        sys.exit(
            f"\nFALLA: el conteo no coincide (SQLite={src_count}, Postgres={dst_count}). "
            f"Revisá antes de dar por buena la migración."
        )
    print(f"\nOK: conteos coinciden ({src_count} == {dst_count}).")


if __name__ == "__main__":
    main()
