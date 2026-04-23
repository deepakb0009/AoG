/* app.js — SPA Router + Init */

const APP = {
  currentPage: 'fleet',
  currentAircraft: 'AC001',

  pages: {
    fleet:       { title: 'Fleet Overview',      init: () => initFleet() },
    aircraft:    { title: 'Aircraft Detail',     init: (id) => initAircraft(id) },
    predictions: { title: 'Prediction Engine',   init: () => initPredictions() },
    maintenance: { title: 'Maintenance Planner', init: () => initMaintenance() },
    data:        { title: 'Data Explorer',       init: () => initDataExplorer() },
    report:      { title: 'Domain Report',       init: () => initReport() },
  },

  navigate(page, param) {
    if (param) this.currentAircraft = param;
    this.currentPage = page;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });

    // Show page
    document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
    const pageEl = document.getElementById(`page-${page}`);
    if (pageEl) pageEl.classList.add('active');

    // Update topbar
    const titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = this.pages[page]?.title || '';

    // Init page
    const cfg = this.pages[page];
    if (cfg?.init) cfg.init(param);

    // Update URL hash
    location.hash = param ? `${page}/${param}` : page;
  },

  init() {
    // Nav click handlers
    document.querySelectorAll('.nav-item[data-page]').forEach(el => {
      el.addEventListener('click', () => this.navigate(el.dataset.page));
    });

    // Clock
    this.startClock();

    // Ticker
    this.startTicker();

    // Route from hash
    const hash = location.hash.replace('#', '');
    if (hash) {
      const [page, param] = hash.split('/');
      if (this.pages[page]) { this.navigate(page, param); return; }
    }

    this.navigate('fleet');
  },

  startClock() {
    const el = document.getElementById('topbar-time');
    if (!el) return;
    const update = () => {
      const now = new Date();
      el.textContent = now.toUTCString().slice(17, 25) + ' UTC';
    };
    update();
    setInterval(update, 1000);
  },

  startTicker() {
    const alerts = [
      '🔴 AC003 N20003 — CRITICAL: Landing Gear hydraulic seal leak — AOG at KORD',
      '🟠 AC001 N20001 — HIGH: APU EGT trending toward exceedance — action in 62h',
      '🟠 AC005 N20005 — CRITICAL: Engine shop visit required — 18h TTF',
      '🟡 AC007 N20007 — MODERATE: APU vibration elevated — inspection in 7d',
      '🟠 AC008 N20008 — HIGH: Bleed precooler fouling — cleaning required',
      '✅ Fleet Availability: 94.3% (+2.5% vs prior year)',
    ];
    const el = document.querySelector('.ticker-text');
    if (el) el.textContent = alerts.join('   ·   ');
  }
};

/* ── Data Explorer ──────────────────────────────────────────────────────────── */
async function initDataExplorer() {
  const fleet = await fetch('data/aircraft_metadata.json').then(r => r.json());
  renderSchemaOverview();
  renderDataPreview(fleet);
}

function renderSchemaOverview() {
  const container = document.getElementById('schema-overview');
  if (!container) return;
  const tables = [
    { name:'aircraft_metadata', rows:'10', cols:'19', desc:'Master fleet registry — one row per aircraft' },
    { name:'sensor_telemetry',  rows:'~10.5M (2yr)', cols:'37', desc:'High-frequency time-series sensor readings' },
    { name:'flight_cycles',     rows:'~28,000 (2yr)', cols:'18', desc:'One record per flight departure→arrival' },
    { name:'maintenance_logs',  rows:'~18 (labeled)', cols:'20', desc:'Historical and scheduled maintenance events' },
    { name:'failure_labels',    rows:'18', cols:'14', desc:'ML ground-truth labels for supervised training' },
    { name:'prediction_results',rows:'Live', cols:'16', desc:'ML model output — risk scores and TTF predictions' },
  ];
  container.innerHTML = `
    <table class="data-table">
      <thead><tr><th>Table</th><th>Rows (est.)</th><th>Columns</th><th>Description</th></tr></thead>
      <tbody>
        ${tables.map(t => `
        <tr>
          <td class="mono">${t.name}</td>
          <td class="mono">${t.rows}</td>
          <td class="mono">${t.cols}</td>
          <td class="text-muted">${t.desc}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

function renderDataPreview(fleet) {
  const container = document.getElementById('data-preview');
  if (!container) return;
  const keys = ['aircraft_id','registration','series','engine','age_yrs','total_fh','total_cycles','base','status'];
  container.innerHTML = `
    <table class="data-table">
      <thead><tr>${keys.map(k => `<th>${k}</th>`).join('')}</tr></thead>
      <tbody>
        ${fleet.aircraft.map(ac => `
        <tr>${keys.map(k => `<td class="mono">${ac[k] ?? '—'}</td>`).join('')}</tr>
        `).join('')}
      </tbody>
    </table>`;
}

/* ── Domain Report ─────────────────────────────────────────────────────────── */
async function initReport() {
  const container = document.getElementById('report-content');
  if (!container) return;
  try {
    const md = await fetch('docs/domain_specialist_report.md').then(r => r.text());
    // Basic markdown → HTML (tables, headers, bold, code)
    container.innerHTML = md
      .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/^---$/gm, '<hr>')
      .replace(/^\| (.+) \|$/gm, row => {
        const cells = row.split('|').filter(c => c.trim());
        return `<tr>${cells.map(c => `<td>${c.trim()}</td>`).join('')}</tr>`;
      })
      .replace(/(<tr>.*<\/tr>\n?)+/gs, m => `<table class="data-table">${m}</table>`)
      .replace(/\n\n/g, '</p><p>')
      .replace(/^(?!<[hHtTpPcC])/gm, '');
  } catch {
    container.innerHTML = '<p class="text-muted">Load docs/domain_specialist_report.md via a local server.</p>';
  }
}

// Boot
document.addEventListener('DOMContentLoaded', () => APP.init());
