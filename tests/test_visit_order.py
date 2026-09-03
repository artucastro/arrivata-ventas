"""Prueba de "Mi orden" (orden personal de visitas por usuario).

  1. database.py puro: fallback por score_auto cuando no hay posiciones,
     independencia entre usuarios, prospecto nuevo nunca se pierde, y el
     merge de un reorder parcial (subconjunto filtrado) no pisa la posición
     de lo que quedó afuera.
  2. Contra la app real (test client): dos admins con órdenes propios y
     distintos sobre los MISMOS prospectos, y que un viewer reciba 403 REAL
     al pegarle al endpoint de guardar (no solo que el drag no aparezca).

IMPORTANTE: mismo patrón que los demás tests de auth — el aislamiento de DB
se arma ANTES de `import app` (app.py llama a db.init_db() al importarse).

Uso:  python tests/test_visit_order.py
"""
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_VIEWER_PW = 'test-viewer-pw-visitorder-1'
os.environ['VIEWER_PASSWORD'] = _VIEWER_PW
os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key-no-usar-en-serio')

import database as db  # noqa: E402

_fails = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'OK ' if ok else 'FALLA'}  {label}: {got!r}" + ("" if ok else f"  (esperaba {expected!r})"))
    if not ok:
        _fails.append(label)


def relative_order(full_list, subset):
    """`full_list` filtrado a solo los elementos de `subset` (en el orden en
    que aparecen). Cada test corre sobre el mismo esquema/DB que los
    anteriores (pueden quedar OTROS prospectos de un test previo mezclados
    como "rest" — es el comportamiento correcto de save_visit_order, ver su
    docstring); esto compara solo el orden relativo de lo que nos importa."""
    subset = set(subset)
    return [x for x in full_list if x in subset]


def _setup_db():
    if getattr(db, 'USE_POSTGRES', False):
        schema = f"test_vorder_{os.getpid()}_{int(time.time())}"
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


def test_fallback_and_independence():
    print("\n[1] Fallback por score_auto + independencia entre usuarios")
    from werkzeug.security import generate_password_hash

    u1 = db.create_user('vendedor1', generate_password_hash('clave-vendedor-1'))
    u2 = db.create_user('vendedor2', generate_password_hash('clave-vendedor-2'))

    p1 = db.create_prospect({'name': 'Prospecto Uno', 'neighborhood': 'Palermo'})
    p2 = db.create_prospect({'name': 'Prospecto Dos', 'neighborhood': 'Belgrano'})
    p3 = db.create_prospect({'name': 'Prospecto Tres', 'neighborhood': 'Once'})

    # Nadie posicionó nada todavía -> los dos ven el mismo fallback (score_auto).
    fallback = [p['id'] for p in db.get_all_prospects()]
    check("u1 sin posiciones -> fallback = get_all_prospects()", db.get_ordered_prospect_ids(u1), fallback)
    check("u2 sin posiciones -> mismo fallback", db.get_ordered_prospect_ids(u2), fallback)

    # u1 guarda SU orden.
    db.save_visit_order(u1, [p3, p1, p2])
    check("u1: orden guardado", db.get_ordered_prospect_ids(u1)[:3], [p3, p1, p2])
    check("u2 NO se afecta por lo que guardó u1 (sigue en fallback)",
          db.get_ordered_prospect_ids(u2), fallback)

    # u2 guarda un orden DISTINTO sobre los mismos prospectos.
    db.save_visit_order(u2, [p2, p3, p1])
    check("u2: su propio orden, distinto al de u1", db.get_ordered_prospect_ids(u2)[:3], [p2, p3, p1])
    check("u1 sigue con el suyo, sin cambios", db.get_ordered_prospect_ids(u1)[:3], [p3, p1, p2])

    # Prospecto nuevo (creado DESPUÉS de guardar el orden): nunca se pierde,
    # aparece al final (fallback por score_auto).
    p4 = db.create_prospect({'name': 'Prospecto Nuevo Sin Posición', 'neighborhood': 'Caballito'})
    order_u1 = db.get_ordered_prospect_ids(u1)
    check("prospecto nuevo aparece en la lista de u1", p4 in order_u1, True)
    check("prospecto nuevo va DESPUÉS de los ya posicionados (al final)",
          order_u1, [p3, p1, p2, p4])
    order_u2 = db.get_ordered_prospect_ids(u2)
    check("prospecto nuevo también aparece para u2, al final del SUYO",
          order_u2, [p2, p3, p1, p4])


def test_partial_reorder_merge():
    print("\n[2] Reorder de un subconjunto filtrado no pisa lo que queda afuera")
    from werkzeug.security import generate_password_hash
    u = db.create_user('vendedor3', generate_password_hash('clave-vendedor-3'))
    ids = [db.create_prospect({'name': f'Merge Test {i}', 'neighborhood': 'X'}) for i in range(5)]
    a, b, c, d, e = ids

    db.save_visit_order(u, [a, b, c, d, e])
    check("orden inicial (relativo a estos 5)",
          relative_order(db.get_ordered_prospect_ids(u), ids), [a, b, c, d, e])

    # Reordena SOLO un subconjunto (como si fuera lo que quedó visible tras un
    # filtro): [b, d] -> se invierten a [d, b]. a/c/e no estaban en el drag.
    db.save_visit_order(u, [d, b])
    check("el resto mantiene su posición relativa; el bloque reordenado se reinserta donde estaba",
          relative_order(db.get_ordered_prospect_ids(u), ids), [a, d, b, c, e])


def test_app_client(app_module, auth):
    print("\n[3] Contra la app real: dos admins, cada uno con su orden + 403 real a viewer")
    app = app_module.app
    app.config['TESTING'] = True

    from werkzeug.security import generate_password_hash
    db.create_user('adminuno', generate_password_hash('clave-admin-uno-1'))
    db.create_user('adosdmin', generate_password_hash('clave-admin-dos-2'))
    p1 = db.create_prospect({'name': 'App Test Prospecto A', 'neighborhood': 'Y'})
    p2 = db.create_prospect({'name': 'App Test Prospecto B', 'neighborhood': 'Y'})
    p3 = db.create_prospect({'name': 'App Test Prospecto C', 'neighborhood': 'Y'})

    def row_order(html):
        return re.findall(r'<tr data-id="(\d+)"', html)

    # Filtramos por neighborhood='Y' -> en la tabla SOLO aparecen p1/p2/p3
    # (nada más en la DB de este test tiene ese barrio), así el orden de las
    # filas se puede comparar exacto sin filtrar por relative_order().
    mine_url = '/?order=mine&neighborhood=Y'

    client1 = app.test_client()
    client1.post('/login', data={'mode': 'admin', 'username': 'adminuno', 'password': 'clave-admin-uno-1'})

    r = client1.post('/api/visit-order', json={'prospect_ids': [p3, p1, p2]})
    check("admin1 POST /api/visit-order -> 200", r.status_code, 200)
    check("admin1 POST /api/visit-order -> {ok: true}", r.get_json(), {'ok': True})

    r = client1.get(mine_url)
    check("admin1 GET /?order=mine -> 200", r.status_code, 200)
    html1 = r.get_data(as_text=True)
    order1 = row_order(html1)
    check("admin1 ve SU orden guardado",
          order1, [str(p3), str(p1), str(p2)])
    check("admin1 en modo 'mine' SÍ ve el drag handle", 'drag-handle' in html1, True)
    check("admin1 en modo 'mine' carga SortableJS", 'sortablejs' in html1, True)

    client2 = app.test_client()
    client2.post('/login', data={'mode': 'admin', 'username': 'adosdmin', 'password': 'clave-admin-dos-2'})

    r = client2.post('/api/visit-order', json={'prospect_ids': [p2, p3, p1]})
    check("admin2 POST /api/visit-order -> 200", r.status_code, 200)

    r = client2.get(mine_url)
    order2 = row_order(r.get_data(as_text=True))
    check("admin2 ve SU PROPIO orden (distinto al de admin1)",
          order2, [str(p2), str(p3), str(p1)])

    # admin1 no se vio afectado por lo que guardó admin2.
    r = client1.get(mine_url)
    order1_again = row_order(r.get_data(as_text=True))
    check("admin1 sigue viendo el suyo, sin que admin2 lo haya tocado",
          order1_again, [str(p3), str(p1), str(p2)])

    client1.get('/logout')
    client2.get('/logout')

    # ── Viewer: ve los dos modos, pero SIN drag, y 403 real al guardar ──────
    viewer = app.test_client()
    viewer.post('/login', data={'mode': 'viewer', 'viewer_password': _VIEWER_PW})

    r = viewer.get('/')
    check("viewer ve el modo 'Por prioridad' (default)", r.status_code, 200)
    r = viewer.get('/?order=mine')
    check("viewer SÍ puede ver el modo 'Mi orden' (no bloqueado)", r.status_code, 200)
    html_v = r.get_data(as_text=True)
    check("viewer NO ve el drag handle en 'Mi orden'", 'drag-handle' in html_v, False)
    check("viewer NO carga SortableJS", 'sortablejs' in html_v, False)

    r = viewer.post('/api/visit-order', json={'prospect_ids': [p1, p2, p3]})
    check("viewer POST /api/visit-order -> 403 REAL", r.status_code, 403)

    # Y que ese intento no haya cambiado nada de verdad en la base.
    admin1_row = db.get_user_by_username('adminuno')
    order_db = db.get_ordered_prospect_ids(admin1_row['id'])
    check("el 403 del viewer no tocó ningún orden real",
          relative_order(order_db, [p1, p2, p3]), [p3, p1, p2])

    viewer.get('/logout')


def main():
    teardown = _setup_db()
    try:
        test_fallback_and_independence()
        test_partial_reorder_merge()

        import auth
        import app as app_module
        test_app_client(app_module, auth)
    finally:
        teardown()

    print("\n" + ("=" * 50))
    if _fails:
        print(f"RESULTADO: {len(_fails)} CHECK(S) FALLARON -> {_fails}")
        sys.exit(1)
    print("RESULTADO: TODO OK")


if __name__ == '__main__':
    main()
