# EasySpin Python Port - Web Application Design Specification

This document provides a comprehensive design specification for the web frontend of the EasySpin Python Port (EPR Simulator). It is intended to be used as a prompt or spec for a UI generator (like Stitch) to build the frontend application.

## 1. Overview
The goal is to build a modern, responsive Single Page Application (SPA) that interfaces with a FastAPI backend. The application allows users to interactively construct an EPR spin system, configure experiment parameters, and visualize simulated Continuous Wave (CW) EPR spectra and energy levels.

### Tech Stack Recommendations
* **Framework:** React, Vue, or Svelte (Vanilla JS is also acceptable if well-structured).
* **Styling:** Material Design 3 (e.g., MUI for React, Vuetify for Vue) or TailwindCSS with a Material-inspired theme.
* **Visualization:** Plotly.js for interactive scientific plotting.
* **HTTP Client:** Fetch API or Axios.

## 2. Global Layout & Theme
* **Theme:** Responsive Material Design 3. Vibrant colors, smooth micro-animations on hover, and a sleek dark mode option. The interface should feel "premium" and "scientific yet modern".
* **Layout Structure:**
  * **App Bar (Top):** Logo/Title ("EPR Simulator"), Dark/Light mode toggle, and a global status indicator (e.g., API connection status).
  * **Left Sidebar (Spin System):** Form to manage electron parameters and a dynamic list to add/remove/edit nuclei.
  * **Right/Main Content Area:** 
    * Top section: Experiment parameters (frequency, field range, points).
    * Bottom section: A large area containing Tabs for "Spectrum" and "Energy Levels", each holding a Plotly chart.
  * **Bottom/Snackbar:** For displaying validation warnings and simulation errors.

## 3. UI Components Details

### 3.1 Spin System Panel (Left Sidebar)
This panel manages the state of the spin system via the `/api/system` and `/api/system/nuclei` endpoints.

**Electron Parameters Form:**
* `S` (Electron Spin): Numeric input (default 0.5).
* `g` (g-tensor): 3 numeric inputs for isotropic or anisotropic values.
* `D` (Zero Field Splitting, MHz): 3 numeric inputs.
* `lw` (Linewidth, mT): 2 numeric inputs (Gaussian, Lorentzian).
* `tcorr` (Correlation time, s): Optional numeric input.
* *Action:* A "Save/Update" button or auto-save on blur (`PUT /api/system`).

**Nuclei Management:**
* A list showing currently added nuclei (fetching from `GET /api/system`).
* Each item shows the Isotope Symbol, Spin (I), and HFI coupling (A). Includes a "Delete" button (`DELETE /api/system/nuclei/{idx}`).
* "Add Nucleus" Button: Opens a modal or inline form (`POST /api/system/nuclei`):
  * `symbol` (e.g., '14N', '1H' - can use autocomplete from `GET /api/isotopes`).
  * `A` (Isotropic HFI, MHz).
  * `Q` (Quadrupole, MHz).

### 3.2 Experiment Parameters (Main Top)
A horizontal toolbar or card above the plots.
* `Simulator`: Dropdown / Toggle Switch (`garlic` for isotropic liquid, `pepper` for solid-state powder).
* `mwFreq` (Microwave Frequency, GHz): Numeric input (default 9.5).
* `B_min` / `B_max` (Magnetic Field Range, mT): Numeric inputs.
* `nPoints`: Numeric input (default 1024).
* `Harmonic`: Dropdown (0 = Absorption, 1 = First Derivative).
* `nKnots`: Numeric input (only visible if `pepper` is selected, default 20).
* *Action:* A prominent, styled primary button **"Simulate"**.

### 3.3 Visualization Area (Main Bottom)
Uses Plotly.js for rendering.
* **Tabs:** Switch between "Spectrum" and "Energy Levels".
* **Spectrum Chart:**
  * X-axis: Magnetic Field (mT)
  * Y-axis: Intensity (arb. u.)
  * Data source: `POST /api/simulate/spectrum`
* **Energy Levels Chart:**
  * X-axis: Magnetic Field (mT)
  * Y-axis: Energy (MHz or GHz)
  * Data source: `POST /api/simulate/levels`
* Both plots should be fully interactive (zoom, pan, export to PNG).

### 3.4 Validation Layer
Before or during simulation, display any validation warnings.
* Data source: `validation` object in the simulation response, or explicitly from `GET /api/validate/{simulator}`.
* Presentation: Material Design Alert banners or toast notifications. Red for errors (blocking simulation), yellow for warnings.

## 4. REST API Integration Mapping

Here is the exact schema the frontend needs to communicate with:

### Data Models
* `SpinSystemState`: `{ S: [0.5], g: [2.0], D: [], lw: [0.3], tcorr: null, nuclei: [...] }`
* `Nucleus`: `{ symbol: "14N", A: 10.0, Q: 0.0 }`

### Endpoints
* `GET /api/system` - Load the initial configuration.
* `PUT /api/system` - Save electron parameters. Send partial or full state.
* `POST /api/system/nuclei` - Add a nucleus. Body: `NucleusRequest`.
* `DELETE /api/system/nuclei/{idx}` - Remove a specific nucleus.
* `GET /api/isotopes` - For populating the nucleus selection dropdown.
* `POST /api/simulate/spectrum`
  * Request Body: `{ mwFreq: 9.5, B_min: 300, B_max: 400, nPoints: 1024, Harmonic: 1, simulator: "garlic", nKnots: 20 }`
  * Response: `{ B: [...], spc: [...], validation: { valid: true, messages: [] } }`
* `POST /api/simulate/levels`
  * Request Body: `{ B_min: 0, B_max: 400, nPoints: 200 }`
  * Response: `{ B: [...], E: [[...], [...]], validation: {...} }`

## 5. Non-Functional Requirements for the UI Generator
1. **Error Handling:** Gracefully handle HTTP 400/422/500 errors from the API and display human-readable messages to the user.
2. **Loading States:** Show skeleton loaders or spinner overlays on the Plotly charts while waiting for the `POST /api/simulate/*` endpoints to resolve.
3. **Responsiveness:** On smaller screens, the Left Sidebar should collapse into a drawer (Hamburger menu).
4. **State Management:** Keep the spin system state in sync with the backend. Changes in the UI should ideally optimistically update or trigger immediate API calls.
