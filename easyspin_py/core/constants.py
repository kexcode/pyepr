"""
EasySpin constants mapped to scipy.constants where possible.
scipy >= 1.14 removed the 'planck' alias; use 'h' directly.
"""
from scipy.constants import (
    physical_constants,
    h,
    Boltzmann as k_B,
    Avogadro as N_A,
    e as echarge,
)

# Alias for compatibility with rest of the codebase
planck = h

# Bohr magneton (J/T)
bmagn = physical_constants['Bohr magneton'][0]

# Nuclear magneton (J/T)
nmagn = physical_constants['nuclear magneton'][0]

# Electron gyromagnetic ratio (rad s^-1 T^-1)
gammae = physical_constants['electron gyromag. ratio'][0]

# Planck constant
planck = h

# Boltzmann constant
boltzm = k_B

# Avogadro constant
avogadro = N_A
