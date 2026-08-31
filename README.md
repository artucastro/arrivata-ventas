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

Python 3.11 · Flask · SQLite · Bootstrap 5 · Leaflet · SDK `anthropic`

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env            # completar ANTHROPIC_API_KEY y FLASK_SECRET_KEY
cp config.example.json config.json   # ajustar si se usa Google Sheets
python app.py                   # http://localhost:5001
```

En Windows también sirve `start.bat`.

### Google Sheets (opcional)

- **Lectura** ("Importar desde Sheets"): el sheet debe estar *publicado en la web*
  como CSV; pegar esa URL en `config.json` → `sheets_csv_url`.
- **Escritura** ("Sincronizar" / "Probar conexión"): requiere una *service account*
  de Google (Sheets API + Drive API) con el JSON en `credentials/google_credentials.json`
  y el spreadsheet compartido como Editor. Completar `sheets_spreadsheet_key` y
  `sheets_gid` en `config.json`.

## Tests

```bash
python tests/test_import_protection.py
```

## Archivos que NO están en el repo

`.env`, `config.json`, `credentials/`, `arrivata.db` — contienen secretos o datos
locales. Ver `.env.example` y `config.example.json`.
