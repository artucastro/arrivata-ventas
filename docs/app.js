const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const slug = (s) => String(s || '').toLowerCase().replace(/ /g, '-');

let ALL = [];

fetch('data.json')
  .then(r => r.json())
  .then(d => {
    ALL = d.prospects;
    document.getElementById('demo-tag').textContent =
      (d.anonymized ? 'DATOS DE EJEMPLO · ' : '') + 'FOTO AL ' + d.generated;
    document.getElementById('footer-note').textContent =
      'Arrivata Sales Tool — vista de solo lectura' +
      (d.anonymized ? ' · datos anonimizados' : '') + ' · generada el ' + d.generated;
    fillFilter('f-zone', [...new Set(ALL.map(p => p.zone).filter(Boolean))].sort());
    fillFilter('f-neigh', [...new Set(ALL.map(p => p.neighborhood).filter(Boolean))].sort());
    fillFilter('f-status', [...new Set(ALL.map(p => p.contact_status).filter(Boolean))]);
    ['f-search', 'f-zone', 'f-neigh', 'f-status', 'f-score'].forEach(id =>
      document.getElementById(id).addEventListener('input', render));
    document.getElementById('f-clear').addEventListener('click', () => {
      ['f-search', 'f-zone', 'f-neigh', 'f-status', 'f-score'].forEach(id => document.getElementById(id).value = '');
      render();
    });
    document.getElementById('btn-csv').addEventListener('click', exportCsv);
    render();
  })
  .catch(() => {
    document.getElementById('rows').innerHTML =
      '<tr><td colspan="6" class="text-center py-5 text-muted">No se pudo cargar data.json</td></tr>';
  });

function fillFilter(id, values) {
  const sel = document.getElementById(id);
  values.forEach(v => sel.insertAdjacentHTML('beforeend', `<option value="${esc(v)}">${esc(v)}</option>`));
}

function currentFilters() {
  return {
    q: document.getElementById('f-search').value.trim().toLowerCase(),
    zone: document.getElementById('f-zone').value,
    neigh: document.getElementById('f-neigh').value,
    status: document.getElementById('f-status').value,
    minScore: parseInt(document.getElementById('f-score').value) || 0,
  };
}

function filtered() {
  const f = currentFilters();
  return ALL.filter(p => {
    if (f.zone && p.zone !== f.zone) return false;
    if (f.neigh && p.neighborhood !== f.neigh) return false;
    if (f.status && p.contact_status !== f.status) return false;
    if (f.minScore && p.score < f.minScore) return false;
    if (f.q) {
      const hay = `${p.name} ${p.address} ${p.notes} ${p.type}`.toLowerCase();
      if (!hay.includes(f.q)) return false;
    }
    return true;
  });
}

function render() {
  const list = filtered();
  renderStats(list);
  const tb = document.getElementById('rows');
  if (!list.length) {
    tb.innerHTML = '<tr><td colspan="6" class="text-center py-5 text-muted">Sin resultados con esos filtros</td></tr>';
  } else {
    tb.innerHTML = list.map((p, i) => `
      <tr style="cursor:pointer" data-i="${ALL.indexOf(p)}">
        <td class="ps-4" style="min-width:180px">
          <span class="prospect-name">${esc(p.name)}</span>
          ${p.address ? `<div class="text-muted" style="font-size:.75rem">${esc(p.address)}</div>` : ''}
        </td>
        <td><span style="font-size:.78rem;color:var(--a-gray)">${esc(p.type)}</span></td>
        <td style="font-size:.82rem">${esc(p.neighborhood)}</td>
        <td class="text-center"><span class="score-badge badge-${p.score_color}" title="${esc(p.score_label)} prioridad">${p.score}</span></td>
        <td><span class="status-badge status-${slug(p.contact_status)}">${esc(p.contact_status)}</span></td>
        <td>
          ${p.products.slice(0, 2).map(x => `<span class="badge bg-light text-muted border me-1" style="font-size:.7rem;font-weight:500">${esc(x)}</span>`).join('')}
          ${p.products.length > 2 ? `<span class="text-muted" style="font-size:.74rem">+${p.products.length - 2}</span>` : ''}
        </td>
      </tr>`).join('');
    tb.querySelectorAll('tr[data-i]').forEach(tr =>
      tr.addEventListener('click', () => showDetail(ALL[+tr.dataset.i])));
  }
  document.getElementById('count').textContent =
    `${list.length} PROSPECTO${list.length !== 1 ? 'S' : ''}` + (list.length !== ALL.length ? ` (de ${ALL.length})` : '');
}

function renderStats(list) {
  const total = list.length;
  const alta = list.filter(p => p.score >= 7).length;
  const contactados = list.filter(p => p.contact_status !== 'Pendiente').length;
  const clientes = list.filter(p => p.contact_status === 'Cliente').length;
  const card = (icon, cls, val, label, color) => `
    <div class="col-6 col-md-3"><div class="card stat-card border-0 h-100"><div class="card-body">
      <div class="d-flex align-items-center gap-3">
        <div class="stat-icon ${cls}"><i class="bi ${icon}" style="font-size:1.1rem;${color ? 'color:' + color : ''}"></i></div>
        <div><div class="stat-number" ${color ? `style="color:${color}"` : ''}>${val}</div><div class="stat-label">${label}</div></div>
      </div></div></div></div>`;
  document.getElementById('stats').innerHTML =
    card('bi-people', 'bg-navy-soft', total, 'Total') +
    card('bi-star', 'bg-red-soft', alta, 'Alta prioridad', 'var(--a-red)') +
    card('bi-telephone', 'bg-amber-soft', contactados, 'Contactados', '#c68700') +
    card('bi-bag-check', 'bg-green-soft', clientes, 'Clientes', '#2e7d52');
}

function showDetail(p) {
  const ig = p.instagram ? `<a href="https://instagram.com/${esc(p.instagram)}" target="_blank" rel="noopener" style="color:var(--a-red)">@${esc(p.instagram)}</a>` : '—';
  const web = p.website ? `<a href="${esc(p.website)}" target="_blank" rel="noopener" style="color:var(--a-red)">${esc(p.website.slice(0, 40))}</a>` : '—';
  const tel = p.phone ? `<a href="tel:${esc(p.phone)}" style="color:var(--a-red)">${esc(p.phone)}</a>` : '—';
  document.getElementById('detailBody').innerHTML = `
    <div class="modal-header border-0 pb-1">
      <div>
        <h5 class="modal-title" style="font-family:'Amiri',serif;font-weight:400">${esc(p.name)}</h5>
        <div class="text-muted" style="font-size:.8rem">${esc(p.type)} · ${esc(p.neighborhood)} · ${esc(p.zone)}</div>
      </div>
      <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
    </div>
    <div class="modal-body pt-2">
      <div class="d-flex align-items-center gap-3 mb-3">
        <span class="score-badge badge-${p.score_color}" style="width:38px;height:38px;font-size:1rem">${p.score}</span>
        <div>
          <div style="font-weight:600">${esc(p.score_label)} prioridad</div>
          <span class="status-badge status-${slug(p.contact_status)}">${esc(p.contact_status)}</span>
          ${p.is_premium ? '<span class="badge ms-1" style="background:var(--a-red-light);color:var(--a-red);font-size:.7rem">Premium</span>' : ''}
        </div>
      </div>
      <dl class="row small mb-2">
        <dt class="col-4 text-muted fw-normal">Dirección</dt><dd class="col-8">${esc(p.address) || '—'}</dd>
        <dt class="col-4 text-muted fw-normal">Teléfono</dt><dd class="col-8">${tel}</dd>
        <dt class="col-4 text-muted fw-normal">Instagram</dt><dd class="col-8">${ig}</dd>
        <dt class="col-4 text-muted fw-normal">Website</dt><dd class="col-8">${web}</dd>
      </dl>
      ${p.products.length ? `<div class="mb-2">${p.products.map(x => `<span class="badge bg-light text-muted border me-1 mb-1" style="font-size:.72rem">${esc(x)}</span>`).join('')}</div>` : ''}
      ${p.notes ? `<div class="p-2 rounded" style="background:var(--a-bg-2);font-size:.85rem;line-height:1.6">${esc(p.notes)}</div>` : ''}
      ${p.lat ? `<a class="d-inline-block mt-2" style="font-size:.8rem;color:var(--a-red)" target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=17/${p.lat}/${p.lng}">Ver en el mapa →</a>` : ''}
    </div>`;
  new bootstrap.Modal(document.getElementById('detailModal')).show();
}

function exportCsv() {
  const cols = ['name', 'neighborhood', 'address', 'type', 'phone', 'notes', 'score', 'score_label', 'contact_status', 'instagram', 'website'];
  const head = ['Nombre', 'Barrio', 'Dirección', 'Tipo', 'Teléfono', 'Nota', 'Score', 'Prioridad', 'Estado', 'Instagram', 'Website'];
  const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [head.join(',')].concat(filtered().map(p => cols.map(c => q(p[c])).join(',')));
  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'prospectos_arrivata.csv';
  a.click();
}
