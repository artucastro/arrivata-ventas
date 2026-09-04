import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'credentials', 'google_credentials.json')

# NOTE: sheets_csv_url / sheets_spreadsheet_key / sheets_gid son intencionalmente
# NOT defaulted here. sheets_integration raises an explicit RuntimeError when one
# is missing, instead of silently falling back to an empty value.
DEFAULTS = {
    'sheets_credentials_path': '',
    'sheets_enabled': False,
    'last_sync': None,
}

# En un filesystem efímero (plan gratis de Render: el disco del contenedor
# se descarta en cada reinicio/redeploy — no hay "subir un archivo a mano" que
# sobreviva como en PythonAnywhere) config.json no persiste. Estas variables de
# entorno, si están seteadas, pisan lo que haya en config.json en cada arranque
# — así Sheets sigue andando sin tener que re-cargar nada por la UI de /sheets
# después de cada sleep/wake. Se cargan desde el dashboard de Render (nunca
# committeadas al repo); ver DEPLOY.md.
_ENV_OVERRIDES = {
    'sheets_csv_url': 'SHEETS_CSV_URL',
    'sheets_spreadsheet_key': 'SHEETS_SPREADSHEET_KEY',
    'sheets_gid': 'SHEETS_GID',
}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        config = {**DEFAULTS, **data}
    else:
        config = dict(DEFAULTS)

    for field, env_var in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var, '').strip()
        if value:
            config[field] = value

    # El archivo de credenciales de Google (subido a mano por /sheets, o
    # materializado desde GOOGLE_CREDENTIALS_JSON al arrancar — ver abajo) es
    # la fuente de verdad de si Sheets-escritura está disponible en ESTE
    # arranque del proceso, no lo que diga un config.json viejo.
    if os.path.exists(CREDENTIALS_PATH):
        config['sheets_credentials_path'] = CREDENTIALS_PATH
        config['sheets_enabled'] = True

    return config


def save_config(config: dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def materialize_credentials_from_env():
    """Si GOOGLE_CREDENTIALS_JSON está seteada (el JSON completo de la cuenta
    de servicio de Google, pegado tal cual como valor de la variable de
    entorno en el dashboard de Render), la escribe a
    credentials/google_credentials.json al arrancar la app.

    Necesario porque el filesystem del plan gratis de Render es efímero: un
    archivo subido a mano por la UI de /sheets se pierde en el próximo
    reinicio/redeploy, pero una variable de entorno no — así Sheets-escritura
    sigue andando sin re-subir el archivo después de cada sleep/wake.

    No hace nada si la variable no está seteada (deploys que no usan Sheets,
    o dev local con el archivo ya presente a mano vía /sheets).
    """
    raw = os.environ.get('GOOGLE_CREDENTIALS_JSON', '').strip()
    if not raw:
        return
    try:
        json.loads(raw)  # valida antes de escribir — mejor fallar temprano y claro
    except ValueError as e:
        print(f"[config_manager] GOOGLE_CREDENTIALS_JSON no es JSON válido, se ignora: {e}")
        return
    os.makedirs(os.path.dirname(CREDENTIALS_PATH), exist_ok=True)
    with open(CREDENTIALS_PATH, 'w', encoding='utf-8') as f:
        f.write(raw)
