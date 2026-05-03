"""
SpinSystem and Nucleus definitions.

Replaces the MATLAB Sys struct and validatespinsys.m.

The key design principle is that nuclei are stored as a List[Nucleus] so they
can be added/removed dynamically at runtime (e.g. from a web UI) without
breaking the Hamiltonian builder.  The builder reads only the computed
@property accessors (nNuclei, I, gn, A, Q) which remain backward-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union

import numpy as np

from easyspin_py.core.isotopes import nucspin, nucgval


# ---------------------------------------------------------------------------
# Nucleus dataclass
# ---------------------------------------------------------------------------

@dataclass
class Nucleus:
    """
    A single nuclear spin coupled to the electron spin system.

    Parameters
    ----------
    symbol : str
        Isotope symbol, e.g. '1H', '14N', '63Cu'.
    A : float
        Isotropic hyperfine coupling constant in MHz.
    A_aniso : list of 3 floats, optional
        Anisotropic principal values [Axx, Ayy, Azz] in MHz.
        If given, overrides the isotropic A for the Hamiltonian.
    Q : float
        Nuclear quadrupole coupling constant in MHz (only relevant for I >= 1).
    label : str, optional
        User-visible label for the nucleus (e.g. 'alpha-H', 'ring-N').
    """
    symbol: str
    A: float = 0.0
    A_aniso: Optional[List[float]] = None   # [Axx, Ayy, Azz] in MHz
    Q: float = 0.0
    label: Optional[str] = None

    # Cached isotope properties (set on first access or at construction)
    _I: Optional[float] = field(default=None, repr=False, compare=False)
    _gn: Optional[float] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        # Pre-fetch from isotope database at construction time to catch bad symbols early
        self._I = float(nucspin(self.symbol))
        self._gn = float(nucgval(self.symbol))

    @property
    def I(self) -> float:
        """Nuclear spin quantum number."""
        return self._I

    @property
    def gn(self) -> float:
        """Nuclear g-value."""
        return self._gn

    @property
    def A_eff(self) -> np.ndarray:
        """
        Effective 3x3 A tensor in MHz.
        Uses A_aniso if given, otherwise isotropic A on the diagonal.
        """
        if self.A_aniso is not None:
            return np.diag(self.A_aniso)
        return np.diag([self.A, self.A, self.A])

    @property
    def Q_eff(self) -> float:
        """Quadrupole coupling in MHz (0 for I < 1)."""
        if self.I < 1:
            return 0.0
        return self.Q

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "A": self.A,
            "A_aniso": self.A_aniso,
            "Q": self.Q,
            "label": self.label,
            "I": self.I,
            "gn": self.gn,
        }


# ---------------------------------------------------------------------------
# SpinSystem
# ---------------------------------------------------------------------------

@dataclass
class SpinSystem:
    """
    Representation of a paramagnetic spin system.

    Electron spin parameters
    ------------------------
    S : float or list
        Electron spin quantum number(s). Default 0.5.
    g : float, list of 3, or 3x3 array
        g-tensor. Scalar = isotropic, 3-vector = principal values, 3x3 = full tensor.
    D : float, list of 1/2/3 values, or 3x3 array
        Zero-field splitting in MHz.
        - Scalar D:      axial ZFS, E=0
        - [D, E]:        D and rhombicity parameter
        - [Dxx,Dyy,Dzz]: principal values
    lw : float or [lG, lL]
        Linewidth in mT.  lG = Gaussian FWHM, lL = Lorentzian FWHM.
    tcorr : float, optional
        Rotational correlation time in seconds (fast-motion/garlic regime).

    Nuclei
    ------
    nuclei : list of Nucleus
        Nuclear spins coupled to the electrons. Use add_nucleus() / remove_nucleus()
        to modify this list; do NOT mutate it directly.

    Legacy constructor arguments
    ----------------------------
    Nucs : str
        Comma-separated isotope symbols, e.g. '14N,1H'.
        Kept for backward compatibility; prefer add_nucleus().
    A : list
        Isotropic HFI per nucleus (MHz). Paired with Nucs.
    Q : list
        Quadrupole coupling per nucleus (MHz). Paired with Nucs.
    """

    # Electron spin
    S: Union[float, List[float], np.ndarray] = 0.5
    g: Union[float, List[float], np.ndarray] = 2.0023
    D: Union[float, List[float], np.ndarray] = field(default_factory=list)
    lw: Union[float, List[float], np.ndarray] = 0.0
    lwpp: Union[float, List[float], np.ndarray] = 0.0
    tcorr: Optional[float] = None

    # Nuclei — primary storage as a list of Nucleus objects
    nuclei: List[Nucleus] = field(default_factory=list)

    # ---- Legacy flat-array arguments (backward compat) ----
    # These are consumed in __post_init__ and converted to Nucleus objects.
    # Do NOT set these after construction; use add_nucleus() instead.
    Nucs: str = field(default="", repr=False)
    _legacy_A: List[float] = field(default_factory=list, repr=False)
    _legacy_Q: List[float] = field(default_factory=list, repr=False)

    def __init__(
        self,
        S: Union[float, List[float], np.ndarray] = 0.5,
        g: Union[float, List[float], np.ndarray] = 2.0023,
        D: Union[float, List[float], np.ndarray] = None,
        lw: Union[float, List[float], np.ndarray] = 0.0,
        lwpp: Union[float, List[float], np.ndarray] = 0.0,
        tcorr: Optional[float] = None,
        nuclei: Optional[List[Nucleus]] = None,
        # Legacy keyword args kept for backward compatibility
        Nucs: str = "",
        A: Union[float, List[float], np.ndarray] = None,
        Q: Union[float, List[float], np.ndarray] = None,
        n: Union[int, List[int], np.ndarray] = None,  # unused, for compat
    ):
        self.S = np.atleast_1d(np.asarray(S, dtype=float))
        self.g = np.atleast_1d(np.asarray(g, dtype=float))
        self.D = np.atleast_1d(np.asarray(D if D is not None else [], dtype=float))
        self.lw = np.atleast_1d(np.asarray(lw, dtype=float))
        self.lwpp = np.atleast_1d(np.asarray(lwpp, dtype=float))
        self.tcorr = tcorr

        # Start with a copy of any pre-built Nucleus objects provided
        self.nuclei: List[Nucleus] = list(nuclei) if nuclei else []

        # Ingest legacy Nucs/A/Q strings into the Nucleus list
        if Nucs:
            sym_list = [s.strip() for s in Nucs.split(",") if s.strip()]
            A_arr = np.atleast_1d(np.asarray(A if A is not None else [], dtype=float))
            Q_arr = np.atleast_1d(np.asarray(Q if Q is not None else [], dtype=float))
            for k, sym in enumerate(sym_list):
                a_val = float(A_arr[k]) if k < len(A_arr) else 0.0
                q_val = float(Q_arr[k]) if k < len(Q_arr) else 0.0
                self.nuclei.append(Nucleus(symbol=sym, A=a_val, Q=q_val))

        self._validate()

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate(self):
        """Normalize parameters after any mutation."""
        if np.any(self.S < 0):
            raise ValueError("Electron spin S must be >= 0.")
        if np.any(self.S % 0.5 != 0):
            raise ValueError("Electron spin S must be a multiple of 0.5.")

    # -----------------------------------------------------------------------
    # Dynamic nuclei management
    # -----------------------------------------------------------------------

    def add_nucleus(
        self,
        symbol: str,
        A: float = 0.0,
        A_aniso: Optional[List[float]] = None,
        Q: float = 0.0,
        label: Optional[str] = None,
    ) -> Nucleus:
        """
        Add a nucleus to the spin system.

        Parameters
        ----------
        symbol : str
            Isotope symbol, e.g. '1H', '14N', '63Cu'.
        A : float
            Isotropic HFI coupling in MHz.
        A_aniso : list of 3 floats, optional
            Anisotropic [Axx, Ayy, Azz] values in MHz.
        Q : float
            Quadrupole coupling in MHz (only used for I >= 1).
        label : str, optional
            User label for the nucleus.

        Returns
        -------
        Nucleus
            The newly created Nucleus object.

        Raises
        ------
        ValueError
            If `symbol` is not found in the isotope database.
        """
        nuc = Nucleus(symbol=symbol, A=A, A_aniso=A_aniso, Q=Q, label=label)
        self.nuclei.append(nuc)
        return nuc

    def remove_nucleus(self, index: int) -> Nucleus:
        """
        Remove a nucleus by its index in the nuclei list.

        Parameters
        ----------
        index : int
            0-based index into self.nuclei.

        Returns
        -------
        Nucleus
            The removed Nucleus object.

        Raises
        ------
        IndexError
            If index is out of range.
        """
        if index < 0 or index >= len(self.nuclei):
            raise IndexError(
                f"Nucleus index {index} out of range (system has {len(self.nuclei)} nuclei)."
            )
        return self.nuclei.pop(index)

    def clear_nuclei(self) -> None:
        """Remove all nuclei from the spin system."""
        self.nuclei.clear()

    # -----------------------------------------------------------------------
    # Computed properties (used by hamiltonian/builder.py — do not rename)
    # -----------------------------------------------------------------------

    @property
    def nElectrons(self) -> int:
        return len(self.S)

    @property
    def nNuclei(self) -> int:
        return len(self.nuclei)

    @property
    def I(self) -> np.ndarray:
        """Nuclear spin quantum numbers as array."""
        return np.array([n.I for n in self.nuclei], dtype=float)

    @property
    def gn(self) -> np.ndarray:
        """Nuclear g-values as array."""
        return np.array([n.gn for n in self.nuclei], dtype=float)

    @property
    def A(self) -> np.ndarray:
        """Isotropic HFI couplings as array (MHz)."""
        return np.array([n.A for n in self.nuclei], dtype=float)

    @property
    def Q(self) -> np.ndarray:
        """Effective quadrupole couplings as array (MHz)."""
        return np.array([n.Q_eff for n in self.nuclei], dtype=float)

    # -----------------------------------------------------------------------
    # Hilbert space dimension
    # -----------------------------------------------------------------------

    def hsdim(self) -> int:
        """Total Hilbert space dimension (product of all 2J+1 values)."""
        dim = int(np.prod(2 * self.S + 1))
        if self.nNuclei > 0:
            dim *= int(np.prod(2 * self.I + 1))
        return dim

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary for the REST API."""
        return {
            "S": self.S.tolist(),
            "g": self.g.tolist(),
            "D": self.D.tolist(),
            "lw": self.lw.tolist(),
            "lwpp": self.lwpp.tolist(),
            "tcorr": self.tcorr,
            "nuclei": [n.to_dict() for n in self.nuclei],
            "hsdim": self.hsdim(),
            "nElectrons": self.nElectrons,
            "nNuclei": self.nNuclei,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpinSystem":
        """Reconstruct from a dictionary (e.g. from REST API payload)."""
        nuclei = [
            Nucleus(
                symbol=n["symbol"],
                A=n.get("A", 0.0),
                A_aniso=n.get("A_aniso"),
                Q=n.get("Q", 0.0),
                label=n.get("label"),
            )
            for n in data.get("nuclei", [])
        ]
        return cls(
            S=data.get("S", 0.5),
            g=data.get("g", 2.0023),
            D=data.get("D", []),
            lw=data.get("lw", 0.0),
            lwpp=data.get("lwpp", 0.0),
            tcorr=data.get("tcorr"),
            nuclei=nuclei,
        )

    def __repr__(self) -> str:
        nuc_str = ", ".join(f"{n.symbol}(A={n.A})" for n in self.nuclei)
        return (
            f"SpinSystem(S={self.S.tolist()}, g={self.g.tolist()}, "
            f"D={self.D.tolist()}, lw={self.lw.tolist()}, "
            f"nuclei=[{nuc_str}], hsdim={self.hsdim()})"
        )
