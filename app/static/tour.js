/**
 * EPR Simulator — First-run interactive tour (Shepherd.js)
 * Highlights key UI elements step by step.
 */

function startTour() {
  if (typeof Shepherd === 'undefined') {
    console.warn('Shepherd.js not loaded yet');
    return;
  }

  const tour = new Shepherd.Tour({
    useModalOverlay: true,
    classPrefix: 'shepherd-theme-epr',
    defaultStepOptions: {
      classes: 'shepherd-theme-epr',
      scrollTo: { behavior: 'smooth', block: 'center' },
      cancelIcon: { enabled: true },
      buttons: [
        { text: 'Skip', action: tour.cancel, classes: 'shepherd-button-secondary' },
        { text: 'Next →', action: tour.next,  classes: 'shepherd-button-primary' },
      ],
    },
  });

  const steps = [
    {
      id: 'welcome',
      title: '👋 Welcome to EPR Simulator',
      text: `
        This app lets you simulate CW EPR spectra using the EasySpin physics engine
        — now running entirely in Python, with no MATLAB dependency.
        <br/><br/>
        Let's take a quick tour of the interface.
      `,
      attachTo: { element: '#top-bar', on: 'bottom' },
    },
    {
      id: 'electron-spin',
      title: '⚡ Electron Spin Card',
      text: `
        Define your <strong>electron spin S</strong> and <strong>g-tensor</strong>.
        For a typical organic radical: S = 1/2, g ≈ 2.003–2.006.
        <br/><br/>
        Click the card header to collapse or expand each section.
        <br/><br/>
        📖 <a href="https://easyspin.org/easyspin/documentation/spinsystem.html"
              target="_blank" style="color:#00BCD4;">Spin System docs</a>
      `,
      attachTo: { element: '#card-electron', on: 'right' },
    },
    {
      id: 'zfs',
      title: '🔮 Zero-Field Splitting',
      text: `
        The ZFS card (collapsed by default) lets you set the <strong>D</strong> and
        <strong>E</strong> parameters for systems with S &gt; 1/2.
        <br/><br/>
        If D ≠ 0, the app will automatically recommend using <code>pepper()</code>
        instead of <code>garlic()</code>.
      `,
      attachTo: { element: '#card-zfs', on: 'right' },
    },
    {
      id: 'nuclei',
      title: '⚛️ Adding Nuclei',
      text: `
        Select an isotope from the dropdown and press <strong>Add</strong>.
        Each nucleus gets its own row with an <strong>A</strong> (hyperfine coupling)
        and — for I ≥ 1 — a <strong>Q</strong> (quadrupole coupling) field.
        <br/><br/>
        The Hilbert space dimension (shown in the top badge) updates automatically.
      `,
      attachTo: { element: '#card-nuclei', on: 'right' },
    },
    {
      id: 'simulator',
      title: '🔬 Choosing a Simulator',
      text: `
        Switch between <strong>garlic()</strong> and <strong>pepper()</strong>
        manually using this toggle.
        <br/><br/>
        • <code>garlic()</code> — liquid solutions, fast tumbling, S = 1/2 only<br/>
        • <code>pepper()</code> — solid state, powder average, any S
        <br/><br/>
        📖 <a href="https://easyspin.org/easyspin/documentation/garlic.html"
              target="_blank" style="color:#00BCD4;">garlic docs</a> ·
        <a href="https://easyspin.org/easyspin/documentation/pepper.html"
              target="_blank" style="color:#3D5AFE;">pepper docs</a>
      `,
      attachTo: { element: '#card-simulator', on: 'right' },
    },
    {
      id: 'validation',
      title: '⚠️ Validation Badges',
      text: `
        Below the parameter cards, warnings and errors appear automatically when
        your spin system is incompatible with the chosen simulator.
        <br/><br/>
        Each badge links directly to the relevant EasySpin documentation page.
      `,
      attachTo: { element: '#validation-area', on: 'top' },
    },
    {
      id: 'simulate',
      title: '▶ Run a Simulation',
      text: `
        Press <strong>Simulate</strong> to compute the CW EPR spectrum and energy
        level diagram. Both plots update simultaneously.
        <br/><br/>
        The spectrum and energy levels run in parallel — large spin systems
        (high Hilbert space dimension) may take a few seconds.
      `,
      attachTo: { element: '#simulate-btn', on: 'top' },
    },
    {
      id: 'plots',
      title: '📊 Interactive Plots',
      text: `
        The <strong>spectrum</strong> (top) and <strong>energy level diagram</strong>
        (bottom) are interactive Plotly charts — zoom, pan, and hover for values.
        <br/><br/>
        On mobile, switch between plots using the bottom navigation.
      `,
      attachTo: { element: '#spectrum-card', on: 'left' },
    },
    {
      id: 'done',
      title: '🎉 You\'re all set!',
      text: `
        That's the full tour. You can restart it anytime from the
        <span class="material-icons-round" style="font-size:14px;vertical-align:middle;">help_outline</span>
        button in the top bar, or the <strong>Guide</strong> tab.
        <br/><br/>
        Happy simulating!
      `,
      attachTo: { element: '#top-bar', on: 'bottom' },
      buttons: [
        {
          text: '✓ Done',
          action: () => { tour.complete(); localStorage.setItem('epr_tour_done', '1'); },
          classes: 'shepherd-button-primary',
        },
      ],
    },
  ];

  steps.forEach(s => tour.addStep(s));

  // Make sure the Experiment tab is shown when stepping past nucleus card
  tour.on('show', ({ step }) => {
    if (step.id === 'simulator') {
      // Switch to experiment tab so the simulator card is visible
      const expTab = document.querySelector('[data-tab="exp"]');
      if (expTab) expTab.click();
    }
    if (step.id === 'electron-spin' || step.id === 'nuclei') {
      const paramsTab = document.querySelector('[data-tab="params"]');
      if (paramsTab) paramsTab.click();
    }
  });

  tour.start();
}
