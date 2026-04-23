/* predictions.js — Prediction Engine page */

async function initPredictions() {
  const preds = await fetch('data/predictions.json').then(r => r.json());
  renderPredSummary(preds.alerts);
  renderPredCards(preds.alerts);
  renderRiskMatrix(preds.alerts);
}

function renderPredSummary(alerts) {
  const counts = { CRITICAL:0, HIGH:0, MODERATE:0, LOW:0 };
  alerts.forEach(a => counts[a.risk_category]++);
  const el = id => document.getElementById(id);
  if (el('pred-critical')) el('pred-critical').textContent = counts.CRITICAL;
  if (el('pred-high'))     el('pred-high').textContent     = counts.HIGH;
  if (el('pred-moderate')) el('pred-moderate').textContent = counts.MODERATE;
  if (el('pred-low'))      el('pred-low').textContent      = counts.LOW;
}

function renderPredCards(alerts) {
  const container = document.getElementById('pred-cards');
  if (!container) return;
  const sorted = [...alerts].sort((a, b) => b.risk_score - a.risk_score);
  container.innerHTML = sorted.map(p => {
    const featHtml = (p.top_features || []).map(f => `
      <div class="feature-row">
        <span class="feature-name">${f.feature}</span>
        <div class="feature-track"><div class="feature-fill" style="width:${Math.round(f.importance*100)}%"></div></div>
        <span class="feature-val">${(f.importance*100).toFixed(0)}%</span>
      </div>`).join('');

    const ack = p.acknowledged
      ? `<span class="badge badge-low">✓ Acked by ${p.acknowledged_by}</span>`
      : `<button class="btn btn-ghost text-xs" onclick="ackPred('${p.id}')">Acknowledge</button>`;

    return `
    <div class="pred-card risk-${p.risk_category.toLowerCase()}" id="pred-${p.id}">
      <div class="pred-header">
        <span class="pred-ac">${p.registration}</span>
        <span class="badge badge-${p.risk_category.toLowerCase()}">${p.risk_category}</span>
        <span class="pred-sub">${p.subsystem.replace('_',' ')}</span>
      </div>
      <div class="pred-mode">${p.predicted_failure_mode}</div>
      <div class="pred-action">→ ${p.recommended_action}</div>
      <div class="pred-scores">
        <div class="pred-score-item">
          <div class="pred-score-val score-${p.risk_category.toLowerCase()}">${Math.round(p.risk_score*100)}%</div>
          <div class="pred-score-lbl">Risk Score</div>
        </div>
        <div class="pred-score-item">
          <div class="pred-score-val">${p.predicted_ttf_hours}h</div>
          <div class="pred-score-lbl">Est. TTF</div>
        </div>
        <div class="pred-score-item">
          <div class="pred-score-val text-muted" style="font-size:14px">${p.ttf_ci_lower}–${p.ttf_ci_upper}h</div>
          <div class="pred-score-lbl">95% CI</div>
        </div>
        <div style="margin-left:auto;align-self:flex-end">${ack}</div>
      </div>
      <div class="feature-bar">
        <div class="text-xs text-muted mb-16" style="margin-bottom:8px">Top Contributing Features</div>
        ${featHtml}
      </div>
    </div>`;
  }).join('');
}

function renderRiskMatrix(alerts) {
  // Scatter data: x=TTF, y=risk_score, sized by severity
  const subsysColors = {
    APU:'#38bdf8', ENGINE:'#ef4444', LANDING_GEAR:'#f97316',
    AVIONICS:'#a78bfa', BLEED:'#eab308'
  };
  const datasets = Object.keys(subsysColors).map(sub => ({
    label: sub.replace('_',' '),
    data: alerts
      .filter(a => a.subsystem === sub)
      .map(a => ({ x: a.predicted_ttf_hours, y: +(a.risk_score*100).toFixed(1), r: 10 })),
    backgroundColor: subsysColors[sub] + '88',
    borderColor: subsysColors[sub],
    borderWidth: 1,
  }));

  const ctx = document.getElementById('chart-risk-matrix');
  if (!ctx) return;
  if (ctx._chartInstance) ctx._chartInstance.destroy();
  ctx._chartInstance = new Chart(ctx, {
    type: 'bubble',
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8ca0c0', font: { size: 11 } } },
        tooltip: {
          backgroundColor: 'rgba(13,21,38,0.95)',
          callbacks: {
            label: ctx => `TTF: ${ctx.raw.x}h | Risk: ${ctx.raw.y}%`
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Predicted TTF (hours)', color: '#8ca0c0' },
             grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8ca0c0' } },
        y: { title: { display: true, text: 'Risk Score (%)', color: '#8ca0c0' },
             grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8ca0c0' },
             min: 0, max: 100 },
      }
    }
  });
}

function ackPred(id) {
  const card = document.getElementById(`pred-${id}`);
  if (!card) return;
  const btn = card.querySelector('.btn-ghost');
  if (btn) btn.outerHTML = `<span class="badge badge-low">✓ Acknowledged</span>`;
}
