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
# Second-order perturbation theory resonance fields for S=1/2
# ---------------------------------------------------------------------------

def _resonance_fields_perturb2_orientation(
    sys: SpinSystem,
    B_dir: np.ndarray,
    mw_freq_MHz: float,
) -> np.ndarray:
    """
    Compute 2nd-order perturbation theory resonance fields for S=1/2 along B_dir.
    Accurately accounts for g-anisotropy, hyperfine anisotropy, and Breit-Rabi shifts.
    """
    g_arr = sys.g.flatten()
    if len(g_arr) == 1:
        gx, gy, gz = g_arr[0], g_arr[0], g_arr[0]
    elif len(g_arr) == 3:
        gx, gy, gz = g_arr[0], g_arr[1], g_arr[2]
    else:
        gx, gy, gz = g_arr[0], g_arr[4], g_arr[8]

    # Effective g along B_dir
    ux, uy, uz = B_dir
    g_eff = float(np.sqrt((gx * ux)**2 + (gy * uy)**2 + (gz * uz)**2))
    if g_eff <= 0:
        return np.array([])

    wx = gx * ux / g_eff
    wy = gy * uy / g_eff
    wz = gz * uz / g_eff

    from easyspin_py.core.constants import bmagn, planck
    gB_factor = g_eff * bmagn / planck / 1e9  # MHz/mT

    if sys.nNuclei == 0:
        return np.array([mw_freq_MHz / gB_factor])

    A_eff_list = []
    A_perp_sq_list = []
    I_list = []

    for nuc in sys.nuclei:
        if nuc.I == 0:
            continue
        I_list.append(nuc.I)
        A_diag = np.diag(nuc.A_eff)
        Ax, Ay, Az = float(A_diag[0]), float(A_diag[1]), float(A_diag[2])
        A_k = float(np.sqrt((Ax * wx)**2 + (Ay * wy)**2 + (Az * wz)**2))
        A_eff_list.append(A_k)
        A_perp_sq = 0.5 * max(0.0, (Ax**2 + Ay**2 + Az**2) - A_k**2)
        A_perp_sq_list.append(A_perp_sq)

    if len(I_list) == 0:
        return np.array([mw_freq_MHz / gB_factor])

    from itertools import product
    grids = [np.arange(-I, I + 1) for I in I_list]
    combos = list(product(*grids))

    res_fields = []
    for mi_tuple in combos:
        hfi_1st = sum(A_eff_list[k] * mi_tuple[k] for k in range(len(I_list)))
        hfi_2nd = sum(
            (A_perp_sq_list[k] / (2.0 * mw_freq_MHz)) * (I_list[k] * (I_list[k] + 1) - mi_tuple[k]**2)
            for k in range(len(I_list))
        )
        nu_0 = mw_freq_MHz - hfi_1st - hfi_2nd
        B_res = nu_0 / gB_factor
        res_fields.append(B_res)

    return np.array(res_fields)


# ---------------------------------------------------------------------------
# Lineshape broadening
# ---------------------------------------------------------------------------

def _gaussian_broaden_both(
    B_axis: np.ndarray,
    B_res_list: np.ndarray,
    weights: np.ndarray,
    lw_gauss: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Accumulate Gaussian-broadened sticks onto B_axis for both absorption and 1st derivative."""
    spc_abs = np.zeros(len(B_axis))
    spc_deriv = np.zeros(len(B_axis))
    if lw_gauss <= 0 or len(B_res_list) == 0:
        return spc_abs, spc_deriv
    sigma = lw_gauss / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    inv_sigma2 = 1.0 / (sigma ** 2)

    for B0, w in zip(B_res_list, weights):
        diff = B_axis - B0
        gauss = w * np.exp(-0.5 * (diff / sigma) ** 2)
        spc_abs += gauss
        spc_deriv += -diff * inv_sigma2 * gauss

    return spc_abs, spc_deriv


def _gaussian_broaden(
    B_axis: np.ndarray,
    B_res_list: np.ndarray,
    weights: np.ndarray,
    lw_gauss: float,
    harmonic: int,
) -> np.ndarray:
    """Accumulate Gaussian-broadened sticks onto B_axis."""
    spc_abs, spc_deriv = _gaussian_broaden_both(B_axis, B_res_list, weights, lw_gauss)
    return spc_deriv if harmonic != 0 else spc_abs


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

    method = str(exp.get('method', opt.get('method', 'matrix'))).lower()
    use_perturb2 = (method in ('perturb2', 'perturb') and len(sys.S) == 1 and sys.S[0] == 0.5)

    # Precompute field-independent operators if doing matrix diagonalization
    if not use_perturb2:
        H0, mux, muy, muz = ham(sys)

    # Check for single orientation mode
    single_ori = bool(exp.get('singleOrientation', opt.get('singleOrientation', False)))
    ori_angles = exp.get('orientation', opt.get('orientation', exp.get('Orientation', None)))

    spc = np.zeros(n_points)
    all_B_res = []
    all_weights = []

    if single_ori and ori_angles is not None and len(ori_angles) >= 2:
        # Single crystal / orientation calculation
        theta_rad = np.radians(float(ori_angles[0]))
        phi_rad = np.radians(float(ori_angles[1]))
        B_dir = _B_direction(theta_rad, phi_rad)

        if use_perturb2:
            B_res = _resonance_fields_perturb2_orientation(sys, B_dir, mw_freq_MHz)
        else:
            B_res = _find_resonance_fields(
                sys, B_dir, mw_freq_MHz, B_internal,
                H0, mux, muy, muz
            )
        for B0 in B_res:
            all_B_res.append(B0)
            all_weights.append(1.0)
    else:
        # Powder orientation grid
        thetas, phis, grid_weights = _make_powder_grid(n_theta, n_phi)

        for i_theta, theta in enumerate(thetas):
            for i_phi, phi in enumerate(phis):
                B_dir = _B_direction(theta, phi)
                w = grid_weights[i_theta, i_phi]

                if use_perturb2:
                    B_res = _resonance_fields_perturb2_orientation(sys, B_dir, mw_freq_MHz)
                else:
                    B_res = _find_resonance_fields(
                        sys, B_dir, mw_freq_MHz, B_internal,
                        H0, mux, muy, muz
                    )

                for B0 in B_res:
                    all_B_res.append(B0)
                    all_weights.append(w)

    return_both = bool(opt.get('return_both', exp.get('return_both', False)))

    spc_abs = np.zeros(n_points)
    spc_deriv = np.zeros(n_points)
    if len(all_B_res) > 0:
        all_B_res = np.array(all_B_res)
        all_weights = np.array(all_weights)
        spc_abs, spc_deriv = _gaussian_broaden_both(B_axis, all_B_res, all_weights, lw_gauss)

    if return_both:
        return B_axis, spc_abs, spc_deriv
    return B_axis, (spc_deriv if harmonic != 0 else spc_abs)
