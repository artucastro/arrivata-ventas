# Arrivata Sales Tool

Herramienta web interna para investigar y priorizar clientes potenciales
(restaurantes, pizzerías, hoteles gourmet, etc.) en CABA y AMBA para la venta de
productos de Arrivata (quesos artesanales italianos).

## Funcionalidades

- **Dashboard** de prospectos con filtros (barrio, tipo, estado de contacto, score).
- **Búsqueda con IA** (Claude + web search): encuentra prospectos por barrio o zona
  y devuelve un listado estructurado para importar.
- **Scoring automático** por tipo de local + barrio + si es premium.
- **Mapa interactivo** (Leaflet / OpenStreetMap) con geocoding vía Nominatim.
- **Google Sheets**: importar el listado existente y sincronizar de vuelta.
- **Export CSV**.

## Stack

Python 3.11 · Flask · PostgreSQL (prod) / SQLite (fallback local) · Bootstrap 5 ·
Leaflet · SDK `anthropic`

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env            # completar ANTHROPIC_API_KEY y FLASK_SECRET_KEY
cp config.example.json config.json   # ajustar si se usa Google Sheets
python app.py                   # http://localhost:5001
```

En Windows también sirve `start.bat`.

## Base de datos (PostgreSQL / SQLite)

La app elige el backend según la variable de entorno **`DATABASE_URL`** (en `.env`):

| `DATABASE_URL`            | Backend            | Cuándo                                        |
|--------------------------|--------------------|-----------------------------------------------|
| con valor (URL Postgres) | PostgreSQL + pool  | **Producción** y acceso multi-usuario. Siempre en la web. |
| vacía / sin definir      | SQLite (`arrivata.db`) | Desarrollo local sin Postgres corriendo.  |

```
# .env  ── producción / desarrollo contra la base compartida
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require

# .env  ── desarrollo 100% local, sin Postgres
DATABASE_URL=
```

No hay que tocar código para cambiar de uno a otro: solo la variable. El esquema
Postgres está en [`migrations/001_init_postgres.sql`](migrations/001_init_postgres.sql)
y `db.init_db()` lo aplica solo (es idempotente) al arrancar la app.

### Migrar los datos de SQLite a Postgres (una sola vez)

```bash
# con DATABASE_URL apuntando al Postgres destino (vacío)
python scripts/migrate_sqlite_to_postgres.py
```

Copia todas las filas preservando ids y valores, resetea la secuencia del `id`,
y falla si el conteo origen/destino no coincide. Es seguro re-ejecutarlo (no
duplica: `INSERT ... ON CONFLICT (id) DO NOTHING`).

### Google Sheets (opcional)

- **Lectura** ("Importar desde Sheets"): el sheet debe estar *publicado en la web*
  como CSV; pegar esa URL en `config.json` → `sheets_csv_url`.
- **Escritura** ("Sincronizar" / "Probar conexión"): requiere una *service account*
  de Google (Sheets API + Drive API) con el JSON en `credentials/google_credentials.json`
  y el spreadsheet compartido como Editor. Completar `sheets_spreadsheet_key` y
  `sheets_gid` en `config.json`.

## Login / usuarios

Toda la app requiere sesión iniciada (`/login`). Dos formas de entrar:

- **Cuenta individual** (Arturo, Emmanuel): usuario + contraseña propios, acceso
  completo (crear/editar/eliminar). Se crean con `scripts/manage_users.py`:
  ```bash
  python scripts/manage_users.py create arturo     # pide la contraseña oculta
  python scripts/manage_users.py passwd arturo      # cambiarla
  python scripts/manage_users.py list               # ver las cuentas que existen
  ```
- **Solo lectura**: una contraseña única compartida (`VIEWER_PASSWORD` en `.env`,
  ver `.env.example`), sin usuario — la reparte Arturo a quien corresponda
  (gerencia, etc.). Ve dashboard, mapa, fichas y reportes; no puede crear, editar
  ni eliminar (ni en la UI —botones ocultos— ni en el backend, 403 si se intenta
  igual).

## Tests

```bash
python tests/test_import_protection.py
python tests/test_priority_score.py
python tests/test_auth.py
```

Corren contra el backend que indique `DATABASE_URL`. Con Postgres, cada uno crea
un **esquema temporal propio**, corre ahí y lo borra al final — nunca tocan la
tabla `prospects` (ni `users`) reales. Con SQLite usan un archivo temporal.

## Archivos que NO están en el repo

`.env`, `config.json`, `credentials/`, `arrivata.db` — contienen secretos o datos
locales. Ver `.env.example` y `config.example.json`.
