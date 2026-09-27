"""
Solid-state CW EPR spectrum simulator (pepper.m port).

Simulates the powder CW EPR spectrum of a paramagnetic center in a solid
(powder or single crystal). Uses eigenfield diagonalization across a
spherical grid of orientations.

For a powder spectrum, the resonance fields are averaged over all molecular
orientations (theta, phi) weighted by sin(theta) for an isotropic distribution.

This implementation uses a simple Lebedev-like Euler angle grid. For the
minimal port needed by the app, we implement:
  - Powder averaging via a theta/phi grid (Euler ZYZ convention)
  - Eigenfield method: find B where E_i(B) - E_j(B) = h*nu for allowed transitions
  - Binning of resonance fields onto a B-axis with Gaussian broadening

Usage
-----
    from easyspin_py.core.spin_system import SpinSystem
    from easyspin_py.simulation.pepper import pepper

    sys = SpinSystem(S=1.0, g=[2.0, 2.05, 2.10], D=[800.0, 80.0], lw=1.0)
    exp = dict(mwFreq=9.5, Range=[250, 450])
    B, spc = pepper(sys, exp)
"""

from __future__ import annotations
import warnings
from typing import Dict, Any, Optional, Tuple

import numpy as np
import scipy.linalg

from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.hamiltonian.builder import ham
from easyspin_py.core.constants import bmagn, planck
from easyspin_py.simulation.validator import validate_pepper, Severity


# ---------------------------------------------------------------------------
# Powder orientation grid
# ---------------------------------------------------------------------------

def _make_powder_grid(n_theta: int = 20, n_phi: int = 40) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate a spherical grid of (theta, phi) orientations with sin(theta) weights.
    Uses a simple uniform grid; for production use a Lebedev grid instead.

    Returns
    -------
    thetas : (n_theta,) array of polar angles [0, pi/2] (upper hemisphere only)
    phis   : (n_phi,) array of azimuthal angles [0, 2*pi)
    weights: (n_theta, n_phi) weight matrix normalized to sum to 1
    """
    thetas = np.linspace(0, np.pi / 2, n_theta, endpoint=False) + np.pi / (4 * n_theta)
    phis = np.linspace(0, 2 * np.pi, n_phi, endpoint=False)

    # Weight = sin(theta) * dtheta * dphi (solid angle element)
    sin_weights = np.sin(thetas)
    weights = np.outer(sin_weights, np.ones(n_phi))
    weights /= weights.sum()

    return thetas, phis, weights


# ---------------------------------------------------------------------------
# Field direction from spherical angles
# ---------------------------------------------------------------------------

def _B_direction(theta: float, phi: float) -> np.ndarray:
    """Convert spherical angles (theta, phi) to a Cartesian unit vector."""
    return np.array([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta)
    ])


# ---------------------------------------------------------------------------
# Resonance field solver via linear interpolation
# ---------------------------------------------------------------------------

def _find_resonance_fields(
    sys: SpinSystem,
    B_dir: np.ndarray,
    mw_freq_MHz: float,
    B_vals: np.ndarray,
    H0: object,
    mux: object,
    muy: object,
    muz: object,
) -> np.ndarray:
    """
    For a given orientation B_dir, find the resonance fields where any energy
    gap equals h*nu (mw_freq_MHz) using linear interpolation of eigenvalue
    differences across the B sweep.

    Returns array of resonance fields in mT (may be empty).
    """
    n_pts = len(B_vals)
    n_states = sys.hsdim()

    # Compute eigenvalues at each field point
    E = np.zeros((n_states, n_pts))
    for i, B_mag in enumerate(B_vals):
        B_vec = B_mag * B_dir
        H = H0 - B_vec[0] * mux - B_vec[1] * muy - B_vec[2] * muz
        E[:, i] = scipy.linalg.eigvalsh(H.toarray())

    # Find all pairs of levels and look for crossings at E_j - E_i = mw_freq_MHz
    res_fields = []
    for i in range(n_states):
        for j in range(i + 1, n_states):
            gap = E[j] - E[i]  # energy gap in MHz
            diff = gap - mw_freq_MHz  # should cross zero at resonance

            # Look for sign changes (zero crossings)
            sign_changes = np.where(np.diff(np.sign(diff)))[0]
            for k in sign_changes:
                # Linear interpolation for the exact crossing point
                d0, d1 = diff[k], diff[k + 1]
                B0, B1 = B_vals[k], B_vals[k + 1]
                B_res = B0 + (B1 - B0) * (-d0) / (d1 - d0)
                res_fields.append(B_res)

    return np.array(res_fields)


# ---------------------------------------------------------------------------
# Lineshape broadening
# ---------------------------------------------------------------------------

def _gaussian_broaden(
    B_axis: np.ndarray,
    B_res_list: np.ndarray,
    weights: np.ndarray,
    lw_gauss: float,
    harmonic: int,
) -> np.ndarray:
    """Accumulate Gaussian-broadened sticks onto B_axis."""
    spc = np.zeros(len(B_axis))
    if lw_gauss <= 0:
        return spc
    sigma = lw_gauss / (2.0 * np.sqrt(2.0 * np.log(2.0)))

    for B0, w in zip(B_res_list, weights):
        if harmonic == 0:
            spc += w * np.exp(-0.5 * ((B_axis - B0) / sigma) ** 2)
        else:
            spc += w * -(B_axis - B0) / sigma ** 2 * np.exp(-0.5 * ((B_axis - B0) / sigma) ** 2)

    return spc


# ---------------------------------------------------------------------------
# Main pepper function
# ---------------------------------------------------------------------------

def pepper(
    sys: SpinSystem,
    exp: Dict[str, Any],
    opt: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate solid-state powder CW EPR spectrum.

    Parameters
    ----------
    sys : SpinSystem
        Spin system with g (3-vector or 3x3), D (ZFS), A (HFI), lw.
    exp : dict
        - 'mwFreq'  : microwave frequency in GHz (default 9.5)
        - 'Range'   : [B_min, B_max] in mT (default [280, 420])
        - 'nPoints' : number of spectrum points (default 1024)
        - 'Harmonic': 0 = absorption, 1 = first derivative (default 1)
    opt : dict, optional
        - 'nKnots'  : number of theta knots for powder average (default 20)
        - 'nPhi'    : number of phi points (default 40)
        - 'nB'      : number of B points for internal sweep (default 200)

    Returns
    -------
    B : ndarray of shape (nPoints,)
        Magnetic field axis in mT.
    spc : ndarray of shape (nPoints,)
        EPR spectrum.
    """
    if opt is None:
        opt = {}

    # --- Validate spin system against pepper() constraints ---
    result = validate_pepper(sys)
    for msg in result.messages:
        if msg.severity == Severity.ERROR:
            raise ValueError(f"[pepper] {msg.message} (see {msg.doc_url})")
        elif msg.severity == Severity.WARNING:
            warnings.warn(f"[pepper] {msg.message} (see {msg.doc_url})", stacklevel=2)

    mw_freq_GHz = float(exp.get('mwFreq', 9.5))
    mw_freq_MHz = mw_freq_GHz * 1e3
    B_range = np.asarray(exp.get('Range', [280.0, 420.0]), dtype=float)
    n_points = int(exp.get('nPoints', 1024))
    harmonic = int(exp.get('Harmonic', 1))
    n_theta = int(opt.get('nKnots', 20))
    n_phi = int(opt.get('nPhi', 40))
    n_B = int(opt.get('nB', 150))

    # Linewidth
    lw = np.atleast_1d(sys.lw).flatten()
    lw_gauss = float(lw[0]) if len(lw) >= 1 else 1.0

    # Output B axis
    B_axis = np.linspace(B_range[0], B_range[1], n_points)

    # Internal B sweep for eigenvalue tracking
    B_internal = np.linspace(B_range[0], B_range[1], n_B)

    # Precompute field-independent operators
    H0, mux, muy, muz = ham(sys)

    # Powder orientation grid
    thetas, phis, grid_weights = _make_powder_grid(n_theta, n_phi)

    spc = np.zeros(n_points)
    all_B_res = []
    all_weights = []

    for i_theta, theta in enumerate(thetas):
        for i_phi, phi in enumerate(phis):
            B_dir = _B_direction(theta, phi)
            w = grid_weights[i_theta, i_phi]

            B_res = _find_resonance_fields(
                sys, B_dir, mw_freq_MHz, B_internal,
                H0, mux, muy, muz
            )

            for B0 in B_res:
                all_B_res.append(B0)
                all_weights.append(w)

    if len(all_B_res) > 0:
        all_B_res = np.array(all_B_res)
        all_weights = np.array(all_weights)
        spc = _gaussian_broaden(B_axis, all_B_res, all_weights, lw_gauss, harmonic)

    return B_axis, spc
