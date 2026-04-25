"""
Spin operator matrices (sop.m port).

For a spin system with quantum numbers J1, J2, ..., the basis states are ordered as:
  |J1,  J2,  ...>
  |J1, J2-1, ...>
  ...
  |J1,  -J2, ...>
  |J1-1, J2, ...>
  ...
  |-J1, -J2, ...>

Uses scipy.sparse (COO/CSR) matrices and Kronecker products to build operators
without allocating the full dense matrix until needed.
"""

from __future__ import annotations
from typing import Union, List, Sequence
import numpy as np
import scipy.sparse as sp


def _single_spin_op(J: float, component: str) -> sp.csr_matrix:
    """
    Build a single-spin operator for spin quantum number J.

    Parameters
    ----------
    J : float
        Spin quantum number (0, 0.5, 1, 1.5, ...).
    component : str
        One of 'x', 'y', 'z', '+', '-', 'e' (identity), 'a' (alpha), 'b' (beta).

    Returns
    -------
    scipy.sparse.csr_matrix
        The (2J+1) x (2J+1) operator matrix.
    """
    n = int(2 * J + 1)
    m = np.arange(J, -J - 1, -1)  # mJ from +J down to -J

    if component == 'e':
        # Identity
        return sp.eye(n, format='csr', dtype=complex)

    elif component == 'z':
        # Sz: diagonal matrix with mJ values
        return sp.diags(m, 0, shape=(n, n), format='csr', dtype=complex)

    elif component == '+':
        # S+: raises mJ by 1
        # <mJ+1|S+|mJ> = sqrt(J(J+1) - mJ(mJ+1))
        mJ = m[1:]           # source states (all but highest)
        vals = np.sqrt(J * (J + 1) - mJ * (mJ + 1))
        row = np.arange(n - 1)          # row index of destination state
        col = np.arange(1, n)           # col index of source state
        return sp.csr_matrix((vals, (row, col)), shape=(n, n), dtype=complex)

    elif component == '-':
        # S-: lowers mJ by 1 (Hermitian conjugate of S+)
        mJ = m[1:]
        vals = np.sqrt(J * (J + 1) - mJ * (mJ + 1))
        row = np.arange(1, n)
        col = np.arange(n - 1)
        return sp.csr_matrix((vals, (row, col)), shape=(n, n), dtype=complex)

    elif component == 'x':
        # Sx = (S+ + S-) / 2
        Sp = _single_spin_op(J, '+')
        Sm = _single_spin_op(J, '-')
        return 0.5 * (Sp + Sm)

    elif component == 'y':
        # Sy = (S+ - S-) / (2i)
        Sp = _single_spin_op(J, '+')
        Sm = _single_spin_op(J, '-')
        return (0.5j) * (Sm - Sp)

    elif component == 'a':
        # Alpha state projector, spin-1/2 only
        if J != 0.5:
            raise ValueError("'a' (alpha) is only valid for spin-1/2.")
        return sp.csr_matrix(([1.0], ([0], [0])), shape=(2, 2), dtype=complex)

    elif component == 'b':
        # Beta state projector, spin-1/2 only
        if J != 0.5:
            raise ValueError("'b' (beta) is only valid for spin-1/2.")
        return sp.csr_matrix(([1.0], ([1], [1])), shape=(2, 2), dtype=complex)

    else:
        raise ValueError(f"Unknown spin operator component '{component}'.")


def sop(
    spins: Union[float, List[float], np.ndarray],
    spin_idx: int,
    component: str,
    sparse: bool = True,
) -> Union[sp.csr_matrix, np.ndarray]:
    """
    Build a spin operator for a multi-spin system.

    Equivalent to EasySpin's sop(SpinVec, [spin_idx, component]).

    Parameters
    ----------
    spins : float or list of floats
        Spin quantum numbers for all spins in the system.
    spin_idx : int
        1-based index of the spin to apply the operator to.
    component : str
        Operator component: 'x', 'y', 'z', '+', '-', 'e', 'a', 'b'.
    sparse : bool
        If True, returns a sparse CSR matrix (default). Otherwise, dense.

    Returns
    -------
    numpy.ndarray or scipy.sparse.csr_matrix
        Operator matrix in the full Hilbert space.
    """
    spins = np.atleast_1d(np.asarray(spins, dtype=float))
    n_spins = len(spins)

    if spin_idx < 1 or spin_idx > n_spins:
        raise ValueError(
            f"spin_idx={spin_idx} out of range for {n_spins}-spin system."
        )

    # Build the full operator as a Kronecker product:
    # I ⊗ ... ⊗ I ⊗ Op_k ⊗ I ⊗ ... ⊗ I
    result = sp.eye(1, format='csr', dtype=complex)
    for i, J in enumerate(spins, start=1):
        comp = component if i == spin_idx else 'e'
        M = _single_spin_op(J, comp)
        result = sp.kron(result, M, format='csr')

    if not sparse:
        return result.toarray()
    return result


def sop_multi(
    spins: Union[float, List[float], np.ndarray],
    specs: Sequence[tuple],
    sparse: bool = True,
) -> Union[sp.csr_matrix, np.ndarray]:
    """
    Build a product operator for multiple spins simultaneously.

    This replicates sop(SpinVec, [i1 c1; i2 c2; ...]).

    Parameters
    ----------
    spins : array-like
        All spin quantum numbers.
    specs : list of (spin_idx, component) tuples
        1-based spin index and operator component for each active spin.
    sparse : bool
        Return sparse matrix if True.

    Returns
    -------
    Matrix in the full Hilbert space.
    """
    spins = np.atleast_1d(np.asarray(spins, dtype=float))

    # Map spin index -> component (default identity)
    comp_map = {s: 'e' for s in range(1, len(spins) + 1)}
    for spin_idx, comp in specs:
        comp_map[spin_idx] = comp

    result = sp.eye(1, format='csr', dtype=complex)
    for i, J in enumerate(spins, start=1):
        M = _single_spin_op(J, comp_map[i])
        result = sp.kron(result, M, format='csr')

    if not sparse:
        return result.toarray()
    return result
