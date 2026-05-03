r"""
Smoke tests for Phase 3: EPR Simulation Algorithms (levels, garlic, pepper).

Run with:
    .venv\Scripts\python tests\test_phase3_sims.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from easyspin_py.core.spin_system import SpinSystem
from easyspin_py.simulation.levels import levels
from easyspin_py.simulation.garlic import garlic
from easyspin_py.simulation.pepper import pepper


# ---------------------------------------------------------------------------
# levels() tests
# ---------------------------------------------------------------------------

def test_levels_free_electron():
    """
    For a free electron (S=1/2, no nuclei), energy levels vs B are two lines
    with equal and opposite slopes. At B=0 they should be degenerate.
    """
    sys = SpinSystem(S=0.5, g=2.0023, Nucs='')
    E, B = levels(sys, [0, 400], n_points=50)

    assert E.shape == (2, 50), f"Expected shape (2,50), got {E.shape}"
    # At B=0 both levels should be equal (degenerate)
    assert abs(E[0, 0] - E[1, 0]) < 1e-6, \
        f"At B=0, levels not degenerate: {E[:,0]}"
    # Level splitting should increase monotonically with B
    splits = E[1] - E[0]
    assert np.all(np.diff(splits) >= 0), "Energy splitting not monotonically increasing"
    print(f"PASS: levels() free electron — {E.shape[0]} levels, "
          f"split at 400 mT = {splits[-1]:.2f} MHz")


def test_levels_nitrogen_radical():
    """
    S=1/2 + 14N (I=1) gives 6 energy levels.
    At high field, they should clearly split into 3 groups (one per mI).
    """
    sys = SpinSystem(S=0.5, g=2.006, Nucs='14N', A=[40.0])
    E, B = levels(sys, [0, 400], n_points=100)

    n_expected = sys.hsdim()  # 2 * 3 = 6
    assert E.shape[0] == n_expected, \
        f"Expected {n_expected} levels, got {E.shape[0]}"
    print(f"PASS: levels() 14N radical — {n_expected} levels computed")


# ---------------------------------------------------------------------------
# garlic() tests
# ---------------------------------------------------------------------------

def test_garlic_no_nuclei():
    """
    A radical with no nuclei should give a single peak in the spectrum.
    The peak should be near the free-electron resonance field.
    """
    g = 2.0055
    mw_GHz = 9.5
    sys = SpinSystem(S=0.5, g=g, Nucs='', lw=[0.5])
    exp = {'mwFreq': mw_GHz, 'Range': [330, 345], 'nPoints': 512, 'Harmonic': 0}
    B, spc = garlic(sys, exp)

    assert len(B) == 512
    B_peak = B[np.argmax(spc)]

    # Expected resonance: B = h*nu / (g*bmagn) in mT
    from scipy.constants import physical_constants, h
    bmagn_val = physical_constants['Bohr magneton'][0]
    B_expected = h * mw_GHz * 1e9 / (g * bmagn_val) * 1e3  # T -> mT
    assert abs(B_peak - B_expected) < 0.5, \
        f"Peak at {B_peak:.3f} mT, expected {B_expected:.3f} mT"
    print(f"PASS: garlic() single line — peak at {B_peak:.3f} mT "
          f"(expected {B_expected:.3f} mT)")


def test_garlic_14N_triplet():
    """
    S=1/2 + 14N (I=1): should give 3 lines (mI = -1, 0, +1).
    Check that spectrum has 3 distinct peaks.
    """
    sys = SpinSystem(S=0.5, g=2.006, Nucs='14N', A=[14.0], lw=[0.1])
    exp = {'mwFreq': 9.5, 'Range': [335, 345], 'nPoints': 2048, 'Harmonic': 0}
    B, spc = garlic(sys, exp)

    # Count peaks by finding local maxima
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(spc, height=spc.max() * 0.1)
    assert len(peaks) == 3, f"Expected 3 peaks for 14N, found {len(peaks)}"
    print(f"PASS: garlic() 14N triplet — {len(peaks)} peaks found")


def test_garlic_derivative_integrates_to_zero():
    """First derivative spectrum should integrate to ~0 (symmetric lineshape)."""
    sys = SpinSystem(S=0.5, g=2.0023, Nucs='1H', A=[10.0], lw=[0.5])
    exp = {'mwFreq': 9.5, 'Range': [330, 345], 'nPoints': 1024, 'Harmonic': 1}
    B, spc = garlic(sys, exp)

    integral = np.trapezoid(spc, B)
    assert abs(integral) < 0.01 * np.max(np.abs(spc)), \
        f"Derivative spectrum integral {integral:.4f} is not ~0"
    print(f"PASS: garlic() derivative integrates to ~0 (integral={integral:.6f})")


# ---------------------------------------------------------------------------
# pepper() tests
# ---------------------------------------------------------------------------

def test_pepper_isotropic_g():
    """
    For isotropic g and no ZFS, pepper should give a single line similar to garlic.
    """
    sys = SpinSystem(S=0.5, g=2.0023, Nucs='', lw=[1.0])
    exp = {'mwFreq': 9.5, 'Range': [330, 345], 'nPoints': 512, 'Harmonic': 0}
    opt = {'nKnots': 10, 'nPhi': 20, 'nB': 80}
    B, spc = pepper(sys, exp, opt)

    assert len(B) == 512
    assert np.max(spc) > 0, "pepper() returned zero spectrum"
    print(f"PASS: pepper() isotropic S=1/2 — max intensity = {np.max(spc):.4f}")


def test_pepper_axial_zfs():
    """
    S=1 with axial ZFS (D only, E=0) should show a recognizable powder pattern
    with non-zero spectral intensity.
    """
    sys = SpinSystem(S=1.0, g=2.0, D=[1000.0, 0.0], lw=[2.0])
    exp = {'mwFreq': 9.5, 'Range': [250, 500], 'nPoints': 512, 'Harmonic': 0}
    opt = {'nKnots': 15, 'nPhi': 30, 'nB': 100}
    B, spc = pepper(sys, exp, opt)

    assert np.max(spc) > 0, "pepper() returned zero spectrum for S=1, D!=0"
    print(f"PASS: pepper() S=1 axial ZFS — max intensity = {np.max(spc):.4f}")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("=== Phase 3: Simulation Algorithm Tests ===\n")

    print("--- levels() ---")
    test_levels_free_electron()
    test_levels_nitrogen_radical()

    print("\n--- garlic() ---")
    test_garlic_no_nuclei()
    test_garlic_14N_triplet()
    test_garlic_derivative_integrates_to_zero()

    print("\n--- pepper() ---")
    test_pepper_isotropic_g()
    test_pepper_axial_zfs()

    print("\nAll Phase 3 tests passed!")
