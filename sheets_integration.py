import csv
import io
import os
import time
import requests

from config_manager import load_config

# ─── Config-driven spreadsheet identifiers ─────────────────────────────────
# Nothing is hardcoded and nothing is silently defaulted: if a required field
# is missing from config.json we raise a RuntimeError that says which field and
# what it is used for (read vs write).

_FIELD_PURPOSE = {
    'sheets_csv_url':
        'la LECTURA del spreadsheet (botón "Importar desde Sheets"). '
        'Debe ser la URL de "Publicar en la web" en formato CSV.',
    'sheets_spreadsheet_key':
        'la ESCRITURA al spreadsheet (botones "Probar conexión" y "Sincronizar todo"). '
        'Es la clave que aparece en https://docs.google.com/spreadsheets/d/<CLAVE>/edit',
    'sheets_gid':
        'identificar la pestaña del spreadsheet (gid numérico de la URL).',
}


def _require(field: str) -> str:
    value = str(load_config().get(field) or '').strip()
    if not value:
        raise RuntimeError(
            f"Falta '{field}' en config.json. Se usa para {_FIELD_PURPOSE[field]}"
        )
    return value


def _csv_url() -> str:
    """URL used to READ the public sheet as CSV."""
    return _require('sheets_csv_url')


def _write_target() -> tuple[str, str]:
    """(spreadsheet_key, gid) used to WRITE / validate via the gspread API."""
    return _require('sheets_spreadsheet_key'), _require('sheets_gid')


# Columns written back to the spreadsheet (extends the user's original format)
SHEET_HEADERS = [
    '#', 'Nombre del Local', 'Localidad / Barrio', 'Dirección',
    'Tipo de Local', 'Teléfono', 'Nota Comercial',
    'Score', 'Prioridad', 'Estado', 'Email', 'Instagram', 'Website',
]

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


# ─── READ (no credentials needed — sheet must be public) ────────────────────

def read_from_public_csv() -> list[dict]:
    """Reads the public Google Sheet and returns a list of prospect dicts."""
    csv_url = _csv_url()  # RuntimeError here if the field is missing
    try:
        resp = requests.get(csv_url, allow_redirects=True, timeout=20,
                            headers={"User-Agent": "ArrivataSalesApp/1.0"})
        resp.raise_for_status()
        content = resp.content.decode('utf-8-sig')  # handle BOM
    except Exception as e:
        raise RuntimeError(f"No se pudo leer el spreadsheet: {e}")

    reader = csv.DictReader(io.StringIO(content))
    prospects = []
    for row in reader:
        name = row.get('Nombre del Local', '').strip()
        if not name or name == '#':
            continue
        neighborhood = row.get('Localidad / Barrio', '').strip()
        # Solo campos que el CSV realmente aporta (o deriva de sus columnas).
        # NO se incluyen email/instagram/website/contact_status/lat/lng/score:
        # en un update parcial, incluirlos vacíos pisaría datos cargados a mano.
        prospects.append({
            'name': name,
            'neighborhood': neighborhood,
            'zone': _detect_zone(neighborhood),
            'address': row.get('Dirección', '').strip(),
            'type': row.get('Tipo de Local', '').strip(),
            'phone': row.get('Teléfono', '').strip(),
            'products_interest': _suggest_products(row.get('Tipo de Local', ''), row.get('Nota Comercial', '')),
            'notes': row.get('Nota Comercial', '').strip().strip('"'),
            'is_premium': _is_premium(row.get('Nota Comercial', ''), row.get('Tipo de Local', '')),
        })
    return prospects


def _detect_zone(neighborhood: str) -> str:
    n = neighborhood.lower()
    gba_norte = ['san isidro', 'martínez', 'martinez', 'la lucila', 'acassuso',
                 'vicente lopez', 'olivos', 'florida', 'tigre', 'delta', 'nordelta']
    gba_oeste = ['morón', 'moron', 'ramos mejía', 'ramos mejia', 'ituzaingó', 'haedo']
    gba_sur = ['lomas de zamora', 'quilmes', 'lanús', 'lanus', 'avellaneda']
    if any(x in n for x in gba_norte):
        return 'GBA Norte'
    if any(x in n for x in gba_oeste):
        return 'GBA Oeste'
    if any(x in n for x in gba_sur):
        return 'GBA Sur'
    return 'CABA'


def _is_premium(nota: str, tipo: str) -> bool:
    keywords = ['premium', 'gourmet', 'alta gama', 'michelin', 'donato', 'bib gourmand',
                'fine dining', 'boutique', 'artesanal', 'exclusiv']
    text = (nota + ' ' + tipo).lower()
    return any(k in text for k in keywords)


def _suggest_products(tipo: str, nota: str) -> str:
    text = (tipo + ' ' + nota).lower()
    products = []
    if any(x in text for x in ['burrata', 'strachiatella', 'bufala', 'trattoria', 'osteria',
                                'italiano', 'italiana', 'premium', 'gourmet']):
        products += ['Burrata', 'Strachiatella Fior Di Latte']
    if any(x in text for x in ['pizza', 'pizzería', 'muzzarella', 'mozzarella', 'fior di latte']):
        products += ['Bocha de Muzarella', 'Bocconcino Fior Di Latte']
    if any(x in text for x in ['ahumad', 'provola', 'bodegón']):
        products += ['Provola Ahumada']
    if any(x in text for x in ['ricotta', 'sfoglia', 'pasta', 'pastas']):
        products += ['Ricotta', 'Sfoglia']
    if any(x in text for x in ['deli', 'almacén', 'gourmet', 'mercado']):
        products += ['Bocconcino Fior Di Latte', 'Ricotta', 'Burrata']
    seen = set()
    return '|'.join(p for p in products if not (p in seen or seen.add(p)))


# ─── WRITE (requires service account credentials) ───────────────────────────

def _get_client(credentials_path: str):
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def _prospect_to_row(idx: int, p: dict) -> list:
    from scoring import score_label
    return [
        idx,
        p.get('name', ''),
        p.get('neighborhood', ''),
        p.get('address', ''),
        p.get('type', ''),
        p.get('phone', ''),
        p.get('notes', ''),
        p.get('score', 5),
        score_label(p.get('score', 5)),
        p.get('contact_status', 'Pendiente'),
        p.get('email', ''),
        p.get('instagram', ''),
        p.get('website', ''),
    ]


def sync_to_sheets(prospects: list[dict], credentials_path: str) -> int:
    """Full sync: writes all prospects to the 'Prospectos Arrivata' tab
    (a separate tab, so the source data tab is never overwritten)."""
    import gspread
    spreadsheet_key, _gid = _write_target()
    gc = _get_client(credentials_path)
    spreadsheet = gc.open_by_key(spreadsheet_key)

    try:
        ws = spreadsheet.worksheet('Prospectos Arrivata')
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet('Prospectos Arrivata', rows=2000, cols=len(SHEET_HEADERS))

    # Header row
    ws.update(values=[SHEET_HEADERS], range_name='A1')
    ws.format('A1:M1', {
        'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        'backgroundColor': {'red': 0.698, 'green': 0.122, 'blue': 0.094},
        'horizontalAlignment': 'CENTER',
    })

    if prospects:
        rows = [_prospect_to_row(i + 1, p) for i, p in enumerate(prospects)]
        ws.update(values=rows, range_name='A2')

    return len(prospects)


def append_prospect_to_sheets(prospect: dict, credentials_path: str) -> bool:
    """Appends a single prospect as a new row."""
    spreadsheet_key, _gid = _write_target()  # RuntimeError if config incomplete
    try:
        import gspread
        gc = _get_client(credentials_path)
        spreadsheet = gc.open_by_key(spreadsheet_key)

        try:
            ws = spreadsheet.worksheet('Prospectos Arrivata')
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet('Prospectos Arrivata', rows=2000, cols=len(SHEET_HEADERS))
            ws.update(values=[SHEET_HEADERS], range_name='A1')

        # Get current last row to assign # correctly
        all_values = ws.get_all_values()
        next_idx = max(1, len(all_values))
        row = _prospect_to_row(next_idx, prospect)
        ws.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception:
        return False


def test_connection(credentials_path: str) -> tuple[bool, str]:
    try:
        spreadsheet_key, gid = _write_target()
        gc = _get_client(credentials_path)
        spreadsheet = gc.open_by_key(spreadsheet_key)
        ws = spreadsheet.get_worksheet_by_id(int(gid))
        return True, f'Conexión exitosa — pestaña "{ws.title}" ({ws.row_count} filas)'
    except RuntimeError as e:
        return False, str(e)
    except FileNotFoundError:
        return False, "Archivo de credenciales no encontrado"
    except ValueError:
        return False, "El campo 'sheets_gid' de config.json no es un número válido"
    except Exception as e:
        return False, str(e)
