"""
Spin system validator for simulation functions.

Checks compatibility between a SpinSystem and the chosen simulation function,
returning structured warnings and errors before any heavy computation begins.

Based on EasySpin documentation constraints:
  - https://easyspin.org/easyspin/documentation/garlic.html
  - https://easyspin.org/easyspin/documentation/pepper.html
  - https://easyspin.org/easyspin/documentation/levels.html
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List

import numpy as np


class Severity(str, Enum):
    ERROR = "error"        # Simulation cannot run
    WARNING = "warning"    # Simulation runs but results may be wrong/slow
    INFO = "info"          # Informational hint


@dataclass
class ValidationMessage:
    severity: Severity
    code: str              # machine-readable code for the UI
    message: str           # human-readable explanation
    doc_url: str = ""      # link to relevant EasySpin doc page


@dataclass
class ValidationResult:
    messages: List[ValidationMessage] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def errors(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.WARNING]

    @property
    def infos(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.INFO]

    def add(self, severity: Severity, code: str, message: str, doc_url: str = ""):
        self.messages.append(ValidationMessage(severity, code, message, doc_url))

    def to_dict(self) -> dict:
        return {
            "valid": not self.has_errors,
            "messages": [
                {
                    "severity": m.severity.value,
                    "code": m.code,
                    "message": m.message,
                    "doc_url": m.doc_url,
                }
                for m in self.messages
            ],
        }


# ---------------------------------------------------------------------------
# Common validation checks
# ---------------------------------------------------------------------------

_GARLIC_DOC = "https://easyspin.org/easyspin/documentation/garlic.html"
_PEPPER_DOC = "https://easyspin.org/easyspin/documentation/pepper.html"
_LEVELS_DOC = "https://easyspin.org/easyspin/documentation/levels.html"
_SPINSYSTEM_DOC = "https://easyspin.org/easyspin/documentation/spinsystem.html"

_HSDIM_WARN_THRESHOLD = 512
_HSDIM_ERROR_THRESHOLD = 4096


def _check_hilbert_space(sys, result: ValidationResult, func_name: str):
    """Warn if Hilbert space is very large."""
    dim = sys.hsdim()
    if dim > _HSDIM_ERROR_THRESHOLD:
        result.add(
            Severity.ERROR,
            "HSDIM_TOO_LARGE",
            f"Hilbert space dimension is {dim}, which exceeds the limit of "
            f"{_HSDIM_ERROR_THRESHOLD}. Reduce the number or spin of nuclei.",
            _SPINSYSTEM_DOC,
        )
    elif dim > _HSDIM_WARN_THRESHOLD:
        result.add(
            Severity.WARNING,
            "HSDIM_LARGE",
            f"Hilbert space dimension is {dim}. {func_name}() may be slow. "
            f"Consider using fewer or lower-spin nuclei.",
            _SPINSYSTEM_DOC,
        )


def _check_electron_spin(sys, result: ValidationResult):
    """Info if S > 1 (higher-order interactions may be needed)."""
    for i, S in enumerate(sys.S):
        if S > 2:
            result.add(
                Severity.INFO,
                "HIGH_ELECTRON_SPIN",
                f"Electron spin S={S} is very large. Make sure you have "
                f"included all relevant zero-field splitting terms (D, B4, etc.).",
                _SPINSYSTEM_DOC,
            )


def _check_nucleus_quadrupole(sys, result: ValidationResult):
    """Warn if I < 1 nuclei have non-zero Q."""
    # Support both current flat API and future Nucleus-list API
    if hasattr(sys, 'nuclei') and sys.nuclei:
        # Future refactored API
        for nuc in sys.nuclei:
            if nuc.Q != 0 and nuc.I < 1:
                result.add(
                    Severity.WARNING,
                    "QUADRUPOLE_ON_SPIN_HALF",
                    f"Nucleus '{nuc.symbol}' (I={nuc.I}) has Q={nuc.Q} MHz, but "
                    f"quadrupole coupling only applies to I \u2265 1. Q will be ignored.",
                    _SPINSYSTEM_DOC,
                )
    else:
        # Current flat API
        Q_arr = np.atleast_1d(getattr(sys, 'Q', []))
        I_arr = np.atleast_1d(getattr(sys, 'I', []))
        nuc_list = getattr(sys, 'nuclei_list', [])
        for i, (q, I_val) in enumerate(zip(Q_arr, I_arr)):
            if q != 0 and I_val < 1:
                sym = nuc_list[i] if i < len(nuc_list) else f"nucleus {i}"
                result.add(
                    Severity.WARNING,
                    "QUADRUPOLE_ON_SPIN_HALF",
                    f"Nucleus '{sym}' (I={I_val}) has Q={q} MHz, but "
                    f"quadrupole coupling only applies to I \u2265 1. Q will be ignored.",
                    _SPINSYSTEM_DOC,
                )


# ---------------------------------------------------------------------------
# garlic() validator
# ---------------------------------------------------------------------------

def validate_garlic(sys) -> ValidationResult:
    """
    Validate a SpinSystem for use with garlic().

    garlic() constraints (from EasySpin docs):
    - S must be 1/2 (doublet radicals only)
    - Single electron spin only
    - No ZFS (D tensor) — it is simply ignored
    - Only fast-motion / isotropic regime (liquid solutions)
    - Cross-nuclear terms are neglected (perturbation theory)
    """
    result = ValidationResult()

    # Check S = 1/2
    if len(sys.S) > 1:
        result.add(
            Severity.ERROR,
            "GARLIC_MULTI_ELECTRON",
            "garlic() does not support multiple electron spins. "
            "Use pepper() for multi-electron systems.",
            _GARLIC_DOC,
        )
    elif sys.S[0] != 0.5:
        result.add(
            Severity.ERROR,
            "GARLIC_S_NOT_HALF",
            f"garlic() requires S=1/2, but S={sys.S[0]} was given. "
            f"Use pepper() for S > 1/2.",
            _GARLIC_DOC,
        )

    # Warn about D tensor (ignored by garlic)
    D_arr = np.atleast_1d(sys.D)
    if len(D_arr) > 0 and np.any(D_arr != 0):
        result.add(
            Severity.WARNING,
            "GARLIC_ZFS_IGNORED",
            "garlic() ignores zero-field splitting (D tensor). "
            "For solid-state simulations with ZFS, use pepper().",
            _GARLIC_DOC,
        )

    # Warn about lw = 0
    lw = np.atleast_1d(sys.lw)
    if np.all(lw == 0):
        result.add(
            Severity.WARNING,
            "NO_LINEWIDTH",
            "No linewidth (lw) is set. The spectrum will consist of "
            "infinitely sharp lines. Set Sys.lw to a Gaussian FWHM in mT.",
            _GARLIC_DOC,
        )

    _check_hilbert_space(sys, result, "garlic")
    _check_electron_spin(sys, result)
    _check_nucleus_quadrupole(sys, result)

    # Info: recommend garlic only for liquid state
    result.add(
        Severity.INFO,
        "GARLIC_LIQUID_ONLY",
        "garlic() is designed for liquid solutions in the fast-motion regime "
        "(isotropic tumbling). For solid-state or frozen samples, use pepper().",
        _GARLIC_DOC,
    )

    return result


# ---------------------------------------------------------------------------
# pepper() validator
# ---------------------------------------------------------------------------

def validate_pepper(sys) -> ValidationResult:
    """
    Validate a SpinSystem for use with pepper().

    pepper() constraints:
    - Any S, any number of electrons
    - Solid-state (powder/crystal) only
    - Large spin systems may be slow (warn)
    - Requires broadening parameter (lw or lwpp)
    """
    result = ValidationResult()

    # Warn about missing linewidth
    lw = np.atleast_1d(sys.lw)
    if np.all(lw == 0):
        result.add(
            Severity.WARNING,
            "NO_LINEWIDTH",
            "No linewidth (lw) is set. The spectrum will consist of "
            "infinitely sharp sticks. Set Sys.lw to a Gaussian FWHM in mT.",
            _PEPPER_DOC,
        )

    # Warn if this looks like a liquid-state system (tcorr set, small lw)
    if hasattr(sys, 'tcorr') and sys.tcorr is not None:
        result.add(
            Severity.WARNING,
            "PEPPER_LIQUID_SUSPECTED",
            "Sys.tcorr is set, which indicates a fast-motion regime. "
            "Consider using garlic() instead of pepper() for liquid solutions.",
            _PEPPER_DOC,
        )

    _check_hilbert_space(sys, result, "pepper")
    _check_electron_spin(sys, result)
    _check_nucleus_quadrupole(sys, result)

    # Info: recommend for solid-state
    result.add(
        Severity.INFO,
        "PEPPER_SOLID_STATE",
        "pepper() is designed for solid-state samples (powders, single crystals, "
        "oriented films). For liquid solutions, use garlic().",
        _PEPPER_DOC,
    )

    return result


# ---------------------------------------------------------------------------
# levels() validator
# ---------------------------------------------------------------------------

def validate_levels(sys) -> ValidationResult:
    """
    Validate a SpinSystem for use with levels().

    levels() constraints:
    - Any spin system is supported
    - Only real limit is memory/time for very large Hilbert spaces
    """
    result = ValidationResult()

    _check_hilbert_space(sys, result, "levels")
    _check_electron_spin(sys, result)
    _check_nucleus_quadrupole(sys, result)

    return result


# ---------------------------------------------------------------------------
# Auto-selector: suggest the right function for a given spin system
# ---------------------------------------------------------------------------

def suggest_simulator(sys) -> str:
    """
    Auto-suggest whether to use garlic() or pepper() based on the spin system.

    Returns 'garlic' or 'pepper'.
    """
    D_arr = np.atleast_1d(sys.D)
    has_zfs = len(D_arr) > 0 and np.any(D_arr != 0)
    is_doublet = len(sys.S) == 1 and sys.S[0] == 0.5
    has_tcorr = hasattr(sys, 'tcorr') and sys.tcorr is not None

    if is_doublet and not has_zfs and has_tcorr:
        return "garlic"
    if is_doublet and not has_zfs:
        # Ambiguous — default to garlic for S=1/2 without ZFS
        return "garlic"
    return "pepper"
