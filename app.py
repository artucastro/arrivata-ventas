import csv
import hmac
import io
import os
import secrets
import time

from dotenv import load_dotenv, dotenv_values
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   Response, session, url_for)

import database as db
import scoring as sc
from config_manager import load_config, save_config
from geocoding import geocode

# Carga el .env de la carpeta del proyecto sin importar el working directory
# (necesario cuando corre bajo un servidor WSGI, p. ej. PythonAnywhere).
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "arrivata-secret-2024")

db.init_db()


# ─── Login (HTTP Basic) ─────────────────────────────────────────────────────
# Si APP_PASSWORD está seteada (deploy), se pide usuario+contraseña en todas las
# rutas. Si no está (uso local), no hay login.

APP_USER = os.getenv("APP_USER", "arrivata")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


@app.before_request
def _require_login():
    if not APP_PASSWORD:
        return
    auth = request.authorization
    if (auth and hmac.compare_digest(auth.username or "", APP_USER)
            and hmac.compare_digest(auth.password or "", APP_PASSWORD)):
        return
    return Response('Acceso restringido.', 401,
                    {'WWW-Authenticate': 'Basic realm="Arrivata Sales"'})


# ─── Server-side search-results store ───────────────────────────────────────
# The AI search can return 15-30+ rows (each with notes). That easily exceeds
# Flask's ~4 KB client-side session cookie, which would silently drop the data
# and make the results/import screen come up empty. Keep the payload server-side
# and store only a short token in the cookie.

_SEARCH_CACHE: dict[str, list] = {}
_SEARCH_CACHE_MAX = 20


def _store_search_results(results: list) -> None:
    token = session.get('search_token')
    if not token:
        token = secrets.token_hex(8)
        session['search_token'] = token
    if len(_SEARCH_CACHE) >= _SEARCH_CACHE_MAX and token not in _SEARCH_CACHE:
        _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
    _SEARCH_CACHE[token] = results


def _get_search_results() -> list:
    return _SEARCH_CACHE.get(session.get('search_token'), [])


def _clear_search_results() -> None:
    _SEARCH_CACHE.pop(session.pop('search_token', None), None)


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_anthropic_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        vals = dotenv_values(env_path)
        key = vals.get("ANTHROPIC_API_KEY", "").strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            return key
    config = load_config()
    key = config.get("anthropic_api_key", "").strip()
    # Guard against a mistyped value (e.g. a URL pasted into the API-key field).
    return key if key.startswith("sk-") else ""


def _prospect_from_form(form) -> dict:
    is_premium = 'is_premium' in form
    tipo = form.get('type', '')
    barrio = form.get('neighborhood', '')
    # calculate_auto_score sigue siendo el default del slider de score MANUAL
    # cuando el usuario no lo tocó (no es el score_auto que se guarda).
    slider_default = sc.calculate_auto_score(tipo, barrio, is_premium)
    try:
        score = int(form.get('score') or slider_default)
    except (TypeError, ValueError):
        score = slider_default
    score = min(10, max(1, score))
    products = form.getlist('products_interest')

    supplier = form.get('current_supplier', 'desconocido')
    if supplier not in sc.SUPPLIER_POINTS:
        supplier = 'desconocido'
    volume = form.get('potential_volume', 'desconocido')
    if volume not in sc.VOLUME_POINTS:
        volume = 'desconocido'
    display_score = form.get('display_score', 'auto')
    if display_score not in ('auto', 'manual'):
        display_score = 'auto'

    data = {
        'name': form.get('name', '').strip(),
        'type': tipo,
        'neighborhood': barrio,
        'zone': form.get('zone', 'CABA'),
        'address': form.get('address', ''),
        'phone': form.get('phone', ''),
        'email': form.get('email', ''),
        'instagram': form.get('instagram', ''),
        'website': form.get('website', ''),
        'products_interest': '|'.join(products),
        'score': score,
        'is_premium': is_premium,
        'contact_status': form.get('contact_status', 'Pendiente'),
        'notes': form.get('notes', ''),
        'lat': form.get('lat') or None,
        'lng': form.get('lng') or None,
        'current_supplier': supplier,
        'potential_volume': volume,
        'display_score': display_score,
    }
    # score_auto se calcula con la vara de prioridad (5 dimensiones). La capa db
    # lo vuelve a calcular igual al guardar; lo dejamos acá para que `data` quede
    # consistente (p. ej. si se vuelca a Sheets).
    data['score_auto'] = sc.calculate_priority_score(data)
    return data


def _try_sync_sheets(prospect: dict):
    """Best-effort single-row append to Google Sheets (silent if no credentials).
    A missing config field surfaces as a flash warning but never blocks the save."""
    config = load_config()
    if config.get('sheets_enabled') and config.get('sheets_credentials_path'):
        from sheets_integration import append_prospect_to_sheets
        try:
            append_prospect_to_sheets(prospect, config['sheets_credentials_path'])
        except RuntimeError as e:
            flash(f'No se volcó a Google Sheets: {e}', 'danger')


# ─── Dashboard ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    filters = {
        'province': request.args.get('province', ''),
        'neighborhood': request.args.get('neighborhood', ''),
        'type': request.args.get('type', ''),
        'contact_status': request.args.get('contact_status', ''),
        'tier': request.args.get('tier', ''),   # '' | 'A' | 'AB' — sobre score_auto
        'search': request.args.get('search', ''),
    }
    prospects = db.get_all_prospects({k: v for k, v in filters.items() if v})
    stats = db.get_stats()
    neighborhoods = db.get_distinct_values('neighborhood')

    for p in prospects:
        # Prioridad (Tier + orden) = SIEMPRE score_auto, pase lo que pase con
        # display_score. score_color/score_label (sobre el score manual)
        # quedan solo para el detalle chico "ajuste manual".
        if p.get('score_auto') is not None:
            p['tier'] = sc.priority_tier(p['score_auto'])
            p['tier_badge_class'] = sc.tier_badge_class(p['score_auto'])
        p['score_color'] = sc.score_color(p['score'])
        p['score_label'] = sc.score_label(p['score'])
        p['products_list'] = [x for x in p.get('products_interest', '').split('|') if x]

        # Columna "Score" del dashboard: display_score='manual' -> el ajuste a
        # mano; si no (default 'auto', o si por algún motivo no hay score_auto
        # todavía) -> score_auto. Esto es solo qué número se MUESTRA; no toca
        # el Tier ni el orden de arriba.
        if p.get('display_score') == 'manual' or p.get('score_auto') is None:
            p['dashboard_score'] = p['score']
            p['dashboard_score_is_manual'] = True
        else:
            p['dashboard_score'] = p['score_auto']
            p['dashboard_score_is_manual'] = False

    return render_template('index.html',
                           prospects=prospects, stats=stats,
                           filters=filters, neighborhoods=neighborhoods,
                           contact_statuses=sc.CONTACT_STATUSES)


# ─── Map ────────────────────────────────────────────────────────────────────

@app.route('/mapa')
def map_view():
    prospects = db.get_all_prospects()
    for p in prospects:
        p['score_color'] = sc.score_color(p['score'])
        p['score_label'] = sc.score_label(p['score'])
    return render_template('map.html', prospects=prospects)


@app.route('/api/prospects')
def api_prospects():
    prospects = db.get_all_prospects()
    result = []
    for p in prospects:
        if p.get('lat') and p.get('lng'):
            result.append({
                'id': p['id'],
                'name': p['name'],
                'type': p['type'],
                'neighborhood': p['neighborhood'],
                'address': p['address'],
                'score': p['score'],
                'score_color': sc.score_color(p['score']),
                'score_label': sc.score_label(p['score']),
                'contact_status': p['contact_status'],
                'lat': p['lat'],
                'lng': p['lng'],
            })
    return jsonify(result)


# ─── Add / Edit Prospect ────────────────────────────────────────────────────

@app.route('/prospecto/nuevo', methods=['GET', 'POST'])
def add_prospect():
    if request.method == 'POST':
        data = _prospect_from_form(request.form)
        if not data['name']:
            flash('El nombre del prospecto es obligatorio.', 'danger')
            return redirect(url_for('add_prospect'))
        if not data.get('lat') and data.get('address'):
            lat, lng = geocode(data['address'], data['neighborhood'])
            data['lat'], data['lng'] = lat, lng
        new_id = db.create_prospect(data)
        data['id'] = new_id
        _try_sync_sheets(data)
        flash('Prospecto creado.', 'success')
        return redirect(url_for('view_prospect', prospect_id=new_id))

    return render_template('prospect_form.html',
                           prospect=None, action='add',
                           products=sc.PRODUCTS, types=sc.BUSINESS_TYPES,
                           neighborhoods=sc.NEIGHBORHOODS_CABA, zones=sc.ZONES,
                           contact_statuses=sc.CONTACT_STATUSES,
                           current_suppliers=sc.CURRENT_SUPPLIERS,
                           potential_volumes=sc.POTENTIAL_VOLUMES,
                           display_score_options=sc.DISPLAY_SCORE_OPTIONS)


@app.route('/prospecto/<int:prospect_id>')
def view_prospect(prospect_id):
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        flash('Prospecto no encontrado.', 'danger')
        return redirect(url_for('index'))
    prospect['score_color'] = sc.score_color(prospect['score'])
    prospect['score_label'] = sc.score_label(prospect['score'])
    prospect['products_list'] = [x for x in prospect.get('products_interest', '').split('|') if x]
    if prospect.get('score_auto') is not None:
        prospect['tier'] = sc.priority_tier(prospect['score_auto'])
    return render_template(
        'prospect_detail.html', prospect=prospect,
        supplier_label=dict(sc.CURRENT_SUPPLIERS).get(prospect.get('current_supplier'), '—'),
        volume_label=dict(sc.POTENTIAL_VOLUMES).get(prospect.get('potential_volume'), '—'),
    )


@app.route('/prospecto/<int:prospect_id>/editar', methods=['GET', 'POST'])
def edit_prospect(prospect_id):
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        flash('Prospecto no encontrado.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = _prospect_from_form(request.form)
        if not data['name']:
            flash('El nombre del prospecto es obligatorio.', 'danger')
            return redirect(url_for('edit_prospect', prospect_id=prospect_id))
        if not data.get('lat') and data.get('address'):
            lat, lng = geocode(data['address'], data['neighborhood'])
            data['lat'], data['lng'] = lat, lng
        db.update_prospect(prospect_id, data)
        flash('Prospecto actualizado.', 'success')
        return redirect(url_for('view_prospect', prospect_id=prospect_id))

    prospect['products_list'] = [x for x in prospect.get('products_interest', '').split('|') if x]
    return render_template('prospect_form.html',
                           prospect=prospect, action='edit',
                           products=sc.PRODUCTS, types=sc.BUSINESS_TYPES,
                           neighborhoods=sc.NEIGHBORHOODS_CABA, zones=sc.ZONES,
                           contact_statuses=sc.CONTACT_STATUSES,
                           current_suppliers=sc.CURRENT_SUPPLIERS,
                           potential_volumes=sc.POTENTIAL_VOLUMES,
                           display_score_options=sc.DISPLAY_SCORE_OPTIONS)


@app.route('/prospecto/<int:prospect_id>/eliminar', methods=['POST'])
def delete_prospect(prospect_id):
    db.delete_prospect(prospect_id)
    flash('Prospecto eliminado.', 'info')
    return redirect(url_for('index'))


# ─── Auto-score API ─────────────────────────────────────────────────────────

@app.route('/api/score')
def api_score():
    tipo = request.args.get('type', '')
    barrio = request.args.get('neighborhood', '')
    is_premium = request.args.get('is_premium', '0') == '1'
    score = sc.calculate_auto_score(tipo, barrio, is_premium)
    return jsonify({'score': score, 'color': sc.score_color(score), 'label': sc.score_label(score)})


# ─── AI Search ──────────────────────────────────────────────────────────────

@app.route('/busqueda')
def search_view():
    api_key_set = bool(get_anthropic_api_key())
    pending = _get_search_results() or None
    return render_template('search.html',
                           api_key_set=api_key_set,
                           results=pending,
                           neighborhoods_caba=sc.NEIGHBORHOODS_CABA,
                           amba_norte=sc.NEIGHBORHOODS_AMBA_NORTE,
                           amba_oeste=sc.NEIGHBORHOODS_AMBA_OESTE,
                           amba_sur=sc.NEIGHBORHOODS_AMBA_SUR,
                           amba_toda=sc.AMBA_TODA,
                           caba_todos=sc.CABA_TODOS,
                           business_types=sc.BUSINESS_TYPES)


@app.route('/busqueda/ejecutar', methods=['POST'])
def run_search():
    ui_key = request.form.get('api_key_ui', '').strip()
    if ui_key and not ui_key.startswith('sk-'):
        flash('La API key de Anthropic debe empezar con "sk-". Revisá el valor pegado.', 'danger')
        return redirect(url_for('search_view'))
    if ui_key:
        config = load_config()
        config['anthropic_api_key'] = ui_key
        save_config(config)
        os.environ["ANTHROPIC_API_KEY"] = ui_key

    from ai_search import search_prospects
    zone_type = request.form.get('zone_type', 'caba')
    neighborhood = request.form.get('neighborhood', '')
    business_type = request.form.get('business_type', '')
    extra = request.form.get('extra_keywords', '')

    is_amba_all  = zone_type == 'amba' and neighborhood == sc.AMBA_TODA
    is_caba_all  = zone_type == 'caba' and neighborhood == sc.CABA_TODOS

    try:
        api_key = get_anthropic_api_key()
        results = search_prospects(neighborhood, business_type, extra, api_key=api_key, zone_type=zone_type)
        for r in results:
            if is_amba_all:
                nh = r.get('municipio') or neighborhood
                r['neighborhood'] = nh
                r['zone'] = sc._detect_amba_zone(nh)
            elif zone_type == 'amba':
                r['neighborhood'] = neighborhood
                r['zone'] = sc._detect_amba_zone(neighborhood)
            elif is_caba_all:
                r['neighborhood'] = r.get('municipio') or neighborhood
                r['zone'] = 'CABA'
            else:
                r['neighborhood'] = neighborhood
                r['zone'] = 'CABA'
            r['score_auto'] = sc.calculate_auto_score(r.get('type', ''), r['neighborhood'], r.get('is_premium', False))
            r['score'] = r['score_auto']
            r['score_color'] = sc.score_color(r['score'])
            r['score_label'] = sc.score_label(r['score'])
        _store_search_results(results)
        if is_amba_all:
            lugar = "toda la provincia (AMBA)"
        elif is_caba_all:
            lugar = "todos los barrios de CABA"
        else:
            lugar = neighborhood
        flash(f'Se encontraron {len(results)} prospectos en {lugar}.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception as e:
        flash(f'Error en la búsqueda: {str(e)}', 'danger')

    return redirect(url_for('search_view'))


@app.route('/busqueda/importar', methods=['POST'])
def import_search_results():
    results = _get_search_results()
    selected_indexes = request.form.getlist('selected')
    imported = 0
    config = load_config()
    sheets_ok = config.get('sheets_enabled') and config.get('sheets_credentials_path')

    for idx in selected_indexes:
        try:
            r = results[int(idx)]
            lat, lng = None, None
            geo_status = ''
            if r.get('address'):
                from geocoding import geocode_status, REQUEST_DELAY
                lat, lng, st = geocode_status(r['address'], r.get('neighborhood', ''))
                geo_status = 'ok' if (lat and lng) else ('pendiente' if st == 'error' else 'sin_resultado')
                time.sleep(REQUEST_DELAY)
            data = {
                'name': r['name'],
                'type': r.get('type', ''),
                'neighborhood': r.get('neighborhood', ''),
                'zone': r.get('zone', 'CABA'),
                'address': r.get('address', ''),
                'phone': r.get('phone', ''),
                'email': r.get('email', ''),
                'instagram': r.get('instagram', ''),
                'website': r.get('website', ''),
                'products_interest': r.get('products_interest', ''),
                'score': r.get('score', 5),
                'score_auto': r.get('score_auto', 5),
                'is_premium': r.get('is_premium', False),
                'contact_status': 'Pendiente',
                'notes': r.get('notes', ''),
                'lat': lat,
                'lng': lng,
            }
            # email/instagram/website: solo si la IA los trae; si vienen vacíos no
            # se mandan, para no borrar un valor cargado a mano en un update.
            for k in ('email', 'instagram', 'website'):
                if not data[k]:
                    data.pop(k)
            prior = db.get_prospect_by_key(data['name'], data.get('neighborhood', ''))
            prior_had_coords = bool(prior and prior.get('lat') is not None)
            new_id, created = db.upsert_prospect(data, protect_on_update=db.IMPORT_PROTECTED_FIELDS)
            # Coords: solo en alta o si no tenía ubicación; nunca pisamos una ya cargada.
            if geo_status and (created or not prior_had_coords):
                db.update_prospect_location(new_id, lat, lng, geo_status)
            if created:
                data['id'] = new_id
                if sheets_ok:
                    from sheets_integration import append_prospect_to_sheets
                    append_prospect_to_sheets(data, config['sheets_credentials_path'])
                imported += 1
        except (IndexError, KeyError):
            continue
        except Exception:
            continue

    _clear_search_results()
    sheets_note = " También se volcaron al spreadsheet." if sheets_ok and imported > 0 else ""
    flash(f'{imported} prospecto{"s" if imported != 1 else ""} importado{"s" if imported != 1 else ""}.{sheets_note}', 'success')
    return redirect(url_for('index'))


# ─── Google Sheets ──────────────────────────────────────────────────────────

@app.route('/sheets', methods=['GET', 'POST'])
def sheets_view():
    config = load_config()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_config':
            credentials_file = request.files.get('credentials_file')
            if credentials_file and credentials_file.filename:
                creds_dir = os.path.join(os.path.dirname(__file__), 'credentials')
                os.makedirs(creds_dir, exist_ok=True)
                creds_path = os.path.join(creds_dir, 'google_credentials.json')
                credentials_file.save(creds_path)
                config['sheets_credentials_path'] = creds_path
            config['sheets_enabled'] = bool(config.get('sheets_credentials_path'))
            save_config(config)
            flash('Credenciales guardadas.', 'success')

        elif action == 'test':
            from sheets_integration import test_connection
            ok, msg = test_connection(config['sheets_credentials_path'])
            flash(f'Prueba de conexión: {msg}', 'success' if ok else 'danger')

        elif action == 'sync_to_sheets':
            from sheets_integration import sync_to_sheets
            from datetime import datetime
            try:
                prospects = db.get_all_prospects()
                count = sync_to_sheets(prospects, config['sheets_credentials_path'])
                config['last_sync'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                save_config(config)
                flash(f'Sincronización exitosa: {count} prospectos volcados al spreadsheet.', 'success')
            except Exception as e:
                flash(f'Error al sincronizar: {str(e)}', 'danger')

        elif action == 'import_from_sheets':
            from sheets_integration import read_from_public_csv
            try:
                rows = read_from_public_csv()
                created_count = updated_count = 0
                for row in rows:
                    score_auto = sc.calculate_auto_score(row['type'], row['neighborhood'], row['is_premium'])
                    row['score'] = score_auto        # solo aplica al alta (protegido en update)
                    row['score_auto'] = score_auto
                    _, created = db.upsert_prospect(row, protect_on_update=db.IMPORT_PROTECTED_FIELDS)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                flash(f'Importación completa: {created_count} nuevos y {updated_count} actualizados '
                      f'de {len(rows)} leídos. Los datos cargados a mano (contacto, score, '
                      f'coordenadas) se conservaron. Geocodificá para ver los nuevos en el mapa.', 'success')
            except Exception as e:
                flash(f'Error al importar: {str(e)}', 'danger')

        elif action == 'geocode_all':
            from geocoding import geocode_status, REQUEST_DELAY
            pending = [p for p in db.get_all_prospects()
                       if not p.get('lat') and (p.get('address') or p.get('neighborhood'))]
            show_progress = len(pending) > 10
            geocoded = retry_later = no_result = 0
            for i, p in enumerate(pending, 1):
                if show_progress:
                    print(f"  Geocodificando {i}/{len(pending)}... ({p['name'][:40]})", flush=True)
                lat, lng, status = geocode_status(p.get('address', ''), p.get('neighborhood', ''))
                if lat and lng:
                    db.update_prospect_location(p['id'], lat, lng, 'ok')
                    geocoded += 1
                elif status == 'error':
                    db.update_prospect_location(p['id'], None, None, 'pendiente')
                    retry_later += 1
                else:
                    db.update_prospect_location(p['id'], None, None, 'sin_resultado')
                    no_result += 1
                time.sleep(REQUEST_DELAY)
            msg = f'Geocodificación: {geocoded} ubicados'
            if retry_later:
                msg += f', {retry_later} pendientes por rate limit (volvé a correrlo)'
            if no_result:
                msg += f', {no_result} sin resultado en el mapa'
            flash(msg + '.', 'success' if not retry_later else 'danger')

        return redirect(url_for('sheets_view'))

    total = db.get_stats()['total']
    return render_template('sheets.html', config=config,
                           spreadsheet_id=config.get('sheets_spreadsheet_key') or '(no configurado)',
                           total=total)


# ─── CSV Export ─────────────────────────────────────────────────────────────

@app.route('/exportar/csv')
def export_csv():
    prospects = db.get_all_prospects()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Nombre del Local', 'Localidad / Barrio', 'Dirección',
        'Tipo de Local', 'Teléfono', 'Nota Comercial',
        'Score', 'Prioridad', 'Estado', 'Email', 'Instagram', 'Website',
    ])
    for p in prospects:
        writer.writerow([
            p['id'], p['name'], p['neighborhood'], p['address'],
            p['type'], p['phone'], p['notes'],
            p['score'], sc.score_label(p['score']), p['contact_status'],
            p['email'], p['instagram'], p['website'],
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=prospectos_arrivata.csv'},
    )


# ─── Geocode API ────────────────────────────────────────────────────────────

@app.route('/api/geocode')
def api_geocode():
    address = request.args.get('address', '')
    neighborhood = request.args.get('neighborhood', '')
    lat, lng = geocode(address, neighborhood)
    return jsonify({'lat': lat, 'lng': lng})


if __name__ == '__main__':
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print("\n  Arrivata Sales Tool corriendo en: http://localhost:5001\n")
    app.run(debug=debug, host='127.0.0.1', port=5001)
