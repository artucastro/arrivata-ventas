# Deploy en PythonAnywhere (gratis)

Objetivo: tener la app en `https://TU_USUARIO.pythonanywhere.com`, con login,
usándola desde cualquier dispositivo, con la base de datos persistente.

> En el plan gratis funciona todo **menos la búsqueda con IA** (PythonAnywhere no
> deja llamar a la API de Anthropic). El geocoding y Google Sheets sí funcionan.

---

## 1. Crear la cuenta

1. Entrá a https://www.pythonanywhere.com/registration/register/beginner/
2. Elegí un usuario (será tu subdominio: `usuario.pythonanywhere.com`). Sugerencia: `artucastro`.
3. Confirmá el mail.

## 2. Traer el código

En **Consoles → Bash** (consola nueva):

```bash
git clone https://github.com/artucastro/arrivata-ventas.git
cd arrivata-ventas
mkvirtualenv --python=/usr/bin/python3.11 arrivata
pip install -r requirements.txt
```

(La última línea tarda 1-2 min.)

## 3. Crear el archivo `.env` en el servidor

Todavía en la consola Bash, dentro de `~/arrivata-ventas`:

```bash
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(32))" > .env
echo "APP_USER=arrivata"            >> .env
echo "APP_PASSWORD=ELEGI_UNA_CLAVE" >> .env
echo "FLASK_DEBUG=0"                >> .env
nano .env   # cambiá ELEGI_UNA_CLAVE por tu contraseña real; Ctrl+O, Enter, Ctrl+X
```

`APP_USER` + `APP_PASSWORD` son el usuario y contraseña con los que vas a entrar a la app.

## 4. Subir la base de datos actual

En **Files**, navegá a `/home/TU_USUARIO/arrivata-ventas/` → botón **Upload a file** →
subí tu `arrivata.db` (está en la carpeta del proyecto en tu PC).

## 5. Crear la Web App

1. Pestaña **Web** → **Add a new web app** → **Next**.
2. Elegí **Manual configuration** (¡NO "Flask"!) → **Python 3.11** → **Next**.
3. Cuando termine, en esa misma pestaña Web configurá:
   - **Source code:** `/home/TU_USUARIO/arrivata-ventas`
   - **Working directory:** `/home/TU_USUARIO/arrivata-ventas`
   - **Virtualenv:** escribí `arrivata` (se autocompleta a `/home/TU_USUARIO/.virtualenvs/arrivata`)
4. Click en el link del **WSGI configuration file** (arriba). Borrá todo el contenido y
   pegá el de `wsgi_pythonanywhere.py` de este repo, cambiando `USER` si tu usuario no es `artucastro`. Guardá.
5. Botón verde grande **Reload**.

## 6. Probar

Abrí `https://TU_USUARIO.pythonanywhere.com` → el navegador pide usuario y contraseña
(los de `APP_USER` / `APP_PASSWORD`) → entrás al dashboard con tus 86 prospectos.

---

## Google Sheets (opcional)

En **Files**, subí a `/home/TU_USUARIO/arrivata-ventas/`:
- `config.json`
- `credentials/google_credentials.json` (crear la carpeta `credentials` primero con **New directory**)

Editá `config.json` (botón lápiz) y poné la ruta **absoluta**:

```json
"sheets_credentials_path": "/home/TU_USUARIO/arrivata-ventas/credentials/google_credentials.json"
```

Reload.

## Actualizar la app más adelante

Cuando pusheás cambios a GitHub, en la consola Bash:

```bash
cd ~/arrivata-ventas && git pull
```

y **Reload** en la pestaña Web.

## Cosas a saber del plan gratis

- Cada ~3 meses PythonAnywhere te manda un mail para "extender" la cuenta: es un click, sigue gratis.
- La búsqueda IA no funciona (whitelist de PythonAnywhere). Corré esas búsquedas desde tu PC.
- Si el geocoding de prospectos nuevos falla, puede ser que `nominatim.openstreetmap.org`
  no esté en la whitelist: pedí que lo agreguen desde el foro de PythonAnywhere, o
  geocodificá desde tu PC y sincronizá por Sheets.
- La contraseña la cambiás editando `.env` y haciendo Reload.
