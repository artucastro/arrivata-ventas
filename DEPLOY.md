# Deploy en Render (gratis)

Objetivo: tener la app en `https://arrivata-sales-tool.onrender.com` (o el
nombre que elijas), con login, usable desde cualquier dispositivo, con la
base de datos persistente en Postgres (Neon).

> Se usa Render y no PythonAnywhere porque el plan gratis de PythonAnywhere
> no puede conectarse a bases de datos externas (como nuestro Postgres de
> Neon) — solo permite salir a una whitelist corta de hosts. Render sí lo
> permite en su plan gratis.

---

## Antes de empezar: el trade-off del plan gratis — "sleep"

Un web service gratis de Render se **duerme después de 15 minutos sin
tráfico**. El primer acceso después de eso (alguien abre la app, o vos
mismo al día siguiente) tarda unos **30-40 segundos en responder** mientras
el contenedor arranca de nuevo — después de eso anda normal hasta el
próximo período de 15 minutos sin uso.

Esto es una **decisión consciente para arrancar sin costo**, no un bug ni
algo para "arreglar". Si en el uso diario del equipo comercial esos 30-40
segundos ocasionales molestan, la solución es pasar el servicio al plan
**Starter (~US$7/mes)** desde el dashboard de Render — sin cambiar una
línea de código, sin volver a desplegar nada. Starter no duerme el
servicio.

Además, el plan gratis **no tiene disco persistente**: cualquier archivo
escrito en tiempo de ejecución (no en el repo) se pierde en cada
reinicio/redeploy, incluido cada "despertar" tras dormirse. Esto no afecta
a la base de datos (vive en Neon, un servicio aparte) pero sí a la
integración con Google Sheets — ver la sección dedicada más abajo.

---

## 1. Crear la cuenta y conectar el repo

1. Entrá a https://dashboard.render.com/register y creá una cuenta
   (podés usar "Sign up with GitHub" para conectar el repo en el mismo paso).
2. Si tu cuenta de GitHub no está conectada todavía: **Account Settings →
   GitHub** → autorizá acceso al repo `artucastro/arrivata-ventas`.

## 2. Desplegar con el Blueprint (`render.yaml`)

Este repo incluye [`render.yaml`](render.yaml), que describe el servicio
completo (build, arranque, variables de entorno). Con esto Render arma todo
solo, en vez de configurar cada campo a mano desde el dashboard.

1. En el dashboard de Render: **New → Blueprint**.
2. Elegí el repo `artucastro/arrivata-ventas` → rama `main`.
3. Render detecta `render.yaml` y muestra el servicio `arrivata-sales-tool`
   a crear, con sus variables de entorno **vacías** (las marcadas
   `sync: false` en el archivo — a propósito: un secreto nunca vive
   committeado en el repo). Antes de confirmar, Render te deja completarlas
   ahí mismo; si preferís hacerlo después, podés dejarlas en blanco por
   ahora y cargarlas en el paso 3.
4. Confirmá la creación. Render va a intentar el primer deploy — probablemente
   falle o quede en un estado raro hasta que completes las variables
   obligatorias del paso 3, es esperable.

## 3. Cargar las variables de entorno

En el dashboard del servicio recién creado: **Environment** → agregá (o
completá, si ya las viste en el paso 2):

| Variable | Obligatoria | De dónde sale |
|---|---|---|
| `DATABASE_URL` | Sí | Connection string de tu proyecto en [Neon](https://console.neon.tech) — `postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require`. La misma que ya usás en tu `.env` local. |
| `FLASK_SECRET_KEY` | Sí | Una clave larga y random, propia de producción (no reuses la de tu `.env` local). Generarla: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `VIEWER_PASSWORD` | Sí | La contraseña única de "solo lectura" que le vas a pasar al resto del equipo comercial (sin usuario propio). Elegí una vos. |
| `ANTHROPIC_API_KEY` | Sí, para que ande la búsqueda con IA | Tu API key de Anthropic (la misma que usás localmente). |
| `GOOGLE_CREDENTIALS_JSON` | Solo si usás sincronización con Sheets | Ver sección "Google Sheets" abajo. |
| `SHEETS_CSV_URL` | Solo si usás importar desde Sheets | Ver sección "Google Sheets" abajo. |
| `SHEETS_SPREADSHEET_KEY` / `SHEETS_GID` | Solo si usás sincronizar hacia Sheets | Ver sección "Google Sheets" abajo. |

`FLASK_DEBUG` **no** hace falta cargarla a mano: `render.yaml` ya la fija en
`"0"` (apagada) para todo despliegue de producción — esto es, de paso, la
resolución del punto viejo de "debug=True sin apagar" del backlog técnico.

Guardá. Render redespliega solo cada vez que cambiás una variable.

Las cuentas completas (usuario + contraseña) de Arturo y Emmanuel **no** son
variables de entorno — se crean como en local, con `scripts/manage_users.py`,
apuntando **desde tu PC** a la `DATABASE_URL` de producción (poné esa misma
`DATABASE_URL` en tu `.env` local un momento, corré el script, y volvé a
dejar tu `.env` como estaba si desarrollás contra otra base):

```bash
python scripts/manage_users.py create arturo
python scripts/manage_users.py create emmanuel
```
Pide la contraseña de forma oculta (no queda en el historial de la terminal).

## 4. Cargar los datos (primera vez)

Si `DATABASE_URL` apunta a un Neon que ya tiene los prospectos cargados
(el mismo que ya usás en local), no hay nada que migrar — la app usa esa
base tal cual, el esquema lo mantiene al día ella sola
(`db.init_db()` aplica `migrations/*.sql`, todas idempotentes, en cada
arranque).

Si arrancás de cero, migrá tu `arrivata.db` local una sola vez **desde tu
PC** (con la `DATABASE_URL` de producción en tu `.env` local):

```bash
python scripts/migrate_sqlite_to_postgres.py
```

## 5. Probar

Abrí la URL que Render te asignó (visible arriba a la izquierda del
dashboard del servicio, termina en `.onrender.com`) → te lleva a `/login` →
entrá con tu cuenta (usuario + contraseña, la que creaste en el paso 3) y
vas a ver el dashboard. Al resto de la empresa le pasás la pestaña "Solo
lectura" del login + `VIEWER_PASSWORD`.

Si el servicio estaba dormido, esta primera carga tarda 30-40 segundos —
ver la nota del principio.

---

## Google Sheets (opcional)

La integración con Sheets tiene dos partes independientes, y el plan
gratis de Render (sin disco persistente) las afecta distinto:

**Leer desde Sheets** ("Importar desde Sheets") solo necesita la URL
pública del spreadsheet publicado como CSV — no un archivo de
credenciales. Cargá esa URL en la variable de entorno `SHEETS_CSV_URL`
(y `SHEETS_SPREADSHEET_KEY`/`SHEETS_GID` si además vas a sincronizar
hacia el spreadsheet, ver abajo) en vez de cargarla desde la pestaña
`/sheets` de la app: lo que se guarda ahí vive en un archivo
(`config.json`) que Render **descarta en cada reinicio/redeploy** — con
la variable de entorno sobrevive siempre, sin tener que volver a
cargarla nunca.

**Escribir en Sheets** ("Probar conexión", "Sincronizar todo") sí necesita
un archivo de credenciales de cuenta de servicio de Google
(`credentials/google_credentials.json`). En PythonAnywhere esto se subía
a mano por la pestaña Files; en Render no existe eso ni tendría sentido
(se perdería en el próximo reinicio). En cambio:

1. Abrí tu `credentials/google_credentials.json` local en un editor de texto,
   copiá **todo** el contenido (es un JSON de una sola pieza, con `{` y `}`).
2. Pegalo tal cual, completo, como valor de la variable de entorno
   `GOOGLE_CREDENTIALS_JSON` en el dashboard de Render.
3. Guardá. En cada arranque, la app escribe ese contenido a
   `credentials/google_credentials.json` antes de atender cualquier
   pedido (ver `config_manager.materialize_credentials_from_env()`) — así
   sigue disponible después de dormir/despertar o de cada redeploy, sin
   volver a subir nada a mano.

Si no vas a usar Sheets, dejá las 4 variables (`GOOGLE_CREDENTIALS_JSON`,
`SHEETS_CSV_URL`, `SHEETS_SPREADSHEET_KEY`, `SHEETS_GID`) sin cargar — el
resto de la app (dashboard, mapa, CRM, búsqueda con IA) funciona igual.

---

## Actualizar la app más adelante

Por default, Render redespliega solo cada vez que se pushea a `main` en
GitHub (auto-deploy). No hace falta ningún paso manual — a los pocos
minutos del push, el cambio ya está en producción. Podés desactivar esto
por servicio en **Settings → Build & Deploy** si preferís desplegar a mano
con el botón **Manual Deploy**.

## Cosas a saber del plan gratis

- El servicio se duerme tras 15 min sin tráfico; el primer acceso después
  tarda 30-40s (ver nota al principio). Upgrade a Starter (~US$7/mes) para
  sacarlo, sin cambios de código.
- Sin disco persistente: cualquier archivo escrito en tiempo de ejecución
  (subida por `/sheets`, `config.json` guardado desde la UI) se pierde en
  cada reinicio. Usá las variables de entorno de la sección Google Sheets
  arriba en vez de la carga por UI para que sobreviva.
- 750 horas/mes gratis compartidas entre todos tus servicios free — de
  sobra para un solo servicio, aunque nunca durmiera.
- La API de Anthropic (búsqueda con IA) no tiene ninguna restricción de
  salida en Render (a diferencia de PythonAnywhere, que la bloqueaba en el
  plan gratis) — anda igual que en local.
- Solo 512 MB de RAM. `render.yaml` fija `--workers 1` a propósito (más de
  un worker multiplica el footprint entero de la app en memoria) y
  `--timeout 120` (una búsqueda con IA puede tardar minuto y medio o más;
  el default de gunicorn, 30s, la mataría a mitad de camino). Si en el
  dashboard de Render (**Settings → Start Command**, o una env var
  `WEB_CONCURRENCY`) hay algo puesto a mano que pise este `startCommand`,
  eso gana por sobre lo que diga `render.yaml` — revisar ahí primero si
  vuelve a aparecer un `Worker was sent SIGKILL!` en los logs.
