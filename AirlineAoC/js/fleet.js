/* fleet.js — Fleet Overview page */

async function initFleet() {
  const [fleet, preds, sensors, kpis] = await Promise.all([
    fetch('data/aircraft_metadata.json').then(r => r.json()),
    fetch('data/predictions.json').then(r => r.json()),
    fetch('data/sensor_summary.json').then(r => r.json()),
    fetch('data/kpis.json').then(r => r.json()),
  ]);

  renderKPIs(kpis);
  renderFleetGrid(fleet, preds, sensors);
  renderAogTrend(kpis);
  renderAvailability(kpis);
  renderSubsystemBreakdown(preds);
}

function renderKPIs(kpis) {
  const k = kpis.kpis;
  const s = kpis.summary;
  document.getElementById('kpi-aog-reduction').textContent     = `${k.aog_reduction_pct.value}`;
  document.getElementById('kpi-mx-reduction').textContent      = `${k.unscheduled_mx_reduction_pct.value}`;
  document.getElementById('kpi-downtime').textContent          = `${k.downtime_reduction_pct.value}`;
  document.getElementById('kpi-availability').textContent      = `${k.fleet_availability_pct.value}`;
  document.getElementById('kpi-aog-target').textContent        = `Target: ${k.aog_reduction_pct.target}%`;
  document.getElementById('kpi-mx-target').textContent         = `Target: ${k.unscheduled_mx_reduction_pct.target}%`;
  document.getElementById('kpi-downtime-target').textContent   = `Target: ${k.downtime_reduction_pct.target}%`;
  document.getElementById('kpi-avail-target').textContent      = `Target: ${k.fleet_availability_pct.target}%`;

  // Progress bars
  ['aog-bar', 'mx-bar', 'downtime-bar', 'avail-bar'].forEach((id, i) => {
    const vals = [k.aog_reduction_pct, k.unscheduled_mx_reduction_pct, k.downtime_reduction_pct, k.fleet_availability_pct];
    const v = vals[i];
    const pct = Math.min((v.value / v.target) * 100, 100);
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.style.width = `${pct}%`;
    }, 300 + i * 100);
  });

  // Summary stats
  if (document.getElementById('stat-aog-ytd'))
    document.getElementById('stat-aog-ytd').textContent = s.aog_events_ytd;
  if (document.getElementById('stat-rev-protected'))
    document.getElementById('stat-rev-protected').textContent =
      `$${(s.revenue_protected_usd / 1e6).toFixed(2)}M`;
  if (document.getElementById('stat-pred-acc'))
    document.getElementById('stat-pred-acc').textContent = `${s.predictions_correct_pct}%`;
}

function riskColor(cat) {
  return { CRITICAL:'critical', HIGH:'high', MODERATE:'moderate', LOW:'low' }[cat] || 'low';
}

function renderFleetGrid(fleet, preds, sensors) {
  const container = document.getElementById('fleet-grid');
  if (!container) return;

  // Build per-aircraft risk lookup
  const riskMap = {};
  preds.alerts.forEach(a => {
    if (!riskMap[a.aircraft_id] || a.risk_score > riskMap[a.aircraft_id].risk_score)
      riskMap[a.aircraft_id] = a;
  });

  container.innerHTML = fleet.aircraft.map(ac => {
    const top = riskMap[ac.aircraft_id] || { risk_score: 0.05, risk_category: 'LOW' };
    const snap = sensors.sensor_snapshots[ac.aircraft_id] || {};
    const statusClass = `status-${ac.status.toLowerCase()}`;
    const badgeClass  = `badge-${ac.status.toLowerCase()}`;
    const fillClass   = `fill-${top.risk_category.toLowerCase()}`;
    const pct = Math.round(top.risk_score * 100);

    return `
    <div class="aircraft-card ${statusClass}" onclick="APP.navigate('aircraft','${ac.aircraft_id}')">
      <span class="ac-status-badge ${badgeClass}">${ac.status}</span>
      <div class="ac-reg">${ac.registration}</div>
      <div class="ac-series">${ac.series}</div>
      <div class="ac-base">${ac.base} · ${snap.flight_phase || ''}</div>
      <div class="ac-risk">
        <span class="text-xs text-muted">${pct}%</span>
        <div class="ac-risk-bar"><div class="ac-risk-fill ${fillClass}" style="width:${pct}%"></div></div>
        <span class="badge badge-${riskColor(top.risk_category)}">${top.risk_category}</span>
      </div>
    </div>`;
  }).join('');
}

function renderAogTrend(kpis) {
  const months = kpis.aog_trend_monthly;
  barChart('chart-aog-trend',
    months.map(m => m.month.split(' ')[0]),
    months.map(m => m.aog),
    '#ef4444'
  );
}

function renderAvailability(kpis) {
  const trend = kpis.availability_trend_monthly;
  lineChart('chart-availability',
    [{ label: 'Fleet Availability %', data: trend.map(m => m.pct),
       borderColor: '#22c55e', backgroundColor: '#22c55e22', fill: true,
       tension: 0.4, pointRadius: 3 }],
    trend.map(m => m.month.split(' ')[0]),
    { yAxis: { min: 88, max: 100 } }
  );
}

function renderSubsystemBreakdown(preds) {
  const counts = { APU:0, ENGINE:0, LANDING_GEAR:0, AVIONICS:0, BLEED:0 };
  preds.alerts.filter(a => a.risk_category !== 'LOW').forEach(a => {
    if (counts[a.subsystem] !== undefined) counts[a.subsystem]++;
  });
  doughnutChart('chart-subsystem',
    ['APU','Engine','Landing Gear','Avionics','Bleed Air'],
    Object.values(counts),
    ['#38bdf8','#ef4444','#f97316','#a78bfa','#eab308']
  );
}
