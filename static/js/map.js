document.addEventListener('DOMContentLoaded', () => {
  const map = L.map('map').setView([-34.603, -58.381], 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  function scoreColor(score) {
    if (score >= 8) return '#22c55e';
    if (score >= 5) return '#f59e0b';
    return '#ef4444';
  }

  function makeIcon(score) {
    const color = scoreColor(score);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">
      <path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 24 16 24S32 28 32 16C32 7.2 24.8 0 16 0z" fill="${color}" stroke="white" stroke-width="2"/>
      <text x="16" y="21" text-anchor="middle" font-size="13" font-weight="bold" fill="white" font-family="system-ui">${score}</text>
    </svg>`;
    return L.divIcon({
      html: svg, className: '', iconSize: [32, 40], iconAnchor: [16, 40], popupAnchor: [0, -40],
    });
  }

  fetch('/api/prospects')
    .then(r => r.json())
    .then(prospects => {
      document.getElementById('map-count').textContent = `${prospects.length} pin${prospects.length !== 1 ? 's' : ''}`;

      prospects.forEach(p => {
        const marker = L.marker([p.lat, p.lng], { icon: makeIcon(p.score) }).addTo(map);
        marker.bindPopup(`
          <div style="min-width:200px">
            <div style="font-weight:700;font-size:1rem;margin-bottom:4px">${esc(p.name)}</div>
            <div style="color:#6b7280;font-size:.85rem;margin-bottom:6px">${esc(p.type)} · ${esc(p.neighborhood)}</div>
            <div style="font-size:.82rem;margin-bottom:8px">${esc(p.address)}</div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="background:${scoreColor(p.score)};color:${p.score>=5&&p.score<8?'#1f2937':'white'};padding:2px 10px;border-radius:20px;font-weight:700;font-size:.85rem">
                Score ${esc(p.score)}
              </span>
              <span style="font-size:.8rem;color:#6b7280">${esc(p.score_label)} prioridad</span>
            </div>
            <div style="font-size:.8rem;color:#6b7280;margin-bottom:8px">Estado: ${esc(p.contact_status)}</div>
            <a href="/prospecto/${encodeURIComponent(p.id)}" style="font-size:.82rem;color:#1a3c5e">Ver detalle →</a>
          </div>
        `);
      });

      if (prospects.length > 0) {
        const group = L.featureGroup(
          prospects.map(p => L.marker([p.lat, p.lng]))
        );
        map.fitBounds(group.getBounds().pad(0.1));
      }
    })
    .catch(err => console.error('Error loading prospects:', err));
});
