"""
Genera docs/data.json a partir de arrivata.db para el dashboard estático
(GitHub Pages). Es una FOTO de los datos: no se actualiza sola.

    python export_static.py           # datos reales
    python export_static.py --anon    # nombres/teléfonos/notas ficticios (para demo pública)

Después:  git add docs/data.json && git commit -m "Actualiza datos" && git push
"""
import json
import os
import sqlite3
import sys
from datetime import date

import scoring as sc

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'arrivata.db')
OUT = os.path.join(HERE, 'docs', 'data.json')

ANON = '--anon' in sys.argv

_FAKE_NAMES = [
    "Trattoria del Sol", "La Piazza", "Osteria Nonna", "Il Forno", "Cantina Verde",
    "Bottega Rossa", "La Cucina", "Da Vinci Ristorante", "Pizzería Vesuvio",
    "El Molino", "La Tavola", "Focacceria Centro", "Antica Bottega", "Sapori",
    "La Dispensa", "Forno a Legna", "Mercato", "La Vecchia", "Bella Napoli",
    "Terra Nostra",
]


def _anon_row(i, r):
    r = dict(r)
    r['name'] = f"{_FAKE_NAMES[i % len(_FAKE_NAMES)]} {i + 1}"
    r['phone'] = ""
    r['instagram'] = ""
    r['website'] = ""
    r['address'] = r['address'].split()[0] + " 000" if r['address'] else ""
    r['notes'] = "Prospecto de ejemplo (datos anonimizados para la demo pública)."
    return r


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(x) for x in conn.execute('SELECT * FROM prospects ORDER BY score DESC, name ASC')]
    conn.close()

    out = []
    for i, r in enumerate(rows):
        if ANON:
            r = _anon_row(i, r)
        score = r['score']
        out.append({
            'id': r['id'],
            'name': r['name'],
            'type': r['type'],
            'neighborhood': r['neighborhood'],
            'zone': r['zone'],
            'address': r['address'],
            'phone': r['phone'],
            'instagram': r['instagram'],
            'website': r['website'],
            'products': [p for p in (r['products_interest'] or '').split('|') if p],
            'score': score,
            'score_color': sc.score_color(score),
            'score_label': sc.score_label(score),
            'contact_status': r['contact_status'],
            'is_premium': bool(r['is_premium']),
            'notes': r['notes'],
            'lat': r['lat'],
            'lng': r['lng'],
        })

    payload = {
        'generated': date.today().isoformat(),
        'anonymized': ANON,
        'count': len(out),
        'prospects': out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"OK -> {OUT}  ({len(out)} prospectos, {'ANONIMIZADO' if ANON else 'datos reales'})")


if __name__ == '__main__':
    main()
