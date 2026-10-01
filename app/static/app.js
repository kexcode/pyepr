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
  method: 'matrix',
  singleOrientation: false,
  theta: 0.0,
  phi: 0.0,
  systemState: null,
};

function setModel(method, triggerSim = true) {
  state.method = method;
  ['matrix', 'perturb2'].forEach(m => {
    const btn = document.getElementById('btn-model-' + m);
    if (btn) btn.classList.toggle('active', m === method);
  });
  const summaryEl = document.getElementById('model-summary');
  if (summaryEl) {
    if (method === 'matrix') summaryEl.textContent = 'Matrix diagonalization (exact)';
    else summaryEl.textContent = 'Perturbation (2nd order)';
  }
  updateOptionsSummary();
  // Re-run simulation with the new model if requested
  if (triggerSim) {
    runSimulation();
  }
}

function toggleSingleOrientation(active) {
  state.singleOrientation = active;
  const ctrl = document.getElementById('ori-controls');
  if (ctrl) ctrl.style.display = active ? 'block' : 'none';
  updateOrientationSummary();
  runSimulation();
}

function updateOrientationSummary() {
  const sumEl = document.getElementById('ori-summary');
  if (!sumEl) return;
  if (!state.singleOrientation) {
    sumEl.textContent = 'Powder average';
  } else {
    sumEl.textContent = `Single: θ=${state.theta}°, φ=${state.phi}°`;
  }
}

function updateOrientationPresetButtons(activePreset) {
  ['x', 'y', 'z', 'rnd'].forEach(k => {
    const btn = document.getElementById('btn-ori-' + k);
    if (!btn) return;
    if (activePreset === 'X' && k === 'x') btn.classList.add('active');
    else if (activePreset === 'Y' && k === 'y') btn.classList.add('active');
    else if (activePreset === 'Z' && k === 'z') btn.classList.add('active');
    else if (activePreset === 'random' && k === 'rnd') btn.classList.add('active');
    else btn.classList.remove('active');
  });
}

function setOrientationPreset(preset) {
  if (preset === 'X') {
    state.theta = 90.0;
    state.phi = 0.0;
  } else if (preset === 'Y') {
    state.theta = 90.0;
    state.phi = 90.0;
  } else if (preset === 'Z') {
    state.theta = 0.0;
    state.phi = 0.0;
  } else if (preset === 'random') {
    // Uniform spherical sampling
    const u = Math.random();
    state.theta = Math.round(Math.acos(2 * u - 1) * (180 / Math.PI) * 10) / 10;
    state.phi = Math.round(Math.random() * 360 * 10) / 10;
  }
  const tEl = document.getElementById('f-theta');
  const pEl = document.getElementById('f-phi');
  if (tEl) tEl.value = state.theta;
  if (pEl) pEl.value = state.phi;

  updateOrientationPresetButtons(preset);
  updateOrientationSummary();
  runSimulation();
}

let _oriDebounceTimer = null;
function onOrientationInputChange(immediate = false) {
  const tEl = document.getElementById('f-theta');
  const pEl = document.getElementById('f-phi');
  const theta = parseFloat(tEl?.value || 0.0);
  const phi = parseFloat(pEl?.value || 0.0);
  state.theta = theta;
  state.phi = phi;

  // Update preset highlights if matching
  if (theta === 90 && phi === 0) updateOrientationPresetButtons('X');
  else if (theta === 90 && phi === 90) updateOrientationPresetButtons('Y');
  else if (theta === 0 && phi === 0) updateOrientationPresetButtons('Z');
  else updateOrientationPresetButtons('');

  updateOrientationSummary();

  clearTimeout(_oriDebounceTimer);
  if (immediate) {
    runSimulation();
  } else {
    _oriDebounceTimer = setTimeout(runSimulation, 350);
  }
}

// ============================================================
// API helpers
// ============================================================

async function api(method, path, body, signal = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  if (signal) opts.signal = signal;
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || res.statusText);
  }
  return res.json();
}

const GET    = (path, signal)        => api('GET',    path, undefined, signal);
const PUT    = (path, body, signal)  => api('PUT',    path, body, signal);
const POST   = (path, body, signal)  => api('POST',   path, body, signal);
const DELETE = (path, signal)        => api('DELETE', path, undefined, signal);

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
    sim === 'garlic' ? 'garlic — liquid state' : 'pepper — powder/solid';

  // Toggle orientation card: only visible for solid state pepper
  const oriCard = document.getElementById('card-orientation');
  if (oriCard) {
    oriCard.style.display = (sim === 'pepper') ? '' : 'none';
  }

  refreshValidation();
}

// ============================================================
// Detection mode
// ============================================================

function setHarmonic(h) {
  state.harmonic = h;
  const btnAbs = document.getElementById('btn-absorption');
  const btnDer = document.getElementById('btn-derivative');
  if (btnAbs) btnAbs.classList.toggle('active', h === 0);
  if (btnDer) btnDer.classList.toggle('active', h === 1);
  const sumEl = document.getElementById('detection-summary');
  if (sumEl) sumEl.textContent = (h === 0) ? 'Absorption' : '1st Derivative (modulated)';
  if (state.currentSpectrumData) {
    renderSpectrum(state.currentSpectrumData);
  }
}

// ============================================================
// Input listeners — push changes to API on blur
// ============================================================

function bindInputListeners() {
  const push = () => pushSystemParams();
  ['f-S','f-gx','f-gy','f-gz','f-D','f-E','f-lG','f-lL'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', push);
  });

  // Active Bmin/Bmax/nPoints listeners for immediate plot adjustment
  bindActiveFieldListeners();

  // Orientation angle inputs
  const thetaEl = document.getElementById('f-theta');
  const phiEl = document.getElementById('f-phi');
  [thetaEl, phiEl].forEach(el => {
    if (!el) return;
    el.addEventListener('input', () => onOrientationInputChange(false));
    el.addEventListener('change', () => onOrientationInputChange(true));
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        onOrientationInputChange(true);
      }
    });
  });
}

let _spectrumDebounceTimer = null;
let _levelsDebounceTimer = null;

function onMwFreqDropdownChange(val) {
  if (!val) return;
  const mwInput = document.getElementById('f-mwFreq');
  if (mwInput) {
    mwInput.value = val;
    onFieldParamsChange(true);
  }
}

function syncMwFreqDropdown() {
  const inputVal = parseFloat(document.getElementById('f-mwFreq')?.value);
  const select = document.getElementById('f-mwFreq-dropdown');
  if (!select || isNaN(inputVal)) return;
  const standard = ['3.4', '9.4', '34', '94', '120', '240', '360', '1000'];
  const match = standard.find(s => Math.abs(parseFloat(s) - inputVal) < 1e-4);
  select.value = match ? match : '';
}

function updateOptionsSummary() {
  const sumEl = document.getElementById('options-summary');
  if (!sumEl) return;
  const methodLabel = state.method === 'perturb2' ? 'Perturb 2nd' : 'Matrix';
  const gridSize = document.getElementById('f-gridSize')?.value || 20;
  const nPoints = document.getElementById('f-nPoints')?.value || 1024;
  sumEl.textContent = `${methodLabel} · Grid ${gridSize} · ${nPoints} pts`;
}

function updateMwSummary() {
  syncMwFreqDropdown();
  const ms = document.getElementById('mw-summary');
  if (!ms) return;
  const mwFreq = parseFloat(document.getElementById('f-mwFreq')?.value || 9.4);
  const Bmin = parseFloat(document.getElementById('f-Bmin')?.value || 300);
  const Bmax = parseFloat(document.getElementById('f-Bmax')?.value || 400);
  const tempInput = document.getElementById('f-temperature');
  const tempVal = tempInput && tempInput.value !== '' ? parseFloat(tempInput.value) : null;
  const freqStr = mwFreq >= 1000 ? `${(mwFreq / 1000).toFixed(1)} THz (${mwFreq} GHz)` : `${mwFreq.toFixed(2)} GHz`;
  const tempStr = tempVal != null && !isNaN(tempVal) ? ` · ${tempVal} K` : '';
  ms.textContent = `${freqStr}${tempStr} · ${Bmin}–${Bmax} mT`;
}

function onFieldParamsChange(immediate = false) {
  const Bmin = parseFloat(document.getElementById('f-Bmin')?.value || 300);
  const Bmax = parseFloat(document.getElementById('f-Bmax')?.value || 400);

  syncMwFreqDropdown();
  updateMwSummary();
  updateOptionsSummary();

  if (Bmin >= Bmax) return;

  clearTimeout(_spectrumDebounceTimer);
  if (immediate) {
    simulateSpectrumOnly();
  } else {
    _spectrumDebounceTimer = setTimeout(simulateSpectrumOnly, 350);
  }
}

function onLevelsFieldChange(immediate = false) {
  const lvlBmin = parseFloat(document.getElementById('f-lvl-Bmin')?.value || 0);
  const lvlBmax = parseFloat(document.getElementById('f-lvl-Bmax')?.value || 400);

  const lvlSummary = document.getElementById('levels-summary');
  if (lvlSummary) lvlSummary.textContent = `${lvlBmin}–${lvlBmax} mT · 200 pts`;

  if (lvlBmin >= lvlBmax) return;

  clearTimeout(_levelsDebounceTimer);
  if (immediate) {
    simulateLevelsOnly();
  } else {
    _levelsDebounceTimer = setTimeout(simulateLevelsOnly, 350);
  }
}

function bindActiveFieldListeners() {
  const bminEl = document.getElementById('f-Bmin');
  const bmaxEl = document.getElementById('f-Bmax');
  const mwFreqEl = document.getElementById('f-mwFreq');
  const tempEl = document.getElementById('f-temperature');
  const nPointsEl = document.getElementById('f-nPoints');
  const gridSizeEl = document.getElementById('f-gridSize');

  [bminEl, bmaxEl, mwFreqEl, tempEl, nPointsEl, gridSizeEl].forEach(el => {
    if (!el) return;
    el.addEventListener('input', () => onFieldParamsChange(false));
    el.addEventListener('change', () => onFieldParamsChange(true));
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        onFieldParamsChange(true);
      }
    });
  });

  const lvlBminEl = document.getElementById('f-lvl-Bmin');
  const lvlBmaxEl = document.getElementById('f-lvl-Bmax');

  [lvlBminEl, lvlBmaxEl].forEach(el => {
    if (!el) return;
    el.addEventListener('input', () => onLevelsFieldChange(false));
    el.addEventListener('change', () => onLevelsFieldChange(true));
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        onLevelsFieldChange(true);
      }
    });
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

let _nucleusTimer = null;
function onNucleusInput(idx, immediate = false) {
  clearTimeout(_nucleusTimer);
  if (immediate) {
    saveNucleusParams(idx);
  } else {
    _nucleusTimer = setTimeout(() => saveNucleusParams(idx), 400);
  }
}

async function saveNucleusParams(idx) {
  const tile = document.getElementById(`nucleus-tile-${idx}`);
  if (!tile || !state.systemState || !state.systemState.nuclei[idx]) return;

  const Ax = parseFloat(tile.querySelector('.nuc-Ax')?.value || 0);
  const Ay = parseFloat(tile.querySelector('.nuc-Ay')?.value || 0);
  const Az = parseFloat(tile.querySelector('.nuc-Az')?.value || 0);

  const Qx = parseFloat(tile.querySelector('.nuc-Qx')?.value || 0);
  const Qy = parseFloat(tile.querySelector('.nuc-Qy')?.value || 0);
  const Qz = parseFloat(tile.querySelector('.nuc-Qz')?.value || 0);

  const sym = state.systemState.nuclei[idx].symbol;
  const A_iso = (Ax + Ay + Az) / 3.0;
  const Q_scalar = Qz;

  try {
    state.systemState = await PUT(`/api/system/nuclei/${idx}`, {
      symbol: sym,
      A: A_iso,
      A_aniso: [Ax, Ay, Az],
      Q: Q_scalar,
      Q_aniso: [Qx, Qy, Qz],
      label: null
    });
    updateSummaries(state.systemState);
    updateHsdimBadge(state.systemState.hsdim);
    await refreshValidation();
    runSimulation();
  } catch (e) {
    console.error('Failed to update nucleus:', e);
  }
}

function renderNucleiList(nuclei) {
  const list = document.getElementById('nuclei-list');
  if (!list) return;
  list.innerHTML = '';
  if (!nuclei || nuclei.length === 0) {
    list.innerHTML = '<div style="color:var(--text-hint);font-size:0.78rem;text-align:center;padding:12px 8px;border:1.5px dashed var(--border);border-radius:var(--radius-sm);">No nuclei added</div>';
    return;
  }
  nuclei.forEach((n, idx) => {
    const Ax = n.A_aniso && n.A_aniso.length >= 1 ? n.A_aniso[0] : (n.A || 0);
    const Ay = n.A_aniso && n.A_aniso.length >= 2 ? n.A_aniso[1] : (n.A || 0);
    const Az = n.A_aniso && n.A_aniso.length >= 3 ? n.A_aniso[2] : (n.A || 0);

    const Qx = n.Q_aniso && n.Q_aniso.length >= 1 ? n.Q_aniso[0] : (n.I >= 1 ? -Math.round(n.Q / 3.0 * 100) / 100 : 0);
    const Qy = n.Q_aniso && n.Q_aniso.length >= 2 ? n.Q_aniso[1] : (n.I >= 1 ? -Math.round(n.Q / 3.0 * 100) / 100 : 0);
    const Qz = n.Q_aniso && n.Q_aniso.length >= 3 ? n.Q_aniso[2] : (n.I >= 1 ? Math.round(2.0 * n.Q / 3.0 * 100) / 100 : 0);

    const tile = document.createElement('div');
    tile.className = 'nucleus-tile';
    tile.id = `nucleus-tile-${idx}`;
    tile.innerHTML = `
      <div class="nucleus-tile-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <div class="nucleus-chip">${n.symbol}</div>
          <span class="nucleus-badge-meta">I = ${n.I}</span>
          <span class="nucleus-badge-meta">gₙ = ${n.gn.toFixed(4)}</span>
        </div>
        <button class="del-btn" onclick="removeNucleus(${idx})" title="Remove ${n.symbol}">
          <span class="material-icons-round">close</span>
        </button>
      </div>

      <div class="field-group">
        <label class="field-label" data-tip="Hyperfine tensor principal values: Ax, Ay, Az in MHz">A-Tensor (Ax, Ay, Az in MHz)</label>
        <div class="field-row">
          <div class="field-group">
            <input type="number" class="nuc-Ax" value="${Ax}" step="1"
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Ax</div>
          </div>
          <div class="field-group">
            <input type="number" class="nuc-Ay" value="${Ay}" step="1"
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Ay</div>
          </div>
          <div class="field-group">
            <input type="number" class="nuc-Az" value="${Az}" step="1"
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Az</div>
          </div>
        </div>
      </div>

      <div class="field-group">
        <div style="display:flex; align-items:center; justify-content:space-between;">
          <label class="field-label" data-tip="Nuclear quadrupole tensor: Qx, Qy, Qz in MHz">Q-Tensor (Qx, Qy, Qz in MHz)</label>
          ${n.I < 1 ? '<span style="font-size:0.62rem; color:var(--text-hint); font-style:italic;">N/A (I < 1)</span>' : ''}
        </div>
        <div class="field-row">
          <div class="field-group">
            <input type="number" class="nuc-Qx" value="${Qx}" step="0.1"
                   ${n.I < 1 ? 'disabled style="opacity:0.45;"' : ''}
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Qx</div>
          </div>
          <div class="field-group">
            <input type="number" class="nuc-Qy" value="${Qy}" step="0.1"
                   ${n.I < 1 ? 'disabled style="opacity:0.45;"' : ''}
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Qy</div>
          </div>
          <div class="field-group">
            <input type="number" class="nuc-Qz" value="${Qz}" step="0.1"
                   ${n.I < 1 ? 'disabled style="opacity:0.45;"' : ''}
                   oninput="onNucleusInput(${idx}, false)" onchange="onNucleusInput(${idx}, true)"/>
            <div class="nucleus-field-label">Qz</div>
          </div>
        </div>
      </div>
    `;
    list.appendChild(tile);
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

async function simulateSpectrumOnly() {
  const mwFreq  = parseFloat(document.getElementById('f-mwFreq')?.value || 9.4);
  const Bmin    = parseFloat(document.getElementById('f-Bmin')?.value   || 300);
  const Bmax    = parseFloat(document.getElementById('f-Bmax')?.value   || 400);
  const nPoints = parseInt(document.getElementById('f-nPoints')?.value  || 1024);
  const gridSize = parseInt(document.getElementById('f-gridSize')?.value || 20);
  const tempEl = document.getElementById('f-temperature');
  const temperature = tempEl && tempEl.value !== '' && !isNaN(parseFloat(tempEl.value))
    ? parseFloat(tempEl.value)
    : null;

  if (Bmin >= Bmax) return;

  const isSingle = state.simulator === 'pepper' && state.singleOrientation;
  try {
    const spectrum = await POST('/api/simulate/spectrum', {
      mwFreq, B_min: Bmin, B_max: Bmax,
      nPoints, Harmonic: state.harmonic,
      simulator: state.simulator,
      method: state.method,
      nKnots: gridSize,
      gridSize: gridSize,
      Temperature: temperature,
      singleOrientation: isSingle,
      orientation: [state.theta, state.phi]
    });
    renderSpectrum(spectrum);
    updateSpectrumBadge(spectrum);
  } catch (e) {
    console.warn('Spectrum update failed:', e);
  }
}

async function simulateLevelsOnly() {
  const mwFreq  = parseFloat(document.getElementById('f-mwFreq')?.value || 9.4);
  const lvlBmin = parseFloat(document.getElementById('f-lvl-Bmin')?.value || 0);
  const lvlBmax = parseFloat(document.getElementById('f-lvl-Bmax')?.value || 400);

  if (lvlBmin >= lvlBmax) return;

  const isSingle = state.simulator === 'pepper' && state.singleOrientation;
  const ori = isSingle ? [state.theta, state.phi] : [0.0, 0.0];

  try {
    const levelsData = await POST('/api/simulate/levels', {
      B_min: lvlBmin, B_max: lvlBmax, nPoints: 200,
      method: state.method,
      mwFreq: mwFreq,
      orientation: ori,
    });
    renderLevels(levelsData);
  } catch (e) {
    console.warn('Levels update failed:', e);
  }
}

let _isSimulating = false;
let _simulationAbortController = null;

function onSimulateBtnClick() {
  if (_isSimulating) {
    abortSimulation();
  } else {
    runSimulation();
  }
}

async function abortSimulation() {
  if (!_isSimulating) return;
  if (_simulationAbortController) {
    _simulationAbortController.abort();
    _simulationAbortController = null;
  }
  try {
    fetch('/api/simulate/cancel', { method: 'POST' }).catch(() => {});
  } catch (e) {}

  setSimulationButtonState(false);
  showToast('Simulation stopped', 'info');
}

function setSimulationButtonState(isBusy) {
  _isSimulating = isBusy;
  const btn = document.getElementById('simulate-btn');
  const icon = document.getElementById('sim-icon');
  const text = document.getElementById('sim-text');

  if (isBusy) {
    if (btn) {
      btn.disabled = false;
      btn.classList.add('break-mode');
    }
    if (icon) {
      icon.textContent = 'stop';
      icon.classList.remove('spin');
    }
    if (text) {
      text.textContent = 'Break';
    }
  } else {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('break-mode');
    }
    if (icon) {
      icon.textContent = 'play_arrow';
      icon.classList.remove('spin');
    }
    if (text) {
      text.textContent = 'Simulate';
    }
  }
}

async function runSimulation() {
  if (_isSimulating) {
    abortSimulation();
    return;
  }

  _simulationAbortController = new AbortController();
  const signal = _simulationAbortController.signal;
  setSimulationButtonState(true);

  const mwFreq  = parseFloat(document.getElementById('f-mwFreq')?.value || 9.4);
  const Bmin    = parseFloat(document.getElementById('f-Bmin')?.value   || 300);
  const Bmax    = parseFloat(document.getElementById('f-Bmax')?.value   || 400);
  const nPoints = parseInt(document.getElementById('f-nPoints')?.value  || 1024);
  const gridSize = parseInt(document.getElementById('f-gridSize')?.value || 20);
  const tempEl = document.getElementById('f-temperature');
  const temperature = tempEl && tempEl.value !== '' && !isNaN(parseFloat(tempEl.value))
    ? parseFloat(tempEl.value)
    : null;
  const lvlBmin = parseFloat(document.getElementById('f-lvl-Bmin')?.value || 0);
  const lvlBmax = parseFloat(document.getElementById('f-lvl-Bmax')?.value || 400);

  const isSingle = state.simulator === 'pepper' && state.singleOrientation;
  const ori = isSingle ? [state.theta, state.phi] : [0.0, 0.0];

  try {
    // Run spectrum and levels in parallel
    const [spectrum, levelsData] = await Promise.all([
      POST('/api/simulate/spectrum', {
        mwFreq, B_min: Bmin, B_max: Bmax,
        nPoints, Harmonic: state.harmonic,
        simulator: state.simulator,
        method: state.method,
        nKnots: gridSize,
        gridSize: gridSize,
        Temperature: temperature,
        singleOrientation: isSingle,
        orientation: [state.theta, state.phi]
      }, signal),
      POST('/api/simulate/levels', {
        B_min: lvlBmin, B_max: lvlBmax, nPoints: 200,
        method: state.method,
        mwFreq: mwFreq,
        orientation: ori,
      }, signal),
    ]);

    renderSpectrum(spectrum);
    renderLevels(levelsData);
    renderValidation(spectrum.validation.messages);
    updateSpectrumBadge(spectrum);
  } catch (e) {
    if (e.name === 'AbortError' || e.message?.includes('cancelled')) {
      console.log('Simulation stopped by user.');
    } else {
      showToast('Simulation error: ' + e.message, 'error');
      console.error(e);
    }
  } finally {
    setSimulationButtonState(false);
  }
}

// ============================================================
// Plotly rendering
// ============================================================

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  'transparent',
  font: { family: 'Inter, sans-serif', color: '#CBD5E1', size: 11 },
  margin: { l: 54, r: 16, t: 16, b: 48 },
  xaxis: {
    gridcolor: '#334155', zerolinecolor: '#475569',
    tickfont: { family: 'Roboto Mono, monospace', size: 10, color: '#CBD5E1' },
  },
  yaxis: {
    gridcolor: '#334155', zerolinecolor: '#475569',
    tickfont: { family: 'Roboto Mono, monospace', size: 10, color: '#CBD5E1' },
  },
};

const PLOTLY_CONFIG = {
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d','select2d'],
  displaylogo: false,
  responsive: true,
};

function renderSpectrum(data) {
  state.currentSpectrumData = data;
  const yData = (state.harmonic === 0 && data.spc_abs)
    ? data.spc_abs
    : (data.spc_deriv || data.spc);

  const methodLabel = state.method === 'matrix' ? 'matrix' : 'perturb 2nd';
  const simName = data.simulator || state.simulator;
  const oriLabel = (simName === 'pepper' && state.singleOrientation)
    ? ` [θ=${state.theta}°, φ=${state.phi}°]`
    : '';
  const trace = {
    x: data.B, y: yData,
    type: 'scatter', mode: 'lines',
    line: { color: '#00E5FF', width: 1.8 },
    name: `${simName}() [${methodLabel}]${oriLabel}`,
  };
  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: { text: 'Magnetic Field (mT)', font: { size: 11, color: '#CBD5E1' } } },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis,
      title: { text: state.harmonic === 1 ? "dI/dB" : 'Intensity', font: { size: 11, color: '#CBD5E1' } }
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
  // Okabe-Ito universal colorblind-safe palette (Wong, Nature Methods 2011)
  const OKABE_ITO = [
    '#56B4E9', // Sky blue
    '#E69F00', // Orange
    '#009E73', // Bluish green
    '#F0E442', // Yellow
    '#0072B2', // Dark blue
    '#D55E00', // Vermilion
    '#CC79A7', // Reddish purple
    '#E2E8F0', // Off-white / light silver
  ];
  const traces = data.E.map((row, i) => ({
    x: data.B, y: row,
    type: 'scatter', mode: 'lines',
    line: { color: OKABE_ITO[i % OKABE_ITO.length], width: 1.5 },
    name: `E${i + 1}`,
    hoverinfo: 'x+y+name',
  }));

  // Render EPR transitions with high-contrast electric gold (#FFD600)
  // Contrast ratio > 10:1 on dark background, fully distinguishable across protanopia, deuteranopia, tritanopia
  if (data.transitions && data.transitions.length > 0) {
    data.transitions.forEach((t) => {
      const probPercent = (t.intensity * 100).toFixed(1);
      const deltaE = (t.E_upper - t.E_lower).toFixed(1);
      const opacity = Math.max(0.35, Math.min(1.0, t.intensity));
      const width = 1.4 + 3.0 * t.intensity;

      traces.push({
        x: [t.B_res, t.B_res],
        y: [t.E_lower, t.E_upper],
        type: 'scatter',
        mode: 'lines+markers',
        marker: {
          size: [4 + 4 * t.intensity, 4 + 4 * t.intensity],
          color: `rgba(255, 214, 0, ${opacity.toFixed(2)})`,
          symbol: 'circle',
          line: { color: '#FFFFFF', width: 0.5 },
        },
        line: {
          color: `rgba(255, 214, 0, ${opacity.toFixed(2)})`,
          width: width,
        },
        name: `Transition E${t.lower_idx + 1}&rarr;E${t.upper_idx + 1}`,
        hoverinfo: 'text',
        text: `EPR Transition: E${t.lower_idx + 1} &rarr; E${t.upper_idx + 1}<br>` +
              `Resonance Field: ${t.B_res.toFixed(2)} mT<br>` +
              `&Delta;E: ${deltaE} MHz (${(deltaE / 1000).toFixed(3)} GHz)<br>` +
              `Transition Probability: ${probPercent}%`,
        showlegend: false,
      });
    });
  }

  const layout = {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: { text: 'Magnetic Field (mT)', font: { size: 11, color: '#CBD5E1' } } },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: { text: 'Energy (MHz)', font: { size: 11, color: '#CBD5E1' } } },
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

  // MW & Options summaries
  updateMwSummary();
  updateOptionsSummary();
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
    name: 'Free electron',
    icon: 'adjust',
    badge: 'e⁻',
    desc: 'S = 1/2 · Free spin · g = 2.0023',
    color: '#00BCD4',
    params: { S: 0.5, g: [2.0023, 2.0023, 2.0023], D: [], nuclei: [], lw: [0.3, 0.0], simulator: "garlic", method: "matrix", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 330, Bmax: 340, nPoints: 501, temperature: null } }
  },
  {
    name: '1 Proton',
    icon: 'hdr_strong',
    badge: '¹H',
    desc: 'I = 1/2 · Atomic hydrogen doublet',
    color: '#00E5FF',
    params: { S: 0.5, g: [2.0029, 2.0029, 2.0029], D: [], nuclei: [{ isotope: "1H", A: 1430, A_aniso: [1430, 1430, 1430], Q: 0, Q_aniso: [0, 0, 0] }], lw: [1, 0.0], simulator: "garlic", method: "perturb2", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 200, Bmax: 450, nPoints: 5001, temperature: null } }
  },
  {
    name: '2 Protons',
    icon: 'join_inner',
    badge: '2× ¹H',
    desc: 'Two equivalent protons · 1:2:1 Triplet',
    color: '#3D5AFE',
    params: { S: 0.5, g: [2.0029, 2.0029, 2.0029], D: [], nuclei: [{ isotope: "1H", A: 1430, A_aniso: [1430, 1430, 1430], Q: 0, Q_aniso: [0, 0, 0] }, { isotope: "1H", A: 1430, A_aniso: [1430, 1430, 1430], Q: 0, Q_aniso: [0, 0, 0] }], lw: [1, 0.0], simulator: "garlic", method: "matrix", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 200, Bmax: 450, nPoints: 5001, temperature: null } }
  },
  {
    name: 'Nitroxide radical',
    icon: 'biotech',
    badge: 'R₂NO•',
    desc: '¹⁴N (I = 1) aminoxyl · 1:1:1 Triplet',
    color: '#FF4081',
    params: { S: 0.5, g: [2.0083, 2.0061, 2.0022], D: [], nuclei: [{ isotope: "14N", A: 38.27, A_aniso: [11.2, 11.2, 92.4], Q: 0, Q_aniso: [0, 0, 0] }], lw: [0.5, 0.0], simulator: "pepper", method: "perturb2", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 328, Bmax: 342, nPoints: 501, temperature: null } }
  },
  {
    name: 'Methyl radical',
    icon: 'hub',
    badge: '•CH₃',
    desc: 'Planar carbon radical · 1:3:3:1 Quartet',
    color: '#00E676',
    params: {
      S: 0.5, g: [2.0026, 2.0026, 2.0026], D: [],
      nuclei: [
        { isotope: "1H", A: -70, A_aniso: [-70, -70, -70], Q: 0, Q_aniso: [0, 0, 0] },
        { isotope: "1H", A: -70, A_aniso: [-70, -70, -70], Q: 0, Q_aniso: [0, 0, 0] },
        { isotope: "1H", A: -70, A_aniso: [-70, -70, -70], Q: 0, Q_aniso: [0, 0, 0] },
        { isotope: "13C", A: 105, A_aniso: [105, 105, 105], Q: 0, Q_aniso: [0, 0, 0] }
      ],
      lw: [0.2, 0.0], simulator: "garlic", method: "perturb2", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 325, Bmax: 345, nPoints: 501, temperature: null }
    }
  },
  {
    name: 'Spin triplet',
    icon: 'height',
    badge: 'S = 1',
    desc: 'Parallel spins ↑↑ · Axial & rhombic ZFS',
    color: '#7C4DFF',
    params: { S: 1.0, g: [2.0000, 2.0000, 2.0000], D: [4496.88, 749.48], nuclei: [], lw: [10, 0.0], simulator: "pepper", method: "matrix", gridSize: 23, exp: { mwFreq: 9.4, Bmin: 0, Bmax: 600, nPoints: 2501, temperature: null } }
  },
  {
    name: 'Triplet nitrene',
    icon: 'whatshot',
    badge: 'R–N:',
    desc: 'High-field 94 GHz · Large axial ZFS',
    color: '#FF6E40',
    params: { S: 1.0, g: [2.0033, 2.0033, 2.0033], D: [41041.59, 2788.07], nuclei: [], lw: [30, 0.0], simulator: "pepper", method: "matrix", gridSize: 17, exp: { mwFreq: 94.0, Bmin: 0, Bmax: 6000, nPoints: 5001, temperature: null } }
  },
  {
    name: 'Triplet carbene',
    icon: 'diamond',
    badge: 'R₂C:',
    desc: 'Divalent carbene · Rhombic ZFS',
    color: '#E040FB',
    params: { S: 1.0, g: [2.0033, 2.0033, 2.0033], D: [12258.51, 2788.07], nuclei: [], lw: [10, 0.0], simulator: "pepper", method: "matrix", gridSize: 17, exp: { mwFreq: 9.4, Bmin: 0, Bmax: 1400, nPoints: 5001, temperature: null } }
  },
  {
    name: 'Mn(III) ion',
    icon: 'hexagon',
    badge: 'Mn³⁺',
    desc: 'High-spin d⁴ (S = 2) · Negative ZFS',
    color: '#FFAB00',
    params: { S: 2.0, g: [2.0000, 2.0000, 2.0000], D: [-119317.40, 0], nuclei: [], lw: [80, 0.0], simulator: "pepper", method: "matrix", gridSize: 201, exp: { mwFreq: 240.0, Bmin: 0, Bmax: 12000, nPoints: 2501, temperature: 5 } }
  },
  {
    name: 'Fe(III) ion',
    icon: 'star',
    badge: 'Fe³⁺',
    desc: 'High-spin d⁵ (S = 5/2) · Huge ZFS',
    color: '#FF5252',
    params: { S: 2.5, g: [2.0000, 2.0000, 2.0000], D: [149896.23, 0], nuclei: [], lw: [20, 0.0], simulator: "pepper", method: "matrix", gridSize: 30, exp: { mwFreq: 9.4, Bmin: 0, Bmax: 400, nPoints: 2501, temperature: 5 } }
  }
];

function initExamples() {
  const grid = document.getElementById('examples-grid');
  if (!grid) return;
  grid.innerHTML = '';
  PRESETS.forEach((preset, idx) => {
    const btn = document.createElement('button');
    btn.style.cssText = `
      display: flex; flex-direction: column; align-items: flex-start; justify-content: space-between;
      background: var(--surface2); border: 1.5px solid var(--border); border-radius: var(--radius-md);
      padding: 12px 10px; cursor: pointer; transition: var(--transition);
      color: var(--text); gap: 8px; width: 100%; box-sizing: border-box; text-align: left;
    `;
    btn.onmouseover = () => {
      btn.style.borderColor = preset.color || 'var(--primary)';
      btn.style.background = 'rgba(255,255,255,0.04)';
      btn.style.transform = 'translateY(-2px)';
    };
    btn.onmouseout = () => {
      btn.style.borderColor = 'var(--border)';
      btn.style.background = 'var(--surface2)';
      btn.style.transform = 'none';
    };
    btn.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
        <span class="material-icons-round" style="font-size: 26px; color: ${preset.color || 'var(--accent)'};">${preset.icon}</span>
        <span class="preset-badge" style="background:${preset.color}22; color:${preset.color}">${preset.badge}</span>
      </div>
      <div>
        <div style="font-size: 0.80rem; font-weight: 700; color: var(--text); margin-bottom: 2px;">${preset.name}</div>
        <div style="font-size: 0.66rem; color: var(--text-hint); line-height: 1.3;">${preset.desc}</div>
      </div>
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
  syncMwFreqDropdown();
  const tempInput = document.getElementById('f-temperature');
  if(tempInput) tempInput.value = (p.params.exp.temperature != null) ? p.params.exp.temperature : '';
  if(document.getElementById('f-Bmin')) document.getElementById('f-Bmin').value = p.params.exp.Bmin;
  if(document.getElementById('f-Bmax')) document.getElementById('f-Bmax').value = p.params.exp.Bmax;
  if(document.getElementById('f-nPoints')) document.getElementById('f-nPoints').value = p.params.exp.nPoints;
  if(document.getElementById('f-gridSize')) document.getElementById('f-gridSize').value = (p.params.opt && p.params.opt.GridSize) || p.params.gridSize || 20;

  updateMwSummary();
  updateOptionsSummary();

  if(document.getElementById('f-lvl-Bmin')) document.getElementById('f-lvl-Bmin').value = 0;
  if(document.getElementById('f-lvl-Bmax')) document.getElementById('f-lvl-Bmax').value = p.params.exp.Bmax;
  const lvlSummary = document.getElementById('levels-summary');
  if (lvlSummary) lvlSummary.textContent = `0–${p.params.exp.Bmax} mT · 200 pts`;

  // Expand all relevant parameter cards so all parameters are immediately visible
  const cardElectron = document.getElementById('card-electron');
  if (cardElectron) cardElectron.classList.remove('collapsed');

  const cardZfs = document.getElementById('card-zfs');
  if (cardZfs) {
    if ((p.params.D && p.params.D.length > 0 && (p.params.D[0] !== 0 || p.params.D[1] !== 0)) || p.params.S > 0.5) {
      cardZfs.classList.remove('collapsed');
    }
  }

  const cardLw = document.getElementById('card-lw');
  if (cardLw) cardLw.classList.remove('collapsed');

  const cardDetection = document.getElementById('card-detection');
  if (cardDetection) cardDetection.classList.remove('collapsed');

  const cardOptions = document.getElementById('card-options');
  if (cardOptions) cardOptions.classList.remove('collapsed');

  const cardMw = document.getElementById('card-mw');
  if (cardMw) cardMw.classList.remove('collapsed');

  // Reset orientation controls
  state.singleOrientation = false;
  state.theta = 0.0;
  state.phi = 0.0;
  const chkOri = document.getElementById('chk-single-orientation');
  if (chkOri) chkOri.checked = false;
  const oriCtrl = document.getElementById('ori-controls');
  if (oriCtrl) oriCtrl.style.display = 'none';
  const thetaEl = document.getElementById('f-theta');
  if (thetaEl) thetaEl.value = 0.0;
  const phiEl = document.getElementById('f-phi');
  if (phiEl) phiEl.value = 0.0;
  updateOrientationPresetButtons('Z');
  updateOrientationSummary();

  setSimulator(p.params.simulator);
  setModel(p.params.method || 'matrix', false);

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
        A_aniso: n.A_aniso || (n.A != null ? [n.A, n.A, n.A] : null),
        Q: n.Q || 0,
        Q_aniso: n.Q_aniso || (n.Q != null ? [n.Q, n.Q, n.Q] : [0, 0, 0]),
        label: null
      });
    }

    // Ensure Nuclei card is expanded if preset has nuclei
    const nucCard = document.getElementById('card-nuclei');
    if (nucCard && p.params.nuclei && p.params.nuclei.length > 0) {
      nucCard.classList.remove('collapsed');
    }
    
    await refreshSystem();
    const tabParams = document.getElementById('tab-params');
    if (tabParams) tabParams.click();
    showToast(p.name + ' loaded successfully!', 'success');
    
    // Automatically simulate loaded preset
    return await runSimulation();
  } catch (e) {
    showToast('Failed to load preset: ' + e.message, 'error');
  }
}

