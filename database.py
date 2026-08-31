import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get('ARRIVATA_DB_PATH') or os.path.join(os.path.dirname(__file__), 'arrivata.db')

# Campos que se cargan / ajustan a mano en la app: una importación (Sheets o IA)
# NUNCA los pisa cuando el prospecto ya existe, aunque el origen traiga otro valor.
# is_premium y products_interest arrancan por heurística en el ALTA, pero desde ahí
# son campos del usuario: la importación no los vuelve a tocar.
IMPORT_PROTECTED_FIELDS = frozenset({
    'lat', 'lng', 'geocode_status', 'contact_status', 'score',
    'is_premium', 'products_interest',
})

# Columnas que un UPDATE parcial puede tocar (cualquier otra clave del dict se ignora).
_UPDATABLE_COLUMNS = (
    'name', 'type', 'neighborhood', 'zone', 'address', 'phone', 'email',
    'instagram', 'website', 'products_interest', 'score', 'score_auto',
    'is_premium', 'contact_status', 'notes', 'lat', 'lng', 'geocode_status',
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT DEFAULT '',
            neighborhood TEXT DEFAULT '',
            zone TEXT DEFAULT 'CABA',
            address TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            instagram TEXT DEFAULT '',
            website TEXT DEFAULT '',
            products_interest TEXT DEFAULT '',
            score INTEGER DEFAULT 5,
            score_auto INTEGER DEFAULT 5,
            is_premium INTEGER DEFAULT 0,
            contact_status TEXT DEFAULT 'Pendiente',
            notes TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            geocode_status TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migración para bases creadas antes de la columna geocode_status.
    # Valores: '' (sin intentar) | 'ok' | 'pendiente' (falló, reintentar) | 'sin_resultado'
    cols = [row[1] for row in conn.execute("PRAGMA table_info(prospects)")]
    if 'geocode_status' not in cols:
        conn.execute("ALTER TABLE prospects ADD COLUMN geocode_status TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def get_all_prospects(filters=None):
    conn = get_db()
    query = 'SELECT * FROM prospects'
    params = []

    if filters:
        conditions = []
        if filters.get('province'):
            if filters['province'] == 'CABA':
                conditions.append("zone = 'CABA'")
            elif filters['province'] == 'GBA':
                conditions.append("zone LIKE 'GBA%'")
        if filters.get('neighborhood'):
            conditions.append('neighborhood = ?')
            params.append(filters['neighborhood'])
        if filters.get('type'):
            conditions.append('type LIKE ?')
            params.append(f"%{filters['type']}%")
        if filters.get('contact_status'):
            conditions.append('contact_status = ?')
            params.append(filters['contact_status'])
        if filters.get('min_score'):
            conditions.append('score >= ?')
            params.append(int(filters['min_score']))
        if filters.get('search'):
            conditions.append('(name LIKE ? OR address LIKE ? OR notes LIKE ?)')
            term = f"%{filters['search']}%"
            params.extend([term, term, term])
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

    query += ' ORDER BY score DESC, name ASC'
    cursor = conn.execute(query, params)
    prospects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return prospects


def get_prospect(prospect_id):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM prospects WHERE id = ?', (prospect_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_prospect(data):
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute('''
        INSERT INTO prospects (name, type, neighborhood, zone, address, phone, email,
                              instagram, website, products_interest, score, score_auto,
                              is_premium, contact_status, notes, lat, lng, geocode_status,
                              created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['name'], data.get('type', ''), data.get('neighborhood', ''),
        data.get('zone', 'CABA'), data.get('address', ''), data.get('phone', ''),
        data.get('email', ''), data.get('instagram', ''), data.get('website', ''),
        data.get('products_interest', ''), data.get('score', 5), data.get('score_auto', 5),
        1 if data.get('is_premium') else 0, data.get('contact_status', 'Pendiente'),
        data.get('notes', ''), data.get('lat'), data.get('lng'),
        data.get('geocode_status', ''), now, now
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def update_prospect(prospect_id, data):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute('''
        UPDATE prospects SET name=?, type=?, neighborhood=?, zone=?, address=?, phone=?,
        email=?, instagram=?, website=?, products_interest=?, score=?, score_auto=?,
        is_premium=?, contact_status=?, notes=?, lat=?, lng=?, updated_at=?
        WHERE id=?
    ''', (
        data['name'], data.get('type', ''), data.get('neighborhood', ''),
        data.get('zone', 'CABA'), data.get('address', ''), data.get('phone', ''),
        data.get('email', ''), data.get('instagram', ''), data.get('website', ''),
        data.get('products_interest', ''), data.get('score', 5), data.get('score_auto', 5),
        1 if data.get('is_premium') else 0, data.get('contact_status', 'Pendiente'),
        data.get('notes', ''), data.get('lat'), data.get('lng'), now, prospect_id
    ))
    conn.commit()
    conn.close()


def update_prospect_partial(prospect_id, data: dict, skip=frozenset()):
    """UPDATE parcial: escribe SOLO las claves presentes en `data` que sean
    columnas válidas y no estén en `skip`. Las columnas ausentes quedan intactas
    (no se resetean a NULL ni a su default)."""
    cols = [c for c in _UPDATABLE_COLUMNS if c in data and c not in skip]
    if not cols:
        return
    values = [(1 if data[c] else 0) if c == 'is_premium' else data[c] for c in cols]
    set_clause = ', '.join(f'{c}=?' for c in cols) + ', updated_at=?'
    values += [datetime.now().isoformat(), prospect_id]
    conn = get_db()
    conn.execute(f'UPDATE prospects SET {set_clause} WHERE id=?', values)
    conn.commit()
    conn.close()


def get_prospect_by_key(name, neighborhood=''):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM prospects WHERE name = ? AND neighborhood = ?',
        (name, neighborhood)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_prospect_location(prospect_id, lat, lng, geocode_status):
    """Actualiza solo coordenadas + estado de geocoding (usado por el batch)."""
    conn = get_db()
    conn.execute(
        'UPDATE prospects SET lat=?, lng=?, geocode_status=?, updated_at=? WHERE id=?',
        (lat, lng, geocode_status, datetime.now().isoformat(), prospect_id)
    )
    conn.commit()
    conn.close()


def delete_prospect(prospect_id):
    conn = get_db()
    conn.execute('DELETE FROM prospects WHERE id = ?', (prospect_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM prospects').fetchone()[0]
    high_priority = conn.execute('SELECT COUNT(*) FROM prospects WHERE score >= 7').fetchone()[0]
    contacted = conn.execute(
        "SELECT COUNT(*) FROM prospects WHERE contact_status NOT IN ('Pendiente')"
    ).fetchone()[0]
    clients = conn.execute(
        "SELECT COUNT(*) FROM prospects WHERE contact_status = 'Cliente'"
    ).fetchone()[0]
    conn.close()
    return {'total': total, 'high_priority': high_priority, 'contacted': contacted, 'clients': clients}


def get_distinct_values(column):
    conn = get_db()
    if column not in {'neighborhood', 'type', 'zone', 'contact_status'}:
        raise ValueError(f'columna no permitida: {column}')
    cursor = conn.execute(
        f"SELECT DISTINCT {column} FROM prospects WHERE {column} != '' ORDER BY {column}"
    )
    values = [row[0] for row in cursor.fetchall()]
    conn.close()
    return values


def upsert_prospect(data: dict, protect_on_update=None) -> tuple[int, bool]:
    """Insert or update. Returns (id, created). Key: name + neighborhood.

    - Alta (no existe): se cargan todos los campos del dict, sin restricción.
    - Update (ya existe):
        protect_on_update is None  -> UPDATE full (compat, reescribe todo el registro)
        protect_on_update=set(...) -> UPDATE parcial: solo las claves presentes en
                                      `data`, saltando las de ese set.
    """
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM prospects WHERE name = ? AND neighborhood = ?',
        (data['name'], data.get('neighborhood', ''))
    ).fetchone()
    conn.close()

    if existing:
        if protect_on_update is None:
            update_prospect(existing['id'], data)
        else:
            update_prospect_partial(existing['id'], data, skip=protect_on_update)
        return existing['id'], False
    else:
        new_id = create_prospect(data)
        return new_id, True
