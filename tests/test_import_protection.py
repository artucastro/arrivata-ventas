"""
Prueba de la protección de campos en "Importar desde Sheets".

Verifica que un import sobre un prospecto EXISTENTE:
  - actualiza los campos que trae el CSV (nombre, dirección, barrio, tipo, teléfono...)
  - NO pisa los campos que se manejan a mano: lat, lng, geocode_status,
    contact_status, score, is_premium, products_interest
Y que un prospecto NUEVO se da de alta con todos los campos que traiga el CSV
(incluida la heurística de is_premium / products_interest).

Uso:  python tests/test_import_protection.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db

_fails = []


def check(label, got, expected):
    ok = got == expected
    print(f"  {'OK ' if ok else 'FALLA'}  {label}: {got!r}" + ("" if ok else f"  (esperaba {expected!r})"))
    if not ok:
        _fails.append(label)


def sheet_row(**over):
    """Fila con la forma exacta que hoy devuelve read_from_public_csv()."""
    row = {
        'name': 'La Alacena Trattoria',
        'neighborhood': 'Palermo',
        'zone': 'CABA',
        'address': 'Gascón 1401',
        'type': 'Trattoria',
        'phone': '+54 11 4867-2389',
        'products_interest': 'Burrata|Strachiatella Fior Di Latte',
        'notes': 'Bib Gourmand.',
        'is_premium': True,
    }
    row.update(over)
    return row


def main():
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    db.init_db()

    # ── 1) Prospecto existente con datos cargados a mano ──────────────────────
    # is_premium y products_interest se setean a valores OPUESTOS a lo que la
    # heurística del sheet_row produciría (is_premium=True / 'Burrata|Strachiatella...').
    manual_id = db.create_prospect({
        'name': 'La Alacena Trattoria',
        'neighborhood': 'Palermo',
        'address': 'Dirección vieja 1',
        'type': 'Restaurante',
        'phone': '000',
        'email': 'contacto@laalacena.com',      # cargado a mano
        'instagram': 'laalacena',                # cargado a mano
        'contact_status': 'Cliente',             # pipeline avanzado
        'score': 9,                              # ajustado a mano
        'lat': -34.5939654,                      # geocodificado
        'lng': -58.4227598,
        'geocode_status': 'ok',
        'is_premium': 0,                         # ajuste manual: NO es premium
        'products_interest': 'Ricotta|Provola Ahumada',  # selección manual
    })

    print("\n[1] Import sobre prospecto EXISTENTE (name+neighborhood coincide)")
    row = sheet_row(address='Gascón 1401', phone='+54 11 4867-2389', type='Trattoria')
    pid, created = db.upsert_prospect(row, protect_on_update=db.IMPORT_PROTECTED_FIELDS)
    p = db.get_prospect(manual_id)

    check("created == False", created, False)
    check("mismo id", pid, manual_id)
    # actualizados desde el CSV
    check("address actualizada", p['address'], 'Gascón 1401')
    check("phone actualizado", p['phone'], '+54 11 4867-2389')
    check("type actualizado", p['type'], 'Trattoria')
    # PROTEGIDOS: intactos
    check("lat intacta", p['lat'], -34.5939654)
    check("lng intacta", p['lng'], -58.4227598)
    check("geocode_status intacto", p['geocode_status'], 'ok')
    check("contact_status intacto", p['contact_status'], 'Cliente')
    check("score intacto", p['score'], 9)
    check("is_premium intacto (ajuste manual)", p['is_premium'], 0)
    check("products_interest intacto (selección manual)", p['products_interest'], 'Ricotta|Provola Ahumada')
    # ausentes en el CSV: no se tocan
    check("email intacto (ausente en CSV)", p['email'], 'contacto@laalacena.com')
    check("instagram intacto (ausente en CSV)", p['instagram'], 'laalacena')

    # ── 2) Prospecto NUEVO: se cargan todos los campos del CSV ────────────────
    print("\n[2] Import de prospecto NUEVO (no existe en la DB)")
    row2 = sheet_row(name='Osteria Nova', neighborhood='Belgrano', zone='CABA',
                     address='Cabildo 2000', type='Ostería / Trattoria', phone='555')
    row2['score'] = 7          # como hace app.py antes del upsert
    row2['score_auto'] = 7
    nid, created2 = db.upsert_prospect(row2, protect_on_update=db.IMPORT_PROTECTED_FIELDS)
    n = db.get_prospect(nid)

    check("created == True", created2, True)
    check("name", n['name'], 'Osteria Nova')
    check("neighborhood", n['neighborhood'], 'Belgrano')
    check("address", n['address'], 'Cabildo 2000')
    check("type", n['type'], 'Ostería / Trattoria')
    check("phone", n['phone'], '555')
    check("score del alta se respeta", n['score'], 7)
    check("is_premium por heurística (alta)", n['is_premium'], 1)
    check("products_interest por heurística (alta)", n['products_interest'], 'Burrata|Strachiatella Fior Di Latte')
    check("lat None (sin geocodificar aún)", n['lat'], None)
    check("contact_status default", n['contact_status'], 'Pendiente')

    # ── 3) Re-import que NO trae cambios reales deja los protegidos igual ─────
    print("\n[3] Segundo import idéntico: protegidos siguen intactos")
    db.upsert_prospect(sheet_row(), protect_on_update=db.IMPORT_PROTECTED_FIELDS)
    p = db.get_prospect(manual_id)
    check("lat sigue intacta", p['lat'], -34.5939654)
    check("contact_status sigue 'Cliente'", p['contact_status'], 'Cliente')
    check("score sigue 9", p['score'], 9)
    check("is_premium sigue 0", p['is_premium'], 0)
    check("products_interest sigue manual", p['products_interest'], 'Ricotta|Provola Ahumada')

    os.unlink(tmp.name)

    print("\n" + ("=" * 50))
    if _fails:
        print(f"RESULTADO: {len(_fails)} CHECK(S) FALLARON -> {_fails}")
        sys.exit(1)
    print("RESULTADO: TODO OK")


if __name__ == '__main__':
    main()
