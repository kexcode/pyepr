from dataclasses import dataclass, field
from typing import List, Union, Optional
import numpy as np

from easyspin_py.core.isotopes import nucspin, nucgval

@dataclass
class SpinSystem:
    """
    Representation of a paramagnetic spin system.
    Replaces the MATLAB Sys struct and the validatespinsys function.
    """
    S: Union[float, List[float], np.ndarray] = 0.5
    g: Union[float, List[float], np.ndarray] = 2.0023
    
    # Nuclei definition
    Nucs: str = ""
    n: Union[int, List[int], np.ndarray] = field(default_factory=lambda: [])
    
    # Couplings (in MHz)
    A: Union[float, List[float], np.ndarray] = field(default_factory=lambda: [])
    Q: Union[float, List[float], np.ndarray] = field(default_factory=lambda: [])
    D: Union[float, List[float], np.ndarray] = field(default_factory=lambda: [])
    
    # Linewidths (in mT)
    lw: Union[float, List[float], np.ndarray] = 0.0
    lwpp: Union[float, List[float], np.ndarray] = 0.0

    # Fast motion correlation time (in s)
    tcorr: Optional[float] = None
    
    def __post_init__(self):
        self.validate()

    def validate(self):
        """
        Validates the spin system parameters and normalizes them into numpy arrays.
        """
        # Convert spins to array
        self.S = np.atleast_1d(self.S)
        
        # Convert g to array (can be scalar, 3-element vector, or 3x3 matrix)
        self.g = np.atleast_1d(self.g)
        
        # Parse nuclei
        self.nuclei_list = [n.strip() for n in self.Nucs.split(",")] if self.Nucs else []
        self.nNuclei = len(self.nuclei_list)
        
        # Nuclei spins and g-values
        self.I = np.array([nucspin(n) for n in self.nuclei_list])
        self.gn = np.array([nucgval(n) for n in self.nuclei_list])
        
        # Convert A, Q, D, lw to arrays
        self.A = np.atleast_1d(self.A) if self.nNuclei > 0 else np.array([])
        self.Q = np.atleast_1d(self.Q) if self.nNuclei > 0 else np.array([])
        self.D = np.atleast_1d(self.D)
        
        self.lw = np.atleast_1d(self.lw)
        
        # Number of electron spins
        self.nElectrons = len(self.S)

    def hsdim(self) -> int:
        """
        Calculates the Hilbert space dimension of the spin system.
        """
        dim = int(np.prod(2 * self.S + 1))
        if self.nNuclei > 0:
            dim *= int(np.prod(2 * self.I + 1))
        return dim
