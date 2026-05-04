/**
 * EPR Simulator — Main application logic
 * Handles: state sync, nuclei CRUD, simulation, Plotly rendering, validation badges
 */

'use strict';

// ============================================================
// State
// ============================================================

let state = {
  simulator: 'garlic',
  harmonic: 1,
  systemState: null,
};

// ============================================================
// API helpers
// ============================================================

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || res.statusText);
  }
  return res.json();
}

const GET    = (path)        => api('GET',    path);
const PUT    = (path, body)  => api('PUT',    path, body);
const POST   = (path, body)  => api('POST',   path, body);
const DELETE = (path)        => api('DELETE', path);

// ============================================================
// Init
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  await refreshSystem();
  bindInputListeners();
  initMobileTutorial();

  // First-run tour
  if (!localStorage.getItem('epr_tour_done')) {
    setTimeout(startTour, 1200);
  }
});

// ============================================================
// System refresh
// ============================================================

async function refreshSystem() {
  try {
    state.systemState = await GET('/api/system');
    renderNucleiList(state.systemState.nuclei);
    updateSummaries(state.systemState);
    updateHsdimBadge(state.systemState.hsdim);
    await refreshValidation();
  } catch (e) {
    console.error('Failed to refresh system:', e);
  }
}

// ============================================================
// Collapsible cards
// ============================================================

function toggleCard(id) {
  document.getElementById(id).classList.toggle('collapsed');
}

// ============================================================
// Panel tabs (desktop)
// ============================================================

document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
    tab.classList.add('active');
    document.getElementById('pane-' + tab.dataset.tab).style.display = '';
  });
});

// ============================================================
// Mobile tabs
// ============================================================

function switchMobileTab(btn) {
  document.querySelectorAll('.bottom-nav-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const targetId = btn.dataset.mobileTab;
  ['mobile-params','mobile-spectrum','mobile-levels','mobile-tutorial'].forEach(id => {
    document.getElementById(id).classList.toggle('active', id === targetId);
  });
  // Trigger Plotly resize when switching to plot tabs
  if (targetId === 'mobile-spectrum') {
    const el = document.getElementById('m-spectrum-plot');
    if (el._plotly) Plotly.Plots.resize(el);
  }
  if (targetId === 'mobile-levels') {
    const el = document.getElementById('m-levels-plot');
    if (el._plotly) Plotly.Plots.resize(el);
  }
}

function initMobileTutorial() {
  const src = document.getElementById('pane-tutorial').innerHTML;
  document.getElementById('mobile-tutorial').innerHTML = src;
  // Also clone the panel cards to mobile-params
  const paramsContent = document.getElementById('pane-params').innerHTML;
  document.getElementById('mobile-params').innerHTML = paramsContent;
}

// ============================================================
// Simulator toggle
// ============================================================

function setSimulator(sim) {
  state.simulator = sim;
  document.getElementById('btn-garlic').classList.toggle('active', sim === 'garlic');
  document.getElementById('btn-pepper').classList.toggle('active', sim === 'pepper');
  document.getElementById('sim-summary').textContent =
    sim === 'garlic' ? 'garlic \u2014 liquid state' : 'pepper \u2014 powder/solid';
  refreshValidation();
}

// ============================================================
// Detection mode
// ============================================================

function setHarmonic(h) {
  state.harmonic = h;
  document.getElementById('btn-absorption').classList.toggle('active', h === 0);
  document.getElementById('btn-derivative').classList.toggle('active', h === 1);
}

// ============================================================
// Input listeners — push changes to API on blur
// ============================================================

function bindInputListeners() {
  const push = () => pushSystemParams();
  ['f-S','f-gx','f-gy','f-gz','f-D','f-E','f-lG','f-lL','f-mwFreq'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', push);
  });
}

async function pushSystemParams() {
  const S  = parseFloat(document.getElementById('f-S')?.value  || 0.5);
  const gx = parseFloat(document.getElementById('f-gx')?.value || 2.0023);
  const gy = parseFloat(document.getElementById('f-gy')?.value || 2.0023);
  const gz = parseFloat(document.getElementById('f-gz')?.value || 2.0023);
  const D  = parseFloat(document.getElementById('f-D')?.value  || 0);
  const E  = parseFloat(document.getElementById('f-E')?.value  || 0);
  const lG = parseFloat(document.getElementById('f-lG')?.value || 0.3);
  const lL = parseFloat(document.getElementById('f-lL')?.value || 0.0);

  const Darr = (D !== 0 || E !== 0) ? [D, E] : [];
  const lwarr = lL > 0 ? [lG, lL] : [lG];

  try {
    state.systemState = await PUT('/api/system', {
      S, g: [gx, gy, gz], D: Darr, lw: lwarr, tcorr: null
    });
    updateSummaries(state.systemState);
    updateHsdimBadge(state.systemState.hsdim);
    await refreshValidation();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ============================================================
// Nuclei management
// ============================================================

async function addNucleus() {
  const symbol = document.getElementById('nucleus-symbol-select')?.value || '14N';
  try {
    state.systemState = await POST('/api/system/nuclei', { symbol, A: 0, Q: 0, label: null });
    renderNucleiList(state.systemState.nuclei);
    updateSummaries(state.systemState);
    updateHsdimBadge(state.systemState.hsdim);
    await refreshValidation();
  } catch (e) {
    showToast('Error adding nucleus: ' + e.message, 'error');
  }
}

async function removeNucleus(idx) {
  try {
    state.systemState = await DELETE('/api/system/nuclei/' + idx);
    renderNucleiList(state.systemState.nuclei);
    updateSummaries(state.systemState);
    updateHsdimBadge(state.systemState.hsdim);
    await refreshValidation();
  } catch (e) {
    showToast('Error removing nucleus: ' + e.message, 'error');
  }
}

async function updateNucleusA(idx, value) {
  // Debounced push: update local state immediately, push to API after 500ms
  clearTimeout(window._nucleusTimer);
  window._nucleusTimer = setTimeout(async () => {
    // Rebuild the full nucleus from current UI
    const rows = document.querySelectorAll('#nuclei-list .nucleus-row');
    if (!rows[idx]) return;
    const A = parseFloat(rows[idx].querySelector('.nuc-A').value) || 0;
    const Q = parseFloat(rows[idx].querySelector('.nuc-Q')?.value || 0);
    const sym = state.systemState.nuclei[idx].symbol;
    // Remove and re-add to update (simplest approach given current API)
    try {
      await DELETE('/api/system/nuclei/' + idx);
      // Re-insert at same position by adding to end (limitation of current API)
      // For now use add — full reorder API is a future enhancement
      state.systemState = await POST('/api/system/nuclei', { symbol: sym, A, Q, label: null });
      updateHsdimBadge(state.systemState.hsdim);
      await refreshValidation();
    } catch (e) {
      console.error('Nucleus update failed:', e);
    }
  }, 600);
}

function renderNucleiList(nuclei) {
  const list = document.getElementById('nuclei-list');
  if (!list) return;
  list.innerHTML = '';
  if (nuclei.length === 0) {
    list.innerHTML = '<div style="color:var(--text-hint);font-size:0.78rem;text-align:center;padding:8px;">No nuclei added</div>';
    return;
  }
  nuclei.forEach((n, idx) => {
    const row = document.createElement('div');
    row.className = 'nucleus-row';
    row.innerHTML = `
      <div class="nucleus-chip">${n.symbol}</div>
      <div class="nucleus-col">
        <input type="number" class="nuc-A" value="${n.A}" step="1"
               onchange="updateNucleusA(${idx}, this.value)" placeholder="A"/>
        <div class="nucleus-field-label">A (MHz)</div>
      </div>
      ${n.I >= 1 ? `
      <div class="nucleus-col">
        <input type="number" class="nuc-Q" value="${n.Q}" step="0.1"
               onchange="updateNucleusA(${idx}, 0)" placeholder="Q"/>
        <div class="nucleus-field-label">Q (MHz)</div>
      </div>` : ''}
      <div style="font-size:0.68rem;color:var(--text-hint);font-family:'Roboto Mono',monospace;flex-shrink:0;">
        I=${n.I}
      </div>
      <button class="del-btn" onclick="removeNucleus(${idx})" title="Remove ${n.symbol}">
        <span class="material-icons-round">close</span>
      </button>
    `;
    list.appendChild(row);
  });
}

// ============================================================
// Validation badges
// ============================================================

async function refreshValidation() {
  try {
    const result = await GET('/api/validate/' + state.simulator);
    renderValidation(result.messages);
  } catch (e) {
    console.warn('Validation fetch failed:', e);
  }
}

function renderValidation(messages) {
  const area = document.getElementById('validation-area');
  if (!area) return;
  area.innerHTML = '';

  const visible = messages.filter(m => m.severity !== 'info');
  if (visible.length === 0) return;

  visible.forEach(msg => {
    const icons = { error: 'error', warning: 'warning', info: 'info' };
    const badge = document.createElement('div');
    badge.className = 'val-badge ' + msg.severity;
    badge.innerHTML = `
      <span class="material-icons-round">${icons[msg.severity] || 'info'}</span>
      <span>${msg.message}${msg.doc_url
        ? ` <a href="${msg.doc_url}" target="_blank" rel="noopener">Docs</a>`
        : ''}</span>
    `;
    area.appendChild(badge);
  });
}

// ============================================================
// Run simulation
// ============================================================

async function runSimulation() {
  const btn = document.getElementById('simulate-btn');
  const icon = document.getElementById('sim-icon');
  if (btn) { btn.disabled = true; }
  if (icon) { icon.textContent = 'refresh'; icon.classList.add('spin'); }

  const mwFreq  = parseFloat(document.getElementById('f-mwFreq')?.value || 9.5);
  const Bmin    = parseFloat(document.getElementById('f-Bmin')?.value   || 300);
  const Bmax    = parseFloat(document.getElementById('f-Bmax')?.value   || 400);
  const nPoints = parseInt(document.getElementById('f-nPoints')?.value  || 1024);
  const lvlBmin = parseFloat(document.getElementById('f-lvl-Bmin')?.value || 0);
  const lvlBmax = parseFloat(document.getElementById('f-lvl-Bmax')?.value || 400);

  try {
    // Run spectrum and levels in parallel
    const [spectrum, levelsData] = await Promise.all([
      POST('/api/simulate/spectrum', {
        mwFreq, B_min: Bmin, B_max: Bmax,
        nPoints, Harmonic: state.harmonic,
        simulator: state.simulator, nKnots: 20
      }),
      POST('/api/simulate/levels', {
        B_min: lvlBmin, B_max: lvlBmax, nPoints: 200
      }),
    ]);

    renderSpectrum(spectrum);
    renderLevels(levelsData);
    renderValidation(spectrum.validation.messages);
    updateSpectrumBadge(spectrum);
  } catch (e) {
    showToast('Simulation error: ' + e.message, 'error');
    console.error(e);
  } finally {
    if (btn) btn.disabled = false;
    if (icon) { icon.textContent = 'play_arrow'; icon.classList.remove('spin'); }
  }
}

// ============================================================
// Plotly rendering
// ============================================================

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  'transparent',
  font: { family: 'Inter, sans-serif', color: '#A0AEC0', size: 11 },
  margin: { l: 54, r: 16, t: 16, b: 48 },
  xaxis: {
    gridcolor: '#2D3055', zerolinecolor: '#2D3055',
    tickfont: { family: 'Roboto Mono, monospace', size: 10 },
  },
  yaxis: {
    gridcolor: '#2D3055', zerolinecolor: '#2D3055',
    tickfont: { family: 'Roboto Mono, monospace', size: 10 },
  },
};

const PLOTLY_CONFIG = {
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d','select2d'],
  displaylogo: false,
  responsive: true,
};

function renderSpectrum(data) {
  const trace = {
    x: data.B, y: data.spc,
    type: 'scatter', mode: 'lines',
    line: { color: '#00BCD4', width: 1.5 },
    name: data.simulator === 'garlic' ? 'garlic()' : 'pepper()',
  };
  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: { text: 'Magnetic Field (mT)', font: { size: 11 } } },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis,
      title: { text: state.harmonic === 1 ? "dI/dB" : 'Intensity', font: { size: 11 } }
    },
  };

  const el = document.getElementById('spectrum-plot');
  Plotly.react(el, [trace], layout, PLOTLY_CONFIG);
  el._plotly = true;

  // Mobile
  const mel = document.getElementById('m-spectrum-plot');
  Plotly.react(mel, [trace], { ...layout, margin: { l:44, r:8, t:8, b:40 } }, PLOTLY_CONFIG);
  mel._plotly = true;
}

function renderLevels(data) {
  const colors = ['#00BCD4','#3D5AFE','#FF5252','#FFB300','#64B5F6','#A5D6A7','#CE93D8','#FFCC80'];
  const traces = data.E.map((row, i) => ({
    x: data.B, y: row,
    type: 'scatter', mode: 'lines',
    line: { color: colors[i % colors.length], width: 1.2 },
    name: `E${i + 1}`,
  }));

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: { text: 'Magnetic Field (mT)', font: { size: 11 } } },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: { text: 'Energy (MHz)', font: { size: 11 } } },
    showlegend: false,
  };

  const el = document.getElementById('levels-plot');
  Plotly.react(el, traces, layout, PLOTLY_CONFIG);
  el._plotly = true;

  const mel = document.getElementById('m-levels-plot');
  Plotly.react(mel, traces, { ...layout, margin: { l:44, r:8, t:8, b:40 } }, PLOTLY_CONFIG);
  mel._plotly = true;
}

// ============================================================
// UI helpers
// ============================================================

function updateHsdimBadge(dim) {
  const b = document.getElementById('hsdim-badge');
  if (b) b.textContent = `dim = ${dim}`;
}

function updateSpectrumBadge(spectrum) {
  const b = document.getElementById('spectrum-badge');
  if (b) b.textContent = `${spectrum.simulator}() · ${spectrum.mwFreq} GHz`;
}

function updateSummaries(sys) {
  // Electron summary
  const g = sys.g;
  const gStr = g.length === 1 ? g[0].toFixed(4)
             : g.length === 3 ? g.map(v => v.toFixed(4)).join(', ')
             : `${g[0].toFixed(4)}…`;
  const el = document.getElementById('electron-summary');
  if (el) el.textContent = `S = ${sys.S[0]} · g = ${gStr}`;

  // Nuclei summary
  const ns = document.getElementById('nuclei-summary');
  if (ns) ns.textContent = `${sys.nNuclei} nucl${sys.nNuclei !== 1 ? 'ei' : 'eus'} · dim = ${sys.hsdim}`;

  // ZFS summary
  const zs = document.getElementById('zfs-summary');
  if (zs) {
    const D = sys.D;
    zs.textContent = D.length >= 2
      ? `D = ${D[0]} MHz · E = ${D[1]} MHz`
      : D.length === 1 ? `D = ${D[0]} MHz · E = 0`
      : 'D = 0 MHz · E = 0 MHz';
  }

  // MW summary
  const ms = document.getElementById('mw-summary');
  if (ms) {
    const mwFreq = parseFloat(document.getElementById('f-mwFreq')?.value || 9.5);
    const Bmin   = parseFloat(document.getElementById('f-Bmin')?.value   || 300);
    const Bmax   = parseFloat(document.getElementById('f-Bmax')?.value   || 400);
    ms.textContent = `${mwFreq.toFixed(2)} GHz · ${Bmin}–${Bmax} mT`;
  }
}

function showToast(message, type = 'info') {
  const t = document.createElement('div');
  t.style.cssText = `
    position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
    background:${type==='error'?'rgba(255,82,82,0.95)':'rgba(61,90,254,0.95)'};
    color:white;padding:10px 18px;border-radius:20px;font-size:0.82rem;
    font-weight:600;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.5);
    animation:fadeIn 0.2s ease;pointer-events:none;max-width:90vw;text-align:center;
  `;
  t.textContent = message;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}
