/**
 * pyEPR — Spin Hamiltonian Pedagogical Tour (Shepherd.js)
 *
 * Walks students through the first 4 presets one by one with progressively
 * increasing Spin Hamiltonian complexity:
 *   1. Free electron: Pure Electron Zeeman (S = 1/2, g = 2.0023, 1 line)
 *   2. 1 Proton: Fermi contact hyperfine coupling (I = 1/2, A = 1430 MHz, 1:1 doublet, Breit-Rabi effect)
 *   3. 2 Protons: Equivalent nuclei & Pascal's triangle degeneracies (2x 1H, 1:2:1 triplet)
 *   4. Nitroxide radical: Anisotropic g & A tensors, 14N (I = 1), solid-state powder averaging (pepper)
 *   Followed by: Course Wrap-up & ZFS / High-spin horizons.
 */

function startTour() {
  if (typeof Shepherd === 'undefined') {
    if (typeof showToast === 'function') {
      showToast('Initializing tour engine...', 'info');
    }
    setTimeout(startTour, 200);
    return;
  }

  // If a tour instance is already active, cancel it before starting anew
  if (window._currentEprTour) {
    try {
      window._currentEprTour.cancel();
    } catch (e) {}
  }

  const tour = new Shepherd.Tour({
    useModalOverlay: true,
    classPrefix: 'shepherd-theme-epr',
    defaultStepOptions: {
      classes: 'shepherd-theme-epr',
      scrollTo: { behavior: 'smooth', block: 'center' },
      cancelIcon: { enabled: true },
    },
  });

  window._currentEprTour = tour;

  const isMobile = window.innerWidth < 768;
  const getAttach = (el, on) => (isMobile ? { element: '#top-bar', on: 'bottom' } : { element: el, on: on });

  const steps = [
    // ------------------------------------------------------------
    // Step 0: Welcome & Overview of Spin Hamiltonian
    // ------------------------------------------------------------
    {
      id: 'tour-intro',
      title: '🎓 Spin Hamiltonian Interactive Tour',
      text: `
        <div class="tour-step-badge">Pedagogical Walkthrough · 4 Presets</div>
        <p style="margin-bottom:8px;line-height:1.5;">
          Welcome! In Electron Paramagnetic Resonance (EPR), spectra arise from microwave-induced
          magnetic dipole transitions between quantum spin states governed by the <strong>Spin Hamiltonian</strong>:
        </p>
        <div class="tour-math-box">
          Ĥ = Ĥ<sub>EZ</sub> + Ĥ<sub>HF</sub> + Ĥ<sub>ZFS</sub> + Ĥ<sub>NZ</sub> + Ĥ<sub>NQ</sub>
        </div>
        <ul class="tour-key-points">
          <li><strong>1. Free Electron:</strong> Pure Electron Zeeman splitting (Ĥ<sub>EZ</sub>)</li>
          <li><strong>2. 1 Proton (¹H):</strong> Electron-nuclear Fermi contact hyperfine coupling (Ĥ<sub>HF</sub>)</li>
          <li><strong>3. 2 Protons:</strong> Multiple equivalent nuclei &amp; Pascal's triangle intensities</li>
          <li><strong>4. Nitroxide Radical:</strong> Tensor anisotropy (<b>g</b>, <b>A</b>) &amp; powder averaging (<code>pepper</code>)</li>
        </ul>
        <p style="margin-top:8px;font-size:0.78rem;color:var(--text-hint);line-height:1.4;">
          Each step automatically configures the spin system, computes the quantum Hamiltonian, and updates the live Spectrum &amp; Energy Levels.
        </p>
      `,
      attachTo: { element: '#top-bar', on: 'bottom' },
      buttons: [
        {
          text: 'Skip',
          action: () => tour.cancel(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Start Tour →',
          action: () => tour.next(),
          classes: 'shepherd-button-primary',
        },
      ],
    },

    // ------------------------------------------------------------
    // Step 1: Preset 0 — Free Electron (Pure Electron Zeeman)
    // ------------------------------------------------------------
    {
      id: 'tour-preset-0',
      title: '1️⃣ Electron Zeeman: The Pure Free Spin',
      text: `
        <div class="tour-step-badge">Preset 1 of 4 · S = 1/2 · No Nuclei</div>
        <p style="margin-bottom:6px;line-height:1.5;">
          The simplest EPR system is an isolated unpaired electron with spin <strong>S = 1/2</strong> in a static magnetic field <strong>B₀</strong>.
        </p>
        <div class="tour-math-box">
          Ĥ = Ĥ<sub>EZ</sub> = μ<sub>B</sub> <b>B₀</b> · <b>g</b> · Ŝ ≈ g μ<sub>B</sub> B₀ Ŝ<sub>z</sub>
        </div>
        <ul class="tour-key-points">
          <li><strong>Two Quantum States:</strong> |m<sub>S</sub> = -½⟩ (lower energy, magnetic moment aligned) and |m<sub>S</sub> = +½⟩ (higher energy, opposed).</li>
          <li><strong>Zeeman Splitting:</strong> The energy gap ΔE = g μ<sub>B</sub> B₀ diverges linearly with field <em>(observe the two straight lines in the Energy Levels plot)</em>.</li>
          <li><strong>Resonance Condition:</strong> X-band microwaves (ν = 9.4 GHz) drive transitions with selection rule Δm<sub>S</sub> = ±1 when:
            <div style="text-align:center;margin:4px 0;font-weight:600;color:var(--accent);">
              hν = g μ<sub>B</sub> B<sub>res</sub> &nbsp;⟹&nbsp; B<sub>res</sub> = hν / (g μ<sub>B</sub>) ≈ 335.4 mT
            </div>
          </li>
          <li><strong>Spectrum:</strong> Yields exactly <strong>one sharp resonance line</strong> at ~335.4 mT.</li>
        </ul>
      `,
      attachTo: getAttach('#card-electron', 'right'),
      beforeShowPromise: async () => {
        try {
          await loadPreset(0);
        } catch (e) {
          console.error('Failed to load preset 0 in tour:', e);
        }
      },
      buttons: [
        {
          text: 'Skip',
          action: () => tour.cancel(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: '← Intro',
          action: () => tour.back(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Next: 1 Proton →',
          action: () => tour.next(),
          classes: 'shepherd-button-primary',
        },
      ],
    },

    // ------------------------------------------------------------
    // Step 2: Preset 1 — 1 Proton (Isotropic Hyperfine Coupling)
    // ------------------------------------------------------------
    {
      id: 'tour-preset-1',
      title: '2️⃣ Hyperfine Interaction: Hydrogen Atom',
      text: `
        <div class="tour-step-badge">Preset 2 of 4 · S = 1/2, I = 1/2 (¹H)</div>
        <p style="margin-bottom:6px;line-height:1.5;">
          We now add a <strong>proton nucleus (¹H, I = 1/2)</strong>. The electron spin couples to the nuclear magnetic dipole via the <strong>isotropic hyperfine interaction</strong>:
        </p>
        <div class="tour-math-box">
          Ĥ = g μ<sub>B</sub> B₀ Ŝ<sub>z</sub> + a<sub>iso</sub> Ŝ · Î - g<sub>n</sub> μ<sub>n</sub> B₀ Î<sub>z</sub>
        </div>
        <ul class="tour-key-points">
          <li><strong>Fermi Contact Term:</strong> a<sub>iso</sub> = 1430 MHz is directly proportional to the electron spin density directly at the nucleus (|ψ(0)|²).</li>
          <li><strong>Hilbert Space:</strong> (2S + 1)(2I + 1) = 2 &times; 2 = <strong>4 coupled states</strong> |m<sub>S</sub>, m<sub>I</sub>⟩.</li>
          <li><strong>Selection Rules:</strong> Allowed CW EPR transitions follow <strong>Δm<sub>S</sub> = ±1</strong> and <strong>Δm<sub>I</sub> = 0</strong> (the nucleus does not flip during the electronic transition).</li>
          <li><strong>1 : 1 Doublet:</strong> The electron line splits into 2 lines separated by:
            <div style="text-align:center;margin:3px 0;font-weight:600;color:var(--accent);">
              ΔB = A / (g μ<sub>B</sub>) ≈ 50.7 mT
            </div>
            Centered around g = 2.0029 (one line for m<sub>I</sub> = +½, one for m<sub>I</sub> = -½).
          </li>
          <li><strong>Breit-Rabi Curvature:</strong> Notice the curved energy levels below! At low field, large A (1430 MHz) mixes states into total angular momentum |F, M<sub>F</sub>⟩ multiplets.</li>
        </ul>
      `,
      attachTo: getAttach('#card-nuclei', 'right'),
      beforeShowPromise: async () => {
        try {
          await loadPreset(1);
        } catch (e) {
          console.error('Failed to load preset 1 in tour:', e);
        }
      },
      buttons: [
        {
          text: 'Skip',
          action: () => tour.cancel(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: '← Free Electron',
          action: () => tour.back(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Next: 2 Protons →',
          action: () => tour.next(),
          classes: 'shepherd-button-primary',
        },
      ],
    },

    // ------------------------------------------------------------
    // Step 3: Preset 2 — 2 Protons (Equivalent Nuclei & Pascal's Triangle)
    // ------------------------------------------------------------
    {
      id: 'tour-preset-2',
      title: '3️⃣ Equivalent Nuclei: Pascal\'s Triangle',
      text: `
        <div class="tour-step-badge">Preset 3 of 4 · 2× ¹H (I = 1/2) Equivalent</div>
        <p style="margin-bottom:6px;line-height:1.5;">
          Now the electron couples equally to <strong>N = 2 equivalent protons</strong> (e.g., in a CH₂ radical group), each with identical A = 1430 MHz:
        </p>
        <div class="tour-math-box">
          Ĥ = g μ<sub>B</sub> B₀ Ŝ<sub>z</sub> + ∑<sub>k=1</sub><sup>2</sup> A<sub>k</sub> Ŝ · Î<sub>k</sub> &nbsp; (A₁ = A₂)
        </div>
        <ul class="tour-key-points">
          <li><strong>Total Nuclear Quantum Number:</strong> M<sub>I</sub> = m<sub>I1</sub> + m<sub>I2</sub> ∈ {+1, 0, -1}.</li>
          <li><strong>Degeneracy &amp; Statistical Weights:</strong>
            <br/>• M<sub>I</sub> = +1 (|↑↑⟩): <strong>1 state</strong>
            <br/>• M<sub>I</sub> = 0 (|↑↓⟩, |↓↑⟩): <strong>2 states</strong> (doubly degenerate)
            <br/>• M<sub>I</sub> = -1 (|↓↓⟩): <strong>1 state</strong>
          </li>
          <li><strong>1 : 2 : 1 Triplet:</strong> The spectrum exhibits 2NI + 1 = <strong>3 lines</strong> with binomial intensity ratio <strong>1 : 2 : 1</strong> from Pascal's triangle!</li>
          <li><strong>Observe:</strong> The central peak (at M<sub>I</sub> = 0) is exactly twice the intensity of the outer satellites.</li>
          <li><strong>General Rule:</strong> N equivalent spin-I nuclei produce (2NI + 1) equidistant hyperfine lines.</li>
        </ul>
      `,
      attachTo: getAttach('#card-nuclei', 'right'),
      beforeShowPromise: async () => {
        try {
          await loadPreset(2);
        } catch (e) {
          console.error('Failed to load preset 2 in tour:', e);
        }
      },
      buttons: [
        {
          text: 'Skip',
          action: () => tour.cancel(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: '← 1 Proton',
          action: () => tour.back(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Next: Nitroxide →',
          action: () => tour.next(),
          classes: 'shepherd-button-primary',
        },
      ],
    },

    // ------------------------------------------------------------
    // Step 4: Preset 3 — Nitroxide Radical (Anisotropy & Powder Average)
    // ------------------------------------------------------------
    {
      id: 'tour-preset-3',
      title: '4️⃣ Solid State &amp; Anisotropy: Nitroxide Radical',
      text: `
        <div class="tour-step-badge">Preset 4 of 4 · ¹⁴N (I = 1) · Solid State (pepper)</div>
        <p style="margin-bottom:6px;line-height:1.5;">
          In frozen solutions, glasses, or membranes, molecules cannot tumble to average out directional interactions. Both <strong>g</strong> and <strong>A</strong> become <strong>anisotropic 3&times;3 tensors</strong>:
        </p>
        <div class="tour-math-box">
          Ĥ = μ<sub>B</sub> <b>B₀</b> · <b>g</b> · Ŝ + Ŝ · <b>A</b> · Î
        </div>
        <ul class="tour-key-points">
          <li><strong>Rhombic g-Tensor:</strong> g = [2.0083, 2.0061, 2.0022]. The resonance field shifts with molecular orientation (θ, φ).</li>
          <li><strong>Axial A-Tensor (¹⁴N, I = 1):</strong> Unpaired electron density resides in the nitrogen 2p<sub>z</sub> orbital, making A<sub>zz</sub> (92.4 MHz) vastly larger than A<sub>xx</sub>, A<sub>yy</sub> (11.2 MHz).</li>
          <li><strong>¹⁴N Triplet (I = 1):</strong> Nuclear spin I = 1 yields 3 transitions (M<sub>I</sub> = -1, 0, +1).</li>
          <li><strong>Powder Average (<code>pepper</code>):</strong> In random solid-state orientation, the spectrum is an integral over the unit sphere:
            <div style="font-family:'Roboto Mono',monospace;font-size:0.75rem;margin:3px 0;color:var(--accent);">
              ⟨I(B)⟩ = ¼π ∬ I(B, θ, φ) sinθ dθ dφ
            </div>
            Observe the characteristic asymmetric powder pattern: sharp perpendicular (x,y) edges and broad outer parallel (z) extrema!
          </li>
        </ul>
      `,
      attachTo: getAttach('#card-electron', 'right'),
      beforeShowPromise: async () => {
        try {
          await loadPreset(3);
        } catch (e) {
          console.error('Failed to load preset 3 in tour:', e);
        }
      },
      buttons: [
        {
          text: 'Skip',
          action: () => tour.cancel(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: '← 2 Protons',
          action: () => tour.back(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Next: Summary →',
          action: () => tour.next(),
          classes: 'shepherd-button-primary',
        },
      ],
    },

    // ------------------------------------------------------------
    // Step 5: Summary & Beyond (Mastery of Spin Hamiltonian)
    // ------------------------------------------------------------
    {
      id: 'tour-summary',
      title: '🎓 Spin Hamiltonian Mastery &amp; Beyond',
      text: `
        <div class="tour-step-badge">Course Summary &amp; Exploration</div>
        <p style="margin-bottom:8px;line-height:1.45;">
          You have mastered the foundational hierarchy of CW EPR theory:
        </p>
        <table style="width:100%;font-size:0.74rem;border-collapse:collapse;margin:6px 0 10px 0;border:1px solid var(--border);border-radius:6px;overflow:hidden;">
          <tr style="background:var(--surface);color:var(--accent);">
            <th style="padding:6px 8px;text-align:left;border-bottom:1px solid var(--border);">System</th>
            <th style="padding:6px 8px;text-align:left;border-bottom:1px solid var(--border);">Active Hamiltonian Terms</th>
            <th style="padding:6px 8px;text-align:left;border-bottom:1px solid var(--border);">Spectral Signature</th>
          </tr>
          <tr>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);"><strong>Free Electron</strong></td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);font-family:'Roboto Mono',monospace;color:#82B1FF;">g μ<sub>B</sub> B₀ Ŝ<sub>z</sub></td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);">Single line at hν/(gμ<sub>B</sub>)</td>
          </tr>
          <tr>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);"><strong>1 Proton</strong></td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);font-family:'Roboto Mono',monospace;color:#80D8FF;">+ a<sub>iso</sub> Ŝ·Î</td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);">1 : 1 Doublet (Breit-Rabi)</td>
          </tr>
          <tr>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);"><strong>2 Protons</strong></td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);font-family:'Roboto Mono',monospace;color:#80D8FF;">+ ∑ A<sub>k</sub> Ŝ·Î<sub>k</sub></td>
            <td style="padding:5px 8px;border-bottom:1px solid var(--border);">1 : 2 : 1 Triplet (Pascal)</td>
          </tr>
          <tr>
            <td style="padding:5px 8px;"><strong>Nitroxide</strong></td>
            <td style="padding:5px 8px;font-family:'Roboto Mono',monospace;color:#FF80AB;"><b>B₀</b>·<b>g</b>·Ŝ + Ŝ·<b>A</b>·Î</td>
            <td style="padding:5px 8px;">Anisotropic powder pattern</td>
          </tr>
        </table>

        <div style="padding:8px 10px;background:rgba(124, 77, 255, 0.12);border:1px solid rgba(124, 77, 255, 0.35);border-radius:6px;font-size:0.77rem;line-height:1.45;">
          <strong style="color:#B388FF;">Next Step: Systems with S &gt; 1/2 &amp; Zero-Field Splitting (ZFS)</strong>
          <br/>
          When S &ge; 1, dipolar and spin-orbit interactions split spin states even at zero magnetic field via:
          <div style="text-align:center;font-family:'Roboto Mono',monospace;color:#E040FB;margin:3px 0;">
            Ĥ<sub>ZFS</sub> = D [Ŝ<sub>z</sub>² - ⅓S(S+1)] + E (Ŝ<sub>x</sub>² - Ŝ<sub>y</sub>²)
          </div>
          Click below to open the <strong>Examples tab</strong> and test <strong>Spin Triplet (S=1)</strong>, <strong>Triplet Nitrene</strong>, <strong>Mn(III) (S=2)</strong>, and <strong>Fe(III) (S=5/2)</strong>!
        </div>
      `,
      attachTo: { element: '#top-bar', on: 'bottom' },
      buttons: [
        {
          text: '← Nitroxide',
          action: () => tour.back(),
          classes: 'shepherd-button-secondary',
        },
        {
          text: 'Explore Presets 🚀',
          action: () => {
            tour.complete();
            localStorage.setItem('epr_tour_done', '1');
            const tabEx = document.getElementById('tab-examples');
            if (tabEx) tabEx.click();
          },
          classes: 'shepherd-button-primary',
        },
      ],
    },
  ];

  steps.forEach((s) => tour.addStep(s));

  tour.on('cancel', () => {
    localStorage.setItem('epr_tour_done', '1');
    window._currentEprTour = null;
  });

  tour.on('complete', () => {
    localStorage.setItem('epr_tour_done', '1');
    window._currentEprTour = null;
  });

  try {
    tour.start();
  } catch (err) {
    console.error('Failed to start tour:', err);
    if (typeof showToast === 'function') {
      showToast('Tour failed to start: ' + err.message, 'error');
    }
  }
}
