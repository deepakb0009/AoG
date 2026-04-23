/* aircraft.js — Aircraft Detail page */

let currentAircraftId = 'AC001';

async function initAircraft(aircraftId) {
  currentAircraftId = aircraftId || currentAircraftId;
  const [fleet, sensors, preds] = await Promise.all([
    fetch('data/aircraft_metadata.json').then(r => r.json()),
    fetch('data/sensor_summary.json').then(r => r.json()),
    fetch('data/predictions.json').then(r => r.json()),
  ]);

  const ac = fleet.aircraft.find(a => a.aircraft_id === currentAircraftId);
  const snap = sensors.sensor_snapshots[currentAircraftId] || {};
  const acPreds = preds.alerts.filter(a => a.aircraft_id === currentAircraftId);
  const topRisk = acPreds.reduce((a, b) => (b.risk_score > a.risk_score ? b : a),
    { risk_score: 0.05, risk_category: 'LOW' });

  renderAircraftHeader(ac, snap);
  renderAircraftSelector(fleet, currentAircraftId);
  renderSubsystemChips(snap);
  renderGauge(topRisk);
  renderSensorCharts(snap, currentAircraftId);
  renderAircraftPreds(acPreds);
}

function renderAircraftSelector(fleet, selected) {
  const sel = document.getElementById('ac-selector');
  if (!sel) return;
  sel.innerHTML = fleet.aircraft.map(ac =>
    `<option value="${ac.aircraft_id}" ${ac.aircraft_id === selected ? 'selected' : ''}>
       ${ac.registration} — ${ac.series} (${ac.status})
     </option>`
  ).join('');
  sel.onchange = () => initAircraft(sel.value);
}

function renderAircraftHeader(ac, snap) {
  if (!ac) return;
  const el = id => document.getElementById(id);
  if (el('ac-reg'))    el('ac-reg').textContent    = ac.registration;
  if (el('ac-series')) el('ac-series').textContent = `${ac.series} · ${ac.engine}`;
  if (el('ac-base'))   el('ac-base').textContent   = `${ac.base} · MSN ${ac.msn || '—'}`;
  if (el('ac-fh'))     el('ac-fh').textContent     = `${ac.total_fh.toLocaleString()} FH`;
  if (el('ac-cyc'))    el('ac-cyc').textContent    = `${ac.total_cycles.toLocaleString()} cycles`;
  if (el('ac-age'))    el('ac-age').textContent    = `${ac.age_yrs} yrs`;
  if (el('ac-phase'))  el('ac-phase').textContent  = snap.flight_phase?.replace('_',' ') || '—';
  if (el('ac-status')) {
    el('ac-status').textContent  = ac.status;
    el('ac-status').className    = `badge badge-${ac.status.toLowerCase()}`;
  }
}

function renderSubsystemChips(snap) {
  const container = document.getElementById('subsystem-chips');
  if (!container || !snap.subsystems) return;
  const icons = { APU:'⚡', ENGINE:'🔥', LANDING_GEAR:'🛬', AVIONICS:'📡', BLEED:'💨' };
  container.innerHTML = Object.entries(snap.subsystems).map(([key, sub]) => `
    <div class="subsys-chip" onclick="selectSubsystem('${key}')">
      <div class="subsys-icon">${icons[key] || '🔧'}</div>
      <div class="subsys-name">${key.replace('_',' ')}</div>
      <div class="subsys-score score-${sub.risk.toLowerCase()}">${sub.health}%</div>
      <div class="subsys-trend text-xs text-muted">${sub.trend === 'DOWN' ? '↓ Declining' : sub.trend === 'UP' ? '↑ Rising' : '→ Stable'}</div>
    </div>`).join('');
}

function renderGauge(topRisk) {
  const canvas = document.getElementById('gauge-canvas');
  if (!canvas) return;
  canvas.width = 180; canvas.height = 180;
  drawGauge('gauge-canvas', topRisk.risk_score, topRisk.risk_category, topRisk.risk_category);
}

function renderSensorCharts(snap, aircraftId) {
  const hrs = hours24();

  // EGT trend — pick APU or engine based on which has data
  const egt = snap.egt_trend_24h || [];
  if (egt.length) {
    lineChart('chart-egt', [
      { label: 'EGT (°C)', data: egt, borderColor: '#f97316',
        backgroundColor: '#f9731622', fill: true, tension: 0.4, pointRadius: 0 }
    ], hrs, { yAxis: { min: Math.min(...egt) - 20 } });
  }

  // Vibration trend
  const vib = snap.vib_trend_24h || [];
  if (vib.length) {
    lineChart('chart-vib', [
      { label: 'Vibration (g/IPS)', data: vib, borderColor: '#a78bfa',
        backgroundColor: '#a78bfa22', fill: true, tension: 0.4, pointRadius: 0 }
    ], hrs);
  }

  // Hydraulic pressure (simulated 24h)
  const hydBase = snap.subsystems?.LANDING_GEAR?.value || 3000;
  const hydData = Array.from({length:24}, (_, i) =>
    +(hydBase + (Math.random() - 0.5) * 40).toFixed(1));
  lineChart('chart-hyd', [
    { label: 'Hydraulic Pressure (psi)', data: hydData, borderColor: '#38bdf8',
      backgroundColor: '#38bdf822', fill: true, tension: 0.3, pointRadius: 0 }
  ], hrs, { yAxis: { min: 2400, max: 3100 } });
}

function renderAircraftPreds(preds) {
  const container = document.getElementById('ac-pred-list');
  if (!container) return;
  if (!preds.length) {
    container.innerHTML = '<div class="text-muted text-sm" style="padding:20px">No active predictions for this aircraft.</div>';
    return;
  }
  container.innerHTML = preds.map(p => `
    <div class="alert-item">
      <div class="alert-icon icon-${p.risk_category.toLowerCase()}">${
        {APU:'⚡', ENGINE:'🔥', LANDING_GEAR:'🛬', AVIONICS:'📡', BLEED:'💨'}[p.subsystem]||'🔧'
      }</div>
      <div class="alert-body">
        <div class="alert-title">${p.subsystem.replace('_',' ')} — <span class="badge badge-${p.risk_category.toLowerCase()}">${p.risk_category}</span></div>
        <div class="alert-sub">${p.predicted_failure_mode}</div>
        <div class="alert-meta">⚠️ ${p.recommended_action}</div>
      </div>
      <div class="alert-ttf score-${p.risk_category.toLowerCase()}">
        TTF<br>${p.predicted_ttf_hours}h
      </div>
    </div>`).join('');
}

function selectSubsystem(key) {
  document.querySelectorAll('.subsys-chip').forEach(c => c.classList.remove('active'));
  event.currentTarget.classList.add('active');
}
