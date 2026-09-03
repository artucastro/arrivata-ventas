"""Prueba del login (Flask-Login) y del gate de rol admin/viewer.

  1. auth.authenticate() / auth.authenticate_viewer() — función pura, casos
     de login exitoso/fallido para los dos roles.
  2. Contra la app real (test client de Flask): que un anónimo NO pueda ver
     nada, que el login de sesión funcione para admin y viewer, y que un
     viewer reciba un 403 REAL (no solo el botón oculto) al pegarle un POST
     directo a crear/editar/eliminar un prospecto. También que un admin sí
     pueda (para no estar sobre-bloqueando).

IMPORTANTE: el aislamiento de DB (esquema temporal en Postgres / archivo
temporal en SQLite) se arma ANTES de `import app`, porque app.py llama a
db.init_db() apenas se importa — si el aislamiento se arma después, la app
ya habría inicializado contra la base real.

Uso:  python tests/test_auth.py
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_VIEWER_PW = 'test-viewer-pw-e2e-9x'
os.environ['VIEWER_PASSWORD'] = _VIEWER_PW
os.environ.setdefault('FLASK_SECRET_KEY', 'test-secret-key-no-usar-en-serio')

import database as db  # noqa: E402

_fails = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'OK ' if ok else 'FALLA'}  {label}: {got!r}" + ("" if ok else f"  (esperaba {expected!r})"))
    if not ok:
        _fails.append(label)


def _setup_db():
    """Aísla la corrida ANTES de que nada importe app.py."""
    if getattr(db, 'USE_POSTGRES', False):
        schema = f"test_auth_{os.getpid()}_{int(time.time())}"
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


def test_authenticate_pure(auth):
    print("\n[1] auth.authenticate() / authenticate_viewer() — función pura")
    from werkzeug.security import generate_password_hash

    db.create_user('proba', generate_password_hash('clave-correcta-123'), role='admin')

    ok = auth.authenticate('proba', 'clave-correcta-123')
    check("admin: password correcta -> User", ok is not None, True)
    check("admin: username correcto", ok.username if ok else None, 'proba')
    check("admin: role correcto", ok.role if ok else None, 'admin')
    check("admin: is_admin", ok.is_admin if ok else None, True)

    bad = auth.authenticate('proba', 'password-incorrecta')
    check("admin: password incorrecta -> None", bad, None)

    missing = auth.authenticate('no-existe-este-usuario', 'lo-que-sea')
    check("admin: usuario inexistente -> None", missing, None)

    # username case-insensitive (se normaliza a minúscula al crear/loguear)
    ok2 = auth.authenticate('PROBA', 'clave-correcta-123')
    check("admin: username case-insensitive", ok2 is not None, True)

    v_ok = auth.authenticate_viewer(_VIEWER_PW)
    check("viewer: password correcta -> User", v_ok is not None, True)
    check("viewer: role viewer", v_ok.role if v_ok else None, 'viewer')
    check("viewer: is_admin False", v_ok.is_admin if v_ok else None, False)

    v_bad = auth.authenticate_viewer('password-incorrecta')
    check("viewer: password incorrecta -> None", v_bad, None)

    v_empty = auth.authenticate_viewer('')
    check("viewer: password vacía -> None", v_empty, None)


def test_user_crud():
    print("\n[2] database.py: create_user / get_user_by_username / update_user_password")
    from werkzeug.security import generate_password_hash, check_password_hash

    uid = db.create_user('otro.admin', generate_password_hash('primera-clave-1'), role='admin')
    check("create_user devuelve un id", isinstance(uid, int), True)

    row = db.get_user_by_username('otro.admin')
    check("get_user_by_username lo encuentra", row is not None, True)
    check("password quedó hasheada (no texto plano)", row['password_hash'] != 'primera-clave-1', True)

    ok = db.update_user_password('otro.admin', generate_password_hash('segunda-clave-2'))
    check("update_user_password de usuario existente -> True", ok, True)
    row2 = db.get_user_by_username('otro.admin')
    check("la nueva contraseña matchea", check_password_hash(row2['password_hash'], 'segunda-clave-2'), True)
    check("la vieja ya no matchea", check_password_hash(row2['password_hash'], 'primera-clave-1'), False)

    missing = db.update_user_password('no-existe-para-nada', generate_password_hash('x'))
    check("update_user_password de usuario inexistente -> False", missing, False)

    usernames = [u['username'] for u in db.list_users()]
    check("list_users incluye a los creados", {'proba', 'otro.admin'} <= set(usernames), True)


def test_app_client(app_module, auth):
    print("\n[3] Contra la app real (test client)")
    app = app_module.app
    app.config['TESTING'] = True
    client = app.test_client()

    # ── Anónimo: no puede ver nada ──────────────────────────────────────
    r = client.get('/', follow_redirects=False)
    check("anónimo GET / -> 302 (a /login)", r.status_code, 302)
    check("anónimo GET / -> Location incluye /login", '/login' in r.headers.get('Location', ''), True)

    r = client.get('/mapa', follow_redirects=False)
    check("anónimo GET /mapa -> 302", r.status_code, 302)

    r = client.get('/login')
    check("anónimo SÍ puede ver /login", r.status_code, 200)

    # ── Login admin: fallido ────────────────────────────────────────────
    r = client.post('/login', data={'mode': 'admin', 'username': 'proba', 'password': 'password-incorrecta'})
    check("login admin con password incorrecta -> re-renderiza (200)", r.status_code, 200)
    r = client.get('/', follow_redirects=False)
    check("sigue sin sesión después del login fallido", r.status_code, 302)

    # ── Login admin: exitoso ─────────────────────────────────────────────
    r = client.post('/login', data={'mode': 'admin', 'username': 'proba', 'password': 'clave-correcta-123'},
                    follow_redirects=False)
    check("login admin OK -> 302", r.status_code, 302)
    r = client.get('/')
    check("admin logueado ve el dashboard", r.status_code, 200)
    r = client.get('/busqueda')
    check("admin logueado ve /busqueda (AI search)", r.status_code, 200)

    # ── Admin SÍ puede crear/editar/eliminar (no sobre-bloquear) ─────────
    r = client.post('/prospecto/nuevo', data={'name': 'Admin Test Prospect', 'neighborhood': 'TestBarrio'},
                    follow_redirects=False)
    check("admin POST crear prospecto -> 302 (no 403)", r.status_code, 302)
    created = db.get_prospect_by_key('Admin Test Prospect', 'TestBarrio')
    check("el prospecto se creó de verdad", created is not None, True)
    pid = created['id']

    r = client.post(f'/prospecto/{pid}/editar',
                    data={'name': 'Admin Test Prospect (editado)', 'neighborhood': 'TestBarrio'},
                    follow_redirects=False)
    check("admin POST editar -> 302 (no 403)", r.status_code, 302)

    r = client.post(f'/prospecto/{pid}/eliminar', follow_redirects=False)
    check("admin POST eliminar -> 302 (no 403)", r.status_code, 302)
    check("el prospecto se borró de verdad", db.get_prospect(pid), None)

    client.get('/logout')
    r = client.get('/', follow_redirects=False)
    check("logout admin -> vuelve a pedir login", r.status_code, 302)

    # ── Login viewer: fallido ────────────────────────────────────────────
    r = client.post('/login', data={'mode': 'viewer', 'viewer_password': 'no-es-esta'})
    check("login viewer con password incorrecta -> re-renderiza (200)", r.status_code, 200)
    r = client.get('/', follow_redirects=False)
    check("sigue sin sesión (viewer fallido)", r.status_code, 302)

    # ── Login viewer: exitoso ─────────────────────────────────────────────
    r = client.post('/login', data={'mode': 'viewer', 'viewer_password': _VIEWER_PW}, follow_redirects=False)
    check("login viewer OK -> 302", r.status_code, 302)
    r = client.get('/')
    check("viewer ve el dashboard", r.status_code, 200)
    r = client.get('/mapa')
    check("viewer ve el mapa", r.status_code, 200)

    # ── Viewer: 403 REAL en los endpoints de escritura (no solo UI oculta) ──
    r = client.post('/prospecto/nuevo', data={'name': 'Viewer NO debería poder', 'neighborhood': 'X'})
    check("viewer POST crear prospecto -> 403", r.status_code, 403)
    check("viewer no creó nada de verdad",
          db.get_prospect_by_key('Viewer NO debería poder', 'X'), None)

    target_id = db.create_prospect({'name': 'Target para test de viewer', 'neighborhood': 'Y'})
    r = client.post(f'/prospecto/{target_id}/editar', data={'name': 'hackeado', 'neighborhood': 'Y'})
    check("viewer POST editar -> 403", r.status_code, 403)
    check("el prospecto NO se modificó", db.get_prospect(target_id)['name'], 'Target para test de viewer')

    r = client.post(f'/prospecto/{target_id}/eliminar')
    check("viewer POST eliminar -> 403", r.status_code, 403)
    check("el prospecto sigue existiendo", db.get_prospect(target_id) is not None, True)

    r = client.get('/prospecto/nuevo')
    check("viewer ni siquiera ve el form de alta (GET) -> 403", r.status_code, 403)
    r = client.get('/busqueda')
    check("viewer no puede ver /busqueda (AI search) -> 403", r.status_code, 403)
    r = client.post('/busqueda/ejecutar', data={})
    check("viewer POST /busqueda/ejecutar -> 403", r.status_code, 403)
    r = client.get('/sheets')
    check("viewer no puede ver /sheets -> 403", r.status_code, 403)

    # Lectura que SÍ debería seguir andando para viewer.
    r = client.get(f'/prospecto/{target_id}')
    check("viewer sí puede VER la ficha del prospecto", r.status_code, 200)
    r = client.get('/exportar/csv')
    check("viewer sí puede exportar el CSV (reporte de solo lectura)", r.status_code, 200)

    client.get('/logout')


def main():
    teardown = _setup_db()
    try:
        import auth
        test_authenticate_pure(auth)
        test_user_crud()

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
