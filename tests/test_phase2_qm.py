r"""
Smoke test for Phase 2: Quantum Mechanics Engine.

Validates that:
1. sop() builds correct Sz, S+ matrices for spin-1/2 and spin-1.
2. ham() returns correct energy levels for a simple S=1/2, I=1H system.

Run with:
    cd c:\Users\Media Center\Documents\projects\eprsim
    python -m pytest tests/test_phase2_qm.py -v
  or simply:
    python tests/test_phase2_qm.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
# spla not needed — using dense eigvalsh for small matrices
from easyspin_py.core.operators import sop, _single_spin_op
from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.hamiltonian.builder import ham


def test_sz_spin_half():
    """Sz for spin-1/2 should be [[0.5, 0], [0, -0.5]]."""
    Sz = _single_spin_op(0.5, 'z').toarray()
    expected = np.array([[0.5, 0], [0, -0.5]], dtype=complex)
    assert np.allclose(Sz, expected), f"Sz wrong:\n{Sz}"
    print("PASS: Sz spin-1/2")


def test_sx_spin_half():
    """Sx for spin-1/2 should be [[0, 0.5], [0.5, 0]]."""
    Sx = _single_spin_op(0.5, 'x').toarray()
    expected = np.array([[0, 0.5], [0.5, 0]], dtype=complex)
    assert np.allclose(Sx, expected), f"Sx wrong:\n{Sx}"
    print("PASS: Sx spin-1/2")


def test_sz_spin1():
    """Sz for spin-1 should have diagonal [1, 0, -1]."""
    Sz = _single_spin_op(1.0, 'z').toarray()
    expected = np.diag([1.0, 0.0, -1.0])
    assert np.allclose(Sz, expected), f"Sz spin-1 wrong:\n{Sz}"
    print("PASS: Sz spin-1")


def test_commutation_relations():
    """[Sx, Sy] = i*Sz for spin-1/2."""
    for J in [0.5, 1.0, 1.5]:
        Sx = _single_spin_op(J, 'x').toarray()
        Sy = _single_spin_op(J, 'y').toarray()
        Sz = _single_spin_op(J, 'z').toarray()
        commutator = Sx @ Sy - Sy @ Sx
        assert np.allclose(commutator, 1j * Sz, atol=1e-12), \
            f"Commutation relation failed for J={J}"
    print("PASS: [Sx,Sy]=iSz for J=1/2, 1, 3/2")


def test_free_electron_g_factor():
    """
    For a free electron (g=2.0023, S=1/2, no nuclei) the energy splitting at
    B = [0, 0, 350] mT should be:
        dE = g * bmagn/h * B  [MHz]  ~= 9.788 GHz  (X-band)
    """
    from scipy.constants import physical_constants
    bmagn_val = physical_constants['Bohr magneton'][0]
    planck_val = physical_constants['Planck constant'][0]
    g = 2.0023
    B_mT = 350.0  # mT

    sys = SpinSystem(S=0.5, g=g, Nucs='')
    H = ham(sys, B=np.array([0.0, 0.0, B_mT]))
    # Use dense eigvalsh — matrix is only 2x2, sparse eigsh can't handle k >= N-1
    E = np.sort(np.linalg.eigvalsh(H.toarray()))
    dE = E[1] - E[0]  # MHz

    # Expected: g * bmagn / h * B_T  (convert mT->T and Hz->MHz)
    expected_MHz = g * bmagn_val / planck_val * (B_mT * 1e-3) / 1e6
    assert abs(dE - expected_MHz) / expected_MHz < 1e-4, \
        f"Energy splitting {dE:.4f} MHz != expected {expected_MHz:.4f} MHz"
    print(f"PASS: Free electron dE = {dE:.4f} MHz (expected {expected_MHz:.4f} MHz)")


def test_hyperfine_splitting():
    """
    For S=1/2, one 1H nucleus (I=1/2), the zero-field energy levels split
    into a singlet and triplet separated by A (in MHz).
    The range of eigenvalues at B=0 should be of order A.
    """
    A_MHz = 1430.0  # proton coupling like in the app's examples
    sys = SpinSystem(S=0.5, g=2.0, Nucs='1H', A=[A_MHz])

    H0, mux, muy, muz = ham(sys)
    # 4x4 matrix — use dense eigvalsh
    E_zf = np.sort(np.real(np.linalg.eigvalsh(H0.toarray())))
    print(f"  Zero-field energy levels (MHz): {np.round(E_zf, 2)}")

    E_range = E_zf[-1] - E_zf[0]
    assert E_range > 0.3 * A_MHz, \
        f"Zero-field splitting {E_range:.1f} MHz seems too small for A={A_MHz} MHz"
    print(f"PASS: Hyperfine zero-field range = {E_range:.1f} MHz (A={A_MHz} MHz)")


if __name__ == '__main__':
    test_sz_spin_half()
    test_sx_spin_half()
    test_sz_spin1()
    test_commutation_relations()
    test_free_electron_g_factor()
    test_hyperfine_splitting()
    print("\nAll Phase 2 tests passed!")
