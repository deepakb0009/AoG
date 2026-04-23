/* maintenance.js — Maintenance Planner page */

async function initMaintenance() {
  const data = await fetch('data/maintenance_alerts.json').then(r => r.json());
  renderMxTimeline(data.upcoming);
  renderMxCompleted(data.recent_completed);
  renderMxGantt(data.upcoming);
}

const MX_ICONS = { AOG:'🚨', UNSCHEDULED:'⚠️', A_CHECK:'🔧', B_CHECK:'🔩', C_CHECK:'🛠️', LINE:'✅', TRANSIT:'🔍', PLANNED:'📋' };

function priorityColor(p) {
  return { CRITICAL:'critical', HIGH:'high', MODERATE:'moderate', LOW:'low' }[p] || 'low';
}

function renderMxTimeline(items) {
  const container = document.getElementById('mx-timeline');
  if (!container) return;
  container.innerHTML = items.map(mx => {
    const start = new Date(mx.scheduled_start);
    const end   = new Date(mx.scheduled_end);
    const dur   = ((end - start) / 3.6e6).toFixed(1);
    const statusBadge = mx.status === 'IN_PROGRESS'
      ? '<span class="badge badge-high">IN PROGRESS</span>'
      : mx.status === 'SCHEDULED'
      ? '<span class="badge badge-moderate">SCHEDULED</span>'
      : '<span class="badge badge-low">PLANNED</span>';

    return `
    <div class="mx-item">
      <div class="mx-dot mx-dot-${priorityColor(mx.priority)}"></div>
      <div class="mx-content">
        <div class="mx-header">
          <span class="mx-ac">${mx.registration}</span>
          ${statusBadge}
          <span class="badge badge-${priorityColor(mx.priority)}">${mx.priority}</span>
          <span class="mx-type">${MX_ICONS[mx.type] || '🔧'} ${mx.type.replace('_',' ')}</span>
        </div>
        <div class="mx-desc">${mx.description}</div>
        <div class="mx-meta">
          📍 ${mx.station} &nbsp;·&nbsp;
          🕐 ${start.toLocaleDateString('en-US',{month:'short',day:'numeric'})} ${start.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})} &nbsp;·&nbsp;
          ⏱ ${dur}h
          ${mx.prediction_id ? `&nbsp;·&nbsp; 🤖 AI Triggered` : ''}
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderMxCompleted(items) {
  const container = document.getElementById('mx-completed');
  if (!container) return;
  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Aircraft</th><th>Subsystem</th><th>Type</th>
          <th>Completed</th><th>Duration</th><th>AOG?</th><th>Loss</th>
        </tr>
      </thead>
      <tbody>
        ${items.map(mx => `
        <tr>
          <td><strong>${mx.registration}</strong></td>
          <td>${mx.subsystem}</td>
          <td>${mx.type.replace('_',' ')}</td>
          <td class="mono">${new Date(mx.completed_at).toLocaleDateString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}</td>
          <td>${mx.duration_hours}h</td>
          <td>${mx.aog_event ? '<span class="badge badge-critical">AOG</span>' : '<span class="badge badge-low">No</span>'}</td>
          <td class="mono">${mx.aog_revenue_loss_usd > 0 ? '$'+mx.aog_revenue_loss_usd.toLocaleString() : '—'}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

function renderMxGantt(items) {
  const ctx = document.getElementById('chart-gantt');
  if (!ctx) return;

  const now = new Date('2026-04-24T00:00:00Z').getTime();
  const labels = items.map(mx => mx.registration);
  const colorMap = { CRITICAL:'#ef4444', HIGH:'#f97316', MODERATE:'#eab308', LOW:'#22c55e' };

  const data = items.map(mx => ({
    x: [new Date(mx.scheduled_start).getTime(), new Date(mx.scheduled_end).getTime()],
    y: mx.registration,
  }));

  if (ctx._chartInstance) ctx._chartInstance.destroy();
  ctx._chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: items.map((mx, i) => ({
        label: mx.subsystem,
        data: labels.map((_, j) => j === i ? [
          new Date(mx.scheduled_start).getTime(),
          new Date(mx.scheduled_end).getTime()
        ] : [null, null]),
        backgroundColor: colorMap[mx.priority] + 'aa',
        borderColor: colorMap[mx.priority],
        borderWidth: 1,
        borderRadius: 3,
        borderSkipped: false,
      }))
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(13,21,38,0.95)',
          callbacks: {
            label: ctx => {
              const mx = items[ctx.datasetIndex];
              if (!ctx.raw || ctx.raw[0] == null) return null;
              const s = new Date(ctx.raw[0]).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
              const e = new Date(ctx.raw[1]).toLocaleString('en-US',{hour:'2-digit',minute:'2-digit'});
              return `${mx.type} · ${s} → ${e}`;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'linear',
          min: new Date('2026-04-23T00:00:00Z').getTime(),
          max: new Date('2026-05-12T00:00:00Z').getTime(),
          ticks: {
            color: '#8ca0c0', font: { size: 10 },
            callback: val => new Date(val).toLocaleDateString('en-US',{month:'short',day:'numeric'})
          },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: { ticks: { color: '#8ca0c0' }, grid: { display: false } }
      }
    }
  });
}
