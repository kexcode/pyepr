"""
Hamiltonian builder (ham.m port).

Assembles the full spin Hamiltonian:
    H = H0 - B[0]*mux - B[1]*muy - B[2]*muz

where:
    H0  = field-independent part (ZFS + HFI + NQI)
    mux, muy, muz = magnetic dipole moment operators (electron + nuclear Zeeman)

All energies are in MHz; field in mT.

Usage
-----
    from easyspin_py.hamiltonian.builder import ham

    # Field-independent components
    H0, mux, muy, muz = ham(sys)

    # Full Hamiltonian at a specific field vector B (in mT)
    H = ham(sys, B=[0, 0, 350.0])
"""

from __future__ import annotations
from typing import Optional, Tuple, Union

import numpy as np
import scipy.sparse as sp

from easyspin_py.core.constants import bmagn, nmagn, planck
from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.core.operators import sop, sop_multi


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _all_spins(sys: SpinSystem) -> np.ndarray:
    """Full spin vector: [electron spins..., nuclear spins...]."""
    return np.concatenate([sys.S, sys.I])


def _nstates(sys: SpinSystem) -> int:
    return sys.hsdim()


# ---------------------------------------------------------------------------
# Electron Zeeman Hamiltonian
# ham_ez.m port
# ---------------------------------------------------------------------------

def ham_ez(sys: SpinSystem) -> Tuple[sp.csr_matrix, sp.csr_matrix, sp.csr_matrix]:
    """
    Electron Zeeman magnetic moment operators (mux, muy, muz) in MHz/mT.

    Returns
    -------
    mux, muy, muz : scipy.sparse.csr_matrix
        Magnetic dipole moment components along x, y, z.
        H_Zeeman = -(mux*Bx + muy*By + muz*Bz)
    """
    spins = _all_spins(sys)
    nstates = _nstates(sys)
    mux = sp.csr_matrix((nstates, nstates), dtype=complex)
    muy = sp.csr_matrix((nstates, nstates), dtype=complex)
    muz = sp.csr_matrix((nstates, nstates), dtype=complex)

    # Prefactor: -bmagn/h * g  [Hz/T] -> [MHz/mT]
    # bmagn/planck = 13.9962 GHz/T = 13.9962 MHz/mT
    pre_factor = -bmagn / planck / 1e9  # MHz/mT per unit g

    g_arr = np.atleast_2d(sys.g)
    if g_arr.shape == (1,):  # scalar g
        g_arr = np.array([[g_arr[0], 0, 0],
                          [0, g_arr[0], 0],
                          [0, 0, g_arr[0]]])

    # Handle g being a 3-vector (principal values) or 3x3 matrix
    g_arr = sys.g
    if g_arr.ndim == 1:
        if len(g_arr) == 1:
            g_mat = np.diag([g_arr[0]] * 3)
        elif len(g_arr) == 3:
            g_mat = np.diag(g_arr)
        else:
            raise ValueError("Sys.g must be scalar, 3-vector, or 3x3 matrix.")
    elif g_arr.ndim == 2 and g_arr.shape == (3, 3):
        g_mat = g_arr
    else:
        raise ValueError("Sys.g must be scalar, 3-vector, or 3x3 matrix.")

    for e_idx in range(1, sys.nElectrons + 1):
        for k, comp in enumerate(['x', 'y', 'z'], start=1):
            Sk = sop(spins, e_idx, comp, sparse=True)
            pre = pre_factor * g_mat
            mux = mux + pre[0, k - 1] * Sk
            muy = muy + pre[1, k - 1] * Sk
            muz = muz + pre[2, k - 1] * Sk

    return mux, muy, muz


# ---------------------------------------------------------------------------
# Nuclear Zeeman Hamiltonian
# ham_nz.m port
# ---------------------------------------------------------------------------

def ham_nz(sys: SpinSystem) -> Tuple[sp.csr_matrix, sp.csr_matrix, sp.csr_matrix]:
    """
    Nuclear Zeeman magnetic moment operators (mux, muy, muz) in MHz/mT.
    H_nz = +(mux*Bx + muy*By + muz*Bz)   (sign convention: +nmagn gn I·B)
    """
    spins = _all_spins(sys)
    nstates = _nstates(sys)
    mux = sp.csr_matrix((nstates, nstates), dtype=complex)
    muy = sp.csr_matrix((nstates, nstates), dtype=complex)
    muz = sp.csr_matrix((nstates, nstates), dtype=complex)

    if sys.nNuclei == 0:
        return mux, muy, muz

    # Prefactor: +nmagn/h * gn  [MHz/mT]
    pre_factor = nmagn / planck / 1e9  # MHz/mT per unit gn

    for n_idx, (gn, I) in enumerate(zip(sys.gn, sys.I), start=1):
        # Global index in full spin vector
        global_idx = sys.nElectrons + n_idx
        pre = pre_factor * gn

        Ix = sop(spins, global_idx, 'x', sparse=True)
        Iy = sop(spins, global_idx, 'y', sparse=True)
        Iz = sop(spins, global_idx, 'z', sparse=True)

        mux = mux + pre * Ix
        muy = muy + pre * Iy
        muz = muz + pre * Iz

    return mux, muy, muz


# ---------------------------------------------------------------------------
# Hyperfine Interaction Hamiltonian
# ham_hf.m port
# ---------------------------------------------------------------------------

def ham_hf(sys: SpinSystem) -> sp.csr_matrix:
    """
    Hyperfine interaction Hamiltonian S·A·I in MHz.

    Supports:
    - Scalar A (isotropic coupling)
    - 3-vector A (principal values)
    - 3x3 matrix A (full tensor, not yet supported by SpinSystem)
    """
    spins = _all_spins(sys)
    nstates = _nstates(sys)
    Hhf = sp.csr_matrix((nstates, nstates), dtype=complex)

    if sys.nNuclei == 0 or len(sys.A) == 0:
        return Hhf

    A_arr = np.atleast_1d(sys.A)

    for n_idx in range(sys.nNuclei):
        if sys.I[n_idx] == 0:
            continue

        # Build A matrix for this nucleus (row = electron spin component 1..nElectrons)
        # For a 1-electron system the A array is indexed directly per nucleus
        if A_arr.ndim == 1:
            # One A value per nucleus (isotropic)
            a_val = A_arr[n_idx] if n_idx < len(A_arr) else 0.0
            A_mat = np.diag([a_val, a_val, a_val])
        elif A_arr.ndim == 2 and A_arr.shape[1] == 3:
            # 3 principal values per nucleus
            A_mat = np.diag(A_arr[n_idx])
        else:
            A_mat = A_arr

        global_n = sys.nElectrons + n_idx + 1  # 1-based

        for e_idx in range(1, sys.nElectrons + 1):
            for c1, comp1 in enumerate(['x', 'y', 'z']):
                Se = sop(spins, e_idx, comp1, sparse=True)
                for c2, comp2 in enumerate(['x', 'y', 'z']):
                    In = sop(spins, global_n, comp2, sparse=True)
                    Hhf = Hhf + A_mat[c1, c2] * (Se @ In)

    Hhf = (Hhf + Hhf.conj().T) / 2  # Hermitianize
    return Hhf


# ---------------------------------------------------------------------------
# Zero-Field Splitting Hamiltonian
# ham_zf.m port (quadratic SDS term only — sufficient for app's use cases)
# ---------------------------------------------------------------------------

def ham_zf(sys: SpinSystem) -> sp.csr_matrix:
    """
    Zero-field splitting Hamiltonian S·D·S in MHz.

    Sys.D can be:
    - 1-element [D]             → D_ax = D, E = 0
    - 2-element [D, E]          → Dxx=-D/3+E, Dyy=-D/3-E, Dzz=2D/3
    - 3-element [Dxx, Dyy, Dzz] → principal values
    - 3x3 full D matrix         (not yet supported via simple SpinSystem)
    """
    spins = _all_spins(sys)
    nstates = _nstates(sys)
    Hzf = sp.csr_matrix((nstates, nstates), dtype=complex)

    D_arr = np.atleast_1d(sys.D)
    if len(D_arr) == 0 or not np.any(D_arr):
        return Hzf

    # Unpack D array to 3x3 matrix
    if len(D_arr) == 1:
        D, E = D_arr[0], 0.0
        D_mat = np.diag([-D / 3 + E, -D / 3 - E, 2 * D / 3])
    elif len(D_arr) == 2:
        D, E = D_arr[0], D_arr[1]
        D_mat = np.diag([-D / 3 + E, -D / 3 - E, 2 * D / 3])
    elif len(D_arr) == 3:
        D_mat = np.diag(D_arr)
    elif D_arr.shape == (3, 3):
        D_mat = D_arr
    else:
        raise ValueError("Sys.D must be 1-, 2-, 3-element or 3x3 array.")

    for e_idx in range(1, sys.nElectrons + 1):
        Sxyz = [sop(spins, e_idx, c, sparse=True) for c in ['x', 'y', 'z']]
        for c1 in range(3):
            for c2 in range(3):
                if D_mat[c1, c2] != 0:
                    Hzf = Hzf + D_mat[c1, c2] * (Sxyz[c1] @ Sxyz[c2])

    Hzf = (Hzf + Hzf.conj().T) / 2
    return Hzf


# ---------------------------------------------------------------------------
# Nuclear Quadrupole Hamiltonian
# ham_nq.m port
# ---------------------------------------------------------------------------

def ham_nq(sys: SpinSystem) -> sp.csr_matrix:
    """
    Nuclear quadrupole interaction Hamiltonian I·Q·I in MHz.
    """
    spins = _all_spins(sys)
    nstates = _nstates(sys)
    Hnq = sp.csr_matrix((nstates, nstates), dtype=complex)

    if sys.nNuclei == 0 or len(sys.Q) == 0 or not np.any(sys.Q):
        return Hnq

    Q_arr = np.atleast_1d(sys.Q)

    for n_idx in range(sys.nNuclei):
        if sys.I[n_idx] < 1:
            continue  # quadrupole only for I >= 1

        q_val = Q_arr[n_idx] if n_idx < len(Q_arr) else 0.0
        if q_val == 0:
            continue

        # For simple scalar Q input, interpret as the axial quadrupole coupling
        Q_mat = np.diag([-q_val / 3, -q_val / 3, 2 * q_val / 3])

        global_n = sys.nElectrons + n_idx + 1
        Ixyz = [sop(spins, global_n, c, sparse=True) for c in ['x', 'y', 'z']]

        for k in range(3):
            for q in range(3):
                if Q_mat[k, q] != 0:
                    Hnq = Hnq + Ixyz[k] @ (Q_mat[k, q] * Ixyz[q])

    Hnq = (Hnq + Hnq.conj().T) / 2
    return Hnq


# ---------------------------------------------------------------------------
# Main Hamiltonian assembler
# ham.m port
# ---------------------------------------------------------------------------

def ham(
    sys: SpinSystem,
    B: Optional[np.ndarray] = None,
) -> Union[
    Tuple[sp.csr_matrix, sp.csr_matrix, sp.csr_matrix, sp.csr_matrix],
    sp.csr_matrix,
]:
    """
    Build the complete spin Hamiltonian.

    Parameters
    ----------
    sys : SpinSystem
        Spin system parameters.
    B : array-like of shape (3,), optional
        Magnetic field vector in mT (Bx, By, Bz) in the molecular frame.
        If None, returns (H0, mux, muy, muz).
        If provided, returns the full Hamiltonian H = H0 - norm(B)*muzL.

    Returns
    -------
    If B is None:
        (H0, mux, muy, muz) : 4-tuple of sparse matrices
            H0   : field-independent Hamiltonian (MHz)
            mux,muy,muz : magnetic moment operators (MHz/mT)
    If B is given:
        H : sparse matrix
            Full Hamiltonian at field B (MHz)
    """
    # Field-independent part
    H0 = ham_zf(sys) + ham_hf(sys) + ham_nq(sys)

    # Magnetic moment operators
    emux, emuy, emuz = ham_ez(sys)
    if sys.nNuclei > 0:
        nmux, nmuy, nmuz = ham_nz(sys)
        mux = emux + nmux
        muy = emuy + nmuy
        muz = emuz + nmuz
    else:
        mux, muy, muz = emux, emuy, emuz

    if B is None:
        return H0, mux, muy, muz

    # Full Hamiltonian: H = H0 - B·mu
    B = np.asarray(B, dtype=float)
    if B.shape != (3,):
        raise ValueError("B must be a 3-element array [Bx, By, Bz] in mT.")

    H = H0 - B[0] * mux - B[1] * muy - B[2] * muz
    return H
