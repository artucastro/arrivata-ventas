"""Prueba de la vara de prioridad comercial (score_auto).

  1. calculate_priority_score() — las 5 dimensiones y 3 ejemplos calibrados
     con resultado EXACTO.
  2. Wiring — que create_prospect / update_prospect / update_prospect_partial /
     recalculate_score_auto guarden el score_auto calculado, sin tocar `score`.

Uso:  python tests/test_priority_score.py
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
import scoring as sc

_fails = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'OK ' if ok else 'FALLA'}  {label}: {got!r}" + ("" if ok else f"  (esperaba {expected!r})"))
    if not ok:
        _fails.append(label)


# ─────────────────────────────────────────────────────────────────────────────
# 1) Función pura
# ─────────────────────────────────────────────────────────────────────────────
def test_dimensions():
    print("\n[D1] Potencial de volumen (hasta 3)")
    check("alto",        sc._volume_points({'potential_volume': 'alto'}), 3.0)
    check("medio",       sc._volume_points({'potential_volume': 'medio'}), 2.0)
    check("bajo",        sc._volume_points({'potential_volume': 'bajo'}), 1.0)
    check("desconocido", sc._volume_points({'potential_volume': 'desconocido'}), 0.0)
    check("ausente",     sc._volume_points({}), 0.0)

    print("\n[D2] Facilidad de contacto (hasta 2.5, automática)")
    check("phone gana",       sc._contact_points({'phone': '11 5555', 'instagram': 'x'}), 2.5)
    check("instagram si no hay phone", sc._contact_points({'instagram': 'x', 'address': 'Calle 1'}), 1.5)
    check("address solo",     sc._contact_points({'address': 'Calle 1'}), 0.5)
    check("website solo",     sc._contact_points({'website': 'http://x'}), 0.5)
    check("nada",             sc._contact_points({}), 0.0)
    check("todo vacío",       sc._contact_points({'phone': '', 'instagram': '  ', 'address': ''}), 0.0)

    print("\n[D3] Situación de proveedor (hasta 2)")
    check("ninguno",     sc._supplier_points({'current_supplier': 'ninguno'}), 2.0)
    check("competencia", sc._supplier_points({'current_supplier': 'competencia'}), 1.5)
    check("la_meson",    sc._supplier_points({'current_supplier': 'la_meson'}), 0.5)
    check("desconocido", sc._supplier_points({'current_supplier': 'desconocido'}), 0.0)
    check("ausente",     sc._supplier_points({}), 0.0)

    print("\n[D4] Categoría del local (hasta 1.5)")
    check("Restaurante Italiano -> alto", sc._category_points({'type': 'Restaurante Italiano'}), 1.5)
    check("Vinoteca -> alto",             sc._category_points({'type': 'Vinoteca'}), 1.5)
    check("case-insensitive",             sc._category_points({'type': 'restaurante italiano'}), 1.5)
    check("Pizzería Napolitana -> mid",   sc._category_points({'type': 'Pizzería Napolitana'}), 1.0)
    check("Parrilla Premium -> mid",      sc._category_points({'type': 'Parrilla Premium'}), 1.0)
    check("otro valor -> 0.5",            sc._category_points({'type': 'Bodegón'}), 0.5)
    check("sin type -> 0.5",              sc._category_points({}), 0.5)

    print("\n[D5] Señales premium (hasta 1)")
    check("is_premium=1",            sc._premium_points({'is_premium': 1}), 1.0)
    check("is_premium=True",         sc._premium_points({'is_premium': True}), 1.0)
    check("zona premium por barrio", sc._premium_points({'is_premium': 0, 'neighborhood': 'Palermo'}), 0.5)
    check("zona premium por zone",   sc._premium_points({'is_premium': 0, 'zone': 'Belgrano'}), 0.5)
    check("no premium",              sc._premium_points({'is_premium': 0, 'neighborhood': 'Boedo'}), 0.0)


def test_calibrated_examples():
    print("\n[EJEMPLOS CALIBRADOS] resultado EXACTO")

    # 1) Parrilla premium en Palermo, phone, ninguno, alto, is_premium=1  -> 9.5
    ej1 = {
        'type': 'Parrilla Premium', 'phone': '+54 11 4444-5555',
        'current_supplier': 'ninguno', 'potential_volume': 'alto',
        'is_premium': 1, 'neighborhood': 'Palermo', 'zone': 'CABA',
    }
    check("ej1 = 9.5", sc.calculate_priority_score(ej1), 9.5)

    # 2) Pizzería gourmet de barrio, solo Instagram, competencia, bajo,
    #    is_premium=0, zona no premium  -> 5.0
    ej2 = {
        'type': 'Pizzería Gourmet', 'instagram': 'lapizza',
        'current_supplier': 'competencia', 'potential_volume': 'bajo',
        'is_premium': 0, 'neighborhood': 'Villa del Parque', 'zone': 'CABA',
    }
    check("ej2 = 5.0", sc.calculate_priority_score(ej2), 5.0)

    # 3) Café de barrio sin contacto, la_meson, volumen bajo, is_premium=0,
    #    zona no premium  -> 2.0
    ej3 = {
        'type': 'Café de barrio', 'current_supplier': 'la_meson',
        'potential_volume': 'bajo', 'is_premium': 0,
        'neighborhood': 'Boedo', 'zone': 'CABA',
    }
    check("ej3 = 2.0", sc.calculate_priority_score(ej3), 2.0)


def test_range_and_rounding():
    print("\n[RANGO Y REDONDEO]")
    top = {
        'type': 'Restaurante Italiano', 'phone': '1', 'current_supplier': 'ninguno',
        'potential_volume': 'alto', 'is_premium': 1,
    }
    check("máximo = 10.0", sc.calculate_priority_score(top), 10.0)
    # piso real: 0.5, porque un `type` vacío / desconocido cae en "otro" (D4 = 0.5)
    check("piso = 0.5 (todo lo demás en cero)", sc.calculate_priority_score({}), 0.5)
    check("suma en múltiplos de 0.5", sc.calculate_priority_score(
        {'potential_volume': 'bajo', 'current_supplier': 'la_meson', 'type': 'x'}), 2.0)
    check("tier A", sc.priority_tier(9.5), 'A')
    check("tier B", sc.priority_tier(5.0), 'B')
    check("tier C", sc.priority_tier(4.9), 'C')


# ─────────────────────────────────────────────────────────────────────────────
# 2) Wiring contra la DB
# ─────────────────────────────────────────────────────────────────────────────
def _setup():
    if getattr(db, 'USE_POSTGRES', False):
        schema = f"test_score_{os.getpid()}_{int(time.time())}"
        db.set_pg_schema(schema)
        db.init_db()
        print(f"\n[infra] Postgres, esquema temporal: {schema}")
        return lambda: db.drop_pg_schema(schema)
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    db.init_db()
    print(f"\n[infra] SQLite temporal: {tmp.name}")
    return lambda: os.unlink(tmp.name)


def test_wiring():
    print("\n[WIRING] score_auto se calcula y persiste solo; `score` no se toca")

    data = {
        'name': 'Trattoria Wiring', 'neighborhood': 'Palermo', 'zone': 'CABA',
        'type': 'Restaurante Italiano', 'phone': '+54 11 1234-5678',
        'current_supplier': 'ninguno', 'potential_volume': 'alto',
        'is_premium': 1, 'score': 3,          # score MANUAL bajo a propósito
    }
    expected = sc.calculate_priority_score(data)          # 10.0
    pid = db.create_prospect(data)
    p = db.get_prospect(pid)
    check("create: score_auto calculado", round(p['score_auto'], 1), expected)
    check("create: score manual intacto", p['score'], 3)

    # update parcial: cambia el proveedor -> score_auto baja, score sigue igual
    db.update_prospect_partial(pid, {'current_supplier': 'la_meson'},
                               skip=db.IMPORT_PROTECTED_FIELDS)
    p = db.get_prospect(pid)
    merged = {**data, 'current_supplier': 'la_meson'}
    check("partial: score_auto recalculado", round(p['score_auto'], 1),
          sc.calculate_priority_score(merged))
    check("partial: score manual intacto", p['score'], 3)
    check("partial: proveedor actualizado", p['current_supplier'], 'la_meson')

    # update full
    full = {**data, 'potential_volume': 'bajo', 'current_supplier': 'competencia'}
    db.update_prospect(pid, full)
    p = db.get_prospect(pid)
    check("full update: score_auto recalculado", round(p['score_auto'], 1),
          sc.calculate_priority_score(full))
    check("full update: score manual intacto", p['score'], 3)

    # helper de recálculo masivo
    got = db.recalculate_score_auto(pid)
    check("recalculate_score_auto devuelve el valor", got, sc.calculate_priority_score(db.get_prospect(pid)))

    # import protegido: score_auto NO está protegido, se actualiza igual
    db.upsert_prospect(
        {'name': 'Trattoria Wiring', 'neighborhood': 'Palermo', 'potential_volume': 'medio'},
        protect_on_update=db.IMPORT_PROTECTED_FIELDS)
    p = db.get_prospect(pid)
    check("import: potential_volume entró (no está protegido)", p['potential_volume'], 'medio')
    check("import: score manual sigue intacto (protegido)", p['score'], 3)


def main():
    test_dimensions()
    test_calibrated_examples()
    test_range_and_rounding()

    teardown = _setup()
    try:
        test_wiring()
    finally:
        teardown()

    print("\n" + ("=" * 50))
    if _fails:
        print(f"RESULTADO: {len(_fails)} CHECK(S) FALLARON -> {_fails}")
        sys.exit(1)
    print("RESULTADO: TODO OK")


if __name__ == '__main__':
    main()
