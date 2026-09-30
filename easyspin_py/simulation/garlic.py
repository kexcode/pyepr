"""
Isotropic CW EPR spectrum simulator (garlic.m port).

Simulates the CW EPR spectrum of a radical in fast-motion (isotropic) regime,
where the spin system is characterized by a single g-value and isotropic
hyperfine couplings A (in MHz).

This port implements first-order perturbation theory for line positions
(valid when A << g*bmagn*B/h, i.e. at typical X-band and above) and
constructs the spectrum as a sum of Lorentzian or Gaussian lineshapes.

Usage
-----
    from easyspin_py.core.spin_system import SpinSystem
    from easyspin_py.simulation.garlic import garlic

    sys = SpinSystem(S=0.5, g=2.0055, Nucs='14N', A=[40.0], lw=[0.1, 0.5])
    exp = dict(mwFreq=9.5, Range=[320, 360])   # GHz and mT
    B, spc = garlic(sys, exp)
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, Optional

import numpy as np
import warnings
from itertools import product

from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.core.constants import bmagn, planck
from easyspin_py.simulation.validator import validate_garlic, Severity


# ---------------------------------------------------------------------------
# Helper: generate all mI combinations for a set of nuclei
# ---------------------------------------------------------------------------

def _all_mi_combinations(I_list: np.ndarray) -> np.ndarray:
    """
    Returns all combinations of mI values for the given list of nuclear spins.
    Returns an array of shape (n_combinations, n_nuclei).
    """
    grids = [np.arange(-I, I + 1) for I in I_list]
    combos = list(product(*grids))
    return np.array(combos, dtype=float)


# ---------------------------------------------------------------------------
# Lineshape functions
# ---------------------------------------------------------------------------

def _lorentzian(x: np.ndarray, x0: float, fwhm: float) -> np.ndarray:
    """
    Absorption Lorentzian lineshape, area-normalized.
    fwhm in same units as x.
    """
    gamma = fwhm / 2.0
    return (gamma / np.pi) / ((x - x0) ** 2 + gamma ** 2)


def _gaussian(x: np.ndarray, x0: float, fwhm: float) -> np.ndarray:
    """
    Absorption Gaussian lineshape, area-normalized.
    fwhm in same units as x.
    """
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return (1.0 / (sigma * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x - x0) / sigma) ** 2)


def _deriv_lorentzian(x: np.ndarray, x0: float, fwhm: float) -> np.ndarray:
    """First derivative of a Lorentzian (field-modulation detected)."""
    gamma = fwhm / 2.0
    return -2 * (x - x0) * gamma / (np.pi * ((x - x0) ** 2 + gamma ** 2) ** 2)


def _deriv_gaussian(x: np.ndarray, x0: float, fwhm: float) -> np.ndarray:
    """First derivative of a Gaussian."""
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return -(x - x0) / (sigma ** 3 * np.sqrt(2.0 * np.pi)) * np.exp(-0.5 * ((x - x0) / sigma) ** 2)


# ---------------------------------------------------------------------------
# Resonance field calculation (first-order perturbation theory)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Resonance field calculation (perturbation and matrix methods)
# ---------------------------------------------------------------------------

def _resonance_fields_perturbation(
    sys: SpinSystem,
    mw_freq_GHz: float,
    order: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate resonance fields (mT) and relative intensities using
    perturbation theory (1st or 2nd order).

    Parameters
    ----------
    sys : SpinSystem
    mw_freq_GHz : float
        Microwave frequency in GHz.
    order : int
        1 for first-order perturbation, 2 for second-order (Breit-Rabi shift).

    Returns
    -------
    B_res : ndarray
        Resonance fields in mT.
    intensities : ndarray
        Relative intensities.
    """
    if len(sys.S) != 1 or sys.S[0] != 0.5:
        raise NotImplementedError(
            "garlic currently supports S=1/2 only. "
            "Use pepper() for higher electron spins."
        )

    # Isotropic g-value
    g_arr = sys.g.flatten()
    if len(g_arr) == 1:
        g_iso = float(g_arr[0])
    elif len(g_arr) == 3:
        g_iso = float(np.mean(g_arr))
    elif len(g_arr) == 9:
        g_iso = float(np.mean(np.diag(g_arr.reshape(3, 3))))
    else:
        g_iso = float(g_arr[0])

    mw_freq_MHz = mw_freq_GHz * 1e3  # GHz -> MHz

    # Isotropic A values in MHz (one per nucleus)
    if sys.nNuclei == 0 or len(sys.A) == 0:
        # No nuclei: single resonance line
        B0 = mw_freq_MHz / (g_iso * bmagn / planck / 1e9)  # MHz / (MHz/mT) = mT
        return np.array([B0]), np.array([1.0])

    A_iso = np.zeros(sys.nNuclei)
    A_arr = np.atleast_1d(sys.A)
    for k in range(sys.nNuclei):
        if A_arr.ndim == 1:
            a_val = A_arr[k] if k < len(A_arr) else 0.0
        elif A_arr.ndim == 2:
            a_val = np.mean(A_arr[k])
        else:
            a_val = 0.0
        A_iso[k] = a_val

    # All nuclear spin combinations and their degeneracies
    mi_combos = _all_mi_combinations(sys.I)
    n_combos = len(mi_combos)

    # Pre-factor: g*bmagn/h in MHz/mT
    gB_factor = g_iso * bmagn / planck / 1e9  # MHz/mT

    B_res = np.zeros(n_combos)
    intensities = np.ones(n_combos)

    for idx, mi_vals in enumerate(mi_combos):
        # First-order shift from all nuclei
        dE_1 = np.sum(A_iso * mi_vals)  # MHz
        dE_2 = 0.0
        if order >= 2:
            # Breit-Rabi 2nd order shift: Delta E_2 = sum_k (A_k^2 / (2 * nu0)) * (I_k*(I_k+1) - m_I^2)
            dE_2 = np.sum((A_iso ** 2 / (2.0 * mw_freq_MHz)) * (sys.I * (sys.I + 1.0) - mi_vals ** 2))

        B_res[idx] = (mw_freq_MHz - dE_1 - dE_2) / gB_factor  # mT

    return B_res, intensities


def _resonance_fields_matrix(
    sys: SpinSystem,
    mw_freq_GHz: float,
    B_range: Tuple[float, float],
    n_B: int = 300,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate resonance fields (mT) and transition probabilities using
    exact matrix diagonalization for isotropic solution systems.
    """
    import scipy.linalg
    from easyspin_py.hamiltonian.builder import ham

    mw_freq_MHz = mw_freq_GHz * 1e3
    n_states = sys.hsdim()

    # Precompute field-independent H0 and magnetic moment operators
    H0, mux, muy, muz = ham(sys)

    # Internal B sweep spanning slightly beyond the target range
    b_margin = max(10.0, (B_range[1] - B_range[0]) * 0.1)
    b_min_sweep = max(0.0, B_range[0] - b_margin)
    b_max_sweep = B_range[1] + b_margin
    B_vals = np.linspace(b_min_sweep, b_max_sweep, n_B)

    # Compute eigenvalues at each field point (along z for isotropic)
    E = np.zeros((n_states, n_B))
    for k, B_mag in enumerate(B_vals):
        H = H0 - B_mag * muz
        E[:, k] = scipy.linalg.eigvalsh(H.toarray())

    # Find crossings where E_j(B) - E_i(B) = mw_freq_MHz
    res_fields = []
    res_weights = []

    for i in range(n_states):
        for j in range(i + 1, n_states):
            gap = E[j] - E[i]
            diff = gap - mw_freq_MHz
            sign_changes = np.where(np.diff(np.sign(diff)))[0]
            for k in sign_changes:
                d0, d1 = diff[k], diff[k + 1]
                B0, B1 = B_vals[k], B_vals[k + 1]
                B_res = B0 + (B1 - B0) * (-d0) / (d1 - d0)

                # Compute transition probability at B_res
                H_res = H0 - B_res * muz
                evals, evecs = scipy.linalg.eigh(H_res.toarray())
                ui = evecs[:, i]
                uj = evecs[:, j]

                # Transition dipole matrix element: |<i|mux|j>|^2 + |<i|muy|j>|^2
                mx = np.abs(ui.conj().T @ mux.toarray() @ uj) ** 2
                my = np.abs(ui.conj().T @ muy.toarray() @ uj) ** 2
                prob = float(mx + my)

                res_fields.append(B_res)
                res_weights.append(prob)

    if len(res_fields) == 0:
        # Fallback to perturbation if no crossings found in window
        return _resonance_fields_perturbation(sys, mw_freq_GHz, order=1)

    res_fields = np.array(res_fields)
    res_weights = np.array(res_weights)
    max_w = np.max(res_weights)
    if max_w > 0:
        res_weights = res_weights / max_w

    return res_fields, res_weights


# ---------------------------------------------------------------------------
# Main garlic function
# ---------------------------------------------------------------------------

def garlic(
    sys: SpinSystem,
    exp: Dict[str, Any],
    opt: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate isotropic CW EPR spectrum (fast-motion regime).

    Parameters
    ----------
    sys : SpinSystem
        Spin system with g, Nucs, A, lw (linewidth in mT).
    exp : dict
        Experiment parameters:
          - 'mwFreq'   : microwave frequency in GHz (default 9.5)
          - 'Range'    : [B_min, B_max] in mT (default [300, 400])
          - 'nPoints'  : number of spectrum points (default 1024)
          - 'Harmonic' : 0 = absorption, 1 = first derivative (default 1)
          - 'method'   : 'matrix', 'perturb1', or 'perturb2' (default 'matrix')
    opt : dict, optional
        Options dictionary (supports 'method' or 'Method').

    Returns
    -------
    B : ndarray of shape (nPoints,)
        Magnetic field axis in mT.
    spc : ndarray of shape (nPoints,)
        EPR spectrum (absorption or first derivative).
    """
    if opt is None:
        opt = {}

    # --- Validate spin system against garlic() constraints ---
    result = validate_garlic(sys)
    for msg in result.messages:
        if msg.severity == Severity.ERROR:
            raise ValueError(f"[garlic] {msg.message} (see {msg.doc_url})")
        elif msg.severity == Severity.WARNING:
            warnings.warn(f"[garlic] {msg.message} (see {msg.doc_url})", stacklevel=2)

    mw_freq = float(exp.get('mwFreq', 9.5))  # GHz
    B_range = np.asarray(exp.get('Range', [300.0, 400.0]), dtype=float)
    n_points = int(exp.get('nPoints', 1024))
    harmonic = int(exp.get('Harmonic', 1))

    # Parse simulation method ('matrix', 'perturb1', 'perturb2')
    method = opt.get('Method', opt.get('method', exp.get('method', 'matrix'))).lower()

    # Parse linewidth
    lw = np.atleast_1d(sys.lw).flatten()
    lw_gauss = float(lw[0]) if len(lw) >= 1 else 0.3
    lw_lorentz = float(lw[1]) if len(lw) >= 2 else 0.0

    return_both = bool(opt.get('return_both', exp.get('return_both', False)))

    # Build field axis
    B = np.linspace(B_range[0], B_range[1], n_points)
    spc_abs = np.zeros(n_points)
    spc_deriv = np.zeros(n_points)

    cancel_check = opt.get('cancel_check')
    if cancel_check and cancel_check():
        raise InterruptedError("Simulation cancelled")

    # Compute resonance fields according to chosen model
    if method in ('perturb1', 'first_order', 'first'):
        B_res, intensities = _resonance_fields_perturbation(sys, mw_freq, order=1)
    elif method in ('perturb2', 'second_order', 'second'):
        B_res, intensities = _resonance_fields_perturbation(sys, mw_freq, order=2)
    else:  # 'matrix' / exact
        B_res, intensities = _resonance_fields_matrix(sys, mw_freq, (B_range[0], B_range[1]))

    if cancel_check and cancel_check():
        raise InterruptedError("Simulation cancelled")

    # Accumulate lineshapes simultaneously
    for B0, weight in zip(B_res, intensities):
        if cancel_check and cancel_check():
            raise InterruptedError("Simulation cancelled")
        if B0 < B_range[0] or B0 > B_range[1]:
            continue  # skip lines outside the window

        if lw_gauss > 0:
            spc_abs += weight * _gaussian(B, B0, lw_gauss)
            spc_deriv += weight * _deriv_gaussian(B, B0, lw_gauss)
        if lw_lorentz > 0:
            spc_abs += weight * _lorentzian(B, B0, lw_lorentz)
            spc_deriv += weight * _deriv_lorentzian(B, B0, lw_lorentz)
        if lw_gauss == 0 and lw_lorentz == 0:
            idx = np.argmin(np.abs(B - B0))
            spc_abs[idx] += weight
            if 0 < idx < n_points - 1:
                spc_deriv[idx - 1] -= weight
                spc_deriv[idx + 1] += weight

    if return_both:
        return B, spc_abs, spc_deriv
    return B, (spc_deriv if harmonic != 0 else spc_abs)
