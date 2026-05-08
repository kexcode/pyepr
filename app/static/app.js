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
  initExamples();

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
  ['mobile-params','mobile-spectrum','mobile-levels','mobile-tutorial','mobile-examples'].forEach(id => {
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
  
  const examplesSrc = document.getElementById('pane-examples').innerHTML;
  document.getElementById('mobile-examples').innerHTML = examplesSrc;

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

// ============================================================
// Presets
// ============================================================

const PRESETS = [
  {
    name: 'Free electron', icon: 'bolt',
    params: { S: 0.5, g: [2.0023, 2.0023, 2.0023], D: [], nuclei: [], lw: [0.3, 0.0], simulator: "garlic", exp: { mwFreq: 9.4, Bmin: 330, Bmax: 340, nPoints: 501 } }
  },
  {
    name: '1 Proton', icon: 'filter_1',
    params: { S: 0.5, g: [2.0029, 2.0029, 2.0029], D: [], nuclei: [{ isotope: "1H", A: 1430, Q: 0 }], lw: [1, 0.0], simulator: "garlic", exp: { mwFreq: 9.4, Bmin: 200, Bmax: 450, nPoints: 5001 } }
  },
  {
    name: '2 Protons', icon: 'filter_2',
    params: { S: 0.5, g: [2.0029, 2.0029, 2.0029], D: [], nuclei: [{ isotope: "1H", A: 1430, Q: 0 }, { isotope: "1H", A: 1430, Q: 0 }], lw: [1, 0.0], simulator: "garlic", exp: { mwFreq: 9.4, Bmin: 200, Bmax: 450, nPoints: 5001 } }
  },
  {
    name: 'Nitroxide radical', icon: 'bubble_chart',
    params: { S: 0.5, g: [2.0083, 2.0061, 2.0022], D: [], nuclei: [{ isotope: "14N", A: 0, A_aniso: [11.2, 11.2, 92.4], Q: 0 }], lw: [0.5, 0.0], simulator: "pepper", exp: { mwFreq: 9.4, Bmin: 328, Bmax: 342, nPoints: 501 } }
  },
  {
    name: 'Methyl radical', icon: 'blur_on',
    params: {
      S: 0.5, g: [2.0026, 2.0026, 2.0026], D: [],
      nuclei: [{ isotope: "1H", A: -70, Q: 0 }, { isotope: "1H", A: -70, Q: 0 }, { isotope: "1H", A: -70, Q: 0 }, { isotope: "13C", A: 105, Q: 0 }],
      lw: [0.2, 0.0], simulator: "garlic", exp: { mwFreq: 9.4, Bmin: 325, Bmax: 345, nPoints: 501 }
    }
  },
  {
    name: 'Spin triplet', icon: 'grain',
    params: { S: 1.0, g: [2.0000, 2.0000, 2.0000], D: [4496.88, 749.48], nuclei: [], lw: [10, 0.0], simulator: "pepper", exp: { mwFreq: 9.4, Bmin: 0, Bmax: 600, nPoints: 2501 } }
  },
  {
    name: 'Triplet nitrene', icon: 'scatter_plot',
    params: { S: 1.0, g: [2.0033, 2.0033, 2.0033], D: [41041.59, 2788.07], nuclei: [], lw: [30, 0.0], simulator: "pepper", exp: { mwFreq: 94.0, Bmin: 0, Bmax: 6000, nPoints: 5001 } }
  },
  {
    name: 'Triplet carbene', icon: 'toll',
    params: { S: 1.0, g: [2.0033, 2.0033, 2.0033], D: [12258.51, 2788.07], nuclei: [], lw: [10, 0.0], simulator: "pepper", exp: { mwFreq: 9.4, Bmin: 0, Bmax: 1400, nPoints: 5001 } }
  },
  {
    name: 'Mn(III) ion', icon: 'lens',
    params: { S: 2.0, g: [2.0000, 2.0000, 2.0000], D: [-119317.40, 0], nuclei: [], lw: [80, 0.0], simulator: "pepper", exp: { mwFreq: 240.0, Bmin: 0, Bmax: 12000, nPoints: 2501 } }
  },
  {
    name: 'Fe(III) ion', icon: 'brightness_1',
    params: { S: 2.5, g: [2.0000, 2.0000, 2.0000], D: [149896.23, 0], nuclei: [], lw: [20, 0.0], simulator: "pepper", exp: { mwFreq: 9.4, Bmin: 0, Bmax: 400, nPoints: 2501 } }
  }
];

function initExamples() {
  const grid = document.getElementById('examples-grid');
  if (!grid) return;
  grid.innerHTML = '';
  PRESETS.forEach((preset, idx) => {
    const btn = document.createElement('button');
    btn.style.cssText = `
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius-md);
      padding: 16px 8px; cursor: pointer; transition: var(--transition);
      color: var(--text); gap: 8px;
    `;
    btn.onmouseover = () => { btn.style.borderColor = 'var(--primary)'; btn.style.background = 'rgba(0,188,212,0.05)'; };
    btn.onmouseout = () => { btn.style.borderColor = 'var(--border)'; btn.style.background = 'var(--surface2)'; };
    btn.innerHTML = `
      <span class="material-icons-round" style="font-size: 32px; color: var(--accent); opacity: 0.8;">${preset.icon}</span>
      <span style="font-size: 0.78rem; font-weight: 500; text-align: center;">${preset.name}</span>
    `;
    btn.onclick = async () => {
      showToast('Loading preset: ' + preset.name);
      await loadPreset(idx);
    };
    grid.appendChild(btn);
  });
}

async function loadPreset(idx) {
  const p = PRESETS[idx];
  
  if(document.getElementById('f-S')) document.getElementById('f-S').value = p.params.S;
  if(document.getElementById('f-gx')) document.getElementById('f-gx').value = p.params.g[0].toFixed(4);
  if(document.getElementById('f-gy')) document.getElementById('f-gy').value = p.params.g[1].toFixed(4);
  if(document.getElementById('f-gz')) document.getElementById('f-gz').value = (p.params.g[2] || p.params.g[0]).toFixed(4);
  if(document.getElementById('f-D')) document.getElementById('f-D').value = (p.params.D[0] || 0).toFixed(2);
  if(document.getElementById('f-E')) document.getElementById('f-E').value = (p.params.D[1] || 0).toFixed(2);
  if(document.getElementById('f-lG')) document.getElementById('f-lG').value = (p.params.lw[0] || 0).toFixed(2);
  if(document.getElementById('f-lL')) document.getElementById('f-lL').value = (p.params.lw[1] || 0).toFixed(2);
  
  if(document.getElementById('f-mwFreq')) document.getElementById('f-mwFreq').value = p.params.exp.mwFreq;
  if(document.getElementById('f-Bmin')) document.getElementById('f-Bmin').value = p.params.exp.Bmin;
  if(document.getElementById('f-Bmax')) document.getElementById('f-Bmax').value = p.params.exp.Bmax;
  if(document.getElementById('f-nPoints')) document.getElementById('f-nPoints').value = p.params.exp.nPoints;

  setSimulator(p.params.simulator);

  try {
    await PUT('/api/system', {
      S: p.params.S,
      g: p.params.g,
      D: p.params.D,
      lw: p.params.lw,
      tcorr: null
    });
    
    await DELETE('/api/system/nuclei');
    
    for (const n of p.params.nuclei) {
      await POST('/api/system/nuclei', {
        symbol: n.isotope,
        A: n.A,
        A_aniso: n.A_aniso || null,
        Q: n.Q || 0,
        label: null
      });
    }
    
    await refreshSystem();
    const tabParams = document.getElementById('tab-params');
    if (tabParams) tabParams.click();
    showToast(p.name + ' loaded successfully!', 'success');
  } catch (e) {
    showToast('Failed to load preset: ' + e.message, 'error');
  }
}

