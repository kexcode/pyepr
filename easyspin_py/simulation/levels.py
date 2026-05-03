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


def levels(
    sys: SpinSystem,
    B_range: Union[List[float], np.ndarray],
    B_dir: Optional[np.ndarray] = None,
    n_points: int = 200,
) -> Tuple[np.ndarray, np.ndarray]:
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

    Returns
    -------
    E : ndarray of shape (n_states, n_points)
        Energy levels in MHz, sorted ascending at each field point.
    B : ndarray of shape (n_points,)
        Magnetic field values in mT.
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

    for i, B_mag in enumerate(B_vals):
        B_vec = B_mag * B_dir
        # H = H0 - B·mu
        H = H0 - B_vec[0] * mux - B_vec[1] * muy - B_vec[2] * muz
        # Use scipy.linalg.eigvalsh (Hermitian) — returns real eigenvalues, sorted
        E[:, i] = scipy.linalg.eigvalsh(H.toarray())

    return E, B_vals
