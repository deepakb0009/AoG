/* charts.js — Reusable Chart.js wrappers */

const CHART_DEFAULTS = {
  color: { accent:'#38bdf8', critical:'#ef4444', high:'#f97316', moderate:'#eab308', low:'#22c55e' },
  grid: 'rgba(255,255,255,0.05)',
  text: '#8ca0c0',
  font: "'Inter', sans-serif",
};

function sparklineChart(canvasId, labels, data, color = CHART_DEFAULTS.color.accent) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInstance) ctx._chartInstance.destroy();
  const inst = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{ data, borderColor: color, borderWidth: 2,
        backgroundColor: `${color}22`, fill: true, pointRadius: 0, tension: 0.4 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      animation: { duration: 800, easing: 'easeInOutQuart' },
    }
  });
  ctx._chartInstance = inst;
  return inst;
}

function lineChart(canvasId, datasets, xlabels, opts = {}) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInstance) ctx._chartInstance.destroy();
  const inst = new Chart(ctx, {
    type: 'line',
    data: { labels: xlabels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: CHART_DEFAULTS.text, font: { family: CHART_DEFAULTS.font, size: 11 }, boxWidth: 12 }
        },
        tooltip: {
          backgroundColor: 'rgba(13,21,38,0.95)',
          borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
          titleColor: '#f0f6ff', bodyColor: CHART_DEFAULTS.text,
        }
      },
      scales: {
        x: { grid: { color: CHART_DEFAULTS.grid }, ticks: { color: CHART_DEFAULTS.text, font: { size: 10 }, maxTicksLimit: 12 } },
        y: { grid: { color: CHART_DEFAULTS.grid }, ticks: { color: CHART_DEFAULTS.text, font: { size: 10 } }, ...opts.yAxis },
      },
      animation: { duration: 600 },
    }
  });
  ctx._chartInstance = inst;
  return inst;
}

function barChart(canvasId, labels, data, color = CHART_DEFAULTS.color.accent) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInstance) ctx._chartInstance.destroy();
  const inst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data, backgroundColor: `${color}55`, borderColor: color, borderWidth: 1, borderRadius: 4 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: CHART_DEFAULTS.text, font: { size: 10 } } },
        y: { grid: { color: CHART_DEFAULTS.grid }, ticks: { color: CHART_DEFAULTS.text, font: { size: 10 } }, beginAtZero: true },
      },
      animation: { duration: 600 },
    }
  });
  ctx._chartInstance = inst;
  return inst;
}

function doughnutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (ctx._chartInstance) ctx._chartInstance.destroy();
  const inst = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: { position: 'bottom', labels: { color: CHART_DEFAULTS.text, font: { size: 11 }, padding: 12 } },
        tooltip: { backgroundColor: 'rgba(13,21,38,0.95)', titleColor: '#f0f6ff', bodyColor: CHART_DEFAULTS.text }
      },
    }
  });
  ctx._chartInstance = inst;
  return inst;
}

function drawGauge(canvasId, score, label, riskCategory) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx2d = canvas.getContext('2d');
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const r = Math.min(cx, cy) - 14;
  const colorMap = { CRITICAL: '#ef4444', HIGH: '#f97316', MODERATE: '#eab308', LOW: '#22c55e' };
  const color = colorMap[riskCategory] || '#38bdf8';
  const startAngle = Math.PI * 0.75, endAngle = Math.PI * 2.25;
  const fillEnd = startAngle + (endAngle - startAngle) * score;

  ctx2d.clearRect(0, 0, canvas.width, canvas.height);
  // Track
  ctx2d.beginPath(); ctx2d.arc(cx, cy, r, startAngle, endAngle);
  ctx2d.strokeStyle = 'rgba(255,255,255,0.08)'; ctx2d.lineWidth = 12; ctx2d.lineCap = 'round'; ctx2d.stroke();
  // Fill
  if (score > 0) {
    ctx2d.beginPath(); ctx2d.arc(cx, cy, r, startAngle, fillEnd);
    ctx2d.strokeStyle = color; ctx2d.lineWidth = 12; ctx2d.lineCap = 'round';
    ctx2d.shadowColor = color; ctx2d.shadowBlur = 16; ctx2d.stroke(); ctx2d.shadowBlur = 0;
  }
  // Center text
  ctx2d.fillStyle = color; ctx2d.font = `bold 28px Inter`; ctx2d.textAlign = 'center'; ctx2d.textBaseline = 'middle';
  ctx2d.fillText(`${Math.round(score * 100)}%`, cx, cy - 6);
  ctx2d.fillStyle = '#8ca0c0'; ctx2d.font = `11px Inter`;
  ctx2d.fillText(riskCategory, cx, cy + 18);
}

// Generate hour labels for 24h chart
function hours24() {
  return Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2,'0')}:00`);
}
