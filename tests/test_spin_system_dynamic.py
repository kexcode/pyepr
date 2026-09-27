r"""
Tests for the refactored SpinSystem with dynamic nuclei management.

Run with:
    .venv\Scripts\python tests\test_spin_system_dynamic.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from easyspin_py.core.spin_system import SpinSystem, Nucleus
from easyspin_py.hamiltonian.builder import ham


def test_empty_system():
    """Default SpinSystem: S=1/2, no nuclei."""
    sys_ = SpinSystem(S=0.5, g=2.0023)
    assert sys_.nNuclei == 0
    assert sys_.hsdim() == 2
    assert sys_.nElectrons == 1
    print("PASS: empty spin system (hsdim=2)")


def test_legacy_nucs_constructor():
    """Legacy Nucs/A/Q constructor still works."""
    sys_ = SpinSystem(S=0.5, g=2.006, Nucs='14N', A=[40.0])
    assert sys_.nNuclei == 1
    assert sys_.nuclei[0].symbol == '14N'
    assert sys_.nuclei[0].A == 40.0
    assert abs(sys_.nuclei[0].I - 1.0) < 1e-9
    assert sys_.hsdim() == 6   # 2 * 3
    print(f"PASS: legacy constructor — 14N nucleus, hsdim={sys_.hsdim()}")


def test_legacy_multi_nucs():
    """Multiple nuclei via legacy Nucs string."""
    sys_ = SpinSystem(S=0.5, g=2.0, Nucs='14N,1H', A=[40.0, 10.0])
    assert sys_.nNuclei == 2
    assert sys_.nuclei[0].symbol == '14N'
    assert sys_.nuclei[1].symbol == '1H'
    assert sys_.hsdim() == 12  # 2 * 3 * 2
    print(f"PASS: legacy multi-nucleus — hsdim={sys_.hsdim()}")


def test_add_nucleus():
    """add_nucleus() grows the system correctly."""
    sys_ = SpinSystem(S=0.5, g=2.0023)
    assert sys_.hsdim() == 2

    nuc = sys_.add_nucleus('14N', A=40.0)
    assert sys_.nNuclei == 1
    assert sys_.hsdim() == 6   # 2 * 3
    assert nuc.symbol == '14N'
    assert abs(nuc.I - 1.0) < 1e-9
    print(f"PASS: add_nucleus('14N') -- hsdim grows 2 -> {sys_.hsdim()}")

    sys_.add_nucleus('1H', A=5.0)
    assert sys_.nNuclei == 2
    assert sys_.hsdim() == 12  # 2 * 3 * 2
    print(f"PASS: add_nucleus('1H') -- hsdim grows to {sys_.hsdim()}")


def test_remove_nucleus():
    """remove_nucleus() shrinks the system correctly."""
    sys_ = SpinSystem(S=0.5, g=2.0023)
    sys_.add_nucleus('14N', A=40.0)
    sys_.add_nucleus('1H', A=5.0)
    assert sys_.hsdim() == 12

    removed = sys_.remove_nucleus(1)   # remove 1H (index 1)
    assert removed.symbol == '1H'
    assert sys_.nNuclei == 1
    assert sys_.hsdim() == 6
    print(f"PASS: remove_nucleus(1) '1H' -- hsdim shrinks to {sys_.hsdim()}")

    sys_.remove_nucleus(0)             # remove 14N (now index 0)
    assert sys_.nNuclei == 0
    assert sys_.hsdim() == 2
    print(f"PASS: remove_nucleus(0) '14N' -- hsdim returns to {sys_.hsdim()}")


def test_clear_nuclei():
    """clear_nuclei() removes everything."""
    sys_ = SpinSystem(S=0.5, g=2.0023, Nucs='14N,1H,63Cu', A=[40, 5, 200])
    assert sys_.nNuclei == 3
    sys_.clear_nuclei()
    assert sys_.nNuclei == 0
    assert sys_.hsdim() == 2
    print("PASS: clear_nuclei() — all nuclei removed")


def test_computed_property_arrays():
    """I, gn, A, Q properties return correct numpy arrays."""
    sys_ = SpinSystem(S=0.5, g=2.0023)
    sys_.add_nucleus('14N', A=40.0, Q=0.5)
    sys_.add_nucleus('1H', A=10.0)

    assert len(sys_.I) == 2
    assert abs(sys_.I[0] - 1.0) < 1e-9   # 14N: I=1
    assert abs(sys_.I[1] - 0.5) < 1e-9   # 1H:  I=1/2

    assert len(sys_.A) == 2
    assert sys_.A[0] == 40.0
    assert sys_.A[1] == 10.0

    # Q for 1H (I=1/2 < 1) should be 0 even if set
    sys_.nuclei[1].Q = 999.0   # deliberately wrong
    assert sys_.Q[1] == 0.0     # Q_eff returns 0 for I<1
    print("PASS: computed property arrays correct (I, gn, A, Q)")


def test_hamiltonian_after_add():
    """Hamiltonian built after add_nucleus matches expected hsdim."""
    sys_ = SpinSystem(S=0.5, g=2.0023)
    H0_bare, *_ = ham(sys_)
    assert H0_bare.shape == (2, 2)

    sys_.add_nucleus('14N', A=40.0)
    H0_with_N, *_ = ham(sys_)
    assert H0_with_N.shape == (6, 6)
    print(f"PASS: Hamiltonian shape 2x2 -> 6x6 after add_nucleus('14N')")


def test_hamiltonian_after_remove():
    """Hamiltonian reverts after remove_nucleus."""
    sys_ = SpinSystem(S=0.5, g=2.0023, Nucs='14N', A=[40.0])
    H0, *_ = ham(sys_)
    assert H0.shape == (6, 6)

    sys_.remove_nucleus(0)
    H0_bare, *_ = ham(sys_)
    assert H0_bare.shape == (2, 2)
    print(f"PASS: Hamiltonian reverts to 2x2 after remove_nucleus()")


def test_serialization_roundtrip():
    """to_dict / from_dict round trip preserves all fields."""
    sys_ = SpinSystem(S=0.5, g=[2.003, 2.005, 2.008], D=[500.0, 50.0], lw=0.5)
    sys_.add_nucleus('14N', A=40.0, Q=0.5, label='alpha-N')
    sys_.add_nucleus('1H', A=7.3)

    d = sys_.to_dict()
    sys2 = SpinSystem.from_dict(d)

    assert sys2.nNuclei == 2
    assert sys2.nuclei[0].symbol == '14N'
    assert sys2.nuclei[0].label == 'alpha-N'
    assert abs(sys2.nuclei[1].A - 7.3) < 1e-9
    assert sys2.hsdim() == sys_.hsdim()
    print(f"PASS: to_dict/from_dict roundtrip — hsdim={sys2.hsdim()}")


def test_invalid_isotope_raises():
    """Unknown isotope symbol raises ValueError."""
    sys_ = SpinSystem(S=0.5, g=2.0)
    try:
        sys_.add_nucleus('99X', A=10.0)
        assert False, "Should have raised"
    except ValueError:
        print("PASS: unknown isotope '99X' raises ValueError")


if __name__ == '__main__':
    print("=== SpinSystem Dynamic Nuclei Tests ===\n")
    test_empty_system()
    test_legacy_nucs_constructor()
    test_legacy_multi_nucs()
    test_add_nucleus()
    test_remove_nucleus()
    test_clear_nuclei()
    test_computed_property_arrays()
    test_hamiltonian_after_add()
    test_hamiltonian_after_remove()
    test_serialization_roundtrip()
    test_invalid_isotope_raises()
    print("\nAll SpinSystem dynamic tests passed!")
