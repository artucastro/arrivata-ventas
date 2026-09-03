"""Prueba de la búsqueda con IA "profunda" (más datos + inferencias).

  1. ai_search._parse_results() — función pura, sobre un JSON sintético con
     la forma exacta que devolvería el modelo. Sin llamar a la API real.
  2. scoring.normalize_closed_type() / scripts.reclassify_types.classify_type()
     — funciones puras de clasificación.
  3. Contra la app real (test client): una búsqueda IA simulada (se carga el
     caché de resultados directo, sin pegarle a Anthropic) sobre un prospecto
     NUEVO completa todos los campos nuevos; sobre uno EXISTENTE con
     potential_volume/current_supplier ya cargados a mano NO los pisa aunque
     la IA infiera otra cosa; sí los completa si estaban en 'desconocido'.

IMPORTANTE: mismo patrón que los demás tests — el aislamiento de DB se arma
ANTES de `import app` (app.py llama a db.init_db() al importarse), y esta
prueba NUNCA llama a la API de Anthropic (cuesta plata / necesita red):
simula el resultado de la búsqueda escribiendo directo en _SEARCH_CACHE.

Uso:  python tests/test_ai_search_depth.py
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key-no-usar-en-serio')

import database as db  # noqa: E402

_fails = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'OK ' if ok else 'FALLA'}  {label}: {got!r}" + ("" if ok else f"  (esperaba {expected!r})"))
    if not ok:
        _fails.append(label)


def _setup_db():
    if getattr(db, 'USE_POSTGRES', False):
        schema = f"test_aidepth_{os.getpid()}_{int(time.time())}"
        db.set_pg_schema(schema)
        db.init_db()
        print(f"[infra] Postgres, esquema temporal: {schema}")
        return lambda: db.drop_pg_schema(schema)
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    db.init_db()
    print(f"[infra] SQLite temporal: {tmp.name}")
    return lambda: os.unlink(tmp.name)


# ─────────────────────────────────────────────────────────────────────────────
# 1) ai_search._parse_results() — función pura
# ─────────────────────────────────────────────────────────────────────────────
_FAKE_RESPONSE_JSON = """
Acá tenés los resultados:
{
  "barrio": "Palermo",
  "resultados": [
    {
      "nombre": "Trattoria Completa",
      "tipo": "pizzería napolitana",
      "municipio": "CABA",
      "direccion": "Calle Falsa 123",
      "telefono": "+54 11 4444-5555",
      "instagram": "trattoriacompleta",
      "website": "https://trattoriacompleta.com",
      "es_premium": true,
      "rango_precio": "$$$",
      "rating_google": 4.6,
      "cantidad_resenas_google": 380,
      "estado_redes_sociales": "activa",
      "tamano_cadena": "cadena_chica",
      "notas_menu_quesos": "provoleta, 2 pizzas con bocconcino",
      "potencial_volumen_estimado": "alto",
      "proveedor_actual_inferido": "competencia",
      "productos_recomendados": ["Burrata", "Provola Ahumada"],
      "justificacion": "Buen fit por su carta con quesos premium.",
      "resumen_ia": "Vale la pena visitarlo: carta con varios platos con queso y buen posicionamiento."
    },
    {
      "nombre": "Local Con Datos Raros",
      "tipo": "un tipo de local que no existe en la lista",
      "rango_precio": "gratis",
      "rating_google": 11,
      "cantidad_resenas_google": -5,
      "estado_redes_sociales": "ni idea",
      "tamano_cadena": "mega cadena",
      "potencial_volumen_estimado": "altisimo",
      "proveedor_actual_inferido": "seguro que la competencia"
    }
  ]
}
"""


def test_parse_results_pure():
    print("\n[1] ai_search._parse_results() — función pura, sin red")
    import ai_search

    results = ai_search._parse_results(_FAKE_RESPONSE_JSON)
    check("parsea 2 resultados", len(results), 2)

    r = results[0]
    check("type normalizado a Título Canónico", r['type'], 'Pizzería Napolitana')
    check("price_range", r['price_range'], '$$$')
    check("google_rating", r['google_rating'], 4.6)
    check("google_review_count", r['google_review_count'], 380)
    check("social_media_status", r['social_media_status'], 'activa')
    check("chain_size", r['chain_size'], 'cadena_chica')
    check("cheese_menu_notes", r['cheese_menu_notes'], 'provoleta, 2 pizzas con bocconcino')
    check("potential_volume", r['potential_volume'], 'alto')
    check("current_supplier", r['current_supplier'], 'competencia')
    check("ai_summary", r['ai_summary'], 'Vale la pena visitarlo: carta con varios platos con queso y buen posicionamiento.')

    # El segundo resultado tiene basura en TODOS los campos de vocabulario
    # cerrado / rango numérico — nada de eso puede colarse a la DB tal cual.
    r2 = results[1]
    check("tipo inválido -> 'Otro'", r2['type'], 'Otro')
    check("price_range inválido -> 'desconocido'", r2['price_range'], 'desconocido')
    check("rating fuera de 0-5 -> None", r2['google_rating'], None)
    check("cantidad de reseñas negativa -> None", r2['google_review_count'], None)
    check("estado de redes inválido -> 'sin_datos'", r2['social_media_status'], 'sin_datos')
    check("tamaño de cadena inválido -> 'desconocido'", r2['chain_size'], 'desconocido')
    check("volumen inválido -> 'desconocido'", r2['potential_volume'], 'desconocido')
    check("proveedor inválido -> 'desconocido'", r2['current_supplier'], 'desconocido')


def test_classification_pure():
    print("\n[2] Clasificación de `type` — funciones puras")
    import scoring as sc
    from scripts.reclassify_types import classify_type

    check("normalize_closed_type matchea case-insensitive", sc.normalize_closed_type('VINOTECA'), 'Vinoteca')
    check("normalize_closed_type sin match -> Otro", sc.normalize_closed_type('un texto cualquiera'), 'Otro')
    check("normalize_closed_type vacío -> Otro", sc.normalize_closed_type(''), 'Otro')
    check("normalize_closed_type None -> Otro", sc.normalize_closed_type(None), 'Otro')

    check("classify_type: Trattoria -> Restaurante Italiano",
          classify_type({'type': 'Trattoria', 'name': 'La Trattoria'}), 'Restaurante Italiano')
    check("classify_type: Vinoteca Boutique -> Vinoteca",
          classify_type({'type': 'Vinoteca Boutique', 'name': 'X'}), 'Vinoteca')
    check("classify_type: Pizzería napolitana artesanal -> Pizzería Napolitana",
          classify_type({'type': 'Pizzería napolitana artesanal', 'name': 'X'}), 'Pizzería Napolitana')
    check("classify_type: texto sin señal -> Otro",
          classify_type({'type': 'Almacén Gourmet', 'name': 'Doña María'}), 'Otro')
    check("classify_type: señal en el NOMBRE, no en el type -> matchea igual",
          classify_type({'type': 'Restaurante', 'name': 'Osteria Del Puerto'}), 'Restaurante Italiano')


# ─────────────────────────────────────────────────────────────────────────────
# 3) Contra la app real: import de una búsqueda IA simulada
# ─────────────────────────────────────────────────────────────────────────────
def test_import_with_conditional_protection(app_module):
    print("\n[3] Import IA contra la app real: protección condicional")
    from werkzeug.security import generate_password_hash
    app = app_module.app
    app.config['TESTING'] = True

    db.create_user('vendedor_ia', generate_password_hash('clave-vendedor-ia-1'))
    client = app.test_client()
    client.post('/login', data={'mode': 'admin', 'username': 'vendedor_ia', 'password': 'clave-vendedor-ia-1'})

    def fake_search_result(**overrides):
        base = {
            'name': 'Ristorante IA Test', 'type': 'Restaurante Italiano',
            'neighborhood': 'Palermo', 'zone': 'CABA', 'address': '',
            'phone': '', 'instagram': '', 'website': '',
            'products_interest': 'Burrata', 'score': 7, 'score_auto': 7,
            'is_premium': True, 'notes': 'justificación', 'ai_summary': 'resumen de la IA',
            'price_range': '$$$', 'google_rating': 4.5, 'google_review_count': 120,
            'social_media_status': 'activa', 'chain_size': 'único_local',
            'cheese_menu_notes': 'burrata en la carta',
            'current_supplier': 'competencia', 'potential_volume': 'alto',
        }
        base.update(overrides)
        return base

    def simulate_search_and_import(results):
        """Carga _SEARCH_CACHE + session como si run_search() hubiera corrido,
        sin pegarle a la API real, y llama al endpoint de import de verdad."""
        with client.session_transaction() as sess:
            sess['search_token'] = 'tok-test'
        app_module._SEARCH_CACHE['tok-test'] = results
        selected = [str(i) for i in range(len(results))]
        return client.post('/busqueda/importar', data={'selected': selected}, follow_redirects=False)

    # ── Caso 1: prospecto NUEVO -> se completan TODOS los campos nuevos ──────
    r = simulate_search_and_import([fake_search_result()])
    check("import prospecto nuevo -> 302", r.status_code, 302)
    p = db.get_prospect_by_key('Ristorante IA Test', 'Palermo')
    check("prospecto nuevo: se creó", p is not None, True)
    check("  type (closed list)", p['type'], 'Restaurante Italiano')
    check("  price_range", p['price_range'], '$$$')
    check("  google_rating", p['google_rating'], 4.5)
    check("  google_review_count", p['google_review_count'], 120)
    check("  social_media_status", p['social_media_status'], 'activa')
    check("  chain_size", p['chain_size'], 'único_local')
    check("  cheese_menu_notes", p['cheese_menu_notes'], 'burrata en la carta')
    check("  ai_summary", p['ai_summary'], 'resumen de la IA')
    check("  current_supplier (alta, sin protección)", p['current_supplier'], 'competencia')
    check("  potential_volume (alta, sin protección)", p['potential_volume'], 'alto')

    # ── Caso 2: RE-búsqueda con potential_volume/current_supplier YA cargados
    #    a mano (como si alguien hubiera visitado el local) -> la IA NO los pisa,
    #    aunque infiera otra cosa distinta. El resto SÍ se refresca. ──────────
    db.update_prospect_partial(p['id'], {'current_supplier': 'ninguno', 'potential_volume': 'alto'})
    before = db.get_prospect(p['id'])
    check("(setup) current_supplier cargado a mano = 'ninguno'", before['current_supplier'], 'ninguno')
    check("(setup) potential_volume cargado a mano = 'alto'", before['potential_volume'], 'alto')

    r = simulate_search_and_import([fake_search_result(
        current_supplier='la_meson', potential_volume='bajo',   # la IA infiere OTRA cosa
        price_range='$', ai_summary='resumen actualizado',       # esto sí se refresca
    )])
    check("re-import -> 302", r.status_code, 302)
    after = db.get_prospect(p['id'])
    check("current_supplier NO se pisa (sigue 'ninguno', cargado a mano)",
          after['current_supplier'], 'ninguno')
    check("potential_volume NO se pisa (sigue 'alto', cargado a mano)",
          after['potential_volume'], 'alto')
    check("price_range SÍ se refresca con la nueva búsqueda", after['price_range'], '$')
    check("ai_summary SÍ se refresca con la nueva búsqueda", after['ai_summary'], 'resumen actualizado')

    # ── Caso 3: prospecto EXISTENTE con potential_volume/current_supplier en
    #    'desconocido' (nunca tocado) -> la IA SÍ los completa. ─────────────
    other_id = db.create_prospect({
        'name': 'Otro Local IA', 'neighborhood': 'Belgrano',
        'current_supplier': 'desconocido', 'potential_volume': 'desconocido',
    })
    r = simulate_search_and_import([fake_search_result(
        name='Otro Local IA', neighborhood='Belgrano',
        current_supplier='la_meson', potential_volume='medio',
    )])
    check("re-import sobre prospecto en 'desconocido' -> 302", r.status_code, 302)
    p3 = db.get_prospect(other_id)
    check("current_supplier SE COMPLETA (estaba en 'desconocido')", p3['current_supplier'], 'la_meson')
    check("potential_volume SE COMPLETA (estaba en 'desconocido')", p3['potential_volume'], 'medio')

    client.get('/logout')


def main():
    teardown = _setup_db()
    try:
        test_parse_results_pure()
        test_classification_pure()

        import app as app_module
        test_import_with_conditional_protection(app_module)
    finally:
        teardown()

    print("\n" + ("=" * 50))
    if _fails:
        print(f"RESULTADO: {len(_fails)} CHECK(S) FALLARON -> {_fails}")
        sys.exit(1)
    print("RESULTADO: TODO OK")


if __name__ == '__main__':
    main()
