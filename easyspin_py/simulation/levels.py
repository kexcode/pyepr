"""
Energy level diagram computation (levels.m port).

Computes the eigenvalues of the spin Hamiltonian as a function of magnetic
field magnitude, replicating EasySpin's levels() function.

Usage
-----
    from easyspin_py.core.spin_system import SpinSystem
    from easyspin_py.simulation.levels import levels

    sys = SpinSystem(S=0.5, g=2.0023, Nucs='14N', A=[40.0])
    B_range = [0, 400]   # mT
    E, B = levels(sys, B_range, n_points=200)

    # E shape: (n_states, n_points)
    # B shape: (n_points,)
"""

from __future__ import annotations
from typing import Optional, Tuple, Union, List

import numpy as np
import scipy.linalg

from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.hamiltonian.builder import ham


def compute_transitions(
    sys: SpinSystem,
    B_range: Union[List[float], np.ndarray],
    mw_freq_GHz: float = 9.5,
    B_dir: Optional[np.ndarray] = None,
    method: str = "matrix",
) -> List[dict]:
    """
    Find resonance fields and calculate EPR transition probabilities.

    Parameters
    ----------
    sys : SpinSystem
        Spin system.
    B_range : list or ndarray of shape (2,)
        [B_min, B_max] in mT.
    mw_freq_GHz : float
        Microwave frequency in GHz.
    B_dir : ndarray of shape (3,), optional
        Field direction (default z-axis).
    method : str
        'matrix', 'perturb1', or 'perturb2'.

    Returns
    -------
    transitions : list of dict
        Each dict contains:
            B_res : float (mT)
            E_lower : float (MHz)
            E_upper : float (MHz)
            lower_idx : int (0-based)
            upper_idx : int (0-based)
            intensity : float (normalized to max=1.0)
    """
    B_range = np.asarray(B_range, dtype=float)
    mw_freq_MHz = float(mw_freq_GHz) * 1e3
    n_states = sys.hsdim()

    if B_dir is None:
        B_dir = np.array([0.0, 0.0, 1.0])
    else:
        B_dir = np.asarray(B_dir, dtype=float)
        norm = np.linalg.norm(B_dir)
        if norm > 0:
            B_dir = B_dir / norm
        else:
            B_dir = np.array([0.0, 0.0, 1.0])

    H0, mux, muy, muz = ham(sys)
    mu_B = B_dir[0] * mux + B_dir[1] * muy + B_dir[2] * muz

    # Construct perpendicular detection operators (perpendicular to B_dir)
    # Pick arbitrary unit vector not parallel to B_dir
    ref = np.array([1.0, 0.0, 0.0]) if abs(B_dir[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x_perp = np.cross(B_dir, ref)
    x_perp /= np.linalg.norm(x_perp)
    y_perp = np.cross(B_dir, x_perp)

    mux_perp = x_perp[0] * mux + x_perp[1] * muy + x_perp[2] * muz
    muy_perp = y_perp[0] * mux + y_perp[1] * muy + y_perp[2] * muz

    # Search for eigenvalue crossings across B_range
    n_search = max(200, int((B_range[1] - B_range[0]) * 1.5))
    n_search = min(600, max(100, n_search))
    B_vals = np.linspace(B_range[0], B_range[1], n_search)

    E_grid = np.zeros((n_states, n_search))
    for k, b_val in enumerate(B_vals):
        H = H0 - b_val * mu_B
        E_grid[:, k] = scipy.linalg.eigvalsh(H.toarray())

    raw_transitions = []

    for i in range(n_states):
        for j in range(i + 1, n_states):
            gap = E_grid[j] - E_grid[i]
            diff = gap - mw_freq_MHz
            sign_changes = np.where(np.diff(np.sign(diff)))[0]

            for k in sign_changes:
                d0, d1 = diff[k], diff[k + 1]
                denom = d1 - d0
                if abs(denom) < 1e-12:
                    continue
                B_res = B_vals[k] + (B_vals[k + 1] - B_vals[k]) * (-d0) / denom

                if B_res < B_range[0] or B_res > B_range[1]:
                    continue

                # Diagonalize at B_res to get precise levels and eigenvectors
                H_res = H0 - B_res * mu_B
                evals, evecs = scipy.linalg.eigh(H_res.toarray())

                ui = evecs[:, i]
                uj = evecs[:, j]

                # Transition probability: |<i|mux_perp|j>|^2 + |<i|muy_perp|j>|^2
                mx = np.abs(ui.conj().T @ mux_perp.toarray() @ uj) ** 2
                my = np.abs(ui.conj().T @ muy_perp.toarray() @ uj) ** 2
                prob = float(mx + my)

                raw_transitions.append({
                    "B_res": float(B_res),
                    "E_lower": float(evals[i]),
                    "E_upper": float(evals[j]),
                    "lower_idx": int(i),
                    "upper_idx": int(j),
                    "raw_prob": prob,
                })

    if not raw_transitions:
        return []

    # Normalize intensities to max = 1.0
    max_p = max(t["raw_prob"] for t in raw_transitions)
    if max_p <= 0:
        max_p = 1.0

    result = []
    for t in raw_transitions:
        rel_int = t["raw_prob"] / max_p
        if rel_int >= 0.005:  # threshold out negligible transitions
            result.append({
                "B_res": round(t["B_res"], 2),
                "E_lower": round(t["E_lower"], 2),
                "E_upper": round(t["E_upper"], 2),
                "lower_idx": t["lower_idx"],
                "upper_idx": t["upper_idx"],
                "intensity": round(rel_int, 4),
            })

    result.sort(key=lambda x: x["B_res"])
    return result


def levels(
    sys: SpinSystem,
    B_range: Union[List[float], np.ndarray],
    B_dir: Optional[np.ndarray] = None,
    n_points: int = 200,
    method: str = "matrix",
    mw_freq_GHz: Optional[float] = None,
    return_transitions: bool = False,
) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, List[dict]]]:
    """
    Compute energy levels of the spin system as a function of magnetic field.

    Replicates EasySpin's levels(Sys, Exp) where Exp.Range defines the field sweep
    and Exp.mwFreq is omitted (we return raw energies in MHz).

    Parameters
    ----------
    sys : SpinSystem
        Spin system parameters.
    B_range : list or ndarray of shape (2,)
        [B_min, B_max] magnetic field range in mT.
    B_dir : ndarray of shape (3,), optional
        Unit vector defining the field direction in the molecular frame.
        Default is [0, 0, 1] (z-axis, standard lab frame).
    n_points : int
        Number of field points to compute. Default is 200.
    method : str
        Calculation model: 'matrix' (exact diagonalization), 'perturb1' (1st order),
        or 'perturb2' (2nd order).
    mw_freq_GHz : float, optional
        Microwave frequency in GHz for EPR transition determination.
    return_transitions : bool
        If True, returns (E, B, transitions). Default is False for backwards compatibility.

    Returns
    -------
    E : ndarray of shape (n_states, n_points)
        Energy levels in MHz, sorted ascending at each field point.
    B : ndarray of shape (n_points,)
        Magnetic field values in mT.
    transitions : list of dict (only if return_transitions=True)
    """
    B_range = np.asarray(B_range, dtype=float)
    if B_range.shape != (2,):
        raise ValueError("B_range must be a 2-element array [B_min, B_max] in mT.")
    if B_range[0] > B_range[1]:
        raise ValueError("B_range[0] must be <= B_range[1].")

    # Default field direction: along z
    if B_dir is None:
        B_dir = np.array([0.0, 0.0, 1.0])
    else:
        B_dir = np.asarray(B_dir, dtype=float)
        norm = np.linalg.norm(B_dir)
        if norm == 0:
            raise ValueError("B_dir cannot be a zero vector.")
        B_dir = B_dir / norm

    n_states = sys.hsdim()
    B_vals = np.linspace(B_range[0], B_range[1], n_points)
    E = np.zeros((n_states, n_points))

    # Precompute field-independent H0 and moment operators once
    H0, mux, muy, muz = ham(sys)
    mu_B = B_dir[0] * mux + B_dir[1] * muy + B_dir[2] * muz

    method_lower = method.lower() if isinstance(method, str) else "matrix"

    if method_lower in ('perturb1', 'first_order') and len(sys.S) == 1 and sys.S[0] == 0.5:
        # First-order perturbation energy levels: straight lines
        from easyspin_py.core.constants import bmagn, planck
        g_arr = sys.g.flatten()
        g_eff = float(g_arr[0]) if len(g_arr) == 1 else float(np.mean(g_arr[:3]))
        gB_factor = g_eff * bmagn / planck / 1e9  # MHz/mT

        # Hyperfine values
        A_arr = np.atleast_1d(sys.A) if sys.nNuclei > 0 else np.array([])
        from itertools import product
        if sys.nNuclei > 0:
            grids = [np.arange(-I, I + 1) for I in sys.I]
            combos = list(product(*grids))
        else:
            combos = [()]

        state_idx = 0
        for mS in [-0.5, 0.5]:
            for mi in combos:
                if state_idx >= n_states:
                    break
                hfi_shift = sum(mS * (A_arr[k] if k < len(A_arr) else 0.0) * mi[k] for k in range(len(mi)))
                E[state_idx, :] = mS * gB_factor * B_vals + hfi_shift
                state_idx += 1
        E = np.sort(E, axis=0)

    elif method_lower in ('perturb2', 'second_order') and len(sys.S) == 1 and sys.S[0] == 0.5:
        # Second-order perturbation energy levels
        from easyspin_py.core.constants import bmagn, planck
        g_arr = sys.g.flatten()
        g_eff = float(g_arr[0]) if len(g_arr) == 1 else float(np.mean(g_arr[:3]))
        gB_factor = g_eff * bmagn / planck / 1e9  # MHz/mT

        A_arr = np.atleast_1d(sys.A) if sys.nNuclei > 0 else np.array([])
        from itertools import product
        if sys.nNuclei > 0:
            grids = [np.arange(-I, I + 1) for I in sys.I]
            combos = list(product(*grids))
        else:
            combos = [()]

        state_idx = 0
        for mS in [-0.5, 0.5]:
            for mi in combos:
                if state_idx >= n_states:
                    break
                hfi_shift = sum(mS * (A_arr[k] if k < len(A_arr) else 0.0) * mi[k] for k in range(len(mi)))
                # 2nd order curvature: A^2 / (4 * g * B) * (I(I+1) - mI^2)
                curv = 0.0
                if sys.nNuclei > 0:
                    for k in range(len(mi)):
                        ak = A_arr[k] if k < len(A_arr) else 0.0
                        Ik = sys.I[k]
                        curv += (ak ** 2) * (Ik * (Ik + 1.0) - mi[k] ** 2)
                denom = 4.0 * np.maximum(gB_factor * B_vals, 50.0)
                e2 = np.sign(mS) * curv / denom
                E[state_idx, :] = mS * gB_factor * B_vals + hfi_shift + e2
                state_idx += 1
        E = np.sort(E, axis=0)

    else:
        # Exact matrix diagonalization
        for i, B_mag in enumerate(B_vals):
            H = H0 - B_mag * mu_B
            E[:, i] = scipy.linalg.eigvalsh(H.toarray())

    if return_transitions:
        freq = mw_freq_GHz if mw_freq_GHz is not None else 9.5
        trans = compute_transitions(sys, B_range, mw_freq_GHz=freq, B_dir=B_dir, method=method)
        return E, B_vals, trans

    return E, B_vals
